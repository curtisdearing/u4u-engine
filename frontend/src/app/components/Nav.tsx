"use client";

import Link from "next/link";
import { useAuth } from "../lib/auth";

export function Nav() {
  const { token, logout } = useAuth();

  return (
    <header className="bg-white border-b border-zinc-200">
      <div className="mx-auto max-w-4xl px-4 h-14 flex items-center justify-between">
        <Link
          href="/"
          className="flex items-center gap-2 font-semibold text-zinc-900 hover:text-blue-700 transition-colors"
        >
          <span className="text-blue-700 text-lg">🧬</span>
          <span>FMB Genomics</span>
        </Link>

        <nav className="flex items-center gap-4 text-sm">
          {token ? (
            <>
              <Link
                href="/"
                className="text-zinc-600 hover:text-zinc-900 transition-colors"
              >
                New Analysis
              </Link>
              <button
                onClick={logout}
                className="text-zinc-500 hover:text-zinc-900 transition-colors"
              >
                Sign out
              </button>
            </>
          ) : (
            <Link
              href="/auth"
              className="rounded-full bg-blue-700 text-white px-4 py-1.5 text-sm font-medium hover:bg-blue-800 transition-colors"
            >
              Sign in
            </Link>
          )}
        </nav>
      </div>
    </header>
  );
}
