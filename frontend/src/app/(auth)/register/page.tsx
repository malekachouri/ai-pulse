"use client";

import { Loader2 } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { toast } from "sonner";

import { Field, FormError, PasswordField, passwordProblem } from "@/components/auth/fields";
import { Button } from "@/components/ui/button";
import { api, errorMessage } from "@/lib/api";
import { useAuth } from "@/lib/auth";

export default function RegisterPage() {
  const { login } = useAuth();
  const router = useRouter();
  const [error, setError] = useState<string | null>(null);
  const [pending, setPending] = useState(false);

  return (
    <>
      <h1 className="text-xl font-semibold">Create your account</h1>
      <p className="mt-1 text-sm text-muted-foreground">Personalised briefings, bookmarks and alerts.</p>
      <form
        className="mt-6 space-y-4"
        onSubmit={async (e) => {
          e.preventDefault();
          const f = new FormData(e.currentTarget);
          const email = String(f.get("email"));
          const password = String(f.get("password"));
          const problem = passwordProblem(password);
          if (problem) return setError(problem);
          if (password !== String(f.get("confirm"))) return setError("Passwords don't match.");
          setPending(true);
          setError(null);
          try {
            await api.post("/auth/register", { email, password, full_name: String(f.get("name")).trim() || null });
            await login(email, password);
            toast.success("Welcome to AI Pulse");
            router.push("/settings#preferences");
          } catch (err) {
            setError(errorMessage(err));
          } finally {
            setPending(false);
          }
        }}
      >
        <FormError message={error} />
        <Field id="name" name="name" label="Full name (optional)" autoComplete="name" maxLength={200} />
        <Field id="email" name="email" label="Email" type="email" autoComplete="email" required />
        <PasswordField
          id="password"
          name="password"
          label="Password"
          autoComplete="new-password"
          required
          minLength={12}
          maxLength={128}
          hint="12+ characters, with 3 of: lowercase, uppercase, digit, symbol."
        />
        <PasswordField id="confirm" name="confirm" label="Confirm password" autoComplete="new-password" required />
        <Button type="submit" variant="brand" className="w-full" disabled={pending}>
          {pending && <Loader2 className="animate-spin" />} Create account
        </Button>
      </form>
      <p className="mt-6 text-center text-sm text-muted-foreground">
        Already registered?{" "}
        <Link href="/login" className="font-medium text-primary hover:underline">
          Sign in
        </Link>
      </p>
    </>
  );
}
