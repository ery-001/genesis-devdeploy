"use client";

import { AppShell } from "@/components/app-shell";
import { ProjectList } from "@/components/projects/project-list";
import { useRequireUser } from "@/hooks/use-require-user";

export default function DashboardPage() {
  const { user, loading } = useRequireUser("/dashboard");

  if (loading || !user) {
    return (
      <div className="dd-atmosphere flex min-h-full flex-1 items-center justify-center">
        <p className="text-sm text-muted-foreground">Checking session…</p>
      </div>
    );
  }

  return (
    <AppShell user={user}>
      <div className="space-y-6">
        <p className="rounded-md border border-border/70 bg-white/40 px-4 py-3 text-sm text-muted-foreground">
          Account sign-in (email, Google, GitHub login, Apple, Microsoft) is
          separate from repository access. Open a project and install or connect
          the <span className="font-medium text-ink">GitHub App</span> to list
          and attach repos.
        </p>
        <ProjectList
          title="Dashboard"
          subtitle="Your DevDeploy control plane — projects you can configure and deploy."
        />
      </div>
    </AppShell>
  );
}
