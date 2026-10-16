"use client";

import { Button } from "@/components/ui/button";
import { oauthStartUrl, type OAuthProviderStatus } from "@/lib/api";

const PROVIDER_LABELS: Record<string, string> = {
  google: "Google",
  github: "GitHub",
  apple: "Apple",
  microsoft: "Microsoft",
};

const DEFAULT_PROVIDERS = ["github", "google", "apple", "microsoft"] as const;

export function OAuthButtons({
  mockMode,
  oauthProviders,
}: {
  mockMode: boolean;
  oauthProviders: OAuthProviderStatus[];
}) {
  const byId = new Map(oauthProviders.map((p) => [p.id, p]));
  const ordered = [
    ...DEFAULT_PROVIDERS.filter((id) => byId.has(id) || oauthProviders.length === 0),
    ...oauthProviders.map((p) => p.id).filter((id) => !(DEFAULT_PROVIDERS as readonly string[]).includes(id)),
  ];
  const ids = ordered.length ? ordered : [...DEFAULT_PROVIDERS];

  return (
    <div className="space-y-3">
      <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
        {ids.map((id) => {
          const status = byId.get(id);
          const label = PROVIDER_LABELS[id] ?? id;
          const configured = status?.configured ?? false;
          const enabled = mockMode || configured;
          const href = oauthStartUrl(id);

          if (!enabled) {
            return (
              <Button
                key={id}
                variant="outline"
                disabled
                className="h-10 justify-center border-border/80 bg-white/30 text-muted-foreground"
                title={`${label} OAuth is not configured`}
              >
                {label} — not configured
              </Button>
            );
          }

          return (
            <Button
              key={id}
              variant="outline"
              className="h-10 justify-center border-border/80 bg-white/50"
              render={<a href={href} />}
            >
              Continue with {label}
              {mockMode ? " (demo)" : ""}
            </Button>
          );
        })}
      </div>
      {mockMode ? (
        <p className="font-mono text-xs text-muted-foreground">
          Demo OAuth on — providers create a local session without real
          credentials. Set AUTH_MOCK_MODE=false for live provider sign-in.
        </p>
      ) : (
        <p className="font-mono text-xs text-muted-foreground">
          Sign-in providers above use real OAuth. Account login is separate from
          installing the GitHub App to list or attach repositories.
        </p>
      )}
    </div>
  );
}
