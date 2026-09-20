"""Independent verification of commit ab87154's correction.

Uses the project's OWN run_pipeline (detect -> rectify -> classify), which is the
production input path. My earlier settle_cls.py fed whole scenes to a 96x96
classifier, which is NOT the production path.
"""
import os, sys, glob, collections
import numpy as np

BASE = r"C:\Users\26671\Desktop\Test\lpr-showcase"
sys.path.insert(0, os.path.join(BASE, "tools"))
GREEN = r"C:\Users\26671\Desktop\车牌识别\_scratch\green"

import hlpr_reference as H

det = H.sess("y5fu_320x_sim.onnx")
rec = H.sess("rpv3_mdict_160_r3.onnx")
cls = H.sess("litemodel_cls_96x_r1.onnx")

files = sorted(glob.glob(os.path.join(GREEN, "*.jpg")))
print(f"green scene images: {len(files)}")
print("=" * 82)

hist = collections.Counter()
for p in files:
    img = H.imread_u(p)
    res = H.run_pipeline(img, det, rec, cls, full=True)
    if not res:
        print(f"  {os.path.basename(p):<20} no plate detected")
        continue
    for r in res:
        v = np.asarray(r["cls"]).ravel()
        k = int(np.argmax(v))
        hist[k] += 1
        print(f"  {os.path.basename(p):<20} crop={r['crop_shape']} code={r['code']:<10} "
              f"argmax={k}  {np.array2string(v, precision=5)}")

print()
print("PRODUCTION-PATH argmax histogram (green plates):", dict(hist))
print()
print("ADR-0005 reason one established the label table is rotated;")
print("correct order is blue=0, green=1, yellow=2.")
print(f"=> index 1 count = {hist.get(1,0)}/{sum(hist.values())}")

print()
print("=" * 82)
print("CONTROL: the 4 project samples, also via run_pipeline")
SAMPLES = os.path.join(BASE, "assets", "samples")
for name, truth in [("crop-0-津B6H920.jpg", "BLUE"),
                    ("crop-1-皖KD01833.jpg", "GREEN"),
                    ("crop-8-冀D5L690.jpg", "YELLOW"),
                    ("hlpr-test.jpg", "GREEN(disputed)")]:
    p = os.path.join(SAMPLES, name)
    if not os.path.exists(p):
        continue
    img = H.imread_u(p)
    res = H.run_pipeline(img, det, rec, cls, full=True)
    for r in res:
        v = np.asarray(r["cls"]).ravel()
        print(f"  {name:<24} truth={truth:<16} code={r['code']:<12} argmax={int(np.argmax(v))}")
