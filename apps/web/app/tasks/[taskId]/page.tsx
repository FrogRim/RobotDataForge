import { ApiError } from "../../../components/common/ApiState";
import { KeyValueTable } from "../../../components/common/KeyValueTable";
import { StatusPill } from "../../../components/common/StatusPill";
import { getTask, listEpisodes } from "../../../lib/api";

export default async function TaskDetailPage({ params }: { params: Promise<{ taskId: string }> }) {
  const { taskId } = await params;
  const [taskResult, episodeResult] = await Promise.all([getTask(taskId), listEpisodes(taskId)]);
  if (!taskResult.ok) return <main><h1>Task Detail</h1><ApiError title="Task API unavailable" error={taskResult.error} /></main>;
  return (
    <main>
      <h1>{taskResult.data.name}</h1>
      <section className="panel">
        <h2>Task</h2>
        <p><StatusPill value={taskResult.data.status} /></p>
        <KeyValueTable
          data={{
            id: taskResult.data.id,
            task_type: taskResult.data.task_type,
            description: taskResult.data.description,
            environment_config: taskResult.data.environment_config,
            success_criteria: taskResult.data.success_criteria,
          }}
        />
      </section>
      <section className="panel">
        <h2>Episodes</h2>
        {!episodeResult.ok ? (
          <p className="danger-text">{episodeResult.error}</p>
        ) : episodeResult.data.length ? (
          <table>
            <thead><tr><th>ID</th><th>Status</th><th>Trajectory</th></tr></thead>
            <tbody>
              {episodeResult.data.map((episode) => (
                <tr key={episode.id}>
                  <td><a href={`/episodes/${episode.id}`}>{episode.id}</a></td>
                  <td><StatusPill value={episode.status} /></td>
                  <td>{episode.trajectory_id ?? "n/a"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        ) : (
          <p className="muted">No episodes.</p>
        )}
      </section>
    </main>
  );
}
