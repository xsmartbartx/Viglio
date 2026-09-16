import Link from "next/link";
import { Show, UserButton } from "@clerk/nextjs";
import { ScanSubmitForm } from "../components/ScanSubmitForm";
import { Footer } from "../components/Footer";
import { brand } from "../lib/brand";

export default function Home() {
  return (
    <>
      <header className="flex items-center justify-between px-6 py-4 border-b border-black/10 dark:border-white/10">
        <span className="font-semibold">{brand.name}</span>
        <nav className="flex items-center gap-4 text-sm">
          <Show when="signed-out">
            <Link href="/sign-in">Sign in</Link>
          </Show>
          <Show when="signed-in">
            <UserButton />
          </Show>
        </nav>
      </header>
      <main className="flex flex-1 flex-col items-center justify-center gap-6 p-8 text-center">
        <div className="max-w-lg space-y-2">
          <h1 className="text-3xl font-bold">{brand.tagline}</h1>
          <p className="text-black/60 dark:text-white/60">{brand.shortDescription}</p>
        </div>
        <ScanSubmitForm />
      </main>
      <Footer />
    </>
  );
}
