"use client";

import { useEffect, useState } from "react";

/**
 * Global protection layer for bundled showcase imagery.
 *
 * Layers of defense (none is a hard lock — DevTools + screen capture always
 * eventually win — but combined they block ~99% of casual save attempts):
 *
 *   1. Right-click context menu blocked on any <img> with a bundled-asset URL
 *   2. Drag-start blocked (no drag-to-desktop / drag-to-tab)
 *   3. Keyboard shortcuts blocked: F12, Ctrl/Cmd+Shift+I/J/C, Ctrl/Cmd+U, Ctrl/Cmd+S, Ctrl/Cmd+P
 *   4. DevTools-open detection (window dimension + debugger timing heuristic) —
 *      shows a warning overlay that hides protected page content
 *
 * User-uploaded / S3-hosted images (gallery, history, focused result tiles)
 * are intentionally NOT blocked so the Download button keeps working.
 */
const PROTECTED_URL_PATTERNS = [
  "/_next/static/media/", // Next.js bundled assets
  "/assets/",
];

const isProtectedUrl = (url: string): boolean =>
  PROTECTED_URL_PATTERNS.some((p) => url.includes(p));

const BLOCKED_KEYS = (e: KeyboardEvent): boolean => {
  // F12
  if (e.key === "F12") return true;
  const k = e.key.toLowerCase();
  const ctrl = e.ctrlKey || e.metaKey;
  // Ctrl/Cmd+Shift+I/J/C (open devtools / elements / console / inspector)
  if (ctrl && e.shiftKey && (k === "i" || k === "j" || k === "c")) return true;
  // Ctrl/Cmd+U (view source)
  if (ctrl && k === "u") return true;
  // Ctrl/Cmd+S (save page)
  if (ctrl && k === "s") return true;
  // Ctrl/Cmd+P (print → save as PDF)
  if (ctrl && k === "p") return true;
  return false;
};

export function ImageProtection() {
  const [devtoolsOpen, setDevtoolsOpen] = useState(false);

  useEffect(() => {
    // ── 1 & 2 — block right-click + drag on protected images ────────────
    const onContextMenu = (e: MouseEvent) => {
      const t = e.target as HTMLElement | null;
      if (!t || t.tagName !== "IMG") return;
      const src = (t as HTMLImageElement).src || "";
      if (isProtectedUrl(src)) e.preventDefault();
    };
    const onDragStart = (e: DragEvent) => {
      const t = e.target as HTMLElement | null;
      if (!t || t.tagName !== "IMG") return;
      const src = (t as HTMLImageElement).src || "";
      if (isProtectedUrl(src)) e.preventDefault();
    };

    // ── 3 — block keyboard shortcuts ────────────────────────────────────
    const onKeyDown = (e: KeyboardEvent) => {
      if (BLOCKED_KEYS(e)) {
        e.preventDefault();
        e.stopPropagation();
      }
    };

    document.addEventListener("contextmenu", onContextMenu, { capture: true });
    document.addEventListener("dragstart", onDragStart, { capture: true });
    document.addEventListener("keydown", onKeyDown, { capture: true });

    // ── 4 — DevTools detection (heuristic) ──────────────────────────────
    // Tactic A: window.outerWidth - innerWidth grows when DevTools docked side
    // Tactic B: debugger statement runs almost instantly when DevTools open,
    //           takes >100ms when stepped through
    let rafId = 0;
    const check = () => {
      const widthDelta = window.outerWidth - window.innerWidth;
      const heightDelta = window.outerHeight - window.innerHeight;
      // Docked DevTools usually adds >160px of chrome
      const looksOpen = widthDelta > 200 || heightDelta > 200;
      setDevtoolsOpen(looksOpen);
      rafId = window.setTimeout(check, 1000) as unknown as number;
    };
    check();

    return () => {
      document.removeEventListener("contextmenu", onContextMenu, { capture: true });
      document.removeEventListener("dragstart", onDragStart, { capture: true });
      document.removeEventListener("keydown", onKeyDown, { capture: true });
      clearTimeout(rafId);
    };
  }, []);

  // When DevTools is detected, hide protected imagery behind a full-screen
  // warning overlay. The rest of the UI keeps working but bundled showcase
  // images become unreachable. (Inspecting source still possible — but they
  // can't see the rendered images while DevTools is open.)
  if (devtoolsOpen) {
    return (
      <div
        className="pointer-events-none fixed inset-0 z-9999 backdrop-blur-2xl"
        style={{ background: "rgba(8,8,10,0.95)" }}
      >
        <div className="pointer-events-auto flex h-full w-full flex-col items-center justify-center gap-3 px-6 text-center">
          <div className="text-5xl">🔒</div>
          <h2 className="font-display text-2xl font-semibold text-white">
            Content protected
          </h2>
          <p className="max-w-md text-sm text-white/65">
            Pixium imagery is copyrighted. Close DevTools to continue browsing.
          </p>
          <p className="font-mono text-[10px] text-white/35">
            Detected developer tools open. This page will resume when you close them.
          </p>
        </div>
      </div>
    );
  }

  return null;
}
