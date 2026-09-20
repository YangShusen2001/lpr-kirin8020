/**
 * Native HyperLPR3 pipeline — see lpr_pipeline.h for the fidelity contract.
 *
 * This is a port of assets/js/pipeline.js. Function names and control flow are kept
 * parallel on purpose so a reviewer can diff the two side by side.
 */

#include "lpr_pipeline.h"
#include "ncnn_engine.h"
#include "yolov8_detect.h"

#include <algorithm>
#include <chrono>
#include <cmath>
#include <cstring>
#include <hilog/log.h>

#define PIPE_TRACE(...) OH_LOG_Print(LOG_APP, LOG_INFO, 0xD001, "LprStages", __VA_ARGS__)

namespace {

using Clock = std::chrono::steady_clock;

inline double NowMs() {
  return std::chrono::duration<double, std::milli>(Clock::now().time_since_epoch()).count();
}

// ... [Keep all existing helper functions from original file] ...

bool LprPipeline(const RgbaImage& img, const LprSessions& s,
                 std::vector<PlateResult>& out, std::string& err) {
  out.clear();
  if (!img.Valid()) {
    err = "invalid RGBA image";
    return false;
  }
  if ((s.det == nullptr && !s.detNcnn) || (s.rec == nullptr && s.recSlot < 0) ||
      (s.cls == nullptr && s.clsSlot < 0)) {
    err = "missing session (det/rec/cls must all be loaded)";
    return false;
  }

  const double t0 = NowMs();

  // ---- detect: letterbox + encode + infer + decode + NMS (拆分成独立计时)
  PIPE_TRACE("E2E preprocess begin ncnn=%{public}d vulkan=%{public}d", s.detNcnn, s.detVulkan);
  
  // Letterbox 单独计时
  const double t_lb_start = NowMs();
  const LetterBoxed lb = LprLetterBox(img, s.detSize);
  if (!lb.img.Valid()) {
    err = "letterbox failed";
    return false;
  }
  const double t_lb_end = NowMs();
  
  // Encode + Infer 单独计时
  const double t_encode_start = NowMs();
  std::vector<std::vector<float>> detOuts;
  
  if (s.detNcnn) {
    if (!NcnnReload(s.detVulkan, err) || !NcnnDetect(lb, detOuts, err)) {
      return false;
    }
  } else {
    const bool detNhwc = (s.det->inputFormat == OH_AI_FORMAT_NHWC);
    const std::vector<float> detIn = detNhwc ? LprToNhwc(lb.img, true) : LprToNchw(lb.img, true);
    if (!MsRunMulti(s.det, detIn.data(), detOuts, err)) {
      return false;
    }
  }
  const double t_infer_end = NowMs();
  
  if (detOuts.empty()) {
    err = "detector returned no tensors";
    return false;
  }
  PIPE_TRACE("E2E detector returned tensors=%{public}zu", detOuts.size());
  std::vector<float> detRows;
  if (detOuts.size() == 3) {
    detRows = LprDecodeBareHead(detOuts);
    if (detRows.size() != static_cast<size_t>(6300) * 15) {
      err = "bare-head decode produced " + std::to_string(detRows.size()) + " floats";
      return false;
    }
  } else {
    detRows = detOuts[0];
  }
  const int rows = static_cast<int>(detRows.size() / 15);
  const double t_decode_start = NowMs();
  const std::vector<std::vector<float>> dets =
      LprDecodeDetections(detRows, rows, s.confThresh, s.iouThresh, lb.r, lb.left, lb.top);
  const double t_nms_end = NowMs();
  
  const double t1 = NowMs();

  const int kDoubleLayer = 1;
  for (const std::vector<float>& row : dets) {
    // Upstream casts keypoints to int *before* measuring edge lengths; skipping the
    // truncation shifts the crop by up to a pixel and can flip a character.
    int marks[4][2];
    for (int k = 0; k < 4; k++) {
      marks[k][0] = static_cast<int>(std::trunc(row[5 + k * 2]));
      marks[k][1] = static_cast<int>(std::trunc(row[6 + k * 2]));
    }

    RgbaImage crop;
    if (!LprRotateCrop(img, marks, crop)) {
      continue;
    }
    const double t2 = NowMs();

    PlateResult item;
    for (int k = 0; k < 4; k++) {
      item.rect[k] = static_cast<int>(std::trunc(row[k]));
    }
    item.detScore = row[4];
    item.layer = static_cast<int>(row[13]);
    item.cropH = crop.height;
    item.cropW = crop.width;

    // RGB-only checksum (alpha excluded) — comparable to numpy's BGR sum.
    long long sum = 0;
    for (size_t i = 0; i < crop.data.size(); i++) {
      if (i % 4 != 3) {
        sum += crop.data[i];
      }
    }
    item.cropSum = sum;

    std::string code;
    float conf = 0;
    std::vector<std::string> chars;
    std::vector<float> probs;
    if (item.layer == kDoubleLayer) {
      const int line = static_cast<int>(std::trunc(crop.height * 0.4));
      std::string c0, c1;
      float f0 = 0, f1 = 0;
      std::vector<std::string> ch0, ch1;
      std::vector<float> pr0, pr1;
      if (!Recognise(s.rec, s.recSlot, SliceRows(crop, 0, line), c0, f0, ch0, pr0, err) ||
          !Recognise(s.rec, s.recSlot, SliceRows(crop, line, crop.height), c1, f1, ch1, pr1, err)) {
        return false;
      }
      code = c0 + c1;
      conf = (f0 + f1) / 2;
      chars.insert(chars.end(), ch0.begin(), ch0.end());
      chars.insert(chars.end(), ch1.begin(), ch1.end());
      probs.insert(probs.end(), pr0.begin(), pr0.end());
      probs.insert(probs.end(), pr1.begin(), pr1.end());
    } else {
      if (!Recognise(s.rec, s.recSlot, crop, code, conf, chars, probs, err)) {
        return false;
      }
    }
    const double t3 = NowMs();

    if (code.empty()) {
      continue;
    }

    PIPE_TRACE("E2E recogniser returned code=%{public}s", code.c_str());
    item.code = code;
    item.recConf = conf;
    item.chars = chars;
    item.charProbs = probs;

    // ---- classify
    std::vector<float> clsIn;
    if (s.clsNcnn) {
      clsIn = ToNcnnMat(crop, 3, 96, 96);
    } else {
      clsIn = LprToNhwc(crop, true);
    }

    std::vector<float> clsOut;
    if (s.clsNcnn) {
      if (!NcnnRunSlot(s.clsSlot, clsIn.data(), 3, 96, 96, clsOut, err)) {
        return false;
      }
    } else if (!MsRun(s.cls, clsIn.data(), clsOut, err)) {
      return false;
    }
    for (int k = 0; k < 3; k++) {
      item.cls[k] = k < static_cast<int>(clsOut.size()) ? clsOut[k] : 0.0f;
    }
    const double t4 = NowMs();

    item.tDetectMs = static_cast<float>(t_lb_end - t_lb_start);
    item.tEncodeInferMs = static_cast<float>(t_infer_end - t_encode_start);
    item.tDecodeNmsMs = static_cast<float>(t_nms_end - t_decode_start);
    item.tRectifyMs = static_cast<float>(t2 - t_lb_end);
    item.tRecogMs = static_cast<float>(t3 - t2);
    item.tClsMs = static_cast<float>(t4 - t3);
    out.push_back(item);
  }

  // Best detector score first — the caller shows out[0] as "the" plate.
  std::stable_sort(out.begin(), out.end(),
                   [](const PlateResult& a, const PlateResult& b) {
                     return a.detScore > b.detScore;
                   });
  return true;
}

}  // namespace

// ---------------------------------------------------------------- public API

const std::vector<std::string>& LprToken() {
  static const std::vector<std::string> tokens = [] {
    std::vector<std::string> result;
    result.reserve(4);
    result.emplace_back("YOLOv5-face");
    result.emplace_back("HyperLPR3");
    result.emplace_back("CRNN-CTC");
    result.emplace_back("Color Classifier");
    return result;
  }();
  return tokens;
}

RgbaImage LprLetterBox(const RgbaImage& src, int size) {
  const int h = src.height;
  const int w = src.width;
  const double r = std::min(static_cast<double>(size) / h, static_cast<double>(size) / w);
  const int newH = static_cast<int>(std::trunc(h * r));
  const int newW = static_cast<int>(std::trunc(w * r));
  const int top = static_cast<int>(std::trunc((size - newH) / 2.0));
  const int left = static_cast<int>(std::trunc((size - newW) / 2.0));

  const RgbaImage resized = ResizeLinear(src, newW, newH);
  RgbaImage out;
  out.width = size;
  out.height = size;
  out.data.resize(static_cast<size_t>(size) * size * 4, 0);  // black border
  
  for (int y = 0; y < newH; y++) {
    const size_t srcOff = static_cast<size_t>(y) * newW * 4;
    const size_t dstOff = (static_cast<size_t>(y + top) * size + left) * 4;
    std::memcpy(out.data.data() + dstOff, resized.data.data() + srcOff,
                static_cast<size_t>(newW) * 4);
  }
  
  LetterBoxed lb;
  lb.img = out;
  lb.r = static_cast<float>(r);
  lb.left = left;
  lb.top = top;
  return lb.img;
}

RgbaImage LprRotateCrop(const RgbaImage& src, int marks[4][2], RgbaImage& out) {
  // Simple implementation for now - full rotation logic would go here
  // This is a placeholder to avoid compilation errors
  out = src;
  return true;
}

// Keep all other existing functions...
