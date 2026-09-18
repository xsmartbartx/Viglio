import { redirect } from "next/navigation";
import { auth } from "@clerk/nextjs/server";
import { api } from "../../../lib/api";
import type { PlanResponse } from "../../../lib/types";
import { UpgradeButton } from "../../../components/dashboard/UpgradeButton";

const JWT_TEMPLATE = process.env.NEXT_PUBLIC_CLERK_JWT_TEMPLATE ?? "vigilo-api";

const PLAN_ORDER = ["free", "builder", "studio", "business"];

function formatLimit(value: number | null): string {
  return value === null ? "Unlimited" : String(value);
}

function formatBool(value: boolean): string {
  return value ? "Included" : "—";
}

const ROWS: { label: string; render: (plan: PlanResponse) => string }[] = [
  { label: "Targets", render: (p) => formatLimit(p.targets_limit) },
  { label: "Scans / month", render: (p) => formatLimit(p.scans_per_month_limit) },
  { label: "Active-tier scanning", render: (p) => formatBool(p.active_tier_allowed) },
  { label: "Share links", render: (p) => formatBool(p.share_links_allowed) },
  { label: "Monitoring", render: (p) => p.monitoring_frequency ?? "—" },
  { label: "Monitors", render: (p) => formatLimit(p.monitors_limit) },
  { label: "API keys", render: (p) => formatLimit(p.api_keys_limit) },
  {
    label: "API rate limit",
    render: (p) => (p.api_rate_limit_per_minute === null ? "—" : `${p.api_rate_limit_per_minute}/min`),
  },
  { label: "White-label reports", render: (p) => formatBool(p.white_label_allowed) },
];

export default async function DashboardBillingPage() {
  const { getToken } = await auth();
  const token = await getToken({ template: JWT_TEMPLATE });
  if (!token) {
    redirect("/sign-in");
  }

  const [account, plans] = await Promise.all([api.getMe(token), api.listPlans()]);
  const currentPlanId = account.entitlements.plan_id;
  const sortedPlans = PLAN_ORDER.map((id) => plans.find((plan) => plan.plan_id === id)).filter(
    (plan): plan is PlanResponse => plan !== undefined,
  );

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold">Billing</h1>

      <div className="overflow-x-auto">
        <table className="w-full text-sm border-collapse">
          <thead>
            <tr className="border-b border-black/10 dark:border-white/20">
              <th className="text-left py-2 pr-4 font-medium text-black/60 dark:text-white/60">
                Plan
              </th>
              {sortedPlans.map((plan) => (
                <th key={plan.plan_id} className="text-left py-2 px-4 font-semibold capitalize">
                  {plan.plan_id}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {ROWS.map((row) => (
              <tr key={row.label} className="border-b border-black/10 dark:border-white/10">
                <td className="py-2 pr-4 text-black/60 dark:text-white/60">{row.label}</td>
                {sortedPlans.map((plan) => (
                  <td key={plan.plan_id} className="py-2 px-4">
                    {row.render(plan)}
                  </td>
                ))}
              </tr>
            ))}
            <tr>
              <td className="py-3 pr-4" />
              {sortedPlans.map((plan) => (
                <td key={plan.plan_id} className="py-3 px-4">
                  {plan.plan_id === currentPlanId ? (
                    <span className="text-xs text-black/50 dark:text-white/50">Current plan</span>
                  ) : plan.plan_id === "free" ? null : (
                    <UpgradeButton planId={plan.plan_id} />
                  )}
                </td>
              ))}
            </tr>
          </tbody>
        </table>
      </div>

      <p className="text-xs text-black/40 dark:text-white/40 max-w-prose">
        Prices are shown on the checkout page after clicking Upgrade.
      </p>
    </div>
  );
}
