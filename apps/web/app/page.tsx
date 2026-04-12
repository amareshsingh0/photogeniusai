import { redirect } from "next/navigation";
import { getCurrentUser } from "@/lib/auth";
import HomeClient from "@/components/landing/HomeClient";

export default async function Home() {
  // Check if user is logged in
  const user = await getCurrentUser();

  // Redirect authenticated users to dashboard
  if (user) {
    redirect("/dashboard");
  }

  // Show landing page for non-authenticated users
  return <HomeClient />;
}
