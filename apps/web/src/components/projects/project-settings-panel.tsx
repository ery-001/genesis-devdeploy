"use client";

import { useEffect, useState } from "react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  applyDevDeployYaml,
  createPreview,
  fetchProjectLogs,
  listEnvironments,
  listPreviews,
  updateEnvironment,
  updateProject,
  validateDevDeployYaml,
  type PreviewEnv,
  type Project,
  type ProjectEnvironment,
} from "@/lib/api";

export function ProjectSettingsPanel({
  project,
  onProjectChange,
}: {
  project: Project;
  onProjectChange: (p: Project) => void;
}) {
  const [form, setForm] = useState({
    dockerfile_path: project.dockerfile_path || "Dockerfile",
    container_port: project.container_port || 8000,
    health_path: project.health_path || "/health",
    cpu_request: project.cpu_request || "100m",
    memory_request: project.memory_request || "128Mi",
    cpu_limit: project.cpu_limit || "500m",
    memory_limit: project.memory_limit || "512Mi",
    auto_deploy: project.auto_deploy ?? true,
    replicas: project.replicas || 1,
    approval_required_prod: project.approval_required_prod ?? false,
  });
  const [yamlText, setYamlText] = useState(
    `dockerfile: ${project.dockerfile_path || "Dockerfile"}
port: ${project.container_port || 8000}
health: ${project.health_path || "/health"}
cpu: ${project.cpu_request || "100m"}
memory: ${project.memory_request || "128Mi"}
auto_deploy: ${project.auto_deploy ?? true}
replicas: ${project.replicas || 1}
`,
  );
  const [envs, setEnvs] = useState<ProjectEnvironment[]>([]);
  const [logs, setLogs] = useState<string[]>([]);
  const [logSource, setLogSource] = useState("");
  const [previews, setPreviews] = useState<PreviewEnv[]>([]);
  const [prNumber, setPrNumber] = useState("1");
  const [info, setInfo] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    listEnvironments(project.id).then(setEnvs).catch(() => setEnvs([]));
    listPreviews(project.id).then(setPreviews).catch(() => setPreviews([]));
    fetchProjectLogs(project.id)
      .then((r) => {
        setLogs(r.lines);
        setLogSource(r.source);
      })
      .catch(() => setLogs([]));
  }, [project.id]);

  async function saveSettings() {
    setBusy(true);
    setError(null);
    try {
      const updated = await updateProject(project.id, form);
      onProjectChange(updated);
      setInfo("Settings saved");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Save failed");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="space-y-6">
      {error ? (
        <p className="text-sm text-destructive">{error}</p>
      ) : null}
      {info ? <p className="text-sm text-ink">{info}</p> : null}

      <section className="space-y-4 border border-border/70 bg-white/40 p-6">
        <p className="font-mono text-xs uppercase tracking-[0.14em] text-muted-foreground">
          Runtime settings
        </p>
        <div className="grid gap-3 sm:grid-cols-2">
          {(
            [
              ["dockerfile_path", "Dockerfile path"],
              ["health_path", "Health path"],
              ["cpu_request", "CPU request"],
              ["memory_request", "Memory request"],
              ["cpu_limit", "CPU limit"],
              ["memory_limit", "Memory limit"],
            ] as const
          ).map(([key, label]) => (
            <div key={key} className="space-y-2">
              <Label>{label}</Label>
              <Input
                className="font-mono"
                value={String(form[key])}
                onChange={(e) =>
                  setForm((f) => ({ ...f, [key]: e.target.value }))
                }
              />
            </div>
          ))}
          <div className="space-y-2">
            <Label>Container port</Label>
            <Input
              type="number"
              value={form.container_port}
              onChange={(e) =>
                setForm((f) => ({
                  ...f,
                  container_port: Number(e.target.value),
                }))
              }
            />
          </div>
          <div className="space-y-2">
            <Label>Replicas</Label>
            <Input
              type="number"
              min={1}
              max={20}
              value={form.replicas}
              onChange={(e) =>
                setForm((f) => ({ ...f, replicas: Number(e.target.value) }))
              }
            />
          </div>
          <label className="flex items-center gap-2 text-sm">
            <input
              type="checkbox"
              checked={form.auto_deploy}
              onChange={(e) =>
                setForm((f) => ({ ...f, auto_deploy: e.target.checked }))
              }
            />
            Auto-deploy on push
          </label>
          <label className="flex items-center gap-2 text-sm">
            <input
              type="checkbox"
              checked={form.approval_required_prod}
              onChange={(e) =>
                setForm((f) => ({
                  ...f,
                  approval_required_prod: e.target.checked,
                }))
              }
            />
            Require approval for production
          </label>
        </div>
        <Button disabled={busy} onClick={saveSettings}>
          Save settings
        </Button>
      </section>

      <section className="space-y-3 border border-border/70 bg-white/40 p-6">
        <p className="font-mono text-xs uppercase tracking-[0.14em] text-muted-foreground">
          Environments
        </p>
        <ul className="divide-y divide-border/60 border border-border/50">
          {envs.map((env) => (
            <li
              key={env.id}
              className="flex flex-wrap items-center justify-between gap-3 px-4 py-3 text-sm"
            >
              <div>
                <p className="font-medium text-ink">{env.name}</p>
                <p className="font-mono text-xs text-muted-foreground">
                  replicas {env.replicas}
                  {env.approval_required ? " · approval" : ""}
                </p>
              </div>
              <div className="flex items-center gap-2">
                <Input
                  type="number"
                  className="h-9 w-20"
                  min={1}
                  max={20}
                  defaultValue={env.replicas}
                  onBlur={async (e) => {
                    const replicas = Number(e.target.value);
                    const updated = await updateEnvironment(project.id, env.id, {
                      replicas,
                    });
                    setEnvs((rows) =>
                      rows.map((r) => (r.id === env.id ? updated : r)),
                    );
                  }}
                />
                <label className="flex items-center gap-1 text-xs">
                  <input
                    type="checkbox"
                    checked={env.approval_required}
                    onChange={async (e) => {
                      const updated = await updateEnvironment(
                        project.id,
                        env.id,
                        { approval_required: e.target.checked },
                      );
                      setEnvs((rows) =>
                        rows.map((r) => (r.id === env.id ? updated : r)),
                      );
                    }}
                  />
                  approve
                </label>
              </div>
            </li>
          ))}
        </ul>
      </section>

      <section className="space-y-3 border border-border/70 bg-white/40 p-6">
        <p className="font-mono text-xs uppercase tracking-[0.14em] text-muted-foreground">
          devdeploy.yaml
        </p>
        <textarea
          className="min-h-40 w-full rounded-md border border-border bg-white/70 p-3 font-mono text-xs"
          value={yamlText}
          onChange={(e) => setYamlText(e.target.value)}
        />
        <div className="flex flex-wrap gap-2">
          <Button
            variant="outline"
            disabled={busy}
            onClick={async () => {
              const r = await validateDevDeployYaml(project.id, yamlText);
              setInfo(
                r.valid
                  ? `Valid: ${JSON.stringify(r.parsed)}`
                  : `Errors: ${r.errors.join("; ")}`,
              );
            }}
          >
            Validate
          </Button>
          <Button
            disabled={busy}
            onClick={async () => {
              try {
                const updated = await applyDevDeployYaml(project.id, yamlText);
                onProjectChange(updated);
                setInfo("YAML applied to project settings");
              } catch (err) {
                setError(err instanceof Error ? err.message : "Apply failed");
              }
            }}
          >
            Apply
          </Button>
        </div>
      </section>

      <section className="space-y-3 border border-dashed border-border bg-white/30 p-6">
        <div className="flex items-center justify-between gap-3">
          <p className="font-mono text-xs uppercase tracking-[0.14em] text-muted-foreground">
            Live app logs ({logSource || "—"})
          </p>
          <Button
            variant="ghost"
            className="h-8"
            onClick={async () => {
              const r = await fetchProjectLogs(project.id);
              setLogs(r.lines);
              setLogSource(r.source);
            }}
          >
            Refresh
          </Button>
        </div>
        <pre className="max-h-56 overflow-auto font-mono text-[11px] leading-relaxed">
          {logs.join("\n") || "No logs yet."}
        </pre>
      </section>

      <section className="space-y-3 border border-dashed border-border bg-white/30 p-6">
        <p className="font-mono text-xs uppercase tracking-[0.14em] text-muted-foreground">
          Preview environments (stub)
        </p>
        <div className="flex flex-wrap items-end gap-2">
          <div className="space-y-2">
            <Label>PR number</Label>
            <Input
              value={prNumber}
              onChange={(e) => setPrNumber(e.target.value)}
              className="w-28"
            />
          </div>
          <Button
            variant="outline"
            onClick={async () => {
              const row = await createPreview(project.id, Number(prNumber) || 1);
              setPreviews((p) => [row, ...p]);
              setInfo("Preview stub created");
            }}
          >
            Create preview
          </Button>
        </div>
        <ul className="divide-y divide-border/60 border border-border/50">
          {previews.map((p) => (
            <li key={p.id} className="px-4 py-3 text-sm">
              <p className="font-mono text-xs">
                PR #{p.pr_number} · {p.status}
              </p>
              <p className="text-muted-foreground">{p.preview_url}</p>
            </li>
          ))}
        </ul>
      </section>
    </div>
  );
}
