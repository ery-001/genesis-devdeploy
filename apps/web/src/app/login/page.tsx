import { Suspense } from "react";
import Link from "next/link";

import { AuthForms } from "@/components/auth/auth-forms";
import { AuthShell } from "@/components/auth/auth-shell";

export default function LoginPage() {
  return (
    <AuthShell
      title="Sign in"
      subtitle="Use Google, GitHub, Apple, Microsoft, email, or phone — then land in your control plane."
      footer={
        <>
          GitHub App repository install is separate from sign-in and lands in a later milestone.{" "}
          <Link href="/" className="text-ink underline-offset-4 hover:underline">
            Back home
          </Link>
        </>
      }
    >
      <Suspense fallback={<p className="text-sm text-muted-foreground">Loading…</p>}>
        <AuthForms mode="login" />
      </Suspense>
    </AuthShell>
  );
}
