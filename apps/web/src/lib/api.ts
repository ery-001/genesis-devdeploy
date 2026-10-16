const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://127.0.0.1:8741";

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

async function api<T>(
  path: string,
  init: RequestInit = {},
): Promise<T> {
  const res = await fetch(`${API_URL}${path}`, {
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

export function getApiUrl() {
  return API_URL;
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
  return `${API_URL}/api/v1/auth/oauth/${provider}/start`;
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
  created_at: string;
  updated_at: string;
};

export type GitHubConfig = {
  mock_mode: boolean;
  app_configured: boolean;
  app_slug: string;
  install_url: string | null;
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
  simulate_failure: boolean;
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
  status: string;
  is_current: boolean;
  created_at: string;
};

export type ProjectMetrics = {
  project_id: string;
  cpu_percent: number;
  memory_mib: number;
  uptime_seconds: number;
  requests_per_minute: number;
  source: string;
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
  body: {
    name?: string;
    slug?: string;
    description?: string;
    deploy_branch?: string;
    dockerfile_path?: string;
  },
) {
  return api<Project>(`/api/v1/projects/${id}`, {
    method: "PATCH",
    body: JSON.stringify(body),
  });
}

export function deployProject(
  projectId: string,
  body: { simulate_failure?: boolean } = {},
) {
  return api<DeploymentJob>(`/api/v1/projects/${projectId}/deploy`, {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export function listDeployments(projectId: string) {
  return api<DeploymentJob[]>(`/api/v1/projects/${projectId}/deployments`);
}

export function getDeployment(projectId: string, jobId: string) {
  return api<DeploymentJob>(
    `/api/v1/projects/${projectId}/deployments/${jobId}`,
  );
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
