"use client";

import { Loader2, MailCheck } from "lucide-react";
import Link from "next/link";
import { useState } from "react";

import { Field, FormError } from "@/components/auth/fields";
import { Button } from "@/components/ui/button";
import { api, errorMessage } from "@/lib/api";

export default function ForgotPasswordPage() {
  const [sent, setSent] = useState(false);
  const [devToken, setDevToken] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [pending, setPending] = useState(false);

  if (sent)
    return (
      <div className="text-center">
        <MailCheck className="mx-auto mb-3 size-8 text-primary" />
        <h1 className="text-lg font-semibold">Check your email</h1>
        <p className="mt-2 text-sm text-muted-foreground">
          If an account exists for that address, we sent instructions to reset your password.
        </p>
        {devToken && (
          <p className="mt-4 rounded-lg bg-amber-500/15 p-3 text-left text-xs text-amber-800 dark:text-amber-200">
            Development mode (EXPOSE_RESET_TOKEN): continue at{" "}
            <Link className="underline" href={`/reset-password?token=${encodeURIComponent(devToken)}`}>
              the reset page
            </Link>
            .
          </p>
        )}
        <Link href="/login" className="mt-6 inline-block text-sm text-primary hover:underline">
          Back to sign in
        </Link>
      </div>
    );

  return (
    <>
      <h1 className="text-xl font-semibold">Reset your password</h1>
      <p className="mt-1 text-sm text-muted-foreground">We&apos;ll email you a reset link.</p>
      <form
        className="mt-6 space-y-4"
        onSubmit={async (e) => {
          e.preventDefault();
          setPending(true);
          setError(null);
          try {
            const res = await api.post<{ reset_token: string | null }>("/auth/password-reset/request", {
              email: String(new FormData(e.currentTarget).get("email")),
            });
            setDevToken(res.reset_token);
            setSent(true);
          } catch (err) {
            setError(errorMessage(err));
          } finally {
            setPending(false);
          }
        }}
      >
        <FormError message={error} />
        <Field id="email" name="email" label="Email" type="email" autoComplete="email" required />
        <Button type="submit" variant="brand" className="w-full" disabled={pending}>
          {pending && <Loader2 className="animate-spin" />} Send reset link
        </Button>
      </form>
      <p className="mt-6 text-center text-sm">
        <Link href="/login" className="text-primary hover:underline">
          Back to sign in
        </Link>
      </p>
    </>
  );
}
