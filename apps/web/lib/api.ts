import type { AdminKpis, DatasetRead, EpisodeRead, TaskRead, TaskSummary, TrajectoryRead } from "./types";

export const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

export type ApiResult<T> =
  | { ok: true; data: T }
  | { ok: false; error: string };

async function request<T>(path: string, init?: RequestInit): Promise<ApiResult<T>> {
  try {
    const response = await fetch(`${API_BASE_URL}${path}`, {
      ...init,
      cache: "no-store",
      headers: {
        "Content-Type": "application/json",
        ...(init?.headers ?? {}),
      },
    });
    if (!response.ok) {
      return { ok: false, error: `${response.status} ${response.statusText}` };
    }
    return { ok: true, data: (await response.json()) as T };
  } catch (error) {
    return { ok: false, error: error instanceof Error ? error.message : "Unknown API error" };
  }
}

export function listTasks(): Promise<ApiResult<TaskSummary[]>> {
  return request<TaskSummary[]>("/api/tasks");
}

export function getTask(taskId: string): Promise<ApiResult<TaskRead>> {
  return request<TaskRead>(`/api/tasks/${taskId}`);
}

export function listEpisodes(taskId?: string): Promise<ApiResult<EpisodeRead[]>> {
  const query = taskId ? `?task_id=${encodeURIComponent(taskId)}` : "";
  return request<EpisodeRead[]>(`/api/episodes${query}`);
}

export function getEpisode(episodeId: string): Promise<ApiResult<EpisodeRead>> {
  return request<EpisodeRead>(`/api/episodes/${episodeId}`);
}

export function getTrajectory(trajectoryId: string): Promise<ApiResult<TrajectoryRead>> {
  return request<TrajectoryRead>(`/api/trajectories/${trajectoryId}`);
}

export function listDatasets(): Promise<ApiResult<DatasetRead[]>> {
  return request<DatasetRead[]>("/api/datasets");
}

export function getAdminKpis(): Promise<ApiResult<AdminKpis>> {
  return request<AdminKpis>("/api/admin/kpis");
}

export function exportDataset(payload: {
  task_id: string;
  name: string;
  only_success: boolean;
  min_quality_score: number;
  export_format: "json";
}): Promise<ApiResult<{ dataset_id: string; status: string; export_path: string }>> {
  return request("/api/datasets/export", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}
