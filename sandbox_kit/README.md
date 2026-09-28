# 🧪 Sandbox Kit — ยกแซนด์บ็อกซ์รันโค้ดไปต่อโปรเจกต์อื่น

**ตอบสั้น ๆ: ได้ครับ** — ตัวแซนด์บ็อกซ์เป็นโค้ด Python ไฟล์เดียว ใช้แค่ standard library
(ไม่มี pip install, ไม่ผูกกับ Aether) จะก๊อปทั้งโฟลเดอร์หรือหยิบแค่ `code_sandbox.py` ไปวางที่อื่นก็ได้

| ไฟล์ | ต้องมีไหม | หน้าที่ |
|---|---|---|
| `code_sandbox.py` | ✅ **ไฟล์เดียวที่ต้องมี** | AST allow-list + รันโค้ดในโปรเซสแยก (stdlib ทั้งไฟล์) |
| `standalone_server.py` | ทางเลือก | HTTP server + หน้า playground ในตัว (ไม่ต้องมี FastAPI) |
| `sandbox_router.py` | ทางเลือก | FastAPI router สำเร็จรูป (ถ้าโปรเจกต์ปลายทางใช้ FastAPI อยู่แล้ว) |
| `example_usage.py` | ตัวอย่าง | วิธีเรียกใช้แบบ Python |
| `example_client.js` | ตัวอย่าง | วิธีเรียกแบบ Node / Next.js |

---

## วิธีที่ 1 — import ตรง ๆ (โปรเจกต์ปลายทางเป็น Python)

```bash
cp sandbox_kit/code_sandbox.py /path/to/other-project/
```

```python
from code_sandbox import run_python

result = run_python("import math\nprint(math.factorial(10))", timeout=5)
# {"ok": True, "stage": "execution", "exit_code": 0, "stdout": "3628800\n", "stderr": ""}
```

ผลลัพธ์ที่ได้เมื่อโค้ดไม่ผ่าน (ไม่ throw — คืน dict เสมอ):

```python
{"ok": False, "stage": "validation", "error": "'open()' is not allowed"}
{"ok": False, "stage": "execution", "error": "Timed out after 2s (killed)"}
```

## วิธีที่ 2 — HTTP sidecar (โปรเจกต์ปลายทางเป็น Node / Go / อะไรก็ได้)

รันเซิร์ฟเวอร์แยก แล้วให้โปรเจกต์อื่นเรียกผ่าน HTTP — เหมาะเวลาอยากแยกโปรเซส/แยกเครื่อง
หรือจำกัดสิทธิ์การรันโค้ดไว้ที่เดียว

```bash
python3 standalone_server.py --host 127.0.0.1 --port 8123 --token s3cret
```

| Endpoint | ใช้ทำอะไร |
|---|---|
| `GET /` | หน้า playground เล็ก ๆ (พิมพ์โค้ด กด Run) |
| `GET /info` | รายการโมดูลที่ import ได้ + ลิมิต + blocked features |
| `GET /health` | `{"status":"ok"}` |
| `POST /run` | `{"code": "...", "timeout": 5}` → ผลรัน |

```bash
curl -s -X POST http://127.0.0.1:8123/run \
  -H 'Content-Type: application/json' -H 'X-Sandbox-Token: s3cret' \
  -d '{"code": "print(6*7)"}'
```

```javascript
// Node / Next.js — ดูเวอร์ชันเต็มใน example_client.js
const r = await fetch("http://127.0.0.1:8123/run", {
  method: "POST",
  headers: { "Content-Type": "application/json", "X-Sandbox-Token": "s3cret" },
  body: JSON.stringify({ code: "print(6*7)", timeout: 5 }),
});
console.log(await r.json());
```

> ถ้าเรียกจาก **browser** ให้ proxy ผ่าน backend ของคุณ (อย่าเปิด token ไว้ฝั่ง client)
> ตัวเซิร์ฟเวอร์ตั้ง CORS ให้อยู่แล้วด้วย `--allow-origin`

## วิธีที่ 3 — FastAPI ที่มีอยู่แล้ว

```python
from fastapi import FastAPI
from sandbox_router import router as sandbox_router

app = FastAPI()
app.include_router(sandbox_router)   # -> /api/v1/sandbox/python, /info, /health
```

---

## ข้างในมีอะไร (3 ชั้นป้องกัน)

1. **AST allow-list** — import ได้เฉพาะโมดูลคำนวณบริสุทธิ์ 42 ตัว (`math`, `statistics`, `json`, `random`, `re`, ...)
   ห้าม `open`, `exec`, `eval`, `__import__`, `getattr` และห้ามเข้า dunder (`__class__`, `__subclasses__`, ...)
   → ตัดทางหนีแบบ `().__class__.__bases__[0].__subclasses__()` ก่อนรันจริง
2. **สภาพแวดล้อมขั้นต่ำ** — โปรเซสลูกได้ env ไม่กี่ตัว → API key ในโปรเซสแม่ไม่รั่ว
3. **ลิมิตตอนรัน** — `python -I` (isolated), โฟลเดอร์ชั่วคราว, CPU/RAM/fork rlimit, timeout (default 5 วิ)
   และตัดที่ 4000 ตัวอักษร / 6000 AST nodes

## ลิมิตที่ควรรู้

| เรื่อง | ค่า |
|---|---|
| โมดูลที่ import ได้ | 42 ตัว (ดู `GET /info`) |
| ความยาวโค้ด | ≤ 4000 ตัวอักษร |
| timeout | 1–10 วิ (default 5) |
| RAM / CPU / จำนวนโปรเซสลูก | rlimit ตามที่กำหนดใน `_limits()` |
| Windows | rlimit ถูกข้าม (ไม่มี `resource`) แต่ AST + timeout + env ยังทำงาน |

## ⚠️ ข้อจำกัดด้านความปลอดภัย (อ่านก่อนใช้จริง)

นี่คือ **ด่านสำหรับ "คนกดรันโค้ดเล่น" ไม่ใช่กำแพงกันผู้โจมตีจริงจัง**:

* เป็น allow-list ของ AST + โปรเซสบวม ๆ บนเครื่องเดียวกับแอป → ถ้าจะเปิดให้คนนอก (multi-tenant)
  ควรครอบด้วย container/VM (Docker, gVisor, Firecracker) หรือรันบนเครื่องแยก
* โมดูลที่อนุญาตเป็น pure computation แต่ก็ยังกิน CPU ได้ → ต้องมี timeout + rlimit เสมอ
* อย่าให้สิทธิ์ไฟล์ระบบกับผู้ใช้ที่รันเซิร์ฟเวอร์นี้ (รันด้วย user ธรรมดา ไม่ใช่ root)
* ถ้าเปิดฟังสาธารณะ (`--host 0.0.0.0`) **ควรใส่ `--token`** และวางไว้หลัง reverse proxy ที่จำกัด rate

## ที่มา / การซิงก์

`code_sandbox.py` ในโฟลเดอร์นี้คือสำเนาของตัวที่ใช้จริงใน Aether (`src/utils/code_sandbox.py`
ซึ่งให้บริการ `POST /api/v1/sandbox/python` และ playground) — ถ้าแก้ฝั่งโน้น ให้ก๊อปมาแทนไฟล์นี้:

```bash
cp src/utils/code_sandbox.py sandbox_kit/code_sandbox.py
```
