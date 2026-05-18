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
        <a href="/tasks">Tasks</a>
        <a href="/datasets">Datasets</a>
        <a href="/admin">Admin KPIs</a>
      </nav>
    </main>
  );
}
