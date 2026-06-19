import { redirect } from "next/navigation";

/**
 * Root route — redirect straight to the dashboard.
 * NextAuth's middleware will bounce unauthenticated users to /login.
 */
export default function RootPage() {
  redirect("/dashboard");
}
