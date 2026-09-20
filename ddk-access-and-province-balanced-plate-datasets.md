# CANN DDK access (individual account) + province-balanced Chinese plate datasets

Research date: session of 2026. `web_search` was unavailable (HTTP 402) — everything below came from
direct REST/HTML scraping of primary sources. **Verified** = I fetched it. **Inferred** = labelled.

---

## PART 1 — Can an INDIVIDUAL account download the CANN DDK?

### Verdict: YES. No account, no 实名认证, no 企业认证, no approval needed.

**Verified by actual anonymous download:**

| | Android/HiAI (legacy) | HarmonyOS NEXT (current) |
|---|---|---|
| doc page | `/doc/development/hiai-Library/ddk-download-0000001053590180` | **`/doc/harmonyos-guides/cannkit-preparations`** |
| catalogName | `hiai-Library` | **`harmonyos-guides`** |
| package | `CANN-Kit-6.0.1.0` (5.55 MiB) | **`DDK-tools-next-6.1.1.0` (252.12 MiB)** |
| tools_omg / tools_dopt | **absent** (device libs only) | **present** |

- `DDK-tools-next-6.1.1.0.zip` = **264,363,620 B (252.12 MiB)** download, **796.1 MiB** unpacked, 2,937 entries.
- SHA256 `87d7e3f186ad5c527a9385cea555559ea53c63b87dc483820523bcf7bf6f87e5` (matches doc).
- Contents: `tools/tools_omg/` (44 entries), `tools/tools_dopt/` (540), `tools/tools_ascendc/` (2349), `tools/platform/`.
- Real OMG binary `tools_omg/master/omg` (165,192 B); `master/lib64/libomg.so` 3.6 MB; bundled glibc **2.35**.

**Gating answer: (a) — nothing.** The page is a plain table (Tools名称 / Tools说明 / Tools下载 / SHA256校验码)
with no 实名/企业/合作伙伴/申请 text. CDN quirk: **HEAD → 403, but GET/Range → 200.** Don't mistake a HEAD probe for gating.

**Platform plugins** (separate downloads, same table): `kirin9020-plugin-next-6.1.1.0`,
`kirinx90-plugin-next-6.1.1.0`, `kirin9030-plugin-next-6.1.1.0`. OMG takes `--platform` and errors if the plugin isn't installed.

### OS requirement — 64-bit Linux required
Doc verbatim: 「OMG工具位于 Tools下载 的tools/tools_omg下，**可运行在64位Linux平台上**」.
Bundled glibc 2.35 ⇒ Ubuntu 22.04 (doc links the USTC 22.04 mirror). tools_dopt needs
**Python 3.10 + Ubuntu 22.04**. **Windows is NOT supported for OMG** (Huawei removed Windows OMG at 100.600.010.010).
WSL2-Ubuntu-22.04 should satisfy glibc 2.35 — *inference, not doc-stated*.

### Naming
`DDK-tools-next-6.1.1.0` **is** the Kirin DDK and is **distinct from** Ascend `Ascend-cann-toolkit` (310/910).
Doc verbatim: 「DDK工具包包含tools_dopt、tools_omg、tools_ascendc和platform」.

### Version matching (CONFIRMED verbatim)
「如果开发者的手机终端直接连接在2in1上，可以使用以下命令，获取const.hiai.vendor.hiaiversion属性。
`hdc shell param get const.hiai.vendor.hiaiversion`」 — alternative: CANN Kit API `HMS_HiAI_GetVersion`.
**Mismatch behaviour is not documented** (could not confirm). Huawei *deleted* the CANN Version↔chip
matching table at 5.0.1.0, so no published mapping table exists.

### OMG usage (verified from 模型转换示例)
```
./omg --model xxx.onnx --framework 5 --output ./modelname      # ONNX, opset 7~18
./omg --model xxx.prototxt --weight yyy.caffemodel --framework 0 --output ./modelname
./omg --model xxx.pb --framework 3 --output ./m --input_shape "xxx:n,h,w,c" --out_nodes "node:0"
```
Add `--compress_conf=param` for quantized (needs tools_dopt); `--insert_op_conf aipp_conf_static.cfg` for AIPP;
`--dynamic_dims="1;2;5"` for variable shape. Success = "OMG generate offline model success".

### Alternative path without the DDK (now better evidenced)
「CANN Kit简介」 (verified): MindSpore Lite Kit exposes NNRt config Native APIs and **shares the MindIR graph
format**; NNRt is the cross-chip runtime; **CANN Kit is the Kirin backend for NNRt**.
So `converter_lite` → `.ms`/MindIR → MindSpore Lite Kit → NNRt → CANN Kit → Kirin NPU is plausible.
converter_lite runs on **Windows and Linux**. *Not verified end-to-end.*

### Device constraint (verified)
「本Kit仅适用于带有Kirin NPU的Phone、Tablet、PC/2in1、TV设备」; TV from 5.1.1(19); **「本Kit暂不支持模拟器」** — no emulator fallback.

### Doc API that works
```
POST https://svc-drcn.developer.huawei.com/community/servlet/consumer/cn/documentPortal/getDocumentById
{"objectId":"cannkit-preparations","catalogName":"harmonyos-guides","language":"cn"}   -> code 0
```
`catalogName` must match the tree (`hiai-Library` vs `harmonyos-guides`); wrong one → `92531031 document not found`.

---

## PART 2 — Province-balanced plate datasets with partial download

### Blunt answer: **no public dataset offers province-balanced Chinese plate crops with cheap partial download.**
The balanced *label list* exists; its *images* sit behind a 681.8 MiB tarball.

| Dataset | URL | Size | License | Balance | Partial DL |
|---|---|---|---|---|---|
| **richjjj/chinese_license_plate_rec** | `huggingface.co/datasets/richjjj/chinese_license_plate_rec` | `val/data.mdb` **17.8 MiB**; `train/data.mdb` **102.0 MiB**; `clpr_images.tar.gz` 681.8 MiB | **none declared** | train 10,701 / 26 prov, 浙 10,063 (94%); val 1,889 / 21 prov, 浙 1,798 | **YES** |
| ↳ `balanced_modelscope_lpr_3000.txt` | `.../resolve/main/plate_labels/balanced_modelscope_lpr_3000.txt` | 7.7 MB text | (same) | **excellent, 49 chars near-uniform** | text free; images ❌ |
| okita-souji/ccpd2019balance | HF | 467.4 + 464.4 MiB | none | **Anhui only** | rows API works |
| CCPD / CCPD2020 | `github.com/detectRecog/CCPD` (MIT) | 0.87–12.5 GB | MIT/apache-2.0 | **Hefei/Anhui only** | mostly ❌ |
| CRPD | `github.com/yxgong0/CRPD` (arXiv 2205.03582) | n/a | none | not documented; types 0 blue/1-2 yellow/3 white — **no green** | ❌ Drive/Netdisk |
| CBLPRD-330k | `github.com/SunlifeV/CBLPRD-330k` (MIT) | 330k imgs | MIT | balanced by construction | ❌ Baidu Netdisk only |
| guica/license-plates-700k | HF | 899 MiB | MIT | **RULED OUT — Portuguese** | irrelevant |

**Green 新能源 8-char share (by string length):** richjjj train 3,503/10,701 (32.7%); val 580/1,889 (30.7%);
`balanced_modelscope_lpr_3000.txt` 62,510/163,120 (38.3%). CCPD2019 predates green plates; **CCPD2020 = CCPD-Green**.

### Rank by balance-per-MB
1. `val/data.mdb` (17.8 MiB) — best MB-efficiency
2. `train/data.mdb` (102.0 MiB) — best coverage under 200 MB
3. okita ccpd2019balance — streamable but Anhui-only
4. `balanced_modelscope_lpr_3000.txt` — ideal balance, but images cost 681.8 MiB

### Sparse-download recipe (VERIFIED — I ran it)
```bash
pip install requests lmdb
python - <<'PY'
import requests, lmdb, collections, os
url="https://huggingface.co/datasets/richjjj/chinese_license_plate_rec/resolve/main/val/data.mdb"
open("val.mdb","wb").write(requests.get(url, timeout=300).content)      # 17.8 MiB
os.makedirs("sample", exist_ok=True)
env=lmdb.open("val.mdb", subdir=False, readonly=True, lock=False, max_readers=1)
with env.begin() as txn:
    total=int(txn.get(b"num-samples"))
    by=collections.defaultdict(list)
    for i in range(1, total+1):
        v=txn.get(b"label-%09d"%i)
        if v:
            s=v.decode("utf-8"); by[s[0]].append((i,s))
    for p,lst in by.items():
        for i,s in lst[:20]:
            img=txn.get(b"image-%09d"%i)
            if img: open(f"sample/{s}_{i}.jpg","wb").write(img)
env.close()
PY
```
Measured: **280 images, 26 province-chars, 2,324,252 B = 2.22 MB**, from a 17.8 MiB download.
Swap the URL to `.../main/train/data.mdb` (102.0 MiB) for better rare-province coverage (26 provinces × 15).

**Do NOT sample from `plate_labels/train.txt` / `val.txt`** — they reference `base/…` and `modelscope/…`
paths that are **not** in the LMDBs and not individually on the Hub (they're inside the 681.8 MiB tarball).

**If all-31-province balance is mandatory and ~700 MB is unacceptable, there is no public option.**
Cheapest fallback: sample N/province from `train/data.mdb` (26 provinces) and accept the 5 missing,
or synthetically re-balance the existing 1000 crops.

---

## Could not confirm
1. Whether Huawei's **UI** walls the DDK link behind login/实名 (I bypassed it; the file itself is anonymous).
2. OMG/DOPT ↔ device-version **mismatch behaviour**.
3. Whether `converter_lite` + NNRt yields a Kirin-loadable model **end-to-end**.
4. **CBLPRD-330k** per-province counts (Baidu only; HF returns 401 for both nonexistent and gated repos,
   so "401" ≠ "exists but gated").
5. **CRPD** total size / province distribution / green-plate support.
6. **CCPD2020** exact green-plate count.
7. `gitee.com/ascend` contents (403 to scraper) — no DDK mirror confirmed or excluded.
8. Green vs merely 8-character counts — counted by string length, which is consistent with 新能源 but not proof.
