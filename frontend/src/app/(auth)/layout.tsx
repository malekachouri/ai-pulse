import Link from "next/link";

import { BrandIcon } from "@/lib/nav";

export default function AuthLayout({ children }: { children: React.ReactNode }) {
  return (
    <div className="brand-glow flex min-h-dvh flex-col items-center justify-center px-4 py-10">
      <Link href="/" className="mb-8 flex items-center gap-2.5">
        <span className="flex size-9 items-center justify-center rounded-lg bg-gradient-to-br from-brand-blue to-brand-violet text-white shadow-md shadow-brand-violet/30">
          <BrandIcon className="size-5" />
        </span>
        <span className="text-lg font-semibold tracking-tight">AI Pulse</span>
      </Link>
      <div className="w-full max-w-sm rounded-2xl border bg-card p-6 shadow-xl dark:shadow-black/30 sm:p-8">{children}</div>
    </div>
  );
}
