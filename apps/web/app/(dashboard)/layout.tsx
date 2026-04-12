import { redirect } from "next/navigation";
import { getCurrentUser } from "@/lib/auth";
import DashboardLayoutClient from "./dashboard-layout-client";

export default async function DashboardLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  // Require authentication for all dashboard routes
  const user = await getCurrentUser();

  if (!user) {
    redirect("/login");
  }

  return <DashboardLayoutClient>{children}</DashboardLayoutClient>;
}
