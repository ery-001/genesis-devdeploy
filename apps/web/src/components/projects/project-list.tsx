"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import { Button } from "@/components/ui/button";
import { listProjects, type Project } from "@/lib/api";

export function ProjectList({
  title = "Projects",
  subtitle = "Dockerfile HTTP apps you manage in the control plane.",
}: {
  title?: string;
  subtitle?: string;
}) {
  const [projects, setProjects] = useState<Project[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    listProjects()
      .then((items) => {
        if (!cancelled) setProjects(items);
      })
      .catch((err: unknown) => {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : "Failed to load projects");
          setProjects([]);
        }
      });
    return () => {
      cancelled = true;
    };
  }, []);

  return (
    <div className="space-y-8">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="font-[family-name:var(--font-display)] text-3xl font-bold tracking-tight text-ink">
            {title}
          </h1>
          <p className="mt-2 max-w-xl text-muted-foreground">{subtitle}</p>
        </div>
        <Button
          render={<Link href="/projects/new" />}
          className="h-10 bg-signal text-signal-foreground hover:bg-signal/90"
        >
          New project
        </Button>
      </div>

      {error ? (
        <p className="rounded-md border border-destructive/30 bg-destructive/10 px-3 py-2 text-sm text-destructive">
          {error}
        </p>
      ) : null}

      {projects === null ? (
        <p className="text-sm text-muted-foreground">Loading projects…</p>
      ) : projects.length === 0 ? (
        <div className="border border-dashed border-border bg-white/40 px-6 py-12">
          <p className="font-[family-name:var(--font-display)] text-xl font-semibold text-ink">
            No projects yet
          </p>
          <p className="mt-2 max-w-md text-sm text-muted-foreground">
            Create a project to configure a deploy target. GitHub repo attach
            lands in Milestone 2 — for now you can name and describe the app.
          </p>
          <Button
            render={<Link href="/projects/new" />}
            className="mt-6 h-10 bg-signal text-signal-foreground hover:bg-signal/90"
          >
            Create your first project
          </Button>
        </div>
      ) : (
        <ul className="divide-y divide-border/70 border border-border/70 bg-white/40">
          {projects.map((project) => (
            <li key={project.id}>
              <Link
                href={`/projects/${project.id}`}
                className="flex flex-col gap-1 px-5 py-4 transition-colors hover:bg-white/70 sm:flex-row sm:items-center sm:justify-between"
              >
                <div>
                  <p className="font-medium text-ink">{project.name}</p>
                  <p className="font-mono text-xs text-muted-foreground">
                    {project.slug}
                    {project.description ? ` · ${project.description}` : ""}
                  </p>
                </div>
                <span className="font-mono text-[11px] uppercase tracking-[0.12em] text-muted-foreground">
                  {project.github_repo_full_name
                    ? project.github_repo_full_name
                    : "no repo yet"}
                </span>
              </Link>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
