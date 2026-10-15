import Link from "next/link";
import { ArrowRight } from "lucide-react";

import { Button } from "@/components/ui/button";

export default function Home() {
  return (
    <div className="dd-atmosphere relative flex min-h-full flex-1 flex-col overflow-hidden">
      <div
        aria-hidden
        className="dd-topology pointer-events-none absolute inset-0"
      />
      <div
        aria-hidden
        className="dd-signal-glow pointer-events-none absolute -right-24 top-10 h-[28rem] w-[28rem] rounded-full bg-[radial-gradient(circle,rgba(15,122,107,0.22),transparent_68%)]"
      />

      <header className="relative z-10 mx-auto flex w-full max-w-6xl items-center justify-between px-6 py-5 sm:px-10">
        <p className="font-[family-name:var(--font-display)] text-lg font-bold tracking-tight text-ink">
          DevDeploy
        </p>
        <Link
          href="/dashboard"
          className="text-sm font-medium text-muted-foreground transition-colors hover:text-ink"
        >
          Dashboard
        </Link>
      </header>

      <main className="relative z-10 mx-auto flex w-full max-w-6xl flex-1 flex-col justify-center px-6 pb-20 pt-6 sm:px-10 sm:pb-28">
        <div className="max-w-3xl">
          <p className="dd-rise font-[family-name:var(--font-display)] text-[clamp(3.25rem,10vw,6.5rem)] font-extrabold leading-[0.92] tracking-tight text-ink">
            DevDeploy
          </p>
          <h1 className="dd-rise dd-rise-delay-1 mt-6 max-w-xl font-[family-name:var(--font-display)] text-2xl font-semibold tracking-tight text-ink sm:text-3xl">
            Connect a repo. Deploy. Get a URL.
          </h1>
          <p className="dd-rise dd-rise-delay-2 mt-4 max-w-lg text-base leading-relaxed text-muted-foreground sm:text-lg">
            An internal platform that turns GitHub into a running app while
            keeping builds, rolls, and releases visible for learning DevOps.
          </p>
          <div className="dd-rise dd-rise-delay-3 mt-8 flex flex-wrap items-center gap-3">
            <Button
              render={<Link href="/dashboard" />}
              size="lg"
              className="h-11 gap-2 rounded-md bg-signal px-5 text-signal-foreground hover:bg-signal/90"
            >
              Open dashboard
              <ArrowRight data-icon="inline-end" className="size-4" />
            </Button>
            <Button
              render={<Link href="/dashboard" />}
              variant="outline"
              size="lg"
              className="h-11 rounded-md border-border/80 bg-white/40 px-5 backdrop-blur-sm"
            >
              View projects
            </Button>
          </div>
        </div>
      </main>
    </div>
  );
}
