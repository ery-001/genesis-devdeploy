"use client";

import Link from "next/link";
import { useParams, useSearchParams } from "next/navigation";
import { Suspense, useEffect, useState } from "react";

import { AppShell } from "@/components/app-shell";
import { Button } from "@/components/ui/button";
import { useRequireUser } from "@/hooks/use-require-user";
import {
  approveDeployment,
  cancelDeployment,
  deploymentStreamUrl,
  getDeployment,
  listProjects,
  rejectDeployment,
  type DeploymentJob,
} from "@/lib/api";

function DeploymentDetailInner() {
  const params = useParams<{ id: string }>();
  const search = useSearchParams();
  const projectHint = search.get("project");
  const { user, loading: authLoading } = useRequireUser(
    `/deployments/${params.id}`,
  );
  const [job, setJob] = useState<DeploymentJob | null>(null);
  const [projectId, setProjectId] = useState(projectHint || "");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    let cancelled = false;
    async function load() {
      if (projectHint) {
        try {
          const j = await getDeployment(projectHint, params.id);
          if (!cancelled) {
            setJob(j);
            setProjectId(projectHint);
          }
          return;
        } catch {
          /* fall through */
        }
      }
      const projects = await listProjects();
      for (const p of projects) {
        try {
          const j = await getDeployment(p.id, params.id);
          if (!cancelled) {
            setJob(j);
            setProjectId(p.id);
          }
          return;
        } catch {
          /* try next */
        }
      }
      if (!cancelled) setError("Deployment not found");
    }
    void load();
    return () => {
      cancelled = true;
    };
  }, [params.id, projectHint]);

  // Live log stream once we know the project + job.
  useEffect(() => {
    if (!projectId || !params.id) return;
    const url = deploymentStreamUrl(projectId, params.id);
    let source: EventSource | null = null;
    try {
      source = new EventSource(url, { withCredentials: true });
    } catch {
      return;
    }
    source.onmessage = (ev) => {
      try {
        const data = JSON.parse(ev.data) as Partial<DeploymentJob> & {
          build_logs?: string;
        };
        setJob((prev) =>
          prev
            ? {
                ...prev,
                status: data.status || prev.status,
                message: data.message ?? prev.message,
                build_logs: data.build_logs ?? prev.build_logs,
                app_url: data.app_url ?? prev.app_url,
                public_url: data.public_url ?? prev.public_url,
              }
            : prev,
        );
      } catch {
        /* ignore malformed frames */
      }
    };
    source.addEventListener("done", () => {
      source?.close();
    });
    source.onerror = () => {
      // Fall back to manual refresh; don't spin reconnect forever on auth errors.
      source?.close();
    };
    return () => {
      source?.close();
    };
  }, [projectId, params.id]);

  if (authLoading || !user) {
    return (
      <div className="dd-atmosphere flex min-h-full flex-1 items-center justify-center">
        <p className="text-sm text-muted-foreground">Checking session…</p>
      </div>
    );
  }

  const active = ["queued", "building", "publishing", "deploying", "pending_approval"].includes(
    job?.status || "",
  );

  return (
    <AppShell user={user}>
      <div className="space-y-8">
        <div>
          <Link
            href={projectId ? `/projects/${projectId}` : "/projects"}
            className="text-sm text-muted-foreground hover:text-ink"
          >
            ← Project
          </Link>
          <h1 className="mt-3 font-[family-name:var(--font-display)] text-3xl font-bold tracking-tight text-ink">
            Deployment
          </h1>
          <p className="mt-1 font-mono text-sm text-muted-foreground">
            {params.id}
          </p>
        </div>

        {error ? <p className="text-sm text-destructive">{error}</p> : null}

        {job ? (
          <>
            <dl className="grid gap-3 border border-border/70 bg-white/40 p-6 text-sm sm:grid-cols-2">
              <div>
                <dt className="text-muted-foreground">Status</dt>
                <dd className="font-mono uppercase text-ink">{job.status}</dd>
              </div>
              <div>
                <dt className="text-muted-foreground">Trigger</dt>
                <dd className="font-mono text-ink">{job.trigger}</dd>
              </div>
              <div>
                <dt className="text-muted-foreground">Environment</dt>
                <dd className="font-mono text-ink">
                  {job.environment_name || "development"}
                </dd>
              </div>
              <div>
                <dt className="text-muted-foreground">Ref</dt>
                <dd className="font-mono text-ink">{job.git_ref || "—"}</dd>
              </div>
              <div className="sm:col-span-2">
                <dt className="text-muted-foreground">Message</dt>
                <dd className="text-ink">{job.message || "—"}</dd>
              </div>
              {job.app_url ? (
                <div className="sm:col-span-2">
                  <dt className="text-muted-foreground">App URL</dt>
                  <dd>
                    <a
                      className="font-mono text-signal underline-offset-2 hover:underline"
                      href={job.app_url}
                      target="_blank"
                      rel="noreferrer"
                    >
                      {job.app_url}
                    </a>
                  </dd>
                </div>
              ) : null}
            </dl>

            <div className="flex flex-wrap gap-2">
              <Button
                variant="outline"
                disabled={!active || busy}
                onClick={async () => {
                  setBusy(true);
                  try {
                    setJob(await cancelDeployment(projectId, job.id));
                  } catch (err) {
                    setError(err instanceof Error ? err.message : "Cancel failed");
                  } finally {
                    setBusy(false);
                  }
                }}
              >
                Cancel
              </Button>
              {job.status === "pending_approval" ? (
                <>
                  <Button
                    disabled={busy}
                    className="bg-signal text-signal-foreground hover:bg-signal/90"
                    onClick={async () => {
                      setBusy(true);
                      try {
                        setJob(await approveDeployment(projectId, job.id));
                      } catch (err) {
                        setError(
                          err instanceof Error ? err.message : "Approve failed",
                        );
                      } finally {
                        setBusy(false);
                      }
                    }}
                  >
                    Approve
                  </Button>
                  <Button
                    variant="outline"
                    disabled={busy}
                    onClick={async () => {
                      setBusy(true);
                      try {
                        setJob(await rejectDeployment(projectId, job.id));
                      } catch (err) {
                        setError(
                          err instanceof Error ? err.message : "Reject failed",
                        );
                      } finally {
                        setBusy(false);
                      }
                    }}
                  >
                    Reject
                  </Button>
                </>
              ) : null}
              <Button
                variant="ghost"
                onClick={async () => {
                  setJob(await getDeployment(projectId, job.id));
                }}
              >
                Refresh
              </Button>
            </div>

            <section className="space-y-2 border border-dashed border-border bg-white/30 p-6">
              <p className="font-mono text-xs uppercase tracking-[0.14em] text-muted-foreground">
                Build logs {active ? "· live" : ""}
              </p>
              <pre className="max-h-[28rem] overflow-auto font-mono text-[11px] leading-relaxed text-ink">
                {job.build_logs || "No logs yet — stream opens when the job starts."}
              </pre>
            </section>
          </>
        ) : !error ? (
          <p className="text-sm text-muted-foreground">Loading deployment…</p>
        ) : null}
      </div>
    </AppShell>
  );
}

export default function DeploymentDetailPage() {
  return (
    <Suspense
      fallback={
        <div className="dd-atmosphere flex min-h-full flex-1 items-center justify-center">
          <p className="text-sm text-muted-foreground">Loading…</p>
        </div>
      }
    >
      <DeploymentDetailInner />
    </Suspense>
  );
}
