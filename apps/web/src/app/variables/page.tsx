"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import { AppShell } from "@/components/app-shell";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { useRequireUser } from "@/hooks/use-require-user";
import {
  createVariable,
  deleteVariable,
  listProjects,
  listVariables,
  type Project,
  type ProjectVariable,
} from "@/lib/api";

export default function VariablesPage() {
  const { user, loading } = useRequireUser("/variables");
  const [projects, setProjects] = useState<Project[]>([]);
  const [projectId, setProjectId] = useState("");
  const [vars, setVars] = useState<ProjectVariable[]>([]);
  const [key, setKey] = useState("");
  const [value, setValue] = useState("");
  const [env, setEnv] = useState("development");
  const [isSecret, setIsSecret] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    listProjects()
      .then((rows) => {
        setProjects(rows);
        if (rows[0]) setProjectId(rows[0].id);
      })
      .catch(() => setProjects([]));
  }, []);

  useEffect(() => {
    if (!projectId) {
      setVars([]);
      return;
    }
    listVariables(projectId).then(setVars).catch(() => setVars([]));
  }, [projectId]);

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
          <h1 className="font-[family-name:var(--font-display)] text-3xl font-bold tracking-tight text-ink">
            Variables
          </h1>
          <p className="mt-2 max-w-xl text-sm text-muted-foreground">
            Env vars and secrets are encrypted at rest with a local key. Secret
            values are never shown after save.
          </p>
        </div>

        <div className="space-y-2">
          <Label htmlFor="project">Project</Label>
          <select
            id="project"
            className="h-10 w-full max-w-md rounded-md border border-border bg-white/70 px-3 text-sm"
            value={projectId}
            onChange={(e) => setProjectId(e.target.value)}
          >
            {projects.length === 0 ? (
              <option value="">No projects</option>
            ) : (
              projects.map((p) => (
                <option key={p.id} value={p.id}>
                  {p.name}
                </option>
              ))
            )}
          </select>
          {projectId ? (
            <p className="text-sm text-muted-foreground">
              Also editable from{" "}
              <Link
                className="text-ink underline-offset-2 hover:underline"
                href={`/projects/${projectId}`}
              >
                project page
              </Link>
              .
            </p>
          ) : null}
        </div>

        {error ? (
          <p className="text-sm text-destructive">{error}</p>
        ) : null}

        <section className="space-y-4 border border-border/70 bg-white/40 p-6">
          <p className="font-mono text-xs uppercase tracking-[0.14em] text-muted-foreground">
            Add variable
          </p>
          <div className="grid gap-3 sm:grid-cols-2">
            <div className="space-y-2">
              <Label htmlFor="key">Key</Label>
              <Input
                id="key"
                value={key}
                onChange={(e) => setKey(e.target.value)}
                placeholder="DATABASE_URL"
                className="font-mono"
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="value">Value</Label>
              <Input
                id="value"
                type={isSecret ? "password" : "text"}
                value={value}
                onChange={(e) => setValue(e.target.value)}
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="env">Environment</Label>
              <select
                id="env"
                className="h-10 w-full rounded-md border border-border bg-white/70 px-3 text-sm"
                value={env}
                onChange={(e) => setEnv(e.target.value)}
              >
                {["development", "staging", "production"].map((e) => (
                  <option key={e} value={e}>
                    {e}
                  </option>
                ))}
              </select>
            </div>
            <label className="flex items-center gap-2 self-end text-sm">
              <input
                type="checkbox"
                checked={isSecret}
                onChange={(e) => setIsSecret(e.target.checked)}
              />
              Secret
            </label>
          </div>
          <Button
            disabled={!projectId || !key}
            onClick={async () => {
              setError(null);
              try {
                await createVariable(projectId, {
                  key,
                  value,
                  is_secret: isSecret,
                  environment_name: env,
                });
                setKey("");
                setValue("");
                setVars(await listVariables(projectId));
              } catch (err) {
                setError(err instanceof Error ? err.message : "Failed");
              }
            }}
          >
            Save
          </Button>
        </section>

        <section className="space-y-3 border border-dashed border-border bg-white/30 p-6">
          <p className="font-mono text-xs uppercase tracking-[0.14em] text-muted-foreground">
            Stored
          </p>
          {vars.length === 0 ? (
            <p className="text-sm text-muted-foreground">No variables yet.</p>
          ) : (
            <ul className="divide-y divide-border/60 border border-border/50">
              {vars.map((v) => (
                <li
                  key={v.id}
                  className="flex flex-wrap items-center justify-between gap-3 px-4 py-3 text-sm"
                >
                  <div>
                    <p className="font-mono text-ink">{v.key}</p>
                    <p className="text-muted-foreground">
                      {v.environment_name} ·{" "}
                      {v.is_secret ? "secret" : v.value_preview}
                    </p>
                  </div>
                  <Button
                    variant="outline"
                    className="h-8"
                    onClick={async () => {
                      await deleteVariable(projectId, v.id);
                      setVars(await listVariables(projectId));
                    }}
                  >
                    Delete
                  </Button>
                </li>
              ))}
            </ul>
          )}
        </section>
      </div>
    </AppShell>
  );
}
