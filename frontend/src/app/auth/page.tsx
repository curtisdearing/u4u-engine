"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "../lib/auth";
import { login, signup } from "../lib/api";

export default function AuthPage() {
  const router = useRouter();
  const { setToken } = useAuth();
  const [mode, setMode] = useState<"login" | "signup">("login");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [consent, setConsent] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (mode === "signup" && !consent) {
      setError(
        "You must consent to the privacy policy before creating an account."
      );
      return;
    }

    setError(null);
    setLoading(true);

    try {
      const { access_token } =
        mode === "login"
          ? await login(email, password)
          : await signup(email, password);

      setToken(access_token);
      router.push("/");
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Authentication failed.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="flex items-center justify-center min-h-[70vh]">
      <div className="w-full max-w-sm space-y-6">
        <div className="text-center">
          <span className="text-4xl">🧬</span>
          <h1 className="text-2xl font-bold text-zinc-900 mt-2">
            {mode === "login" ? "Sign in" : "Create account"}
          </h1>
          <p className="text-sm text-zinc-500 mt-1">
            FMB Genomics Platform
          </p>
        </div>

        <div className="bg-white rounded-xl border border-zinc-200 shadow-sm p-6 space-y-4">
          {/* Mode tabs */}
          <div className="flex rounded-lg overflow-hidden border border-zinc-200">
            <button
              type="button"
              onClick={() => { setMode("login"); setError(null); }}
              className={`flex-1 py-2 text-sm font-medium transition-colors ${
                mode === "login"
                  ? "bg-blue-700 text-white"
                  : "bg-white text-zinc-600 hover:bg-zinc-50"
              }`}
            >
              Sign in
            </button>
            <button
              type="button"
              onClick={() => { setMode("signup"); setError(null); }}
              className={`flex-1 py-2 text-sm font-medium transition-colors ${
                mode === "signup"
                  ? "bg-blue-700 text-white"
                  : "bg-white text-zinc-600 hover:bg-zinc-50"
              }`}
            >
              Sign up
            </button>
          </div>

          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <label
                htmlFor="email"
                className="block text-sm font-medium text-zinc-700 mb-1"
              >
                Email
              </label>
              <input
                id="email"
                type="email"
                required
                autoComplete="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                className="w-full rounded-lg border border-zinc-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                placeholder="you@example.com"
              />
            </div>

            <div>
              <label
                htmlFor="password"
                className="block text-sm font-medium text-zinc-700 mb-1"
              >
                Password
              </label>
              <input
                id="password"
                type="password"
                required
                autoComplete={mode === "login" ? "current-password" : "new-password"}
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                className="w-full rounded-lg border border-zinc-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                placeholder="••••••••"
              />
            </div>

            {mode === "signup" && (
              <label className="flex items-start gap-2 cursor-pointer">
                <input
                  type="checkbox"
                  className="mt-0.5 h-4 w-4 rounded text-blue-600"
                  checked={consent}
                  onChange={(e) => setConsent(e.target.checked)}
                />
                <span className="text-xs text-zinc-600 leading-relaxed">
                  I understand that my genome data will be stored encrypted and
                  automatically deleted within 24 hours of job completion. I
                  consent to the{" "}
                  <a
                    href="https://flmanbiosci.net/privacy"
                    target="_blank"
                    rel="noopener noreferrer"
                    className="underline text-blue-700"
                  >
                    privacy policy
                  </a>
                  .
                </span>
              </label>
            )}

            {error && (
              <div className="rounded-md bg-red-50 border border-red-200 px-3 py-2 text-xs text-red-700">
                {error}
              </div>
            )}

            <button
              type="submit"
              disabled={loading}
              className="w-full rounded-lg bg-blue-700 text-white py-2.5 text-sm font-medium disabled:opacity-50 hover:bg-blue-800 transition-colors"
            >
              {loading
                ? "Please wait…"
                : mode === "login"
                  ? "Sign in"
                  : "Create account"}
            </button>
          </form>
        </div>

        <p className="text-center text-xs text-zinc-400">
          Your genomic data is never shared with third parties.
        </p>
      </div>
    </div>
  );
}
