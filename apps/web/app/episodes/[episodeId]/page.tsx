import { ApiError } from "../../../components/common/ApiState";
import { KeyValueTable } from "../../../components/common/KeyValueTable";
import { StatusPill } from "../../../components/common/StatusPill";
import { TrajectorySummary } from "../../../components/replay/TrajectorySummary";
import { getEpisode, getTrajectory } from "../../../lib/api";

export default async function EpisodeReplayPage({ params }: { params: Promise<{ episodeId: string }> }) {
  const { episodeId } = await params;
  const episodeResult = await getEpisode(episodeId);
  if (!episodeResult.ok) return <main><h1>Episode Replay</h1><ApiError title="Episode API unavailable" error={episodeResult.error} /></main>;
  const trajectoryResult = episodeResult.data.trajectory_id ? await getTrajectory(episodeResult.data.trajectory_id) : undefined;
  return (
    <main>
      <h1>Episode Replay</h1>
      <section className="panel">
        <h2>Episode</h2>
        <p><StatusPill value={episodeResult.data.status} /></p>
        <KeyValueTable
          data={{
            id: episodeResult.data.id,
            task_id: episodeResult.data.task_id,
            contributor_id: episodeResult.data.contributor_id,
            duration_sec: episodeResult.data.duration_sec,
            trajectory_id: episodeResult.data.trajectory_id,
            evaluation_id: episodeResult.data.evaluation_id,
          }}
        />
      </section>
      {trajectoryResult ? (
        trajectoryResult.ok ? <TrajectorySummary trajectory={trajectoryResult.data} /> : <ApiError title="Trajectory API unavailable" error={trajectoryResult.error} />
      ) : (
        <section className="panel"><h2>Trajectory</h2><p className="muted">No trajectory attached.</p></section>
      )}
    </main>
  );
}
