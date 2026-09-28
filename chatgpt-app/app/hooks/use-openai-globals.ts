"use client";

/**
 * Minimal bindings to the ChatGPT Apps SDK runtime.
 *
 * The widget runs inside an iframe hosted by ChatGPT, which injects a
 * `window.openai` object (toolOutput, displayMode, maxHeight, ...) and fires a
 * `openai:set_globals` event whenever those values change. This is a compact
 * re-implementation of the hooks shipped with the OpenAI Apps SDK examples
 * (https://github.com/openai/openai-apps-sdk-examples), kept dependency-free.
 */
import { useSyncExternalStore } from "react";

type OpenAIGlobals = {
  toolOutput?: Record<string, unknown> | null;
  toolInput?: Record<string, unknown> | null;
  displayMode?: "pip" | "inline" | "fullscreen";
  maxHeight?: number;
  theme?: "light" | "dark";
  locale?: string;
  widgetState?: Record<string, unknown> | null;
};

type SetGlobalsDetail = { globals: OpenAIGlobals };
type SetGlobalsEvent = CustomEvent<SetGlobalsDetail>;

const SET_GLOBALS_EVENT = "openai:set_globals";

declare global {
  interface Window {
    openai?: OpenAIGlobals & {
      setWidgetState?: (state: unknown) => void;
      openExternal?: (options: { href: string }) => void;
      requestDisplayMode?: (options: { mode: string }) => void;
    };
    __isChatGptApp?: boolean;
  }
}

export function useOpenAIGlobal<K extends keyof OpenAIGlobals>(
  key: K
): OpenAIGlobals[K] | null {
  return useSyncExternalStore(
    (onChange) => {
      if (typeof window === "undefined") return () => {};
      const listener = (event: Event) => {
        const detail = (event as SetGlobalsEvent).detail;
        if (detail?.globals && key in detail.globals) onChange();
      };
      window.addEventListener(SET_GLOBALS_EVENT, listener, { passive: true });
      return () => window.removeEventListener(SET_GLOBALS_EVENT, listener);
    },
    () => (typeof window !== "undefined" ? window.openai?.[key] ?? null : null),
    () => null
  );
}

/** Tool output (structuredContent) delivered by ChatGPT after a tool call. */
export function useWidgetProps<T extends Record<string, unknown>>(): T | null {
  return (useOpenAIGlobal("toolOutput") as T | null) ?? null;
}

export function useDisplayMode() {
  return useOpenAIGlobal("displayMode");
}

export function useMaxHeight() {
  return useOpenAIGlobal("maxHeight");
}

export function useTheme() {
  return useOpenAIGlobal("theme");
}

export function useIsChatGptApp(): boolean {
  return useSyncExternalStore(
    () => () => {},
    () => (typeof window === "undefined" ? false : Boolean(window.__isChatGptApp)),
    () => false
  );
}

export function requestFullscreen() {
  try {
    window.openai?.requestDisplayMode?.({ mode: "fullscreen" });
  } catch {
    /* not running inside ChatGPT */
  }
}
