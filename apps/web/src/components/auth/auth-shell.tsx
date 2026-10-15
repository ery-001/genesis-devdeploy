import Link from "next/link";
import type { ReactNode } from "react";

export function AuthShell({
  title,
  subtitle,
  children,
  footer,
}: {
  title: string;
  subtitle: string;
  children: ReactNode;
  footer: ReactNode;
}) {
  return (
    <div className="dd-atmosphere relative flex min-h-full flex-1 flex-col overflow-hidden">
      <div aria-hidden className="dd-topology pointer-events-none absolute inset-0" />
      <div
        aria-hidden
        className="dd-signal-glow pointer-events-none absolute -left-20 top-24 h-[22rem] w-[22rem] rounded-full bg-[radial-gradient(circle,rgba(15,122,107,0.18),transparent_68%)]"
      />

      <header className="relative z-10 mx-auto flex w-full max-w-6xl items-center justify-between px-6 py-5 sm:px-10">
        <Link
          href="/"
          className="font-[family-name:var(--font-display)] text-lg font-bold tracking-tight text-ink"
        >
          DevDeploy
        </Link>
      </header>

      <main className="relative z-10 mx-auto flex w-full max-w-lg flex-1 flex-col justify-center px-6 pb-16 pt-4 sm:px-10">
        <div className="dd-rise">
          <p className="font-[family-name:var(--font-display)] text-4xl font-extrabold tracking-tight text-ink sm:text-5xl">
            DevDeploy
          </p>
          <h1 className="mt-4 font-[family-name:var(--font-display)] text-2xl font-semibold tracking-tight text-ink">
            {title}
          </h1>
          <p className="mt-2 text-sm leading-relaxed text-muted-foreground sm:text-base">
            {subtitle}
          </p>
        </div>

        <div className="dd-rise dd-rise-delay-1 mt-8 space-y-6">{children}</div>
        <p className="dd-rise dd-rise-delay-2 mt-8 text-sm text-muted-foreground">
          {footer}
        </p>
      </main>
    </div>
  );
}
