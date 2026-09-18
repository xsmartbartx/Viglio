import { redirect } from "next/navigation";
import { auth } from "@clerk/nextjs/server";
import { Header } from "../../components/Header";
import { DashboardNav } from "../../components/dashboard/DashboardNav";

export default async function DashboardLayout({ children }: LayoutProps<"/dashboard">) {
  const { userId } = await auth();
  if (!userId) {
    redirect("/sign-in");
  }

  return (
    <>
      <Header nav={<DashboardNav />} />
      <main className="mx-auto max-w-2xl px-6 py-10 space-y-6">{children}</main>
    </>
  );
}
