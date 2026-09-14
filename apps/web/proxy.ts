// Next.js 16 renamed `middleware.ts` to `proxy.ts` (the exported function
// name changed too, but Clerk's `clerkMiddleware()` just returns a plain
// (request) => Response handler regardless of what it's re-exported as).
import { clerkMiddleware } from "@clerk/nextjs/server";

export default clerkMiddleware();

export const config = {
  matcher: ["/((?!_next/static|_next/image|favicon.ico).*)"],
};
