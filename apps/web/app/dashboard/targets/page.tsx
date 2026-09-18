import { redirect } from "next/navigation";
import { auth } from "@clerk/nextjs/server";
import { api } from "../../../lib/api";
import { TargetsManager } from "../../../components/dashboard/TargetsManager";

const JWT_TEMPLATE = process.env.NEXT_PUBLIC_CLERK_JWT_TEMPLATE ?? "vigilo-api";

export default async function DashboardTargetsPage() {
  const { getToken } = await auth();
  const token = await getToken({ template: JWT_TEMPLATE });
  if (!token) {
    redirect("/sign-in");
  }

  const targets = await api.listTargets(token);

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold">Targets</h1>
      <TargetsManager initialTargets={targets} />
    </div>
  );
}
