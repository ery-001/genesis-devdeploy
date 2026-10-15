"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import type { ReactNode } from "react";

import { Button } from "@/components/ui/button";
import { logout, type AuthUser } from "@/lib/api";

export function AppShell({
  user,
  children,
}: {
  user: AuthUser;
  children: ReactNode;
}) {
  const router = useRouter();

  async function onSignOut() {
    try {
      await logout();
      router.push("/login");
      router.refresh();
    } catch {
      router.push("/login");
    }
  }

  return (
    <div className="dd-atmosphere flex min-h-full flex-1 flex-col">
      <header className="border-b border-border/70 bg-white/50 backdrop-blur-sm">
        <div className="mx-auto flex w-full max-w-6xl items-center justify-between gap-4 px-6 py-4 sm:px-10">
          <div className="flex items-center gap-6">
            <Link
              href="/"
              className="font-[family-name:var(--font-display)] text-lg font-bold tracking-tight text-ink"
            >
              DevDeploy
            </Link>
            <nav className="hidden items-center gap-4 text-sm sm:flex">
              <Link
                href="/dashboard"
                className="text-muted-foreground transition-colors hover:text-ink"
              >
                Dashboard
              </Link>
              <Link
                href="/projects"
                className="text-muted-foreground transition-colors hover:text-ink"
              >
                Projects
              </Link>
            </nav>
          </div>
          <div className="flex items-center gap-3">
            <div className="text-right">
              <p className="text-sm font-medium text-ink">
                {user.display_name || user.email || user.phone || "Signed in"}
              </p>
              <p className="font-mono text-[11px] text-muted-foreground">
                {(user.providers.length ? user.providers : ["session"]).join(" · ")}
              </p>
            </div>
            <Button variant="outline" onClick={onSignOut} className="h-9">
              Sign out
            </Button>
          </div>
        </div>
      </header>
      <main className="mx-auto flex w-full max-w-6xl flex-1 flex-col px-6 py-10 sm:px-10">
        {children}
      </main>
    </div>
  );
}
