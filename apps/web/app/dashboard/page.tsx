import Link from "next/link";
import { redirect } from "next/navigation";
import { auth } from "@clerk/nextjs/server";
import { api } from "../../lib/api";

const JWT_TEMPLATE = process.env.NEXT_PUBLIC_CLERK_JWT_TEMPLATE ?? "vigilo-api";

export default async function DashboardOverviewPage() {
  const { getToken } = await auth();
  const token = await getToken({ template: JWT_TEMPLATE });
  if (!token) {
    redirect("/sign-in");
  }

  const [account, targets] = await Promise.all([api.getMe(token), api.listTargets(token)]);

  return (
    <div className="space-y-6">
      <div>
        <p className="text-sm text-black/60 dark:text-white/60">{account.email}</p>
        <h1 className="text-2xl font-bold mt-1">Dashboard</h1>
      </div>

      <div className="rounded-lg border border-black/10 dark:border-white/20 p-4 text-sm space-y-1">
        <p className="font-semibold capitalize">{account.entitlements.plan_id} plan</p>
        <p className="text-black/60 dark:text-white/60">
          {targets.length} target{targets.length === 1 ? "" : "s"} tracked
        </p>
        <Link
          href="/dashboard/billing"
          className="inline-block mt-1 text-xs underline underline-offset-2"
        >
          Manage plan
        </Link>
      </div>

      <div className="flex gap-4 text-sm">
        <Link
          href="/dashboard/targets"
          className="rounded-md border border-black/10 dark:border-white/20 px-3 py-1.5 font-medium"
        >
          View targets
        </Link>
        <Link
          href="/dashboard/api-keys"
          className="rounded-md border border-black/10 dark:border-white/20 px-3 py-1.5 font-medium"
        >
          API keys
        </Link>
      </div>
    </div>
  );
}
