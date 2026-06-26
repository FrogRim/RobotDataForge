import Link from "next/link";

export default function HomePage() {
  return (
    <main>
      <h1>Robot Data Forge</h1>
      <p>Isaac-first trajectory collection, validation, curation, and export.</p>
      <section className="panel">
        <h2>Current Phase</h2>
        <p>MVP-0 backend and adapter boundary are implemented. Frontend pages expose API state for operator debugging.</p>
      </section>
      <nav className="nav-grid">
        <Link href="/tasks">Tasks</Link>
        <Link href="/datasets">Datasets</Link>
        <Link href="/file-drop">File-Drop Evaluator</Link>
        <Link href="/admin">Admin KPIs</Link>
      </nav>
    </main>
  );
}
