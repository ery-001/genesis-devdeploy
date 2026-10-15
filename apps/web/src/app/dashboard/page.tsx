"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import { Button } from "@/components/ui/button";
import { fetchMe, logout, type AuthUser } from "@/lib/api";

export default function DashboardPage() {
  const router = useRouter();
  const [user, setUser] = useState<AuthUser | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    fetchMe()
      .then((me) => {
        if (!cancelled) {
          setUser(me);
          setLoading(false);
        }
      })
      .catch(() => {
        if (!cancelled) {
          router.replace("/login?next=/dashboard");
        }
      });
    return () => {
      cancelled = true;
    };
  }, [router]);

  async function onSignOut() {
    setError(null);
    try {
      await logout();
      router.push("/login");
      router.refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Sign out failed");
    }
  }

  if (loading || !user) {
    return (
      <div className="dd-atmosphere flex min-h-full flex-1 items-center justify-center">
        <p className="text-sm text-muted-foreground">Checking session…</p>
      </div>
    );
  }

  return (
    <div className="dd-atmosphere flex min-h-full flex-1 flex-col">
      <header className="border-b border-border/70 bg-white/50 backdrop-blur-sm">
        <div className="mx-auto flex w-full max-w-6xl items-center justify-between gap-4 px-6 py-4 sm:px-10">
          <Link
            href="/"
            className="font-[family-name:var(--font-display)] text-lg font-bold tracking-tight text-ink"
          >
            DevDeploy
          </Link>
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

      <main className="mx-auto flex w-full max-w-6xl flex-1 flex-col px-6 py-12 sm:px-10">
        <h1 className="font-[family-name:var(--font-display)] text-3xl font-bold tracking-tight text-ink">
          Dashboard
        </h1>
        <p className="mt-3 max-w-xl text-muted-foreground">
          You&apos;re signed in. Project create/list and GitHub App repository
          install come next — user sign-in is intentionally separate from repo
          access.
        </p>

        {error ? (
          <p className="mt-4 text-sm text-destructive">{error}</p>
        ) : null}

        <div className="mt-10 max-w-lg space-y-4 border border-dashed border-border bg-white/40 p-6">
          <p className="font-mono text-xs uppercase tracking-[0.14em] text-muted-foreground">
            Session
          </p>
          <dl className="space-y-2 text-sm">
            <div className="flex justify-between gap-4">
              <dt className="text-muted-foreground">User ID</dt>
              <dd className="font-mono text-xs text-ink">{user.id}</dd>
            </div>
            <div className="flex justify-between gap-4">
              <dt className="text-muted-foreground">Email</dt>
              <dd className="text-ink">{user.email ?? "—"}</dd>
            </div>
            <div className="flex justify-between gap-4">
              <dt className="text-muted-foreground">Phone</dt>
              <dd className="text-ink">{user.phone ?? "—"}</dd>
            </div>
            <div className="flex justify-between gap-4">
              <dt className="text-muted-foreground">Providers</dt>
              <dd className="text-ink">{user.providers.join(", ") || "—"}</dd>
            </div>
          </dl>
          <p className="pt-2 text-sm text-muted-foreground">
            Coming next: create and list projects, then GitHub App install for
            repo access.
          </p>
        </div>
      </main>
    </div>
  );
}
