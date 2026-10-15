"use client";

import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import { AppShell } from "@/components/app-shell";
import { Button } from "@/components/ui/button";
import { useRequireUser } from "@/hooks/use-require-user";
import { deleteProject, getProject, type Project } from "@/lib/api";

export default function ProjectDetailPage() {
  const params = useParams<{ id: string }>();
  const router = useRouter();
  const { user, loading: authLoading } = useRequireUser(`/projects/${params.id}`);
  const [project, setProject] = useState<Project | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [deleting, setDeleting] = useState(false);

  useEffect(() => {
    if (!params.id) return;
    let cancelled = false;
    setLoading(true);
    getProject(params.id)
      .then((p) => {
        if (!cancelled) {
          setProject(p);
          setLoading(false);
        }
      })
      .catch((err: unknown) => {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : "Failed to load project");
          setLoading(false);
        }
      });
    return () => {
      cancelled = true;
    };
  }, [params.id]);

  if (authLoading || !user) {
    return (
      <div className="dd-atmosphere flex min-h-full flex-1 items-center justify-center">
        <p className="text-sm text-muted-foreground">Checking session…</p>
      </div>
    );
  }

  async function onDelete() {
    if (!project) return;
    if (!window.confirm(`Delete project “${project.name}”?`)) return;
    setDeleting(true);
    try {
      await deleteProject(project.id);
      router.push("/projects");
      router.refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Delete failed");
      setDeleting(false);
    }
  }

  return (
    <AppShell user={user}>
      <div className="space-y-8">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <Link
              href="/projects"
              className="text-sm text-muted-foreground transition-colors hover:text-ink"
            >
              ← Projects
            </Link>
            {loading ? (
              <p className="mt-4 text-sm text-muted-foreground">Loading project…</p>
            ) : project ? (
              <>
                <h1 className="mt-3 font-[family-name:var(--font-display)] text-3xl font-bold tracking-tight text-ink">
                  {project.name}
                </h1>
                <p className="mt-1 font-mono text-sm text-muted-foreground">
                  {project.slug}
                </p>
              </>
            ) : (
              <h1 className="mt-3 font-[family-name:var(--font-display)] text-3xl font-bold tracking-tight text-ink">
                Project not found
              </h1>
            )}
          </div>
          {project ? (
            <Button
              variant="destructive"
              disabled={deleting}
              onClick={onDelete}
              className="h-9"
            >
              {deleting ? "Deleting…" : "Delete"}
            </Button>
          ) : null}
        </div>

        {error ? (
          <p className="rounded-md border border-destructive/30 bg-destructive/10 px-3 py-2 text-sm text-destructive">
            {error}
          </p>
        ) : null}

        {project ? (
          <div className="grid gap-6 lg:grid-cols-[1.2fr_0.8fr]">
            <section className="space-y-4 border border-border/70 bg-white/40 p-6">
              <p className="font-mono text-xs uppercase tracking-[0.14em] text-muted-foreground">
                Overview
              </p>
              <p className="text-sm leading-relaxed text-foreground/90">
                {project.description || "No description yet."}
              </p>
              <dl className="grid gap-3 text-sm sm:grid-cols-2">
                <div>
                  <dt className="text-muted-foreground">Default branch</dt>
                  <dd className="font-mono text-ink">
                    {project.default_branch ?? "—"}
                  </dd>
                </div>
                <div>
                  <dt className="text-muted-foreground">Dockerfile</dt>
                  <dd className="font-mono text-ink">
                    {project.dockerfile_path ?? "—"}
                  </dd>
                </div>
                <div>
                  <dt className="text-muted-foreground">Created</dt>
                  <dd className="text-ink">
                    {new Date(project.created_at).toLocaleString()}
                  </dd>
                </div>
                <div>
                  <dt className="text-muted-foreground">Updated</dt>
                  <dd className="text-ink">
                    {new Date(project.updated_at).toLocaleString()}
                  </dd>
                </div>
              </dl>
            </section>

            <section className="space-y-3 border border-dashed border-border bg-white/30 p-6">
              <p className="font-mono text-xs uppercase tracking-[0.14em] text-muted-foreground">
                Coming next
              </p>
              <ul className="space-y-2 text-sm text-muted-foreground">
                <li>Attach a GitHub repo via GitHub App install</li>
                <li>Manual deploy + push-triggered jobs</li>
                <li>Build logs, status, and rollback</li>
              </ul>
              <p className="pt-2 font-mono text-xs text-muted-foreground">
                Repo: {project.github_repo_full_name ?? "not attached"}
              </p>
            </section>
          </div>
        ) : null}
      </div>
    </AppShell>
  );
}
