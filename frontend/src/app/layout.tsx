import type { Metadata } from "next";
import "./globals.css";
import { AuthProvider } from "./lib/auth";
import { Nav } from "./components/Nav";

export const metadata: Metadata = {
  title: "Florida Man Bioscience — Genomics Platform",
  description:
    "Upload your genome file and receive a clinically prioritized variant report.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body className="antialiased min-h-screen bg-zinc-50">
        <AuthProvider>
          <Nav />
          <main className="mx-auto max-w-4xl px-4 py-8">{children}</main>
        </AuthProvider>
      </body>
    </html>
  );
}
