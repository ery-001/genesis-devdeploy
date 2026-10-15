const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://127.0.0.1:8741";

export type AuthUser = {
  id: string;
  email: string | null;
  phone: string | null;
  display_name: string | null;
  avatar_url: string | null;
  providers: string[];
};

export type AuthConfig = {
  mock_mode: boolean;
  providers: string[];
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
  github_repo_full_name: string | null;
  default_branch: string | null;
  dockerfile_path: string | null;
  created_at: string;
  updated_at: string;
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

export function updateProject(
  id: string,
  body: { name?: string; slug?: string; description?: string },
) {
  return api<Project>(`/api/v1/projects/${id}`, {
    method: "PATCH",
    body: JSON.stringify(body),
  });
}

export function deleteProject(id: string) {
  return api<void>(`/api/v1/projects/${id}`, { method: "DELETE" });
}
