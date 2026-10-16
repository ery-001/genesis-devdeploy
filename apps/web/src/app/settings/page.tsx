"use client";

import { useEffect, useState } from "react";

import { AppShell } from "@/components/app-shell";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { useRequireUser } from "@/hooks/use-require-user";
import {
  createApiKey,
  fetchBilling,
  fetchPlatformFlags,
  inviteMember,
  listApiKeys,
  listAudit,
  listMembers,
  listNotifications,
  listStubs,
  revokeApiKey,
  updateStub,
  upsertNotification,
  type ApiKey,
  type AuditLog,
  type BillingUsage,
  type OrgMember,
  type StubFeature,
} from "@/lib/api";

export default function SettingsPage() {
  const { user, loading } = useRequireUser("/settings");
  const [members, setMembers] = useState<OrgMember[]>([]);
  const [audit, setAudit] = useState<AuditLog[]>([]);
  const [keys, setKeys] = useState<ApiKey[]>([]);
  const [stubs, setStubs] = useState<StubFeature[]>([]);
  const [billing, setBilling] = useState<BillingUsage | null>(null);
  const [flags, setFlags] = useState<{
    multi_cloud_enabled: boolean;
    ha_enabled: boolean;
    aws_mock_mode: boolean;
  } | null>(null);
  const [inviteEmail, setInviteEmail] = useState("");
  const [inviteRole, setInviteRole] = useState("developer");
  const [keyName, setKeyName] = useState("cli");
  const [newToken, setNewToken] = useState<string | null>(null);
  const [emailTarget, setEmailTarget] = useState("");
  const [webhookTarget, setWebhookTarget] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [info, setInfo] = useState<string | null>(null);

  function refresh() {
    listMembers().then(setMembers).catch(() => setMembers([]));
    listAudit().then(setAudit).catch(() => setAudit([]));
    listApiKeys().then(setKeys).catch(() => setKeys([]));
    listStubs().then(setStubs).catch(() => setStubs([]));
    fetchBilling().then(setBilling).catch(() => setBilling(null));
    fetchPlatformFlags().then(setFlags).catch(() => setFlags(null));
    listNotifications()
      .then((rows) => {
        const email = rows.find((r) => r.kind === "email");
        const wh = rows.find((r) => r.kind === "webhook");
        if (email) setEmailTarget(email.target);
        if (wh) setWebhookTarget(wh.target);
      })
      .catch(() => undefined);
  }

  useEffect(() => {
    if (user) refresh();
  }, [user]);

  if (loading || !user) {
    return (
      <div className="dd-atmosphere flex min-h-full flex-1 items-center justify-center">
        <p className="text-sm text-muted-foreground">Checking session…</p>
      </div>
    );
  }

  return (
    <AppShell user={user}>
      <div className="space-y-10">
        <div>
          <h1 className="font-[family-name:var(--font-display)] text-3xl font-bold tracking-tight text-ink">
            Settings
          </h1>
          <p className="mt-2 text-sm text-muted-foreground">
            Team roles, notifications, API keys, audit log, and commercial stubs.
          </p>
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

        <section className="space-y-4 border border-border/70 bg-white/40 p-6">
          <p className="font-mono text-xs uppercase tracking-[0.14em] text-muted-foreground">
            Team
          </p>
          <div className="flex flex-wrap items-end gap-3">
            <div className="space-y-2">
              <Label htmlFor="invite-email">Invite email</Label>
              <Input
                id="invite-email"
                value={inviteEmail}
                onChange={(e) => setInviteEmail(e.target.value)}
                placeholder="dev@example.com"
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="invite-role">Role</Label>
              <select
                id="invite-role"
                className="h-10 rounded-md border border-border bg-white/70 px-3 text-sm"
                value={inviteRole}
                onChange={(e) => setInviteRole(e.target.value)}
              >
                {["viewer", "developer", "admin", "owner"].map((r) => (
                  <option key={r} value={r}>
                    {r}
                  </option>
                ))}
              </select>
            </div>
            <Button
              className="h-10"
              onClick={async () => {
                setError(null);
                try {
                  await inviteMember(inviteEmail, inviteRole);
                  setInviteEmail("");
                  setInfo("Member invited");
                  refresh();
                } catch (err) {
                  setError(err instanceof Error ? err.message : "Invite failed");
                }
              }}
            >
              Invite
            </Button>
          </div>
          <ul className="divide-y divide-border/60 border border-border/50">
            {members.map((m) => (
              <li key={m.id} className="flex justify-between px-4 py-3 text-sm">
                <span>
                  {m.display_name || m.email || m.user_id.slice(0, 8)}
                </span>
                <span className="font-mono text-xs uppercase text-muted-foreground">
                  {m.role}
                </span>
              </li>
            ))}
          </ul>
        </section>

        <section className="space-y-4 border border-border/70 bg-white/40 p-6">
          <p className="font-mono text-xs uppercase tracking-[0.14em] text-muted-foreground">
            Notifications
          </p>
          <div className="grid gap-4 sm:grid-cols-2">
            <div className="space-y-2">
              <Label>Email stub target</Label>
              <Input
                value={emailTarget}
                onChange={(e) => setEmailTarget(e.target.value)}
                placeholder="ops@example.com"
              />
              <Button
                variant="outline"
                className="h-9"
                onClick={async () => {
                  await upsertNotification({
                    kind: "email",
                    enabled: true,
                    target: emailTarget || "ops@example.com",
                  });
                  setInfo("Email notifier saved (stub — logs only)");
                }}
              >
                Save email
              </Button>
            </div>
            <div className="space-y-2">
              <Label>Webhook URL</Label>
              <Input
                value={webhookTarget}
                onChange={(e) => setWebhookTarget(e.target.value)}
                placeholder="https://example.com/hooks/deploy"
              />
              <Button
                variant="outline"
                className="h-9"
                onClick={async () => {
                  await upsertNotification({
                    kind: "webhook",
                    enabled: true,
                    target: webhookTarget,
                  });
                  setInfo("Webhook notifier saved");
                }}
              >
                Save webhook
              </Button>
            </div>
          </div>
        </section>

        <section className="space-y-4 border border-border/70 bg-white/40 p-6">
          <p className="font-mono text-xs uppercase tracking-[0.14em] text-muted-foreground">
            API keys
          </p>
          <div className="flex flex-wrap items-end gap-3">
            <div className="space-y-2">
              <Label htmlFor="key-name">Name</Label>
              <Input
                id="key-name"
                value={keyName}
                onChange={(e) => setKeyName(e.target.value)}
              />
            </div>
            <Button
              className="h-10"
              onClick={async () => {
                const created = await createApiKey(keyName);
                setNewToken(created.token);
                setInfo("Copy the token now — it is shown once.");
                refresh();
              }}
            >
              Create key
            </Button>
          </div>
          {newToken ? (
            <pre className="overflow-x-auto rounded border border-border/60 bg-ink/[0.03] p-3 font-mono text-xs">
              {newToken}
            </pre>
          ) : null}
          <ul className="divide-y divide-border/60 border border-border/50">
            {keys.map((k) => (
              <li
                key={k.id}
                className="flex flex-wrap items-center justify-between gap-2 px-4 py-3 text-sm"
              >
                <span>
                  {k.name}{" "}
                  <span className="font-mono text-xs text-muted-foreground">
                    {k.token_prefix}…
                  </span>
                </span>
                {!k.revoked_at ? (
                  <Button
                    variant="outline"
                    className="h-8"
                    onClick={async () => {
                      await revokeApiKey(k.id);
                      refresh();
                    }}
                  >
                    Revoke
                  </Button>
                ) : (
                  <span className="font-mono text-[11px] uppercase text-muted-foreground">
                    revoked
                  </span>
                )}
              </li>
            ))}
          </ul>
        </section>

        <section className="space-y-4 border border-border/70 bg-white/40 p-6">
          <p className="font-mono text-xs uppercase tracking-[0.14em] text-muted-foreground">
            Usage / billing (stub)
          </p>
          {billing ? (
            <dl className="grid gap-3 text-sm sm:grid-cols-4">
              <div>
                <dt className="text-muted-foreground">Plan</dt>
                <dd className="font-mono text-ink">{billing.plan}</dd>
              </div>
              <div>
                <dt className="text-muted-foreground">Build minutes</dt>
                <dd className="font-mono text-ink">{billing.build_minutes}</dd>
              </div>
              <div>
                <dt className="text-muted-foreground">Deploys</dt>
                <dd className="font-mono text-ink">{billing.deploy_count}</dd>
              </div>
              <div>
                <dt className="text-muted-foreground">Bandwidth GB</dt>
                <dd className="font-mono text-ink">{billing.bandwidth_gb}</dd>
              </div>
            </dl>
          ) : (
            <p className="text-sm text-muted-foreground">Loading meters…</p>
          )}
        </section>

        <section className="space-y-4 border border-border/70 bg-white/40 p-6">
          <p className="font-mono text-xs uppercase tracking-[0.14em] text-muted-foreground">
            Commercial / HA stubs
          </p>
          {flags ? (
            <p className="font-mono text-xs text-muted-foreground">
              multi_cloud={String(flags.multi_cloud_enabled)} · ha=
              {String(flags.ha_enabled)} · aws_mock={String(flags.aws_mock_mode)}
            </p>
          ) : null}
          <ul className="space-y-3">
            {stubs.map((s) => (
              <li
                key={s.feature}
                className="flex flex-wrap items-start justify-between gap-3 border border-border/50 px-4 py-3"
              >
                <div>
                  <p className="font-medium text-ink">{s.feature}</p>
                  <p className="text-sm text-muted-foreground">
                    {s.coming_soon_reason || s.status}
                  </p>
                </div>
                <label className="flex items-center gap-2 text-sm">
                  <input
                    type="checkbox"
                    checked={s.enabled}
                    onChange={async (e) => {
                      await updateStub(s.feature, { enabled: e.target.checked });
                      refresh();
                    }}
                  />
                  Intent on
                </label>
              </li>
            ))}
          </ul>
        </section>

        <section className="space-y-3 border border-dashed border-border bg-white/30 p-6">
          <p className="font-mono text-xs uppercase tracking-[0.14em] text-muted-foreground">
            Org audit log
          </p>
          {audit.length === 0 ? (
            <p className="text-sm text-muted-foreground">No events yet.</p>
          ) : (
            <ul className="max-h-80 divide-y divide-border/60 overflow-y-auto border border-border/50">
              {audit.map((a) => (
                <li key={a.id} className="px-4 py-3 text-sm">
                  <p className="font-mono text-xs text-ink">
                    {a.action} · {a.resource_type}
                    {a.resource_id ? ` · ${a.resource_id.slice(0, 8)}` : ""}
                  </p>
                  <p className="text-muted-foreground">
                    {a.detail || "—"} · {new Date(a.created_at).toLocaleString()}
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
