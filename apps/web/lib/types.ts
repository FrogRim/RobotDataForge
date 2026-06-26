export type TaskStatus = "active" | "inactive" | "archived";

export type TaskSummary = {
  id: string;
  name: string;
  task_type: string;
  status: TaskStatus | string;
};

export type TaskRead = TaskSummary & {
  description: string;
  environment_config: Record<string, unknown>;
  success_criteria: Record<string, unknown>;
  created_at: string;
  updated_at: string;
};

export type EpisodeRead = {
  id: string;
  task_id: string;
  contributor_id: string;
  status: string;
  started_at: string;
  ended_at?: string | null;
  duration_sec?: number | null;
  trajectory_id?: string | null;
  evaluation_id?: string | null;
};

export type CollectionSessionRead = {
  id: string;
  task_id: string;
  contributor_id: string;
  isaac_task_name: string;
  input_device: string;
  xr_runtime: string;
  streaming_stack: string;
  simulator: string;
  robot: string;
  status: string;
  started_at: string;
  ended_at?: string | null;
  runtime_metrics: Record<string, unknown>;
};

export type TrajectoryRead = {
  id: string;
  episode_id: string;
  task_id: string;
  schema_version: string;
  source: TrajectorySource;
  frames: TrajectoryFrame[];
  summary: Record<string, unknown>;
  storage_path?: string | null;
  created_at: string;
};

export type TrajectorySource = {
  input_device: string;
  runtime: string;
  simulator: string;
  robot: string;
  task_name: string;
};

export type TrajectoryFrame = {
  t: number;
  step: number;
  end_effector_position?: number[];
  end_effector_quaternion?: number[];
  object_position?: number[];
  object_quaternion?: number[];
  action?: Record<string, unknown>;
  contacts?: unknown[];
  metadata?: Record<string, unknown>;
};

export type DatasetRead = {
  id: string;
  name: string;
  task_id: string;
  status: string;
  num_episodes: number;
  num_success: number;
  num_failed: number;
  export_format: string;
  export_path: string;
  metadata_json: Record<string, unknown>;
  created_at: string;
};

export type AdminKpis = {
  collection: Record<string, unknown>;
  xr_runtime: Record<string, unknown>;
  evaluation: Record<string, unknown>;
  learning: Record<string, unknown>;
};

export type FileDropProfile = {
  profile_id: string;
  robot_family?: string;
  robot_model?: string;
  source_kind?: string;
  dof?: number;
  action_semantics?: string;
  state_semantics?: string;
  external_partner_data?: boolean;
  live_runtime_support?: boolean;
};

export type FileDropBridgeResult = {
  ok: boolean;
  exit_code: number | null;
  command_argv: string[];
  trust_source: string;
  bridge_error?: string | null;
  result: Record<string, unknown> | null;
  stdout: string;
  stderr: string;
  stdout_truncated: boolean;
  stderr_truncated: boolean;
};

export type FileDropProfilesResult = FileDropBridgeResult & {
  result: {
    ok: boolean;
    profile_ids: string[];
    profile_count: number;
    profiles: FileDropProfile[];
  } | null;
};
