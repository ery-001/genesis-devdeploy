"use client";

import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { useEffect, useState } from "react";

import { OAuthButtons } from "@/components/auth/oauth-buttons";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Separator } from "@/components/ui/separator";
import {
  fetchAuthConfig,
  login,
  register,
  requestMagicLink,
  startPhoneOtp,
  verifyMagicLink,
  verifyPhoneOtp,
} from "@/lib/api";

type Mode = "login" | "signup";

export function AuthForms({ mode }: { mode: Mode }) {
  const router = useRouter();
  const searchParams = useSearchParams();
  const [mockMode, setMockMode] = useState(true);
  const [tab, setTab] = useState<"password" | "magic" | "phone">("password");
  const [error, setError] = useState<string | null>(null);
  const [info, setInfo] = useState<string | null>(null);
  const [pending, setPending] = useState(false);

  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [displayName, setDisplayName] = useState("");
  const [magicToken, setMagicToken] = useState("");
  const [phone, setPhone] = useState("");
  const [otp, setOtp] = useState("");
  const [otpSent, setOtpSent] = useState(false);

  useEffect(() => {
    fetchAuthConfig()
      .then((cfg) => setMockMode(cfg.mock_mode))
      .catch(() => setMockMode(true));

    const err = searchParams.get("error");
    if (err) setError(err.replaceAll("_", " "));
  }, [searchParams]);

  async function onPasswordSubmit(e: React.FormEvent) {
    e.preventDefault();
    setPending(true);
    setError(null);
    setInfo(null);
    try {
      if (mode === "signup") {
        await register({
          email,
          password,
          display_name: displayName || undefined,
        });
      } else {
        await login({ email, password });
      }
      router.push("/dashboard");
      router.refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Authentication failed");
    } finally {
      setPending(false);
    }
  }

  async function onMagicRequest(e: React.FormEvent) {
    e.preventDefault();
    setPending(true);
    setError(null);
    setInfo(null);
    try {
      const res = await requestMagicLink(email);
      if (res.magic_link_token) {
        setMagicToken(res.magic_link_token);
        setInfo("Mock mode: paste or use the issued token below to finish sign-in.");
      } else {
        setInfo(res.message);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not send magic link");
    } finally {
      setPending(false);
    }
  }

  async function onMagicVerify(e: React.FormEvent) {
    e.preventDefault();
    setPending(true);
    setError(null);
    try {
      await verifyMagicLink(magicToken);
      router.push("/dashboard");
      router.refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Invalid magic link");
    } finally {
      setPending(false);
    }
  }

  async function onPhoneStart(e: React.FormEvent) {
    e.preventDefault();
    setPending(true);
    setError(null);
    setInfo(null);
    try {
      const res = await startPhoneOtp(phone);
      setOtpSent(true);
      setInfo(
        res.otp_hint
          ? `Mock OTP ready — use code ${res.otp_hint}`
          : res.message,
      );
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not send OTP");
    } finally {
      setPending(false);
    }
  }

  async function onPhoneVerify(e: React.FormEvent) {
    e.preventDefault();
    setPending(true);
    setError(null);
    try {
      await verifyPhoneOtp(phone, otp);
      router.push("/dashboard");
      router.refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Invalid OTP");
    } finally {
      setPending(false);
    }
  }

  return (
    <div className="space-y-6">
      <OAuthButtons mockMode={mockMode} />

      <div className="flex items-center gap-3">
        <Separator className="flex-1" />
        <span className="font-mono text-[11px] uppercase tracking-[0.14em] text-muted-foreground">
          or with email / phone
        </span>
        <Separator className="flex-1" />
      </div>

      <div className="flex gap-2">
        {(
          [
            ["password", "Password"],
            ["magic", "Magic link"],
            ["phone", "Phone"],
          ] as const
        ).map(([id, label]) => (
          <button
            key={id}
            type="button"
            onClick={() => setTab(id)}
            className={`rounded-md px-3 py-1.5 text-sm transition-colors ${
              tab === id
                ? "bg-ink text-white"
                : "bg-white/40 text-muted-foreground hover:text-ink"
            }`}
          >
            {label}
          </button>
        ))}
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

      {tab === "password" ? (
        <form onSubmit={onPasswordSubmit} className="space-y-4">
          {mode === "signup" ? (
            <div className="space-y-2">
              <Label htmlFor="displayName">Display name</Label>
              <Input
                id="displayName"
                value={displayName}
                onChange={(e) => setDisplayName(e.target.value)}
                placeholder="Ada Lovelace"
                className="h-10 bg-white/60"
              />
            </div>
          ) : null}
          <div className="space-y-2">
            <Label htmlFor="email">Email</Label>
            <Input
              id="email"
              type="email"
              required
              autoComplete="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="you@company.com"
              className="h-10 bg-white/60"
            />
          </div>
          <div className="space-y-2">
            <Label htmlFor="password">Password</Label>
            <Input
              id="password"
              type="password"
              required
              minLength={8}
              autoComplete={mode === "signup" ? "new-password" : "current-password"}
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="At least 8 characters"
              className="h-10 bg-white/60"
            />
          </div>
          <Button
            type="submit"
            disabled={pending}
            className="h-11 w-full bg-signal text-signal-foreground hover:bg-signal/90"
          >
            {pending
              ? "Working…"
              : mode === "signup"
                ? "Create account"
                : "Sign in"}
          </Button>
        </form>
      ) : null}

      {tab === "magic" ? (
        <div className="space-y-4">
          <form onSubmit={onMagicRequest} className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="magic-email">Email</Label>
              <Input
                id="magic-email"
                type="email"
                required
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="you@company.com"
                className="h-10 bg-white/60"
              />
            </div>
            <Button
              type="submit"
              disabled={pending}
              className="h-11 w-full bg-signal text-signal-foreground hover:bg-signal/90"
            >
              {pending ? "Sending…" : "Send magic link"}
            </Button>
          </form>
          <form onSubmit={onMagicVerify} className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="magic-token">Magic link token</Label>
              <Input
                id="magic-token"
                value={magicToken}
                onChange={(e) => setMagicToken(e.target.value)}
                placeholder="Paste token from email / mock response"
                className="h-10 bg-white/60 font-mono text-sm"
              />
            </div>
            <Button
              type="submit"
              variant="outline"
              disabled={pending || !magicToken}
              className="h-11 w-full"
            >
              Verify token
            </Button>
          </form>
        </div>
      ) : null}

      {tab === "phone" ? (
        <div className="space-y-4">
          <form onSubmit={onPhoneStart} className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="phone">Phone number</Label>
              <Input
                id="phone"
                type="tel"
                required
                value={phone}
                onChange={(e) => setPhone(e.target.value)}
                placeholder="+1 555 123 4567"
                className="h-10 bg-white/60"
              />
            </div>
            <Button
              type="submit"
              disabled={pending}
              className="h-11 w-full bg-signal text-signal-foreground hover:bg-signal/90"
            >
              {pending ? "Sending…" : "Send SMS code"}
            </Button>
          </form>
          {otpSent ? (
            <form onSubmit={onPhoneVerify} className="space-y-4">
              <div className="space-y-2">
                <Label htmlFor="otp">One-time code</Label>
                <Input
                  id="otp"
                  inputMode="numeric"
                  required
                  value={otp}
                  onChange={(e) => setOtp(e.target.value)}
                  placeholder={mockMode ? "000000" : "6-digit code"}
                  className="h-10 bg-white/60 font-mono tracking-widest"
                />
              </div>
              <Button type="submit" disabled={pending} className="h-11 w-full">
                Verify phone
              </Button>
            </form>
          ) : null}
        </div>
      ) : null}

      <p className="text-sm text-muted-foreground">
        {mode === "login" ? (
          <>
            New here?{" "}
            <Link href="/signup" className="font-medium text-ink underline-offset-4 hover:underline">
              Create an account
            </Link>
          </>
        ) : (
          <>
            Already have an account?{" "}
            <Link href="/login" className="font-medium text-ink underline-offset-4 hover:underline">
              Sign in
            </Link>
          </>
        )}
      </p>
    </div>
  );
}
