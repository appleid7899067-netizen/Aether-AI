#!/usr/bin/env python3
"""Three ways to use the sandbox from Python - run me:  python3 example_usage.py"""
import json

from code_sandbox import run_python

print("1) แบบปกติ")
print(json.dumps(run_python("import math\nprint(round(math.pi, 4))"), ensure_ascii=False))

print("\n2) โค้ดที่พยายามหนีออกจากแซนด์บ็อกซ์ (โดนปฏิเสธก่อนรัน)")
print(json.dumps(run_python("import os\nprint(os.listdir('/'))"), ensure_ascii=False)[:180] + " ...")

print("\n3) โค้ดที่รันไม่จบ (timeout)")
print(json.dumps(run_python("while True: pass", timeout=2), ensure_ascii=False))

print("\n4) เรียกผ่าน HTTP sidecar แทน import (ถ้าอยากแยกโปรเซส/แยกเครื่อง)")
print("""   curl -s -X POST http://127.0.0.1:8123/run \\\\
     -H 'Content-Type: application/json' \\\\
     -d '{"code": "print(6*7)"}'""")
