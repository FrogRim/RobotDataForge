import { ApiError, EmptyState } from "../../components/common/ApiState";
import { StatusPill } from "../../components/common/StatusPill";
import { listTasks } from "../../lib/api";

export default function TasksPage() {
  return <Tasks />;
}

async function Tasks() {
  const result = await listTasks();
  if (!result.ok) return <main><h1>Tasks</h1><ApiError title="Tasks API unavailable" error={result.error} /></main>;
  return (
    <main>
      <h1>Tasks</h1>
      {!result.data.length ? (
        <EmptyState title="No tasks yet">
          <p>Create a task through <code>POST /api/tasks</code>.</p>
        </EmptyState>
      ) : (
        <table>
          <thead>
            <tr>
              <th>Name</th>
              <th>Type</th>
              <th>Status</th>
              <th>Links</th>
            </tr>
          </thead>
          <tbody>
            {result.data.map((task) => (
              <tr key={task.id}>
                <td>{task.name}</td>
                <td>{task.task_type}</td>
                <td><StatusPill value={task.status} /></td>
                <td>
                  <a href={`/tasks/${task.id}`}>detail</a>{" "}
                  <a href={`/play/${task.id}`}>collect</a>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </main>
  );
}
