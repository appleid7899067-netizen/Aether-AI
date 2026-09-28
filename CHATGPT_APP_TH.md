# เชื่อม Aether เข้ากับ ChatGPT (ChatGPT App + MCP)

> เป้าหมาย: ให้ **ChatGPT เรียกเครื่องมือของ Aether ได้** แล้วโชว์ผลลัพธ์เป็น **widget** ในแชท
> โค้ดอยู่ที่โฟลเดอร์ [`chatgpt-app/`](chatgpt-app) ในรีโปนี้ (ไม่ใช่รีโป `chatgpt-app-with-next-js` เดิม
> เพราะบัญชีนี้ไม่มีสิทธิ์ push รีโปนั้น — สิทธิ์ถูกตรวจแล้วว่า `push: false`)

## สถาปัตยกรรม

```
┌──────────┐   MCP (HTTP/SSE)   ┌────────────────────┐   REST    ┌──────────────┐
│ ChatGPT  │ ─────────────────▶ │ chatgpt-app        │ ────────▶ │ Aether API   │
│ (widget) │ ◀───────────────── │ Next.js, /mcp      │ ◀──────── │ :8000        │
└──────────┘  structuredContent └────────────────────┘           └──────────────┘
```

* แอปนี้ทำหน้าที่เป็น **MCP server** เปิด 5 tools + 1 resource (`text/html+skybridge`)
* ChatGPT เห็นผลลัพธ์เป็น **structuredContent** → widget (`app/page.tsx`) เอาไปวาดเป็นการ์ดสวย ๆ
* ทุก tool คุยกับ Aether ผ่าน HTTP ด้วย `AETHER_API_URL`

## Tools

| Tool | ปลายทางฝั่ง Aether | ต้องมี provider key |
| --- | --- | --- |
| `aether_status` | `/health`, `/api` | ❌ |
| `ask_aether` | `POST /api/v1/chat/conversation` | ✅ |
| `remember` | `POST /api/v1/memory/conversation/message` | ❌ |
| `recall` | `POST /api/v1/memory/conversation/rag-context` | ❌ |
| `run_python` | `POST /api/v1/sandbox/python` | ❌ |

## ของใหม่ฝั่ง Aether ในรอบนี้

1. `src/utils/code_sandbox.py` — ย้าย AST guard ออกจาก playground มาเป็นโมดูลกลาง (ใช้ร่วมกันได้ทั้ง playground, API และอนาคต)
2. `src/api/routes/sandbox.py` — **route ใหม่** `POST /api/v1/sandbox/python` + `GET /api/v1/sandbox/info` + `/health`
   (ลงทะเบียนใน `ROUTER_MODULES` แล้ว → ตอนบูตขึ้น `Routers loaded: 21/25` จากเดิม 20/24)
3. `tools/sandbox_playground/sandbox_guard.py` — กลายเป็น facade ที่ re-export ของเดิม (playground :8100 ยังทำงานเหมือนเดิม)

## รัน + ต่อกับ ChatGPT (สรุปสั้น)

```bash
# เทอร์มินัล 1
uvicorn src.api.main:app --host 0.0.0.0 --port 8000

# เทอร์มินัล 2  (ต้องพอร์ต 3000)
cd chatgpt-app && npm install && AETHER_API_URL=http://localhost:8000 npm run dev

# เทอร์มินัล 3  เปิดท่อ HTTPS ให้ ChatGPT เข้าถึง
ngrok http 3000
```

แล้วที่ ChatGPT: **Settings → Connectors → Advanced → Developer mode** → **Add custom connector**
→ URL = `https://<โดเมน ngrok>/mcp` → เปิด connector ในแชทแล้วสั่งงานได้เลย

รายละเอียดทั้งหมด (env, deploy, ไฟล์ในโปรเจกต์, ข้อควรระวัง) อยู่ใน [`chatgpt-app/README.md`](chatgpt-app/README.md)

## ผลการทดสอบ (รันจริงในเครื่องนี้)

| การทดสอบ | ผล |
| --- | --- |
| `next build` | ✅ ผ่าน (route `/`, `/mcp`, middleware) |
| `initialize` ที่ `POST /mcp` | ✅ protocolVersion `2025-06-18`, serverInfo mcp-typescript 0.1.0 |
| `tools/list` | ✅ `aether_status, ask_aether, remember, recall, run_python` |
| `resources/read ui://widget/aether-template.html` | ✅ `text/html+skybridge`, 17.6 KB, มี bootstrap ของ Apps SDK |
| `aether_status` | ✅ “Aether 3.0.0 (development) - 21 modules loaded, 4 disabled” |
| `remember` | ✅ `{"success":true,"message_id":5,"session_id":"chatgpt"}` |
| `recall` | ✅ คืน `recent_context` ของ session `chatgpt` |
| `run_python` (`statistics.mean`) | ✅ stdout `2.5` |
| `run_python` (`import os`) | ✅ ถูกปฏิเสธ: “Import 'os' is not allowed here” |
| `run_python` (`while True`) | ✅ “Timed out after 2s (killed)” |
| `ask_aether` | ⚠️ HTTP 503 เพราะ **Aether ยังไม่ได้ใส่ API key ของโมเดล** — แอปแจ้งข้อความถูกต้อง (ไม่ใช่ “เชื่อมต่อไม่ได้”) พอใส่ key แล้วจะตอบปกติ |
| CORS `OPTIONS /mcp` | ✅ 204, `access-control-allow-origin: *` |
| Playground :8100 หลัง refactor guard | ✅ GET / 200 (9030 B) เหมือนเดิม |

## ข้อควรรู้

* **พอร์ตในโหมด dev ต้องเป็น 3000** — `lib/base-url.ts` ใช้ `http://localhost:$PORT` และ ChatGPT จะดึง widget จาก URL นั้น
* ตัวสตาร์ทเดิม (`baseUrl.ts`) อ่านแต่ตัวแปรของ Vercel → บน Render จะได้ `https://undefined`; เวอร์ชันนี้รองรับ `NEXT_PUBLIC_BASE_URL` และ `RENDER_EXTERNAL_URL` แล้ว
* `ask_aether` ใช้สมอง/ความจำ/provider ฝั่ง Aether (คีย์ของเซิร์ฟเวอร์) — ต่างจาก Puter mode ใน dashboard ที่ใช้โควตาของผู้ใช้เอง
