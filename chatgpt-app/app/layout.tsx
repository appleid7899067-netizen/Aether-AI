import type { Metadata } from "next";
import "./globals.css";
import { baseURL } from "@/lib/base-url";

export const metadata: Metadata = {
  title: "Aether AI - ChatGPT app",
  description: "Aether AI tools, memory and sandbox, available inside ChatGPT.",
};

/**
 * Patches the browser APIs ChatGPT needs when the app runs inside its iframe
 * (asset base, history calls, external links) - same bootstrap approach as the
 * official Apps SDK starter, but with our own base-url resolution.
 */
function ChatGptBootstrap({ baseUrl }: { baseUrl: string }) {
  const script = `(${function bootstrap() {
    const baseUrl = (window as unknown as { innerBaseUrl: string }).innerBaseUrl;
    const htmlElement = document.documentElement;
    const observer = new MutationObserver((mutations) => {
      mutations.forEach((mutation) => {
        if (mutation.type === "attributes" && mutation.target === htmlElement) {
          const name = mutation.attributeName;
          if (name && name !== "suppresshydrationwarning") htmlElement.removeAttribute(name);
        }
      });
    });
    observer.observe(htmlElement, { attributes: true, attributeOldValue: true });

    const strip = (url?: string | URL | null) => {
      const u = new URL(url ?? "", window.location.href);
      return u.pathname + u.search + u.hash;
    };
    const replaceState = history.replaceState;
    history.replaceState = (s, unused, url) => replaceState.call(history, unused, strip(url));
    const pushState = history.pushState;
    history.pushState = (s, unused, url) => pushState.call(history, unused, strip(url));

    const appOrigin = new URL(baseUrl).origin;
    window.addEventListener(
      "click",
      (event) => {
        const anchor = (event?.target as HTMLElement)?.closest("a");
        if (!anchor || !anchor.href) return;
        const url = new URL(anchor.href, window.location.href);
        if (url.origin !== window.location.origin && url.origin !== appOrigin) {
          const parent = window as unknown as {
            openai?: { openExternal?: (o: { href: string }) => void };
          };
          if (parent.openai?.openExternal) {
            parent.openai.openExternal({ href: anchor.href });
            event.preventDefault();
          }
        }
      },
      true
    );
  }.toString()})()`;

  return (
    <>
      <base href={baseUrl} />
      <script>{`window.innerBaseUrl = ${JSON.stringify(baseUrl)}`}</script>
      <script>{`window.__isChatGptApp = typeof window.openai !== "undefined";`}</script>
      <script>{script}</script>
    </>
  );
}

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="th" suppressHydrationWarning>
      <head>
        <ChatGptBootstrap baseUrl={baseURL} />
      </head>
      <body>{children}</body>
    </html>
  );
}
