import Link from "next/link";
import { notFound } from "next/navigation";
import { auth } from "@clerk/nextjs/server";
import { Show, UserButton } from "@clerk/nextjs";
import { ReportView } from "../../../components/report/ReportView";
import { api, ApiError } from "../../../lib/api";
import { brand } from "../../../lib/brand";

const JWT_TEMPLATE = process.env.NEXT_PUBLIC_CLERK_JWT_TEMPLATE ?? "vigilo-api";

export default async function ReportPage({
  params,
  searchParams,
}: {
  params: Promise<{ scanId: string }>;
  searchParams: Promise<{ print?: string }>;
}) {
  const { scanId } = await params;
  const { print } = await searchParams;
  const printMode = print === "1";

  const { getToken } = await auth();
  const token = await getToken({ template: JWT_TEMPLATE }).catch(() => null);

  let report;
  try {
    report = await api.getScanReport(scanId, token);
  } catch (err) {
    if (err instanceof ApiError && err.status === 404) {
      notFound();
    }
    if (err instanceof ApiError && err.status === 409) {
      return (
        <main className="mx-auto max-w-md px-6 py-16 text-center">
          <p className="text-lg font-medium">Still scanning…</p>
          <p className="mt-2 text-sm text-black/60 dark:text-white/60">
            This report isn&apos;t ready yet. Refresh in a few seconds.
          </p>
        </main>
      );
    }
    throw err;
  }

  const initialShareLinks =
    report.is_owner && token ? await api.listShareLinks(scanId, token).catch(() => []) : [];

  return (
    <>
      {!printMode ? (
        <header className="flex items-center justify-between px-6 py-4 border-b border-black/10 dark:border-white/10">
          <Link href="/" className="font-semibold">
            {brand.name}
          </Link>
          <nav className="flex items-center gap-4 text-sm">
            <Show when="signed-out">
              <Link href="/sign-in">Sign in</Link>
            </Show>
            <Show when="signed-in">
              <UserButton />
            </Show>
          </nav>
        </header>
      ) : null}
      <ReportView report={report} printMode={printMode} initialShareLinks={initialShareLinks} />
    </>
  );
}
