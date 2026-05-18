import "../styles/globals.css";
import type { ReactNode } from "react";

export const metadata = {
  title: "Robot Data Forge",
  description: "Isaac-first trajectory data pipeline",
};

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="en">
      <body>
        <header className="topbar">
          <a href="/">Robot Data Forge</a>
          <nav>
            <a href="/tasks">Tasks</a>
            <a href="/datasets">Datasets</a>
            <a href="/admin">Admin</a>
          </nav>
        </header>
        {children}
      </body>
    </html>
  );
}
