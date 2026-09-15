import Link from "next/link";
import { ReportView } from "../../../components/report/ReportView";
import { api, ApiError } from "../../../lib/api";
import { brand } from "../../../lib/brand";

export default async function SharePage({ params }: { params: Promise<{ token: string }> }) {
  const { token } = await params;

  let report;
  try {
    report = await api.getShareReport(token);
  } catch (err) {
    if (err instanceof ApiError && (err.status === 404 || err.status === 410)) {
      return (
        <main className="mx-auto max-w-md px-6 py-16 text-center">
          <p className="text-lg font-medium">This link isn&apos;t available</p>
          <p className="mt-2 text-sm text-black/60 dark:text-white/60">
            {err.status === 410
              ? "This share link has expired or been revoked."
              : "This share link doesn't exist."}
          </p>
        </main>
      );
    }
    throw err;
  }

  return (
    <>
      <header className="flex items-center px-6 py-4 border-b border-black/10 dark:border-white/10">
        <Link href="/" className="font-semibold">
          {brand.name}
        </Link>
      </header>
      <ReportView report={report} />
    </>
  );
}
