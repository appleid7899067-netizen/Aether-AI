# 🚀 เอาขึ้น Render — คู่มือภาษาไทย

> **สรุปสั้น ๆ:** ขึ้นได้ครับ แต่ **ไม่ใช่ repo เดิมแบบดิบ ๆ** — repo นี้มี merge conflict
> ค้างอยู่ 10 ไฟล์ (มี `<<<<<<< Updated upstream` อยู่ในไฟล์จริง) ทำให้แอป import ไม่ขึ้นเลย
> ตอนนี้แก้ให้เรียบร้อยแล้ว + ทำไฟล์ `render.yaml` ให้กด deploy ได้จากหน้าเว็บ Render

---

## 1. สิ่งที่แก้ให้แล้วในรอบนี้

| ปัญหา | สถานะ | รายละเอียด |
|---|---|---|
| Merge conflict ค้างในโค้ด 10 ไฟล์ (`requirements.txt`, `src/api/main.py`, `src/api/routes/__init__.py`, `src/api/routes/tasks.py`, `docker-compose.yml`, `k8s/deployment.yaml`, `ui/src/App.jsx`, ไฟล์ data ฯลฯ) | ✅ แก้แล้ว | เลือกฝั่ง Aether (โค้ดหลัก) และเขียน `src/api/routes/tasks.py` ใหม่ทั้งไฟล์ เพราะฝั่งที่ merge เข้ามาปนกันจนรันไม่ได้ |
| `src/main.py` มี string พัง (`logger.info("60)`) | ✅ แก้แล้ว | กลับเป็น `"=" * 60` และ compile ผ่าน |
| `data/costs.json` ถูกตัดกลางไฟล์ (JSON ไม่ปิดปีกกา) | ✅ แก้แล้ว | ปิดปีกกาให้ครบ ตอนนี้ parse ได้ 296 รายการ |
| dependency สั่งติดตั้งไม่ได้ (pin ผิด): `litellm==1.54.14`, `edge-tts==7.1.1` | ✅ แก้แล้ว | เปลี่ยนเป็น `>=1.54.0` / `>=7.2.0` |
| `pyautogui`, `pynput`, `pyaudio`, `sounddevice` ถูก import ตรง ๆ → บน server ที่ไม่มีจอ (headless) แอป **ตายตั้งแต่ import** | ✅ แก้แล้ว | เพิ่ม `src/utils/optional_import.py` แล้วแก้ 14 ไฟล์ให้ใช้ตัวช่วยนี้ → โหลดไม่ขึ้นแค่ "ฟีเจอร์ควบคุมเดสก์ท็อป" แต่ API ยังรันได้ |
| `get_ai_router()` ถูกเรียกใช้แต่ไม่มีใน `model_router.py` | ✅ แก้แล้ว | เพิ่มให้แล้ว |
| โหลด route รวมกันทั้งก้อน — พลาดตัวเดียว API ไม่ขึ้นเลย | ✅ แก้แล้ว | `src/api/main.py` โหลด router ทีละตัว ถ้าตัวไหนพังจะข้ามพร้อม log (`Routers loaded: 20/24`) |
| ไม่มี config สำหรับ Render เลย | ✅ เพิ่มแล้ว | `render.yaml`, `requirements-server.txt`, `Dockerfile` (โหมด server), หน้า dashboard ที่ `/` |

### ตรวจสอบแล้วจริง ๆ (ใน sandbox นี้)

```
pip install -r requirements-server.txt        → สำเร็จใน 30 วินาที (Python 3.11)
uvicorn src.api.main:app --port 8000          → Application startup complete
Routers loaded: 20/24 | disabled: ['control','autonomous','live_testing','desktop']
GET /            → 200  (dashboard หน้าเว็บ)
GET /health      → 200  {"status":"healthy","routers_loaded":20,...}
GET /openapi.json→ 200  (248 routes)
GET /api/v1/chat/providers → 200
GET /api/v1/tasks/stats    → 200
```

---

## 2. วิธี deploy (หน้าเว็บ Render — ง่ายสุด)

1. **เอาโค้ดขึ้น GitHub** (ถ้ายังไม่ได้ push) — คำสั่งอยู่ข้อ 5
2. เข้า <https://dashboard.render.com> → **New +** → **Blueprint**
3. เลือก repository `Aether-AI` → Render จะอ่าน `render.yaml` เอง แล้วกด **Apply**
4. ใส่ค่า **API key** ของ AI ที่หน้า Environment (ใส่ตัวใดตัวหนึ่งก็พอ):
   - `GROQ_API_KEY` (ฟรี เร็ว เหมาะที่สุด — <https://console.groq.com/keys>)
   - `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, `GOOGLE_API_KEY`, `FIREWORKS_API_KEY`, `OPENROUTER_API_KEY`
5. รอ build ~2 นาที → เปิด URL ที่ได้ เช่น `https://aether-ai-api.onrender.com`
   - `/` = dashboard (ดูสถานะ + คุยกับ Aether ได้เลย)
   - `/docs` = Swagger UI ทดลองยิง API ทุกตัว
   - `/health` = health check ที่ Render ใช้

> **ทางเลือกใช้ Docker:** New + → Web Service → Runtime = Docker → ใช้ `Dockerfile` ที่ให้ไว้
> (ต้องเลือกแพ็ก **Starter** ขึ้นไป เพราะ Docker ไม่รองรับ free plan)

## 3. ฟีเจอร์ไหนใช้ได้ / ใช้ไม่ได้บน Render

| ใช้ได้ ✅ | ใช้ไม่ได้ ❌ (ต้องรันบน PC) |
|---|---|
| แชทกับ AI (`/api/v1/chat`, `/chat`) | ควบคุมเมาส์/คีย์บอร์ด (`/api/v1/control`) |
| ความจำระยะยาว ChromaDB (`/api/v1/memory`) | เปิดโปรแกรม/พิมพ์งานอัตโนมัติ (`/api/v1/desktop`) |
| สังเคราะห์เสียงพูด TTS (`/api/v1/voice/synthesize`) | Live testing / browser อัตโนมัติ (`/api/v1/live-testing`) |
| Bug bounty recon/scanner (`/api/v1/bugbounty`) | งานอัตโนมัติที่ต้องมีหน้าจอ (`/api/v1/autonomous`) |
| อ่านเว็บ/สแกฟ์ (`/api/v1/openclaw`) | อัดเสียงจากไมค์ (เซิร์ฟเวอร์ไม่มีไมค์) |
| Task, Monitor, n8n, Intelligence, Settings, Discord ฯลฯ | Live vision (จับภาพหน้าจอ) |

เหตุผล: Render เป็น Linux ที่ไม่มีจอภาพ (`DISPLAY`) — โค้ดจะตรวจเองและปิด route เหล่านั้น
พร้อม log ว่า `Routers loaded: 20/24` ไม่ใช่แครช

## 4. ข้อควรรู้เรื่องแพ็กเกจ

- **Free plan**: RAM 512 MB, หลับหลังไม่มีคนใช้ 15 นาที (ตื่นเองเมื่อมี request), **ไม่มี disk ถาวร** →
  ข้อมูลใน `data/` (memory, tasks, costs) จะหายทุกครั้งที่ deploy ใหม่
- ถ้าอยากเก็บความจำถาวร: อัปเป็น **Starter** แล้วเปิด disk ใน `render.yaml` (มีตัวอย่างให้แล้ว ในคอมเมนต์)
- **อย่าใส่ API key ลงใน Git** — ใส่ในหน้า Environment ของ Render เท่านั้น (`.env` ถูก ignore อยู่แล้ว)

## 5. คำสั่ง push โค้ดขึ้น GitHub

```bash
git add -A
git commit -m "Fix merge conflicts + make API deployable on Render (headless support)"
git push origin arena/01a0e54b-aether-ai
```

จากนั้น merge เข้า `main` แล้วให้ Render ผูกกับ branch `main`

## 6. แก้ปัญหาที่เจอบ่อย

| อาการ | สาเหตุ / วิธีแก้ |
|---|---|
| Build fail ที่ `pip install` | ดู log ว่าแพ็กไหน — บน Render ให้ใช้ `requirements-server.txt` เท่านั้น (ห้ามใช้ `requirements.txt` เพราะมี PyQt6/torch/openvino) |
| เปิดเว็บแล้วขึ้น `Application startup failed` | ดู log คำว่า `Route module 'xxx' disabled` — ถ้าเป็น `control/desktop/autonomous/live_testing` คือเรื่องปกติ |
| แชทตอบไม่ได้/ขึ้น 500 | ยังไม่ได้ใส่ API key → ใส่ `GROQ_API_KEY` แล้ว deploy ใหม่, เช็คที่ `/api/v1/chat/providers` ว่ามี provider แล้วหรือยัง |
| อยากใช้ความจำ (ChromaDB) | ครั้งแรกจะดาวน์โหลดโมเดล ONNX ~80 MB (ครั้งเดียว) ต้องมีเน็ตออกนอกได้ |
| อยากให้หน้าเว็บสวย ๆ เป็นของตัวเอง | `ui-ts/` เป็น React+Vite ในตัว เปิดใช้ static site ใน `render.yaml` ได้ (มีตัวอย่างให้) แต่ต้องแก้ `ui-ts/src/App.tsx` ที่ hardcode `localhost:3001` (socket.io) ให้ชี้มา API จริงก่อน |

## 7. รันในเครื่องแบบเดียวกับ Render (ทดสอบก่อน deploy)

```bash
python -m venv .venv && source .venv/bin/activate     # Windows: .venv\Scripts\activate
pip install -r requirements-server.txt
uvicorn src.api.main:app --host 0.0.0.0 --port 8000
# เปิด http://localhost:8000
```

---

### งานที่ยังเหลือ (ถ้าต้องการให้ทำต่อ)

1. `ui/src/App.jsx` (Electron UI) ยังพังจาก merge — ต้องประกอบ UI ส่วนนั้นใหม่ (ตัว API ไม่กระทบ)
2. ลบ `node_modules` ที่ commit ไว้ (15,318 ไฟล์ / ~103 MB) ออกจาก Git → deploy เร็วขึ้นมาก
3. `src/api/routes/vision.py` เป็นไฟล์ว่างเปล่า — ยังไม่มี endpoint วิสชัน
