# Aether AI · ChatGPT App (MCP)

แอป ChatGPT (MCP server) ที่ยกเครื่องมือของ **Aether AI** เข้าไปในแชท
ผู้ใช้พิมพ์สั่งใน ChatGPT แล้ว ChatGPT เรียก Aether ให้ และผลลัพธ์ถูกวาดเป็น **widget**
ในแชท (สถานะระบบ / คำตอบจาก Aether / ความจำ / ผลรันแซนด์บ็อกซ์)

```
ChatGPT  ──MCP /mcp──▶  แอปนี้ (Next.js)  ──HTTP──▶  Aether API (:8000)
                            │
                            └── widget (text/html+skybridge) แสดง structuredContent
```

## Tools ที่เปิดให้ ChatGPT

| Tool | เรียกอะไรที่ Aether | ต้องมี API key? |
| --- | --- | --- |
| `aether_status` | `GET /health` + `GET /api` | ไม่ต้อง |
| `ask_aether` | `POST /api/v1/chat/conversation` | ✅ ต้องมี provider key (Groq/Gemini/…) |
| `remember` | `POST /api/v1/memory/conversation/message` | ไม่ต้อง |
| `recall` | `POST /api/v1/memory/conversation/rag-context` | ไม่ต้อง |
| `run_python` | `POST /api/v1/sandbox/python` | ไม่ต้อง |

`run_python` รันผ่าน AST guard เดียวกับ playground (`src/utils/code_sandbox.py`):
import ได้เฉพาะโมดูลบริสุทธิ์ (math, json, statistics, random, …), ห้าม `open`/`exec`/dunder,
รันเป็นโปรเซสแยกด้วย `python -I` + rlimit + timeout (ค่าเริ่มต้น 5 วินาที) — โค้ดยาวได้ไม่เกิน 4000 ตัวอักษร

## รันในเครื่อง

```bash
# 1) สตาร์ท Aether API (คนละเทอร์มินัล)
cd /path/to/Aether-AI
uvicorn src.api.main:app --host 0.0.0.0 --port 8000

# 2) สตาร์ทแอปนี้  (ต้องเป็นพอร์ต 3000 ในโหมด dev เพราะ base-url ใช้ localhost:3000)
cd chatgpt-app
npm install
AETHER_API_URL=http://localhost:8000 npm run dev
```

ตรวจว่า MCP ตอบ:

```bash
curl -s -X POST http://localhost:3000/mcp \
  -H 'Content-Type: application/json' -H 'Accept: application/json, text/event-stream' \
  -d '{"jsonrpc":"2.0","id":1,"method":"tools/list","params":{}}'
```

## ต่อเข้า ChatGPT

ChatGPT ต้องเข้าถึง MCP server ได้ผ่าน **HTTPS สาธารณะ** จึงต้องเปิดท่อก่อน:

```bash
ngrok http 3000          # หรือ  cloudflared tunnel --url http://localhost:3000
```

จากนั้น

1. ChatGPT → **Settings → Connectors → Advanced → Developer mode** (เปิด)
2. **Create / Add custom connector**
3. ใส่ URL เป็น `https://<โดเมนที่ได้>/mcp`  (ต้องมี `/mcp` ต่อท้าย)
4. กลับไปหน้าแชท → เลือก connector นี้ แล้วพิมพ์ เช่น
   - “ขอสถานะ Aether”
   - “ถาม Aether ว่าเครื่องผมโหลดอะไรอยู่”
   - “remember ว่าผมชอบตอบภาษาไทย”
   - “run python หาค่าเฉลี่ยของ 1..10”

## ตัวแปรสภาพแวดล้อม

| ตัวแปร | ค่าเริ่มต้น | ใช้ทำอะไร |
| --- | --- | --- |
| `AETHER_API_URL` | `http://localhost:8000` | ที่อยู่ Aether API (ไม่ต้องมี `/` ปิดท้าย) |
| `AETHER_API_TOKEN` | – | ถ้าใส่ จะส่ง `Authorization: Bearer …` ทุกคำขอ |
| `NEXT_PUBLIC_BASE_URL` | ตรวจอัตโนมัติ | บังคับ public URL ของแอปนี้ (ใช้ทำ assetPrefix + widget) |
| `PORT` | `3000` | พอร์ตของแอปนี้ |

ลำดับการหา base URL: `NEXT_PUBLIC_BASE_URL` → `VERCEL_*` → `RENDER_EXTERNAL_URL` → `http://localhost:$PORT`
(แก้จาก starter เดิมที่จะกลายเป็น `https://undefined` เมื่อไม่ใช่ Vercel)

## Deploy

### Render (แนะนำ — มีให้ครบใน `../render.yaml`)

`render.yaml` ที่ราก repo สร้าง 2 บริการพร้อมกัน: `aether-ai-api` (Python) และ `aether-chatgpt-app` (โฟลเดอร์นี้)

> Dashboard → **New +** → **Blueprint** → เลือก repo → เลือก branch → ใส่ API key → **Apply**

ค่าที่ตั้งให้อัตโนมัติ:

| ตัวแปร | ที่มา |
| --- | --- |
| `AETHER_API_URL` | `fromService` → `RENDER_EXTERNAL_URL` ของ `aether-ai-api` |
| `PORT` | Render ตั้งเอง (10000) — `next start` อ่านและผูก `0.0.0.0` ตาม `startCommand` |
| `NEXT_PUBLIC_BASE_URL` | ไม่ต้องใส่ — โค้ดอ่าน `RENDER_EXTERNAL_URL` ตอน build ให้เอง (ใส่เมื่อใช้ custom domain เท่านั้น) |

หลัง deploy: เอา `https://<ชื่อบริการ>.onrender.com/mcp` ไปใส่ใน ChatGPT → Settings → Connectors → Developer mode → Add custom connector

### อื่น ๆ

* **Vercel** — import โฟลเดอร์นี้ ตั้ง `AETHER_API_URL` (และ `NEXT_PUBLIC_BASE_URL` ถ้าต้องการตรึงโดเมน)
* **Docker / VPS** — มี `Dockerfile` ให้แล้ว; ตั้ง `AETHER_API_URL` แล้วใช้ URL ของแอปเป็น `/mcp`

### ข้อควรรู้บนแผนฟรี

* หลับหลังไม่มีคนใช้ 15 นาที → request แรกช้า ~30-60 วิ (ทั้งสองบริการ)
* ไม่มี disk ถาวร → หน่วยความจำของ Aether (`data/`) หายทุกครั้งที่ deploy
* widget จะเรียก asset จาก `assetPrefix` ที่ฝังตอน build ถ้าเปลี่ยนโดเมนต้อง redeploy

## ไฟล์สำคัญ

```
app/mcp/route.ts           MCP server: 5 tools + resource widget
app/page.tsx               widget ที่ ChatGPT วาด (อ่าน window.openai.toolOutput)
app/hooks/use-openai-globals.ts  ตัวอ่าน globals ของ Apps SDK (ไม่ต้องพึ่ง dependency ภายนอก)
lib/aether.ts              HTTP client ของ Aether (typed error: HTTP error vs unreachable)
lib/base-url.ts            หา public base URL (Vercel/Render/localhost)
middleware.ts              CORS สำหรับ iframe ของ ChatGPT
```

> หมายเหตุ: `ask_aether` จะได้ HTTP 503 ถ้าฝั่ง Aether ยังไม่ได้ตั้งค่า provider key
> (ตัวแอปนี้จะรายงานว่า “Aether ตอบกลับด้วย HTTP 503 …” ไม่ใช่ “เชื่อมต่อไม่ได้”)
