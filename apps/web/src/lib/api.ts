const LOCAL_API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://127.0.0.1:8741";

/** Local UI → local API; tunnel/shareable host → same-origin (demo proxy). */
export function getApiUrl() {
  if (typeof window !== "undefined") {
    const host = window.location.hostname;
    if (host !== "127.0.0.1" && host !== "localhost") {
      return window.location.origin;
    }
  }
  return LOCAL_API_URL;
}

export type AuthUser = {
  id: string;
  email: string | null;
  phone: string | null;
  display_name: string | null;
  avatar_url: string | null;
  providers: string[];
};

export type OAuthProviderStatus = {
  id: string;
  configured: boolean;
  enabled: boolean;
  callback_url: string;
  callback_urls?: string[];
};

export type AuthConfig = {
  mock_mode: boolean;
  providers: string[];
  oauth_providers?: OAuthProviderStatus[];
  session_cookie: string;
};

export type MessageOut = {
  message: string;
  mock?: boolean;
  magic_link_token?: string | null;
  otp_hint?: string | null;
};

async function api<T>(path: string, init: RequestInit = {}): Promise<T> {
  const res = await fetch(`${getApiUrl()}${path}`, {
    ...init,
    credentials: "include",
    headers: {
      "Content-Type": "application/json",
      ...(init.headers ?? {}),
    },
  });

  if (!res.ok) {
    let detail = res.statusText;
    try {
      const body = (await res.json()) as { detail?: string };
      if (typeof body.detail === "string") detail = body.detail;
    } catch {
      /* ignore */
    }
    throw new Error(detail || `Request failed (${res.status})`);
  }

  if (res.status === 204) return undefined as T;
  return (await res.json()) as T;
}

export function fetchAuthConfig() {
  return api<AuthConfig>("/api/v1/auth/config");
}

export function fetchMe() {
  return api<AuthUser>("/api/v1/auth/me");
}

export function register(body: {
  email: string;
  password: string;
  display_name?: string;
}) {
  return api<AuthUser>("/api/v1/auth/register", {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export function login(body: { email: string; password: string }) {
  return api<AuthUser>("/api/v1/auth/login", {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export function logout() {
  return api<MessageOut>("/api/v1/auth/logout", { method: "POST" });
}

export function requestMagicLink(email: string) {
  return api<MessageOut>("/api/v1/auth/magic-link/request", {
    method: "POST",
    body: JSON.stringify({ email }),
  });
}

export function verifyMagicLink(token: string) {
  return api<AuthUser>("/api/v1/auth/magic-link/verify", {
    method: "POST",
    body: JSON.stringify({ token }),
  });
}

export function startPhoneOtp(phone: string) {
  return api<MessageOut>("/api/v1/auth/phone/start", {
    method: "POST",
    body: JSON.stringify({ phone }),
  });
}

export function verifyPhoneOtp(phone: string, code: string) {
  return api<AuthUser>("/api/v1/auth/phone/verify", {
    method: "POST",
    body: JSON.stringify({ phone, code }),
  });
}

export function oauthStartUrl(provider: string) {
  return `${getApiUrl()}/api/v1/auth/oauth/${provider}/start`;
}

export type Project = {
  id: string;
  organization_id: string;
  owner_user_id: string;
  name: string;
  slug: string;
  description: string | null;
  github_installation_id: string | null;
  github_repo_id: number | null;
  github_repo_full_name: string | null;
  default_branch: string | null;
  deploy_branch: string | null;
  dockerfile_path: string | null;
  container_port: number;
  health_path: string;
  cpu_request: string;
  memory_request: string;
  cpu_limit: string;
  memory_limit: string;
  auto_deploy: boolean;
  replicas: number;
  approval_required_prod: boolean;
  created_at: string;
  updated_at: string;
};

export type GitHubConfig = {
  mock_mode: boolean;
  app_configured: boolean;
  app_slug: string;
  install_url: string | null;
  webhook_callback_hint?: string | null;
};

export type GitHubInstallation = {
  id: string;
  installation_id: number;
  account_login: string;
  account_type: string;
  is_mock: boolean;
  organization_id: string | null;
};

export type GitHubRepo = {
  id: number;
  full_name: string;
  name: string;
  private: boolean;
  default_branch: string;
};

export type DeploymentJob = {
  id: string;
  project_id: string;
  status: string;
  trigger: string;
  git_ref: string | null;
  commit_sha: string | null;
  github_delivery_id: string | null;
  message: string | null;
  build_logs: string | null;
  image_digest: string | null;
  image_tag: string | null;
  app_url: string | null;
  public_url?: string | null;
  simulate_failure: boolean;
  environment_name?: string;
  cancelled_at?: string | null;
  created_at: string;
  updated_at: string;
};

export type Release = {
  id: string;
  project_id: string;
  deployment_job_id: string | null;
  image_digest: string;
  image_tag: string | null;
  app_url: string | null;
  public_url?: string | null;
  status: string;
  is_current: boolean;
  created_at: string;
};

export type MetricPoint = { t: number; v: number };

export type ProjectMetrics = {
  project_id: string;
  cpu_percent: number;
  memory_mib: number;
  uptime_seconds: number;
  requests_per_minute: number;
  source: string;
  series?: Record<string, MetricPoint[]>;
};

export type ProjectVariable = {
  id: string;
  project_id: string;
  key: string;
  is_secret: boolean;
  environment_name: string;
  value_preview: string;
  created_at: string;
  updated_at: string;
};

export type ProjectEnvironment = {
  id: string;
  project_id: string;
  name: string;
  deploy_branch: string | null;
  replicas: number;
  approval_required: boolean;
  created_at: string;
};

export type OrgMember = {
  id: string;
  user_id: string;
  email: string | null;
  display_name: string | null;
  role: string;
  created_at: string;
};

export type Approval = {
  id: string;
  deployment_job_id: string;
  status: string;
  note: string | null;
  created_at: string;
  decided_at: string | null;
};

export type Scan = {
  id: string;
  project_id: string;
  critical: number;
  high: number;
  medium: number;
  low: number;
  scanner: string;
  status: string;
  image_digest: string | null;
  created_at: string;
};

export type AuditLog = {
  id: string;
  action: string;
  resource_type: string;
  resource_id: string | null;
  detail: string | null;
  created_at: string;
};

export type ApiKey = {
  id: string;
  name: string;
  token_prefix: string;
  last_used_at: string | null;
  revoked_at: string | null;
  created_at: string;
};

export type StubFeature = {
  feature: string;
  enabled: boolean;
  status: string;
  config: Record<string, unknown>;
  coming_soon_reason: string | null;
};

export type BillingUsage = {
  build_minutes: number;
  deploy_count: number;
  bandwidth_gb: number;
  seats: number;
  plan: string;
};

export type PreviewEnv = {
  id: string;
  project_id: string;
  pr_number: number;
  status: string;
  preview_url: string | null;
  message: string | null;
  created_at: string;
};

export type Analytics = {
  project_id: string;
  deploy_success_rate: number;
  mean_deploy_seconds: number;
  deploys_last_7d: number;
  rollbacks_last_7d: number;
};

export function listProjects() {
  return api<Project[]>("/api/v1/projects");
}

export function getProject(id: string) {
  return api<Project>(`/api/v1/projects/${id}`);
}

export function createProject(body: {
  name: string;
  slug?: string;
  description?: string;
}) {
  return api<Project>("/api/v1/projects", {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export function deleteProject(id: string) {
  return api<void>(`/api/v1/projects/${id}`, { method: "DELETE" });
}

export function fetchGitHubConfig() {
  return api<GitHubConfig>("/api/v1/github/config");
}

export function listGitHubInstallations() {
  return api<GitHubInstallation[]>("/api/v1/github/installations");
}

export function createMockGitHubInstallation() {
  return api<GitHubInstallation>("/api/v1/github/installations/mock", {
    method: "POST",
    body: "{}",
  });
}

export function syncGitHubInstallations() {
  return api<GitHubInstallation[]>("/api/v1/github/installations/sync", {
    method: "POST",
    body: "{}",
  });
}

export function listGitHubRepos(installationId: string) {
  return api<GitHubRepo[]>(
    `/api/v1/github/installations/${installationId}/repos`,
  );
}

export type GitHubBranch = {
  name: string;
  protected: boolean;
};

export function listGitHubBranches(
  installationId: string,
  owner: string,
  repo: string,
) {
  return api<GitHubBranch[]>(
    `/api/v1/github/installations/${installationId}/repos/${encodeURIComponent(owner)}/${encodeURIComponent(repo)}/branches`,
  );
}

export function attachGitHubRepo(
  projectId: string,
  body: {
    installation_id: string;
    repo_id: number;
    full_name: string;
    default_branch?: string;
    deploy_branch?: string;
  },
) {
  return api<Project>(`/api/v1/projects/${projectId}/github`, {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export function updateProject(
  id: string,
  body: Partial<{
    name: string;
    slug: string;
    description: string;
    deploy_branch: string;
    dockerfile_path: string;
    container_port: number;
    health_path: string;
    cpu_request: string;
    memory_request: string;
    cpu_limit: string;
    memory_limit: string;
    auto_deploy: boolean;
    replicas: number;
    approval_required_prod: boolean;
  }>,
) {
  return api<Project>(`/api/v1/projects/${id}`, {
    method: "PATCH",
    body: JSON.stringify(body),
  });
}

export function deployProject(
  projectId: string,
  body: { simulate_failure?: boolean; environment?: string } = {},
) {
  return api<DeploymentJob>(`/api/v1/projects/${projectId}/deploy`, {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export function cancelDeployment(projectId: string, jobId: string) {
  return api<DeploymentJob>(
    `/api/v1/projects/${projectId}/deployments/${jobId}/cancel`,
    { method: "POST", body: "{}" },
  );
}

export function listDeployments(projectId: string) {
  return api<DeploymentJob[]>(`/api/v1/projects/${projectId}/deployments`);
}

export function getDeployment(projectId: string, jobId: string) {
  return api<DeploymentJob>(
    `/api/v1/projects/${projectId}/deployments/${jobId}`,
  );
}

/** SSE URL for live deployment logs (use with EventSource + credentials). */
export function deploymentStreamUrl(projectId: string, jobId: string) {
  return `${getApiUrl()}/api/v1/projects/${projectId}/deployments/${jobId}/stream`;
}

export function listReleases(projectId: string) {
  return api<Release[]>(`/api/v1/projects/${projectId}/releases`);
}

export function rollbackProject(projectId: string) {
  return api<Release>(`/api/v1/projects/${projectId}/rollback`, {
    method: "POST",
    body: "{}",
  });
}

export function fetchProjectMetrics(projectId: string) {
  return api<ProjectMetrics>(`/api/v1/projects/${projectId}/metrics`);
}

export function fetchProjectLogs(projectId: string) {
  return api<{ lines: string[]; source: string; truncated: boolean }>(
    `/api/v1/projects/${projectId}/logs`,
  );
}

export function listVariables(projectId: string) {
  return api<ProjectVariable[]>(`/api/v1/projects/${projectId}/variables`);
}

export function createVariable(
  projectId: string,
  body: {
    key: string;
    value: string;
    is_secret?: boolean;
    environment_name?: string;
  },
) {
  return api<ProjectVariable>(`/api/v1/projects/${projectId}/variables`, {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export function deleteVariable(projectId: string, variableId: string) {
  return api<void>(`/api/v1/projects/${projectId}/variables/${variableId}`, {
    method: "DELETE",
  });
}

export function validateDevDeployYaml(projectId: string, yaml_text: string) {
  return api<{ valid: boolean; errors: string[]; parsed: Record<string, unknown> }>(
    `/api/v1/projects/${projectId}/devdeploy-yaml/validate`,
    { method: "POST", body: JSON.stringify({ yaml_text }) },
  );
}

export function applyDevDeployYaml(projectId: string, yaml_text: string) {
  return api<Project>(`/api/v1/projects/${projectId}/devdeploy-yaml/apply`, {
    method: "POST",
    body: JSON.stringify({ yaml_text }),
  });
}

export function listEnvironments(projectId: string) {
  return api<ProjectEnvironment[]>(
    `/api/v1/projects/${projectId}/environments`,
  );
}

export function updateEnvironment(
  projectId: string,
  envId: string,
  body: Partial<{
    deploy_branch: string;
    replicas: number;
    approval_required: boolean;
  }>,
) {
  return api<ProjectEnvironment>(
    `/api/v1/projects/${projectId}/environments/${envId}`,
    { method: "PATCH", body: JSON.stringify(body) },
  );
}

export function listApprovals(projectId: string) {
  return api<Approval[]>(`/api/v1/projects/${projectId}/approvals`);
}

export function approveDeployment(projectId: string, jobId: string) {
  return api<DeploymentJob>(
    `/api/v1/projects/${projectId}/deployments/${jobId}/approve`,
    { method: "POST", body: "{}" },
  );
}

export function rejectDeployment(projectId: string, jobId: string) {
  return api<DeploymentJob>(
    `/api/v1/projects/${projectId}/deployments/${jobId}/reject`,
    { method: "POST", body: "{}" },
  );
}

export function listScans(projectId: string) {
  return api<Scan[]>(`/api/v1/projects/${projectId}/scans`);
}

export function fetchQuotas(projectId: string) {
  return api<{
    project_id: string;
    cpu_request: string;
    memory_request: string;
    cpu_limit: string;
    memory_limit: string;
    replicas: number;
    namespace: string;
  }>(`/api/v1/projects/${projectId}/quotas`);
}

export function fetchAnalytics(projectId: string) {
  return api<Analytics>(`/api/v1/projects/${projectId}/analytics`);
}

export function listPreviews(projectId: string) {
  return api<PreviewEnv[]>(`/api/v1/projects/${projectId}/previews`);
}

export function createPreview(projectId: string, pr_number: number) {
  return api<PreviewEnv>(`/api/v1/projects/${projectId}/previews`, {
    method: "POST",
    body: JSON.stringify({ pr_number }),
  });
}

export function listMembers() {
  return api<OrgMember[]>("/api/v1/orgs/me/members");
}

export function inviteMember(email: string, role: string) {
  return api<OrgMember>("/api/v1/orgs/me/members", {
    method: "POST",
    body: JSON.stringify({ email, role }),
  });
}

export function listAudit() {
  return api<AuditLog[]>("/api/v1/orgs/me/audit");
}

export function listApiKeys() {
  return api<ApiKey[]>("/api/v1/orgs/me/api-keys");
}

export function createApiKey(name: string) {
  return api<ApiKey & { token: string }>("/api/v1/orgs/me/api-keys", {
    method: "POST",
    body: JSON.stringify({ name }),
  });
}

export function revokeApiKey(id: string) {
  return api<void>(`/api/v1/orgs/me/api-keys/${id}`, { method: "DELETE" });
}

export function listStubs() {
  return api<StubFeature[]>("/api/v1/orgs/me/stubs");
}

export function updateStub(
  feature: string,
  body: { enabled?: boolean; config?: Record<string, unknown> },
) {
  return api<StubFeature>(`/api/v1/orgs/me/stubs/${feature}`, {
    method: "PUT",
    body: JSON.stringify(body),
  });
}

export function fetchBilling() {
  return api<BillingUsage>("/api/v1/orgs/me/billing");
}

export function upsertNotification(body: {
  kind: "email" | "webhook";
  enabled: boolean;
  target: string;
}) {
  return api("/api/v1/orgs/me/notifications", {
    method: "PUT",
    body: JSON.stringify(body),
  });
}

export function listNotifications() {
  return api<
    {
      id: string;
      kind: string;
      enabled: boolean;
      target: string;
    }[]
  >("/api/v1/orgs/me/notifications");
}

export function fetchPlatformFlags() {
  return api<{
    multi_cloud_enabled: boolean;
    ha_enabled: boolean;
    aws_mock_mode: boolean;
  }>("/api/v1/platform/flags");
}
