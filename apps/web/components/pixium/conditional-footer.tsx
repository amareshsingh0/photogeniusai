"use client";

import { usePathname } from "next/navigation";
import { SiteFooter } from "./site-nav";

// Routes where the global footer would compete with sticky / full-bleed UI
// (workspaces with their own bottom bars). Add new ones here.
const HIDE_FOOTER_PREFIXES = [
  "/generate",
  "/editor",
  "/video",
];

export function ConditionalFooter() {
  const path = usePathname() ?? "/";
  const hidden = HIDE_FOOTER_PREFIXES.some((p) => path === p || path.startsWith(p + "/"));
  if (hidden) return null;
  return <SiteFooter />;
}
