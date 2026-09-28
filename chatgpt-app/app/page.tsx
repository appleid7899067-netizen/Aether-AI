"use client";

/**
 * Aether widget rendered by ChatGPT after a tool call.
 * Reads `window.openai.toolOutput` (the tool's structuredContent) and shows
 * a card per view: status / chat / remember / recall / python.
 */
import {
  requestFullscreen,
  useDisplayMode,
  useIsChatGptApp,
  useMaxHeight,
  useTheme,
  useWidgetProps,
} from "./hooks/use-openai-globals";

type StatusPayload = {
  view: "status";
  health?: {
    status: string;
    service: string;
    version: string;
    components: Record<string, string | number>;
  };
  index?: {
    environment?: string;
    routers?: Record<string, string>;
    disabled_routers?: Record<string, string>;
  };
  endpoint?: string;
  error?: string;
};

type ChatPayload = {
  view: "chat";
  question?: string;
  answer?: string;
  model?: string;
  provider?: string;
  latency_ms?: number;
  error?: string;
};

type RememberPayload = {
  view: "remember";
  saved?: boolean;
  message_id?: number;
  session_id?: string;
  content?: string;
  error?: string;
};

type RecallPayload = {
  view: "recall";
  query?: string;
  context?: unknown;
  error?: string;
};

type PythonPayload = {
  view: "python";
  code?: string;
  ok?: boolean;
  stage?: string;
  stdout?: string;
  stderr?: string;
  exit_code?: number;
  error?: string;
};

type AnyPayload =
  | StatusPayload
  | ChatPayload
  | RememberPayload
  | RecallPayload
  | PythonPayload
  | null;

const card: React.CSSProperties = {
  borderRadius: 14,
  border: "1px solid rgba(127,127,127,0.28)",
  padding: "14px 16px",
  fontSize: 14,
  lineHeight: 1.55,
  overflowWrap: "anywhere",
};

function Header({ title, subtitle }: { title: string; subtitle?: string }) {
  return (
    <div style={{ marginBottom: 10 }}>
      <div style={{ fontSize: 15, fontWeight: 700 }}>{title}</div>
      {subtitle ? (
        <div style={{ fontSize: 12.5, opacity: 0.65, marginTop: 2 }}>{subtitle}</div>
      ) : null}
    </div>
  );
}

function ErrorBox({ message }: { message: string }) {
  return (
    <div
      style={{
        marginTop: 10,
        padding: "10px 12px",
        borderRadius: 10,
        border: "1px solid rgba(220,80,80,0.45)",
        background: "rgba(220,80,80,0.10)",
        fontSize: 13,
        whiteSpace: "pre-wrap",
      }}
    >
      {message}
    </div>
  );
}

function Row({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div
      style={{
        display: "flex",
        justifyContent: "space-between",
        gap: 12,
        padding: "4px 0",
        borderBottom: "1px dashed rgba(127,127,127,0.22)",
      }}
    >
      <span style={{ opacity: 0.75 }}>{label}</span>
      <span style={{ fontWeight: 600, textAlign: "right" }}>{value}</span>
    </div>
  );
}

export default function Widget() {
  const props = useWidgetProps<Record<string, unknown>>() as AnyPayload;
  const maxHeight = useMaxHeight();
  const displayMode = useDisplayMode();
  const theme = useTheme();
  const isChatGptApp = useIsChatGptApp();

  const dark = theme ? theme === "dark" : true;
  const colors = {
    background: dark ? "#0b1020" : "#f7f8fb",
    color: dark ? "#e8eefc" : "#12161f",
    accent: dark ? "#7dd3fc" : "#0969da",
    muted: dark ? "rgba(232,238,252,0.65)" : "rgba(18,22,31,0.6)",
  };

  const wrap: React.CSSProperties = {
    background: colors.background,
    color: colors.color,
    padding: 14,
    fontFamily:
      "ui-sans-serif, system-ui, -apple-system, 'Segoe UI', 'Noto Sans Thai', sans-serif",
    maxHeight: maxHeight ?? undefined,
    height: displayMode === "fullscreen" ? maxHeight ?? undefined : undefined,
    overflow: "auto",
    borderRadius: 16,
  };

  const view = props?.view;

  const body = (() => {
    if (!view) {
      return (
        <div style={card}>
          <Header title="Aether AI" subtitle="widget พร้อมทำงาน" />
          <div style={{ color: colors.muted }}>
            ลองพิมพ์ในแชทว่า “ขอสถานะ Aether”, “ถาม Aether ว่า …”, “remember …” หรือ
            “run python …”
          </div>
        </div>
      );
    }

    if (view === "status") {
      const p = props as StatusPayload;
      return (
        <div style={card}>
          <Header
            title={`Aether ${p.health?.version ?? ""}`.trim()}
            subtitle={p.endpoint ? `API: ${p.endpoint}` : undefined}
          />
          {p.health ? (
            <>
              <Row label="สถานะ" value={p.health.status} />
              <Row label="สภาพแวดล้อม" value={p.index?.environment ?? p.health.service} />
              <Row
                label="โมดูลที่โหลด"
                value={Object.keys(p.index?.routers ?? {}).length}
              />
              <Row
                label="ปิดใช้งาน (desktop only)"
                value={Object.keys(p.index?.disabled_routers ?? {}).length}
              />
            </>
          ) : null}
          {p.index?.routers ? (
            <div style={{ marginTop: 10, fontSize: 12.5, color: colors.muted }}>
              {Object.keys(p.index.routers).join(" · ")}
            </div>
          ) : null}
          {p.error ? <ErrorBox message={p.error} /> : null}
        </div>
      );
    }

    if (view === "chat") {
      const p = props as ChatPayload;
      return (
        <div style={card}>
          <Header title="Aether ตอบ" subtitle={p.provider ? `${p.provider}${p.model ? " · " + p.model : ""}${p.latency_ms ? " · " + Math.round(p.latency_ms) + "ms" : ""}` : undefined} />
          {p.question ? (
            <div style={{ color: colors.muted, marginBottom: 8 }}>ถาม: {p.question}</div>
          ) : null}
          <div style={{ whiteSpace: "pre-wrap" }}>{p.answer ?? "—"}</div>
          {p.error ? <ErrorBox message={p.error} /> : null}
        </div>
      );
    }

    if (view === "remember") {
      const p = props as RememberPayload;
      return (
        <div style={card}>
          <Header
            title={p.saved ? "บันทึกความจำแล้ว" : "บันทึกไม่สำเร็จ"}
            subtitle={p.session_id ? `memory: ${p.session_id} · #${p.message_id}` : undefined}
          />
          <div style={{ whiteSpace: "pre-wrap" }}>{p.content}</div>
          {p.error ? <ErrorBox message={p.error} /> : null}
        </div>
      );
    }

    if (view === "recall") {
      const p = props as RecallPayload;
      const text =
        typeof p.context === "string"
          ? p.context
          : JSON.stringify(p.context ?? {}, null, 2);
      return (
        <div style={card}>
          <Header title="ความจำที่เกี่ยวข้อง" subtitle={p.query ? `ค้นหา: ${p.query}` : undefined} />
          <pre
            style={{
              margin: 0,
              fontSize: 12.5,
              whiteSpace: "pre-wrap",
              maxHeight: 320,
              overflow: "auto",
            }}
          >
            {text}
          </pre>
          {p.error ? <ErrorBox message={p.error} /> : null}
        </div>
      );
    }

    const p = props as PythonPayload;
    return (
      <div style={card}>
        <Header
          title="Aether Sandbox"
          subtitle={
            p.stage === "validation"
              ? "ถูกปฏิเสธที่ขั้นตรวจสอบ AST"
              : `exit ${p.exit_code ?? "?"}`
          }
        />
        <pre
          style={{
            margin: "0 0 10px",
            padding: 10,
            borderRadius: 10,
            background: dark ? "rgba(255,255,255,0.05)" : "rgba(0,0,0,0.05)",
            fontSize: 12.5,
            whiteSpace: "pre-wrap",
          }}
        >
          {p.code}
        </pre>
        <pre style={{ margin: 0, fontSize: 12.5, whiteSpace: "pre-wrap" }}>
          {p.ok ? p.stdout || "(ไม่มี output)" : p.error || p.stderr || "ล้มเหลว"}
        </pre>
      </div>
    );
  })();

  return (
    <div style={wrap}>
      {!isChatGptApp ? (
        <div style={{ ...card, marginBottom: 12, color: colors.muted }}>
          โหมดทดสอบ: เปิดหน้านี้ใน ChatGPT เพื่อให้ widget รับผลจาก tool จริง
        </div>
      ) : null}
      {body}
      {displayMode !== "fullscreen" ? (
        <button
          onClick={requestFullscreen}
          style={{
            marginTop: 12,
            padding: "6px 12px",
            borderRadius: 999,
            border: `1px solid ${colors.accent}`,
            background: "transparent",
            color: colors.accent,
            cursor: "pointer",
            fontSize: 12.5,
          }}
        >
          ขยายเต็มจอ
        </button>
      ) : null}
    </div>
  );
}
