"use client";

import { Button } from "@/components/ui/button";
import { oauthStartUrl } from "@/lib/api";

const PROVIDERS = [
  { id: "google", label: "Google" },
  { id: "github", label: "GitHub" },
  { id: "apple", label: "Apple" },
  { id: "microsoft", label: "Microsoft" },
] as const;

export function OAuthButtons({ mockMode }: { mockMode: boolean }) {
  return (
    <div className="space-y-3">
      <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
        {PROVIDERS.map((provider) => (
          <Button
            key={provider.id}
            variant="outline"
            className="h-10 justify-center border-border/80 bg-white/50"
            render={
              <a href={oauthStartUrl(provider.id)} />
            }
          >
            Continue with {provider.label}
          </Button>
        ))}
      </div>
      {mockMode ? (
        <p className="font-mono text-xs text-muted-foreground">
          Mock OAuth on — providers create a local session without real credentials.
        </p>
      ) : null}
    </div>
  );
}
