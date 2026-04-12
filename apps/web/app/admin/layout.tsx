import { redirect } from "next/navigation";
import { requireAdmin } from "@/lib/admin-auth";

export const metadata = {
  title: "Admin Panel - PhotoGenius API",
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
    // Not admin - block access completely
    redirect("/");
  }

  // PURE ADMIN LAYOUT - NO user features, NO dashboard sidebar
  return (
    <html lang="en" className="dark">
      <body className="bg-[#0a0a0a] text-white min-h-screen antialiased">
        {/* Pure admin panel - no user navigation, no mixing */}
        {children}
      </body>
    </html>
  );
}
