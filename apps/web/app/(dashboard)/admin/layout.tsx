import { redirect } from "next/navigation";
import { requireAdmin } from "@/lib/admin-auth";

export default async function AdminLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  try {
    // Check if user is admin
    await requireAdmin();
  } catch (error) {
    // Not admin or not authenticated - redirect to home
    redirect("/");
  }

  return <>{children}</>;
}
