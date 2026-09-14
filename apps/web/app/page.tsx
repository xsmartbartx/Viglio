import Link from "next/link";
import { SignedIn, SignedOut, UserButton } from "@clerk/nextjs";
import { ScanSubmitForm } from "../components/ScanSubmitForm";
import { brand } from "../lib/brand";

export default function Home() {
  return (
    <>
      <header className="flex items-center justify-between px-6 py-4 border-b border-black/10 dark:border-white/10">
        <span className="font-semibold">{brand.name}</span>
        <nav className="flex items-center gap-4 text-sm">
          <SignedOut>
            <Link href="/sign-in">Sign in</Link>
          </SignedOut>
          <SignedIn>
            <UserButton />
          </SignedIn>
        </nav>
      </header>
      <main className="flex flex-1 flex-col items-center justify-center gap-6 p-8 text-center">
        <div className="max-w-lg space-y-2">
          <h1 className="text-3xl font-bold">{brand.tagline}</h1>
          <p className="text-black/60 dark:text-white/60">{brand.shortDescription}</p>
        </div>
        <ScanSubmitForm />
      </main>
    </>
  );
}
