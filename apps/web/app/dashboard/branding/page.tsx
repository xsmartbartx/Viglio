import Link from "next/link";
import { redirect } from "next/navigation";
import { auth } from "@clerk/nextjs/server";
import { api } from "../../../lib/api";
import { BrandingForm } from "../../../components/dashboard/BrandingForm";

const JWT_TEMPLATE = process.env.NEXT_PUBLIC_CLERK_JWT_TEMPLATE ?? "vigilo-api";

export default async function DashboardBrandingPage() {
  const { getToken } = await auth();
  const token = await getToken({ template: JWT_TEMPLATE });
  if (!token) {
    redirect("/sign-in");
  }

  const account = await api.getMe(token);

  if (!account.entitlements.white_label_allowed) {
    return (
      <div className="space-y-6">
        <h1 className="text-2xl font-bold">Branding</h1>
        <div className="rounded-lg border border-black/10 dark:border-white/20 p-4 text-sm">
          <p className="font-semibold">White-label reports</p>
          <p className="mt-1 text-black/60 dark:text-white/60">
            Custom logo, color, and footer text on reports aren&apos;t included in the current
            plan.
          </p>
          <Link
            href="/dashboard/billing"
            className="mt-2 inline-block text-xs underline underline-offset-2"
          >
            View plans
          </Link>
        </div>
      </div>
    );
  }

  const profile = await api.getBrandingProfile(token);

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold">Branding</h1>
      <BrandingForm initialProfile={profile} />
    </div>
  );
}
