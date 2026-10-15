import { Suspense } from "react";
import Link from "next/link";

import { AuthForms } from "@/components/auth/auth-forms";
import { AuthShell } from "@/components/auth/auth-shell";

export default function SignupPage() {
  return (
    <AuthShell
      title="Create your account"
      subtitle="One DevDeploy identity can link email, phone, and major OAuth providers over time."
      footer={
        <>
          By continuing you agree to use DevDeploy for approved repos and platform workflows.{" "}
          <Link href="/" className="text-ink underline-offset-4 hover:underline">
            Back home
          </Link>
        </>
      }
    >
      <Suspense fallback={<p className="text-sm text-muted-foreground">Loading…</p>}>
        <AuthForms mode="signup" />
      </Suspense>
    </AuthShell>
  );
}
