# 🧪 Aether Sandbox Playground

เว็บแอปเล็ก ๆ ไว้ **ลองเล่นแซนด์บ็อกซ์ของ Aether AI** จากเบราว์เซอร์ — ใช้โค้ดจริงจากโปรเจกต์ ไม่ได้จำลอง

```bash
uvicorn tools.sandbox_playground.app:app --host 0.0.0.0 --port 8100
# เปิด http://localhost:8100
```

## สามโหมด

| โหมด | เบื้องหลัง | กันอะไรได้ |
|---|---|---|
| **1 · Python Sandbox** | `sandbox_guard.run_python` | AST allow-list (42 โมดูลบริสุทธิ์), บล็อก `open/exec/eval/getattr/__import__` และ dunder ที่ใช้หลุด sandbox, รันด้วย `python -I` ใน temp dir, rlimit (CPU 5s / RAM 512MB / no fork), timeout, **ตัด API key ออกจาก env** |
| **2 · Safe Command** | `src/action/automation/script_executor.py` | deny-list (`rm`, `dd`, `sudo`, `shutdown` …) + allow-list คำสั่งอ่านอย่างเดียว + จำกัด output 10 MB |
| **3 · Plugin Sandbox** | `src/core/plugins/sandbox.py` | รันปลั๊กอินใน **process แยก** timeout 10 วิ — แครช/แฮงค์ไม่ลากเซิร์ฟเวอร์ล้ม |

## ลองอะไรได้บ้าง

- `print(sum(range(101)))` → 5050
- `import os` หรือ `()._\_class_\_` → **ถูกปฏิเสธก่อนรัน** (ดูผลในช่องที่ 4)
- `while True: pass` → ถูกฆ่าที่ 5 วินาที
- `rm -rf /` ผ่าน Safe Command → `Command 'rm' is not allowed for safety reasons`
- ปลั๊กอิน fibonacci / text-stats → ผลลัพธ์ JSON กลับมาจากอีก process

## ⚠️ ข้อจำกัด (พูดตรง ๆ)

นี่คือ **เดโม** ไม่ใช่ production multi-tenant sandbox:

- Python runner ปลอดภัยพอให้ลองวางโค้ดเล่น แต่ไม่ใช่กำแพงระดับ gVisor / Firecracker / container
- Safe Command ยังรันบนเครื่องเดียวกับเซิร์ฟเวอร์ — คำสั่งใน allow-list จึงเข้าถึงไฟล์ที่ผู้ใช้รันเข้าถึงได้
- **อย่าเปิด public** โดยไม่มี auth หน้าเว็บ (ในเครื่อง/ในแซนด์บ็อกซ์ทดสอบเท่านั้น)

## โครงสร้าง

```
tools/sandbox_playground/
├── app.py               # FastAPI: หน้าเว็บ + 3 endpoint
├── sandbox_guard.py     # AST validation + subprocess runner + env stripping
├── playground.html      # UI ภาษาไทย
└── demo_plugins/        # ปลั๊กอินตัวอย่างสำหรับ PluginSandbox
    ├── fibonacci_plugin.py
    └── text_stats_plugin.py
```
