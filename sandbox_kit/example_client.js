// เรียก sandbox server ที่รันอยู่ข้าง ๆ (ใช้ได้จาก Node / Next.js / browser ที่มี proxy)
export async function runSandbox(code, { timeout = 5, token } = {}) {
  const response = await fetch("http://127.0.0.1:8123/run", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      ...(token ? { "X-Sandbox-Token": token } : {}),
    },
    body: JSON.stringify({ code, timeout }),
  });
  if (!response.ok) throw new Error(`sandbox HTTP ${response.status}`);
  return response.json(); // { ok, stage, exit_code, stdout, stderr } | { ok:false, error }
}
