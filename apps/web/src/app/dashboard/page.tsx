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
      <ProjectList
        title="Dashboard"
        subtitle="Your DevDeploy control plane — projects you can configure and deploy."
      />
    </AppShell>
  );
}
