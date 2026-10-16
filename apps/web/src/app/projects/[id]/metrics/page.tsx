"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useMemo, useState } from "react";
import {
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import { AppShell } from "@/components/app-shell";
import { useRequireUser } from "@/hooks/use-require-user";
import {
  fetchAnalytics,
  fetchProjectMetrics,
  fetchQuotas,
  getProject,
  listScans,
  type Analytics,
  type Project,
  type ProjectMetrics,
  type Scan,
} from "@/lib/api";

export default function ProjectMetricsPage() {
  const params = useParams<{ id: string }>();
  const { user, loading } = useRequireUser(`/projects/${params.id}/metrics`);
  const [project, setProject] = useState<Project | null>(null);
  const [metrics, setMetrics] = useState<ProjectMetrics | null>(null);
  const [quotas, setQuotas] = useState<{
    cpu_request: string;
    memory_request: string;
    cpu_limit: string;
    memory_limit: string;
    replicas: number;
    namespace: string;
  } | null>(null);
  const [scans, setScans] = useState<Scan[]>([]);
  const [analytics, setAnalytics] = useState<Analytics | null>(null);

  useEffect(() => {
    if (!params.id) return;
    getProject(params.id).then(setProject).catch(() => setProject(null));
    fetchProjectMetrics(params.id).then(setMetrics).catch(() => setMetrics(null));
    fetchQuotas(params.id).then(setQuotas).catch(() => setQuotas(null));
    listScans(params.id).then(setScans).catch(() => setScans([]));
    fetchAnalytics(params.id).then(setAnalytics).catch(() => setAnalytics(null));
    const t = setInterval(() => {
      fetchProjectMetrics(params.id).then(setMetrics).catch(() => undefined);
    }, 15000);
    return () => clearInterval(t);
  }, [params.id]);

  const chartData = useMemo(() => {
    const cpu = metrics?.series?.cpu || [];
    return cpu.map((p, i) => ({
      t: new Date(p.t * 1000).toLocaleTimeString([], {
        hour: "2-digit",
        minute: "2-digit",
      }),
      cpu: p.v,
      memory: metrics?.series?.memory?.[i]?.v ?? 0,
      rpm: metrics?.series?.rpm?.[i]?.v ?? 0,
    }));
  }, [metrics]);

  if (loading || !user) {
    return (
      <div className="dd-atmosphere flex min-h-full flex-1 items-center justify-center">
        <p className="text-sm text-muted-foreground">Checking session…</p>
      </div>
    );
  }

  return (
    <AppShell user={user}>
      <div className="space-y-8">
        <div>
          <Link
            href={`/projects/${params.id}`}
            className="text-sm text-muted-foreground hover:text-ink"
          >
            ← {project?.name || "Project"}
          </Link>
          <h1 className="mt-3 font-[family-name:var(--font-display)] text-3xl font-bold tracking-tight text-ink">
            Monitoring
          </h1>
          <p className="mt-2 text-sm text-muted-foreground">
            Charts from release-derived / synthetic series
            {metrics ? ` (${metrics.source})` : ""}. Wire Prometheus for prod.
          </p>
        </div>

        {metrics ? (
          <div className="grid gap-3 sm:grid-cols-4">
            <Stat label="CPU" value={`${metrics.cpu_percent}%`} />
            <Stat label="Memory" value={`${metrics.memory_mib} MiB`} />
            <Stat label="Uptime" value={`${metrics.uptime_seconds}s`} />
            <Stat label="RPM" value={`${metrics.requests_per_minute}`} />
          </div>
        ) : null}

        <section className="h-72 border border-border/70 bg-white/40 p-4">
          <p className="mb-3 font-mono text-xs uppercase tracking-[0.14em] text-muted-foreground">
            Last 24 samples
          </p>
          <ResponsiveContainer width="100%" height="85%">
            <LineChart data={chartData}>
              <CartesianGrid strokeDasharray="3 3" stroke="#b7c9d4" />
              <XAxis dataKey="t" tick={{ fontSize: 10 }} />
              <YAxis tick={{ fontSize: 10 }} />
              <Tooltip />
              <Line type="monotone" dataKey="cpu" stroke="#0f7a6b" dot={false} />
              <Line
                type="monotone"
                dataKey="memory"
                stroke="#2a6f97"
                dot={false}
              />
              <Line type="monotone" dataKey="rpm" stroke="#c45c26" dot={false} />
            </LineChart>
          </ResponsiveContainer>
        </section>

        {quotas ? (
          <section className="border border-border/70 bg-white/40 p-6">
            <p className="font-mono text-xs uppercase tracking-[0.14em] text-muted-foreground">
              Resource quotas · {quotas.namespace}
            </p>
            <dl className="mt-3 grid gap-3 text-sm sm:grid-cols-3">
              <div>
                <dt className="text-muted-foreground">CPU req / limit</dt>
                <dd className="font-mono">
                  {quotas.cpu_request} / {quotas.cpu_limit}
                </dd>
              </div>
              <div>
                <dt className="text-muted-foreground">Memory req / limit</dt>
                <dd className="font-mono">
                  {quotas.memory_request} / {quotas.memory_limit}
                </dd>
              </div>
              <div>
                <dt className="text-muted-foreground">Replicas</dt>
                <dd className="font-mono">{quotas.replicas}</dd>
              </div>
            </dl>
          </section>
        ) : null}

        {analytics ? (
          <section className="border border-border/70 bg-white/40 p-6">
            <p className="font-mono text-xs uppercase tracking-[0.14em] text-muted-foreground">
              Deployment analytics (7d)
            </p>
            <dl className="mt-3 grid gap-3 text-sm sm:grid-cols-4">
              <div>
                <dt className="text-muted-foreground">Success rate</dt>
                <dd className="font-mono">{analytics.deploy_success_rate}%</dd>
              </div>
              <div>
                <dt className="text-muted-foreground">Mean deploy</dt>
                <dd className="font-mono">{analytics.mean_deploy_seconds}s</dd>
              </div>
              <div>
                <dt className="text-muted-foreground">Deploys</dt>
                <dd className="font-mono">{analytics.deploys_last_7d}</dd>
              </div>
              <div>
                <dt className="text-muted-foreground">Rollbacks</dt>
                <dd className="font-mono">{analytics.rollbacks_last_7d}</dd>
              </div>
            </dl>
          </section>
        ) : null}

        <section className="border border-dashed border-border bg-white/30 p-6">
          <p className="font-mono text-xs uppercase tracking-[0.14em] text-muted-foreground">
            Vulnerability scans
          </p>
          {scans.length === 0 ? (
            <p className="mt-2 text-sm text-muted-foreground">
              No scans yet — they appear after a deploy (Trivy or mock).
            </p>
          ) : (
            <ul className="mt-3 divide-y divide-border/60 border border-border/50">
              {scans.map((s) => (
                <li key={s.id} className="px-4 py-3 text-sm">
                  <p className="font-mono text-xs">
                    {s.scanner} · C{s.critical} H{s.high} M{s.medium} L{s.low}
                  </p>
                  <p className="text-muted-foreground">
                    {s.image_digest?.slice(0, 19) || "—"} ·{" "}
                    {new Date(s.created_at).toLocaleString()}
                  </p>
                </li>
              ))}
            </ul>
          )}
        </section>
      </div>
    </AppShell>
  );
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div className="border border-border/70 bg-white/40 p-4">
      <p className="text-xs text-muted-foreground">{label}</p>
      <p className="mt-1 font-mono text-xl text-ink">{value}</p>
    </div>
  );
}
