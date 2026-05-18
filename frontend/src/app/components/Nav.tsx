import Link from "next/link";

export function Nav() {
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
          <Link
            href="/jobs"
            className="text-zinc-600 hover:text-zinc-900 transition-colors"
          >
            History
          </Link>
          <Link
            href="/"
            className="text-zinc-600 hover:text-zinc-900 transition-colors"
          >
            New Analysis
          </Link>
        </nav>
      </div>
    </header>
  );
}
