import { ApiError } from "../../../components/common/ApiState";
import { KeyValueTable } from "../../../components/common/KeyValueTable";
import { getTask } from "../../../lib/api";

export default async function CollectionPage({ params }: { params: Promise<{ taskId: string }> }) {
  const { taskId } = await params;
  const taskResult = await getTask(taskId);
  if (!taskResult.ok) return <main><h1>Collection Session</h1><ApiError title="Task API unavailable" error={taskResult.error} /></main>;
  return (
    <main>
      <h1>Collection Session</h1>
      <section className="panel">
        <h2>{taskResult.data.name}</h2>
        <KeyValueTable
          data={{
            task_id: taskResult.data.id,
            primary_adapter: "IsaacLabAdapter",
            input_device: "quest3_handtracking",
            runtime: "steamvr_openxr",
            simulator: "isaac_lab",
            robot: "franka",
          }}
        />
      </section>
      <section className="panel">
        <h2>Operator Command</h2>
        <pre>{`cd ~/robot-data-forge
uv run python scripts/record_isaac_episode.py
uv run python scripts/record_isaac_episode.py --api-base http://localhost:8000 --mock-submit`}</pre>
        <p className="muted">Mock submit is fallback/debug only. It does not prove real Quest/OpenXR frame capture.</p>
      </section>
    </main>
  );
}
