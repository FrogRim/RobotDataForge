import type { ReactNode } from "react";

export function ApiError({ title, error }: { title: string; error: string }) {
  return (
    <section className="panel danger">
      <h2>{title}</h2>
      <p>{error}</p>
      <code>NEXT_PUBLIC_API_BASE_URL</code>
    </section>
  );
}

export function EmptyState({ title, children }: { title: string; children?: ReactNode }) {
  return (
    <section className="panel">
      <h2>{title}</h2>
      {children}
    </section>
  );
}
