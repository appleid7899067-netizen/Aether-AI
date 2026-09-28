# 🚀 เอาขึ้น Render — คู่มือภาษาไทย

> **สรุปสั้น ๆ:** ขึ้นได้ครับ แต่ **ไม่ใช่ repo เดิมแบบดิบ ๆ** — repo นี้มี merge conflict
> ค้างอยู่ 10 ไฟล์ (มี `<<<<<<< Updated upstream` อยู่ในไฟล์จริง) ทำให้แอป import ไม่ขึ้นเลย
> ตอนนี้แก้ให้เรียบร้อยแล้ว + ทำไฟล์ `render.yaml` ให้กด deploy ได้จากหน้าเว็บ Render
>
> **อัปเดตล่าสุด:** `render.yaml` สร้างให้ **2 บริการในคลิกเดียว**
> 1. `aether-ai-api` — ตัว Aether API + dashboard (Python)
> 2. `aether-chatgpt-app` — แอป ChatGPT (MCP + widget) ที่ให้ ChatGPT เรียกเครื่องมือของ Aether (Node)
>
> ทั้งคู่ตั้งอยู่ region **singapore** และผูกค่าหากันให้อัตโนมัติ (`AETHER_API_URL` ของแอปชี้มาที่ API)

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
3. เลือก repository `Aether-AI` → เลือก **branch** ที่จะใช้ → Render อ่าน `render.yaml` เอง แล้วกด **Apply**
   - เลือก `arena/01a0e54b-aether-ai` = ได้โค้ดล่าสุดทันที (ยังไม่ต้อง merge)
   - เลือก `main` = ต้อง merge PR ก่อน (ดูข้อ 5)
   - ไฟล์ `render.yaml` **ไม่ล็อก branch** ไว้ เพื่อให้ Render ใช้ branch ที่เราเลือกตอนสร้าง Blueprint
4. ใส่ค่า **API key** ของ AI ที่หน้า Environment ของ `aether-ai-api` (ใส่ตัวใดตัวหนึ่งก็พอ):
   - `GROQ_API_KEY` (ฟรี เร็ว เหมาะที่สุด — <https://console.groq.com/keys>)
   - `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, `GOOGLE_API_KEY`, `FIREWORKS_API_KEY`, `OPENROUTER_API_KEY`
   - ไม่ใส่ก็ได้ ถ้าจะใช้ **โหมด Puter** ในหน้า dashboard (ดู `PUTER_SETUP_TH.md`)
5. กด **Apply** → รอ build ~2 นาที (API) + ~2 นาที (แอป ChatGPT) จะได้ 2 URL:
   - `https://aether-ai-api.onrender.com` — `/` dashboard, `/docs` Swagger, `/health` health check
   - `https://aether-chatgpt-app.onrender.com` — `/` หน้าตัวอย่าง widget, **`/mcp`** ตัว MCP ที่ ChatGPT เรียก

> **ทางเลือกใช้ Docker:** New + → Web Service → Runtime = Docker → ใช้ `Dockerfile` ที่ให้ไว้
> (ต้องเลือกแพ็ก **Starter** ขึ้นไป เพราะ Docker ไม่รองรับ free plan)

## 2.5 ต่อ ChatGPT เข้ากับ Aether (หลัง deploy เสร็จ)

1. เปิด ChatGPT → **Settings → Connectors → Advanced → Developer mode** (เปิด)
2. **Add custom connector** → ใส่ URL:
   `https://aether-chatgpt-app.onrender.com/mcp` ← ต้องมี `/mcp` ต่อท้าย
3. กลับหน้าแชท → เลือก connector นี้ → ลองพิมพ์
   - “ขอสถานะ Aether” → เรียก `aether_status`
   - “ถาม Aether ว่า …” → เรียก `ask_aether` (ต้องมี API key ที่ข้อ 4 ไม่งั้นจะได้ 503)
   - “remember ว่า …” / “recall เรื่อง …” → ใช้ความจำของ Aether
   - “run python …” → รันในแซนด์บ็อกซ์ของ Aether
4. ผลลัพธ์จะถูกวาดเป็น **widget** ในแชท (การ์ดสถานะ / คำตอบ / ความจำ / ผลรันโค้ด)

> **เช็คว่า MCP ยังไม่ตาย** (จากเครื่องตัวเอง):
> ```bash
> curl -s -X POST https://aether-chatgpt-app.onrender.com/mcp \
>   -H 'Content-Type: application/json' -H 'Accept: application/json, text/event-stream' \
>   -d '{"jsonrpc":"2.0","id":1,"method":"tools/list","params":{}}'
> ```
> ต้องเห็นชื่อ tool ทั้ง 5: `aether_status, ask_aether, remember, recall, run_python`

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

จากนั้นถ้าต้องการให้ Render ผูกกับ `main` (แนะนำระยะยาว) ให้ merge PR #1 เข้า `main`
แล้วเปลี่ยน branch ของทั้ง 2 บริการใน Render → Settings → Build & Deploy → Branch
(หรือเลือก branch `arena/01a0e54b-aether-ai` ตอนสร้าง Blueprint เพื่อใช้โค้ดล่าสุดก่อน merge ก็ได้)

## 6. แก้ปัญหาที่เจอบ่อย

| อาการ | สาเหตุ / วิธีแก้ |
|---|---|
| Build fail ที่ `pip install` | ดู log ว่าแพ็กไหน — บน Render ให้ใช้ `requirements-server.txt` เท่านั้น (ห้ามใช้ `requirements.txt` เพราะมี PyQt6/torch/openvino) |
| เปิดเว็บแล้วขึ้น `Application startup failed` | ดู log คำว่า `Route module 'xxx' disabled` — ถ้าเป็น `control/desktop/autonomous/live_testing` คือเรื่องปกติ |
| แชทตอบไม่ได้/ขึ้น 500 | ยังไม่ได้ใส่ API key → ใส่ `GROQ_API_KEY` แล้ว deploy ใหม่, เช็คที่ `/api/v1/chat/providers` ว่ามี provider แล้วหรือยัง — **หรือใช้โหมด Puter ในหน้า dashboard ก็ไม่ต้องมี key เลย** (ดู `PUTER_SETUP_TH.md`) |
| ปุ่มล็อกอิน Puter ในหน้าต่าง preview ไม่เด้ง | Puter ต้องเป็นแท็บปกติ (top-level) เปิด URL ของ Render ในแท็บใหม่แล้วล็อกอิน |
| อยากใช้ความจำ (ChromaDB) | ครั้งแรกจะดาวน์โหลดโมเดล ONNX ~80 MB (ครั้งเดียว) ต้องมีเน็ตออกนอกได้ |
| แอป ChatGPT build ผ่านแต่ widget โหลดไม่ขึ้น / 404 `/_next/...` | ตัว `assetPrefix` ถูกฝังตอน build — ตั้ง `NEXT_PUBLIC_BASE_URL=https://aether-chatgpt-app.onrender.com` ที่ Environment ของบริการนี้ แล้ว **Manual Deploy → Clear build cache & deploy** |
| เปิด `/mcp` แล้วได้ 404/405 | ต้องเป็น **POST** (ไม่ใช่เปิดในเบราว์เซอร์) — ใช้คำสั่ง curl ในข้อ 2.5 ตรวจ และตรวจว่า `rootDir = chatgpt-app` ถูกต้อง |
| ChatGPT ตอบช้ามากในครั้งแรก | แผนฟรีจะ **หลับหลัง 15 นาที** → request แรกปลุก ~30-60 วิ (ทั้ง API และแอปแอป) ถ้าใช้จริงจังแนะนำอัปเป็น Starter (ไม่หลับ) |
| `ask_aether` ขึ้น HTTP 503 | ยังไม่ได้ใส่ API key ฝั่ง `aether-ai-api` — ใส่ `GROQ_API_KEY` แล้ว deploy ใหม่ (หรือดู `GET /api/v1/chat/providers`) |
| อยากให้หน้าเว็บสวย ๆ เป็นของตัวเอง | `ui-ts/` เป็น React+Vite ในตัว เปิดใช้ static site ใน `render.yaml` ได้ (มีตัวอย่างให้) แต่ต้องแก้ `ui-ts/src/App.tsx` ที่ hardcode `localhost:3001` (socket.io) ให้ชี้มา API จริงก่อน |

## 7. รันในเครื่องแบบเดียวกับ Render (ทดสอบก่อน deploy)

```bash
python -m venv .venv && source .venv/bin/activate     # Windows: .venv\Scripts\activate
pip install -r requirements-server.txt
uvicorn src.api.main:app --host 0.0.0.0 --port 8000
# เปิด http://localhost:8000
```

ทดสอบ "โหมด Render" ของแอป ChatGPT (จำลอง env จริง + พอร์ต 10000):

```bash
cd chatgpt-app
RENDER_EXTERNAL_URL=https://aether-chatgpt-app.onrender.com \
AETHER_API_URL=http://localhost:8000 PORT=10000 \
  npm run build && npx next start -H 0.0.0.0 -p 10000
# เปิด http://localhost:10000   →  หน้า widget
# POST http://localhost:10000/mcp  →  MCP server
```

---

### งานที่ยังเหลือ (ถ้าต้องการให้ทำต่อ)

1. `ui/src/App.jsx` (Electron UI) ยังพังจาก merge — ต้องประกอบ UI ส่วนนั้นใหม่ (ตัว API ไม่กระทบ)
2. ลบ `node_modules` ที่ commit ไว้ (15,318 ไฟล์ / ~103 MB) ออกจาก Git → deploy เร็วขึ้นมาก
3. `src/api/routes/vision.py` เป็นไฟล์ว่างเปล่า — ยังไม่มี endpoint วิสชัน
