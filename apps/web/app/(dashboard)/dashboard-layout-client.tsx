"use client";

/**
 * Dashboard layout pass-through.
 * The floating SiteNav + MobileDock + SiteFooter live in the root layout
 * (apps/web/app/layout.tsx) and are shared across public + dashboard pages.
 * The old fixed sidebar has been removed in favor of the Lumen design.
 */

export default function DashboardLayoutClient({
  children,
}: {
  children: React.ReactNode;
}) {
  return <>{children}</>;
}
