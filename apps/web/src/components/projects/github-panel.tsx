"use client";

import { useCallback, useEffect, useState } from "react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  attachGitHubRepo,
  createMockGitHubInstallation,
  deployProject,
  fetchGitHubConfig,
  listDeployments,
  listGitHubInstallations,
  listGitHubRepos,
  updateProject,
  type DeploymentJob,
  type GitHubConfig,
  type GitHubInstallation,
  type GitHubRepo,
  type Project,
} from "@/lib/api";

export function GitHubPanel({
  project,
  onProjectChange,
}: {
  project: Project;
  onProjectChange: (p: Project) => void;
}) {
  const [config, setConfig] = useState<GitHubConfig | null>(null);
  const [installations, setInstallations] = useState<GitHubInstallation[]>([]);
  const [repos, setRepos] = useState<GitHubRepo[]>([]);
  const [selectedInstall, setSelectedInstall] = useState<string>("");
  const [deployBranch, setDeployBranch] = useState(
    project.deploy_branch || project.default_branch || "main",
  );
  const [deployments, setDeployments] = useState<DeploymentJob[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [info, setInfo] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const refreshDeployments = useCallback(() => {
    listDeployments(project.id)
      .then(setDeployments)
      .catch(() => setDeployments([]));
  }, [project.id]);

  const refreshInstallations = useCallback(() => {
    listGitHubInstallations()
      .then((items) => {
        setInstallations(items);
        if (items[0] && !selectedInstall) setSelectedInstall(items[0].id);
      })
      .catch(() => setInstallations([]));
  }, [selectedInstall]);

  useEffect(() => {
    fetchGitHubConfig()
      .then(setConfig)
      .catch(() => setConfig({ mock_mode: true, app_configured: false, app_slug: "devdeploy-local", install_url: null }));
    refreshInstallations();
    refreshDeployments();
  }, [refreshInstallations, refreshDeployments]);

  useEffect(() => {
    if (!selectedInstall) {
      setRepos([]);
      return;
    }
    listGitHubRepos(selectedInstall)
      .then(setRepos)
      .catch((err: unknown) => {
        setError(err instanceof Error ? err.message : "Failed to list repos");
        setRepos([]);
      });
  }, [selectedInstall]);

  async function onMockConnect() {
    setBusy(true);
    setError(null);
    try {
      const installation = await createMockGitHubInstallation();
      setInfo(`Mock GitHub App installed as ${installation.account_login}`);
      await refreshInstallations();
      setSelectedInstall(installation.id);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Mock install failed");
    } finally {
      setBusy(false);
    }
  }

  async function onAttach(repo: GitHubRepo) {
    if (!selectedInstall) return;
    setBusy(true);
    setError(null);
    try {
      const updated = await attachGitHubRepo(project.id, {
        installation_id: selectedInstall,
        repo_id: repo.id,
        full_name: repo.full_name,
        default_branch: repo.default_branch,
        deploy_branch: deployBranch || repo.default_branch,
      });
      onProjectChange(updated);
      setInfo(`Attached ${repo.full_name}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Attach failed");
    } finally {
      setBusy(false);
    }
  }

  async function onSaveBranch() {
    setBusy(true);
    setError(null);
    try {
      const updated = await updateProject(project.id, {
        deploy_branch: deployBranch,
      });
      onProjectChange(updated);
      setInfo("Deploy branch saved");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Save failed");
    } finally {
      setBusy(false);
    }
  }

  async function onDeploy() {
    setBusy(true);
    setError(null);
    try {
      const job = await deployProject(project.id);
      setInfo(`Deployment ${job.id.slice(0, 8)}… queued`);
      refreshDeployments();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Deploy failed");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="space-y-6">
      <section className="space-y-4 border border-border/70 bg-white/40 p-6">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <p className="font-mono text-xs uppercase tracking-[0.14em] text-muted-foreground">
              GitHub App
            </p>
            <h2 className="mt-1 font-[family-name:var(--font-display)] text-xl font-semibold text-ink">
              Connect repository
            </h2>
            <p className="mt-1 text-sm text-muted-foreground">
              Repo access uses a GitHub App installation — separate from user
              sign-in.
              {config?.mock_mode
                ? " Mock mode is on (no real App credentials required)."
                : null}
            </p>
          </div>
          {config?.mock_mode || !config?.app_configured ? (
            <Button
              onClick={onMockConnect}
              disabled={busy}
              className="h-10 bg-signal text-signal-foreground hover:bg-signal/90"
            >
              {busy ? "Working…" : "Connect mock GitHub App"}
            </Button>
          ) : config.install_url ? (
            <Button
              render={<a href={config.install_url} target="_blank" rel="noreferrer" />}
              className="h-10 bg-signal text-signal-foreground hover:bg-signal/90"
            >
              Install GitHub App
            </Button>
          ) : null}
        </div>

        {error ? (
          <p className="rounded-md border border-destructive/30 bg-destructive/10 px-3 py-2 text-sm text-destructive">
            {error}
          </p>
        ) : null}
        {info ? (
          <p className="rounded-md border border-signal/30 bg-signal/10 px-3 py-2 text-sm text-ink">
            {info}
          </p>
        ) : null}

        {installations.length > 0 ? (
          <div className="space-y-2">
            <Label htmlFor="installation">Installation</Label>
            <select
              id="installation"
              className="h-10 w-full rounded-md border border-border bg-white/70 px-3 text-sm"
              value={selectedInstall}
              onChange={(e) => setSelectedInstall(e.target.value)}
            >
              {installations.map((i) => (
                <option key={i.id} value={i.id}>
                  {i.account_login}
                  {i.is_mock ? " (mock)" : ""}
                </option>
              ))}
            </select>
          </div>
        ) : (
          <p className="text-sm text-muted-foreground">
            No installations yet. Use the mock connect button for local demos.
          </p>
        )}

        {repos.length > 0 ? (
          <ul className="divide-y divide-border/70 border border-border/60">
            {repos.map((repo) => (
              <li
                key={repo.id}
                className="flex flex-wrap items-center justify-between gap-3 px-4 py-3"
              >
                <div>
                  <p className="font-medium text-ink">{repo.full_name}</p>
                  <p className="font-mono text-xs text-muted-foreground">
                    default {repo.default_branch}
                    {repo.private ? " · private" : " · public"}
                  </p>
                </div>
                <Button
                  variant="outline"
                  disabled={busy}
                  onClick={() => onAttach(repo)}
                  className="h-9"
                >
                  {project.github_repo_id === repo.id ? "Attached" : "Attach"}
                </Button>
              </li>
            ))}
          </ul>
        ) : null}
      </section>

      <section className="space-y-4 border border-border/70 bg-white/40 p-6">
        <p className="font-mono text-xs uppercase tracking-[0.14em] text-muted-foreground">
          Project settings
        </p>
        <dl className="grid gap-2 text-sm sm:grid-cols-2">
          <div>
            <dt className="text-muted-foreground">Attached repo</dt>
            <dd className="font-mono text-ink">
              {project.github_repo_full_name ?? "—"}
            </dd>
          </div>
          <div>
            <dt className="text-muted-foreground">Default branch</dt>
            <dd className="font-mono text-ink">{project.default_branch ?? "—"}</dd>
          </div>
        </dl>
        <div className="flex flex-wrap items-end gap-3">
          <div className="min-w-[12rem] flex-1 space-y-2">
            <Label htmlFor="deploy-branch">Deploy branch</Label>
            <Input
              id="deploy-branch"
              value={deployBranch}
              onChange={(e) => setDeployBranch(e.target.value)}
              className="h-10 bg-white/70 font-mono text-sm"
            />
          </div>
          <Button variant="outline" disabled={busy} onClick={onSaveBranch} className="h-10">
            Save branch
          </Button>
          <Button
            disabled={busy || !project.github_repo_full_name}
            onClick={onDeploy}
            className="h-10 bg-signal text-signal-foreground hover:bg-signal/90"
          >
            Deploy
          </Button>
        </div>
      </section>

      <section className="space-y-3 border border-dashed border-border bg-white/30 p-6">
        <div className="flex items-center justify-between gap-3">
          <p className="font-mono text-xs uppercase tracking-[0.14em] text-muted-foreground">
            Deployments
          </p>
          <Button variant="ghost" className="h-8" onClick={refreshDeployments}>
            Refresh
          </Button>
        </div>
        {deployments.length === 0 ? (
          <p className="text-sm text-muted-foreground">
            No deployment jobs yet. Attach a repo and click Deploy, or push to
            the deploy branch (webhook).
          </p>
        ) : (
          <ul className="divide-y divide-border/60 border border-border/50">
            {deployments.map((job) => (
              <li key={job.id} className="px-4 py-3 text-sm">
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <span className="font-mono text-xs text-ink">{job.id.slice(0, 8)}</span>
                  <span className="rounded bg-ink/5 px-2 py-0.5 font-mono text-[11px] uppercase tracking-wide text-ink">
                    {job.status}
                  </span>
                </div>
                <p className="mt-1 text-muted-foreground">
                  {job.trigger} · {job.git_ref ?? "—"}
                  {job.commit_sha ? ` · ${job.commit_sha.slice(0, 7)}` : ""}
                </p>
                {job.message ? (
                  <p className="mt-0.5 text-xs text-muted-foreground">{job.message}</p>
                ) : null}
              </li>
            ))}
          </ul>
        )}
      </section>
    </div>
  );
}
