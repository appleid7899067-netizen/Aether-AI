/**
 * MCP server: exposes Aether AI as tools + a widget inside ChatGPT.
 *
 * Tools
 *  - aether_status : health / loaded modules of the Aether deployment
 *  - ask_aether    : send a question to Aether's own brain (server provider)
 *  - remember      : store a fact in Aether's long-term memory
 *  - recall        : retrieve relevant memory for a query
 *  - run_python    : execute a snippet in Aether's AST-guarded sandbox
 *
 * The widget (a registered resource) renders whatever the last tool returned:
 * a status card, a chat answer, memory hits, or sandbox output.
 */
import { createMcpHandler } from "mcp-handler";
import { z } from "zod";
import {
  AETHER_API_URL,
  AetherHttpError,
  askAether,
  getHealth,
  getIndex,
  recall,
  remember,
  runPython,
} from "@/lib/aether";
import { baseURL } from "@/lib/base-url";

const WIDGET_URI = "ui://widget/aether-template.html";

const widgetMeta = {
  "openai/outputTemplate": WIDGET_URI,
  "openai/toolInvocation/invoking": "คุยกับ Aether...",
  "openai/toolInvocation/invoked": "Aether ตอบกลับแล้ว",
  "openai/widgetAccessible": false,
  "openai/resultCanProduceWidget": true,
} as const;

const widgetResourceMeta = {
  "openai/widgetDescription": "ผลลัพธ์จาก Aether AI (สถานะ, คำตอบ, ความจำ, แซนด์บ็อกซ์)",
  "openai/widgetPrefersBorder": true,
  "openai/widgetDomain": AETHER_API_URL,
};

/** Human-readable failure text that distinguishes "down" from "refused". */
const describeError = (error: unknown): string => {
  const message = error instanceof Error ? error.message : String(error);
  if (error instanceof AetherHttpError) {
    return (
      `Aether ตอบกลับด้วย HTTP ${error.status}: ${message}\n` +
      `(ตัว Aether ทำงานอยู่ แต่ปฏิเสธคำขอนี้ - เช่นยังไม่ได้ตั้งค่า API key ของโมเดล)`
    );
  }
  return (
    `เชื่อมต่อ Aether ไม่ได้: ${message}\n` +
    `ตรวจสอบว่า Aether API รันอยู่ที่ ${AETHER_API_URL} (ตั้งค่า env AETHER_API_URL ที่โฮสต์ของแอปนี้)`
  );
};

const handler = createMcpHandler(async (server) => {
  const html = await fetch(`${baseURL}/`).then((r) => r.text());

  // ------------------------------------------------------------------ widget
  server.registerResource(
    "aether-widget",
    WIDGET_URI,
    {
      title: "Aether AI",
      description: "Renders Aether results inside ChatGPT",
      mimeType: "text/html+skybridge",
      _meta: widgetResourceMeta,
    },
    async (uri) => ({
      contents: [
        {
          uri: uri.href,
          mimeType: "text/html+skybridge",
          text: `<html>${html}</html>`,
          _meta: widgetResourceMeta,
        },
      ],
    })
  );

  // ------------------------------------------------------------------ status
  server.registerTool(
    "aether_status",
    {
      title: "Aether status",
      description:
        "Show the health of the Aether AI deployment: version, environment, which modules are loaded and which are disabled.",
      inputSchema: {},
      _meta: widgetMeta,
    },
    async () => {
      try {
        const [health, index] = await Promise.all([getHealth(), getIndex()]);
        const payload = {
          view: "status" as const,
          health,
          index,
          endpoint: AETHER_API_URL,
        };
        return {
          content: [
            {
              type: "text" as const,
              text:
                `Aether ${health.version} (${index.environment}) - ` +
                `${Object.keys(index.routers ?? {}).length} modules loaded, ` +
                `${Object.keys(index.disabled_routers ?? {}).length} disabled (desktop-only).`,
            },
          ],
          structuredContent: payload,
          _meta: widgetMeta,
        };
      } catch (error) {
        return {
          content: [{ type: "text" as const, text: describeError(error) }],
          structuredContent: { view: "status" as const, error: String(error) },
          _meta: widgetMeta,
        };
      }
    }
  );

  // -------------------------------------------------------------------- chat
  server.registerTool(
    "ask_aether",
    {
      title: "Ask Aether",
      description:
        "Send a question to the Aether AI assistant (its own brain, memory and tools) and return the answer. Use this for anything that needs Aether's context, memory or local capabilities.",
      inputSchema: {
        question: z.string().describe("The question or instruction for Aether"),
        session_id: z
          .string()
          .optional()
          .describe("Conversation id so Aether keeps context between calls (default chatgpt)"),
      },
      _meta: widgetMeta,
    },
    async ({ question, session_id }) => {
      try {
        const reply = await askAether(question, session_id ?? "chatgpt");
        return {
          content: [{ type: "text" as const, text: reply.content }],
          structuredContent: {
            view: "chat" as const,
            question,
            answer: reply.content,
            model: reply.model,
            provider: reply.provider,
            latency_ms: reply.latency_ms,
          },
          _meta: widgetMeta,
        };
      } catch (error) {
        return {
          content: [{ type: "text" as const, text: describeError(error) }],
          structuredContent: { view: "chat" as const, question, error: String(error) },
          _meta: widgetMeta,
        };
      }
    }
  );

  // ---------------------------------------------------------------- remember
  server.registerTool(
    "remember",
    {
      title: "Remember in Aether",
      description:
        "Store a fact, preference or note in Aether's long-term memory so later questions can use it.",
      inputSchema: {
        content: z.string().describe("The fact or note to remember"),
        session_id: z.string().optional().describe("Memory scope (default chatgpt)"),
      },
      _meta: widgetMeta,
    },
    async ({ content, session_id }) => {
      try {
        const result = await remember(content, session_id ?? "chatgpt");
        return {
          content: [{ type: "text" as const, text: `บันทึกแล้ว (message #${result.message_id})` }],
          structuredContent: {
            view: "remember" as const,
            saved: result.success,
            message_id: result.message_id,
            session_id: result.session_id,
            content,
          },
          _meta: widgetMeta,
        };
      } catch (error) {
        return {
          content: [{ type: "text" as const, text: describeError(error) }],
          structuredContent: { view: "remember" as const, content, error: String(error) },
          _meta: widgetMeta,
        };
      }
    }
  );

  // ------------------------------------------------------------------ recall
  server.registerTool(
    "recall",
    {
      title: "Recall from Aether",
      description:
        "Search Aether's memory for anything relevant to a query (recent conversation plus semantically similar older messages).",
      inputSchema: {
        query: z.string().describe("What to look for"),
        session_id: z.string().optional().describe("Memory scope (default chatgpt)"),
      },
      _meta: widgetMeta,
    },
    async ({ query, session_id }) => {
      try {
        const context = await recall(query, session_id ?? "chatgpt");
        const text =
          typeof context.context === "string"
            ? context.context
            : JSON.stringify(context.context ?? {}, null, 2);
        return {
          content: [{ type: "text" as const, text: text.slice(0, 4000) }],
          structuredContent: { view: "recall" as const, query, context: context.context },
          _meta: widgetMeta,
        };
      } catch (error) {
        return {
          content: [{ type: "text" as const, text: describeError(error) }],
          structuredContent: { view: "recall" as const, query, error: String(error) },
          _meta: widgetMeta,
        };
      }
    }
  );

  // --------------------------------------------------------------- run_python
  server.registerTool(
    "run_python",
    {
      title: "Run Python in Aether's sandbox",
      description:
        "Execute a short Python snippet inside Aether's sandbox (AST allow-list, isolated process, CPU/memory limits, 5s default timeout). Only pure-computation modules such as math, statistics, json, random are importable; file and network access are refused.",
      inputSchema: {
        code: z.string().describe("Python code to execute (max 4000 characters)"),
        timeout: z
          .number()
          .int()
          .min(1)
          .max(10)
          .optional()
          .describe("Seconds before the snippet is killed (default 5)"),
      },
      _meta: widgetMeta,
    },
    async ({ code, timeout }) => {
      try {
        const result = await runPython(code, timeout ?? 5);
        const output = result.ok
          ? (result.stdout ?? "").trim() || "(ไม่มี output)"
          : `ถูกปฏิเสธ/ล้มเหลว: ${result.error ?? result.stderr ?? "unknown error"}`;
        return {
          content: [{ type: "text" as const, text: output }],
          structuredContent: { view: "python" as const, code, ...result },
          _meta: widgetMeta,
        };
      } catch (error) {
        return {
          content: [{ type: "text" as const, text: describeError(error) }],
          structuredContent: { view: "python" as const, code, error: String(error) },
          _meta: widgetMeta,
        };
      }
    }
  );
});

export const GET = handler;
export const POST = handler;
