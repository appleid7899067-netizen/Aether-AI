/**
 * Public base URL of this app.
 *
 * The official starter reads Vercel-only variables, which yields
 * "https://undefined" on Render / Fly / any other host. This version detects
 * Vercel, then a generic NEXT_PUBLIC_BASE_URL, then RENDER_EXTERNAL_URL, and
 * finally falls back to localhost with the actual PORT.
 */
function resolveBaseUrl(): string {
  const explicit = process.env.NEXT_PUBLIC_BASE_URL?.trim();
  if (explicit) return explicit.replace(/\/+$/, "");

  if (process.env.VERCEL_ENV === "production" && process.env.VERCEL_PROJECT_PRODUCTION_URL) {
    return `https://${process.env.VERCEL_PROJECT_PRODUCTION_URL}`;
  }
  const vercelUrl =
    process.env.VERCEL_BRANCH_URL || process.env.VERCEL_URL || undefined;
  if (vercelUrl) return `https://${vercelUrl}`;

  // Render exposes these at build time as well as runtime.
  if (process.env.RENDER_EXTERNAL_URL) {
    return process.env.RENDER_EXTERNAL_URL.replace(/\/+$/, "");
  }
  const renderHost = process.env.RENDER_EXTERNAL_HOSTNAME;
  if (renderHost) return `https://${renderHost}`;
  if (process.env.RENDER_SERVICE_NAME) {
    return `https://${process.env.RENDER_SERVICE_NAME}.onrender.com`;
  }

  const port = process.env.PORT || "3000";
  return `http://localhost:${port}`;
}

export const baseURL = resolveBaseUrl();

/**
 * The server's own loopback address.
 *
 * The MCP handler needs the rendered widget HTML. Fetching it through the
 * *public* URL means the container has to reach its own public hostname, which
 * adds a needless round trip through the hosting proxy (and hangs if the
 * hostname is not reachable from inside). Loopback always works.
 */
export const internalBaseURL = `http://127.0.0.1:${process.env.PORT || "3000"}`;
