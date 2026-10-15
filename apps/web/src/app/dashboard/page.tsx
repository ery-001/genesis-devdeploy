import Link from "next/link";

import { Button } from "@/components/ui/button";

export default function DashboardPage() {
  return (
    <div className="dd-atmosphere flex min-h-full flex-1 flex-col">
      <header className="border-b border-border/70 bg-white/50 backdrop-blur-sm">
        <div className="mx-auto flex w-full max-w-6xl items-center justify-between px-6 py-4 sm:px-10">
          <Link
            href="/"
            className="font-[family-name:var(--font-display)] text-lg font-bold tracking-tight text-ink"
          >
            DevDeploy
          </Link>
          <span className="font-mono text-xs tracking-wide text-muted-foreground">
            control plane · scaffold
          </span>
        </div>
      </header>

      <main className="mx-auto flex w-full max-w-6xl flex-1 flex-col px-6 py-12 sm:px-10">
        <h1 className="font-[family-name:var(--font-display)] text-3xl font-bold tracking-tight text-ink">
          Dashboard
        </h1>
        <p className="mt-3 max-w-xl text-muted-foreground">
          Project list, create flow, and GitHub sign-in land in the next
          Milestone 1 steps. This route is a placeholder shell for the control
          plane UI.
        </p>

        <div className="mt-10 max-w-lg border border-dashed border-border bg-white/40 p-6">
          <p className="font-mono text-xs uppercase tracking-[0.14em] text-muted-foreground">
            Coming next
          </p>
          <ul className="mt-3 space-y-2 text-sm text-foreground/90">
            <li>GitHub OAuth sign-in</li>
            <li>Create and list projects</li>
            <li>Wire dashboard actions to the FastAPI control plane</li>
          </ul>
          <Button
            render={<Link href="/" />}
            variant="outline"
            className="mt-6"
          >
            Back to home
          </Button>
        </div>
      </main>
    </div>
  );
}
