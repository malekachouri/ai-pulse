"use client";

import { Loader2 } from "lucide-react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useState } from "react";
import { toast } from "sonner";

import { FormError, PasswordField, passwordProblem } from "@/components/auth/fields";
import { Button } from "@/components/ui/button";
import { api, errorMessage } from "@/lib/api";

function ResetForm() {
  const token = useSearchParams().get("token") ?? "";
  const router = useRouter();
  const [error, setError] = useState<string | null>(null);
  const [pending, setPending] = useState(false);

  if (!token)
    return (
      <>
        <h1 className="text-xl font-semibold">Invalid reset link</h1>
        <p className="mt-2 text-sm text-muted-foreground">This link is missing its token or has expired.</p>
        <Button asChild variant="brand" className="mt-6 w-full">
          <Link href="/forgot-password">Request a new link</Link>
        </Button>
      </>
    );

  return (
    <>
      <h1 className="text-xl font-semibold">Choose a new password</h1>
      <form
        className="mt-6 space-y-4"
        onSubmit={async (e) => {
          e.preventDefault();
          const f = new FormData(e.currentTarget);
          const pw = String(f.get("password"));
          const problem = passwordProblem(pw);
          if (problem) return setError(problem);
          if (pw !== String(f.get("confirm"))) return setError("Passwords don't match.");
          setPending(true);
          setError(null);
          try {
            await api.post("/auth/password-reset/confirm", { token, new_password: pw });
            toast.success("Password updated — please sign in");
            router.push("/login");
          } catch (err) {
            setError(errorMessage(err));
          } finally {
            setPending(false);
          }
        }}
      >
        <FormError message={error} />
        <PasswordField id="password" name="password" label="New password" autoComplete="new-password" required minLength={12} maxLength={128} hint="12+ characters, with 3 of: lowercase, uppercase, digit, symbol." />
        <PasswordField id="confirm" name="confirm" label="Confirm password" autoComplete="new-password" required />
        <Button type="submit" variant="brand" className="w-full" disabled={pending}>
          {pending && <Loader2 className="animate-spin" />} Update password
        </Button>
      </form>
    </>
  );
}

export default function ResetPasswordPage() {
  return (
    <Suspense>
      <ResetForm />
    </Suspense>
  );
}
