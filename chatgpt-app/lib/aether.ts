/**
 * Aether API client used by the MCP server (runs on the server, in Node).
 *
 * Configure with:
 *   AETHER_API_URL   e.g. https://aether-ai-api.onrender.com  (default http://localhost:8000)
 *   AETHER_API_TOKEN optional bearer token, sent as `Authorization` when set
 */

export const AETHER_API_URL = (
  process.env.AETHER_API_URL ?? "http://localhost:8000"
).replace(/\/+$/, "");

const TOKEN = process.env.AETHER_API_TOKEN;

/** Aether answered, but with an error status (reachable but refusing). */
export class AetherHttpError extends Error {
  constructor(
    message: string,
    readonly status: number
  ) {
    super(message);
    this.name = "AetherHttpError";
  }
}

/** Could not talk to Aether at all (DNS, refused connection, timeout). */
export class AetherUnreachableError extends Error {
  constructor(message: string) {
    super(message);
    this.name = "AetherUnreachableError";
  }
}

async function aetherFetch<T>(
  path: string,
  init: RequestInit & { timeoutMs?: number } = {}
): Promise<T> {
  const { timeoutMs = 60_000, ...rest } = init;
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);

  try {
    const response = await fetch(`${AETHER_API_URL}${path}`, {
      ...rest,
      signal: controller.signal,
      headers: {
        "Content-Type": "application/json",
        ...(TOKEN ? { Authorization: `Bearer ${TOKEN}` } : {}),
        ...(rest.headers ?? {}),
      },
      cache: "no-store",
    });

    const text = await response.text();
    let body: unknown = text;
    try {
      body = text ? JSON.parse(text) : null;
    } catch {
      /* keep raw text */
    }

    if (!response.ok) {
      const detail =
        typeof body === "object" && body !== null && "detail" in body
          ? String((body as { detail: unknown }).detail)
          : `HTTP ${response.status}`;
      throw new AetherHttpError(detail, response.status);
    }

    return body as T;
  } catch (error) {
    if (error instanceof Error && error.name === "AbortError") {
      throw new AetherUnreachableError(
        `Aether did not answer within ${Math.round(timeoutMs / 1000)}s (${AETHER_API_URL}${path})`
      );
    }
    if (error instanceof AetherHttpError || error instanceof AetherUnreachableError) throw error;
    throw new AetherUnreachableError(
      `${error instanceof Error ? error.message : String(error)} (${AETHER_API_URL}${path})`
    );
  } finally {
    clearTimeout(timer);
  }
}

// --------------------------------------------------------------------------- //
// Endpoints
// --------------------------------------------------------------------------- //

export type AetherHealth = {
  status: string;
  service: string;
  version: string;
  components: Record<string, string | number>;
};

export type AetherIndex = {
  name: string;
  version: string;
  environment: string;
  routers: Record<string, string>;
  disabled_routers: Record<string, string>;
};

export type AetherChatReply = {
  content: string;
  session_id: string;
  intent?: string | null;
  provider?: string;
  model?: string;
  tokens_used?: number;
  latency_ms?: number;
};

export function getHealth(): Promise<AetherHealth> {
  return aetherFetch<AetherHealth>("/health", { timeoutMs: 15_000 });
}

export function getIndex(): Promise<AetherIndex> {
  return aetherFetch<AetherIndex>("/api", { timeoutMs: 15_000 });
}

export function askAether(
  message: string,
  sessionId = "chatgpt"
): Promise<AetherChatReply> {
  return aetherFetch<AetherChatReply>("/api/v1/chat/conversation", {
    method: "POST",
    body: JSON.stringify({ message, session_id: sessionId }),
    timeoutMs: 90_000,
  });
}

export type MemoryMessageResult = {
  success: boolean;
  message_id: number;
  session_id: string;
};

export function remember(
  content: string,
  sessionId = "chatgpt",
  role: "user" | "assistant" = "user"
): Promise<MemoryMessageResult> {
  return aetherFetch<MemoryMessageResult>("/api/v1/memory/conversation/message", {
    method: "POST",
    body: JSON.stringify({ session_id: sessionId, role, content, auto_embed: true }),
    timeoutMs: 30_000,
  });
}

export type MemoryContext = {
  success: boolean;
  context: unknown;
};

export function recall(
  query: string,
  sessionId = "chatgpt"
): Promise<MemoryContext> {
  return aetherFetch<MemoryContext>("/api/v1/memory/conversation/rag-context", {
    method: "POST",
    body: JSON.stringify({
      session_id: sessionId,
      query,
      max_recent: 6,
      max_relevant: 4,
    }),
    timeoutMs: 45_000,
  });
}

export type SandboxResult = {
  ok: boolean;
  stage: "validation" | "execution";
  exit_code?: number;
  stdout?: string;
  stderr?: string;
  error?: string;
};

export function runPython(
  code: string,
  timeout = 5
): Promise<SandboxResult> {
  return aetherFetch<SandboxResult>("/api/v1/sandbox/python", {
    method: "POST",
    body: JSON.stringify({ code, timeout }),
    timeoutMs: 20_000,
  });
}
