import Link from "next/link";
import { notFound, redirect } from "next/navigation";
import { auth } from "@clerk/nextjs/server";
import { UserButton } from "@clerk/nextjs";
import { AlertTimeline } from "../../../../components/monitoring/AlertTimeline";
import { BadgeEmbed } from "../../../../components/monitoring/BadgeEmbed";
import { MonitorPanel } from "../../../../components/monitoring/MonitorPanel";
import { ScoreHistoryChart } from "../../../../components/monitoring/ScoreHistoryChart";
import { api, ApiError } from "../../../../lib/api";
import { brand } from "../../../../lib/brand";

const JWT_TEMPLATE = process.env.NEXT_PUBLIC_CLERK_JWT_TEMPLATE ?? "vigilo-api";

export default async function TargetMonitoringPage({
  params,
}: {
  params: Promise<{ targetId: string }>;
}) {
  const { targetId } = await params;

  const { userId, getToken } = await auth();
  if (!userId) {
    redirect("/sign-in");
  }

  const token = await getToken({ template: JWT_TEMPLATE });
  if (!token) {
    redirect("/sign-in");
  }

  let target;
  try {
    target = await api.getTarget(targetId, token);
  } catch (err) {
    if (err instanceof ApiError && err.status === 404) {
      notFound();
    }
    throw err;
  }

  const [account, monitor, scores, alerts] = await Promise.all([
    api.getMe(token),
    api.getTargetMonitor(targetId, token).catch((err) => {
      if (err instanceof ApiError && err.status === 404) return null;
      throw err;
    }),
    api.getTargetScoreHistory(targetId, token),
    api.getTargetAlerts(targetId, token),
  ]);

  return (
    <>
      <header className="flex items-center justify-between px-6 py-4 border-b border-black/10 dark:border-white/10">
        <Link href="/" className="font-semibold">
          {brand.name}
        </Link>
        <UserButton />
      </header>
      <main className="mx-auto max-w-2xl px-6 py-10 space-y-6">
        <div>
          <p className="text-sm text-black/60 dark:text-white/60 break-all">{target.origin}</p>
          <h1 className="text-2xl font-bold mt-1">Monitoring</h1>
        </div>

        <MonitorPanel
          targetId={targetId}
          initialMonitor={monitor}
          entitlements={account.entitlements}
        />
        <ScoreHistoryChart scores={scores} />
        <AlertTimeline alerts={alerts} />
        <BadgeEmbed targetId={targetId} />
      </main>
    </>
  );
}
