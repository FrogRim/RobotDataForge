import { ApiError, EmptyState } from "../../components/common/ApiState";
import { StatusPill } from "../../components/common/StatusPill";
import { listDatasets, listTasks } from "../../lib/api";

export default async function DatasetsPage() {
  const [datasets, tasks] = await Promise.all([listDatasets(), listTasks()]);
  return (
    <main>
      <h1>Datasets</h1>
      {!tasks.ok ? <ApiError title="Task API unavailable" error={tasks.error} /> : (
        <section className="panel">
          <h2>Export Contract</h2>
          <p><code>only_success=true</code> exports curated successful trajectories.</p>
          <p><code>only_success=false</code> exports success and failed episodes.</p>
          <p>Use <code>POST /api/datasets/export</code> for now; form actions will be added after live API workflows are stable.</p>
        </section>
      )}
      {!datasets.ok ? <ApiError title="Dataset API unavailable" error={datasets.error} /> : !datasets.data.length ? (
        <EmptyState title="No datasets exported">
          <p>Run dataset export after at least one evaluated episode exists.</p>
        </EmptyState>
      ) : (
        <table>
          <thead><tr><th>Name</th><th>Status</th><th>Episodes</th><th>Success</th><th>Failed</th><th>Path</th></tr></thead>
          <tbody>
            {datasets.data.map((dataset) => (
              <tr key={dataset.id}>
                <td>{dataset.name}</td>
                <td><StatusPill value={dataset.status} /></td>
                <td>{dataset.num_episodes}</td>
                <td>{dataset.num_success}</td>
                <td>{dataset.num_failed}</td>
                <td><code>{dataset.export_path}</code></td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </main>
  );
}
