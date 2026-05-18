import type { TrajectoryFrame } from "./types";

export function frameCount(frames: TrajectoryFrame[] | undefined): number {
  return frames?.length ?? 0;
}

export function firstObjectPosition(frames: TrajectoryFrame[] | undefined): number[] | undefined {
  return frames?.find((frame) => frame.object_position?.length)?.object_position;
}

export function lastObjectPosition(frames: TrajectoryFrame[] | undefined): number[] | undefined {
  return [...(frames ?? [])].reverse().find((frame) => frame.object_position?.length)?.object_position;
}

export function formatVector(vector: number[] | undefined): string {
  if (!vector?.length) return "n/a";
  return vector.map((value) => value.toFixed(3)).join(", ");
}
