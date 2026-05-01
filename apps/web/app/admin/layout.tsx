import { redirect } from "next/navigation";
import { requireAdmin } from "@/lib/admin-auth";

export const metadata = {
  title: "Admin Panel - Pixium API",
  description: "System administration and control panel",
};

export default async function AdminLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  try {
    // Require admin role
    await requireAdmin();
  } catch (error) {
    // Not admin - redirect to login
    redirect("/login");
  }

  // PURE ADMIN LAYOUT - NO user features, NO dashboard sidebar, NO mixing
  return (
    <div className="min-h-screen bg-[#0a0a0a] text-white">
      {/* Pure admin panel - standalone, no user navigation */}
      {children}
    </div>
  );
}
