import type { ReactNode } from "react";
import Link from "next/link";
import { Show, UserButton } from "@clerk/nextjs";
import { brand } from "../lib/brand";

export function Header({ nav }: { nav?: ReactNode }) {
  return (
    <header className="flex items-center justify-between px-6 py-4 border-b border-black/10 dark:border-white/10">
      <Link href="/" className="font-semibold">
        {brand.name}
      </Link>
      <nav className="flex items-center gap-4 text-sm">
        {nav}
        <Show when="signed-out">
          <Link href="/sign-in">Sign in</Link>
        </Show>
        <Show when="signed-in">
          <UserButton />
        </Show>
      </nav>
    </header>
  );
}
