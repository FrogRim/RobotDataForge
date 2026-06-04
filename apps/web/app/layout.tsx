import "../styles/globals.css";
import type { ReactNode } from "react";
import Link from "next/link";

export const metadata = {
  title: "Robot Data Forge",
  description: "Isaac-first trajectory data pipeline",
};

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="en">
      <body>
        <header className="topbar">
          <Link href="/">Robot Data Forge</Link>
          <nav>
            <Link href="/tasks">Tasks</Link>
            <Link href="/datasets">Datasets</Link>
            <Link href="/admin">Admin</Link>
          </nav>
        </header>
        {children}
      </body>
    </html>
  );
}
