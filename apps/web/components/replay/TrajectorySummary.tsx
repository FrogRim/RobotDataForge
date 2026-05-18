import type { TrajectoryRead } from "../../lib/types";
import { firstObjectPosition, formatVector, frameCount, lastObjectPosition } from "../../lib/trajectory";
import { KeyValueTable } from "../common/KeyValueTable";

export function TrajectorySummary({ trajectory }: { trajectory: TrajectoryRead }) {
  return (
    <section className="panel">
      <h2>Trajectory</h2>
      <KeyValueTable
        data={{
          id: trajectory.id,
          schema_version: trajectory.schema_version,
          frames: frameCount(trajectory.frames),
          input_device: trajectory.source.input_device,
          runtime: trajectory.source.runtime,
          simulator: trajectory.source.simulator,
          robot: trajectory.source.robot,
          task_name: trajectory.source.task_name,
          first_object_position: formatVector(firstObjectPosition(trajectory.frames)),
          last_object_position: formatVector(lastObjectPosition(trajectory.frames)),
        }}
      />
    </section>
  );
}
