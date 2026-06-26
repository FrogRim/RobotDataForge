"use client";

import { useEffect, useMemo, useState } from "react";

import {
  evaluateFileDrop,
  listFileDropProfiles,
  preflightFileDrop,
  verifyFileDrop,
} from "../../lib/api";
import type { FileDropBridgeResult, FileDropProfile } from "../../lib/types";

type Stage = "profiles" | "preflight" | "evaluate" | "verify";

type StageState = {
  loading: boolean;
  error?: string;
  response?: FileDropBridgeResult;
};

const EMPTY_STAGE: StageState = { loading: false };

function textValue(value: unknown): string {
  if (value === null || value === undefined) return "";
  if (typeof value === "string") return value;
  if (typeof value === "number" || typeof value === "boolean") return String(value);
  return JSON.stringify(value);
}

function stringList(value: unknown): string[] {
  return Array.isArray(value) ? value.map((item) => textValue(item)).filter(Boolean) : [];
}

function resultField(response: FileDropBridgeResult | undefined, field: string): unknown {
  return response?.result?.[field];
}

function verifierVerified(response: FileDropBridgeResult | undefined): boolean {
  return response?.exit_code === 0 && response.result?.ok === true && response.result?.verdict === "VERIFIED";
}

function verifierAccepted(response: FileDropBridgeResult | undefined): boolean {
  return verifierVerified(response) && response?.result?.passed === true;
}

function BridgeStatus({ title, state, verifyStage = false }: { title: string; state: StageState; verifyStage?: boolean }) {
  const response = state.response;
  const rejectionReasons = stringList(resultField(response, "rejection_reasons"));
  const failedChecks = stringList(resultField(response, "failed_checks"));
  const runDir = textValue(resultField(response, "run_dir"));
  const manifest = textValue(resultField(response, "package_manifest"));
  const verified = verifyStage && verifierVerified(response);
  const accepted = verifyStage && verifierAccepted(response);
  const statusClass = accepted ? "good" : verified ? "neutral" : response?.ok ? "neutral" : "bad";
  const statusText = accepted ? "PACKAGE VERIFIED / DATA ACCEPTED" : verified ? "PACKAGE VERIFIED / DATA REJECTED" : response ? (response.ok ? "CLI OK" : "NOT VERIFIED") : "idle";

  return (
    <section className="panel file-drop-section">
      <div className="file-drop-section-header">
        <h2>{title}</h2>
        <span className={`status ${statusClass}`}>{statusText}</span>
      </div>
      {state.loading ? <p className="muted">Running...</p> : null}
      {state.error ? <p className="danger-text">{state.error}</p> : null}
      {response ? (
        <div className="file-drop-result-grid">
          <div>
            <span className="muted">exit</span>
            <strong>{response.exit_code ?? "timeout"}</strong>
          </div>
          <div>
            <span className="muted">trust source</span>
            <strong>{response.trust_source}</strong>
          </div>
          <div>
            <span className="muted">bridge error</span>
            <strong>{response.bridge_error ?? "none"}</strong>
          </div>
          <div>
            <span className="muted">stdout cap</span>
            <strong>{response.stdout_truncated ? "truncated" : "complete"}</strong>
          </div>
          {verifyStage ? (
            <div>
              <span className="muted">data verdict</span>
              <strong>{response.result?.passed === true ? "accepted" : response.result?.passed === false ? "rejected" : "unknown"}</strong>
            </div>
          ) : null}
        </div>
      ) : null}
      {runDir ? (
        <p>
          <span className="muted">run dir </span>
          <code>{runDir}</code>
        </p>
      ) : null}
      {manifest ? (
        <p>
          <span className="muted">manifest </span>
          <code>{manifest}</code>
        </p>
      ) : null}
      {rejectionReasons.length ? (
        <div>
          <p className="muted">rejection reasons</p>
          <ul className="file-drop-list">
            {rejectionReasons.map((reason) => <li key={reason}>{reason}</li>)}
          </ul>
        </div>
      ) : null}
      {failedChecks.length ? (
        <div>
          <p className="muted">failed verifier checks</p>
          <ul className="file-drop-list">
            {failedChecks.map((check) => <li key={check}>{check}</li>)}
          </ul>
        </div>
      ) : null}
      {response ? (
        <details>
          <summary>Command and JSON</summary>
          <pre>{JSON.stringify({ command_argv: response.command_argv, result: response.result }, null, 2)}</pre>
        </details>
      ) : null}
    </section>
  );
}

export default function FileDropPage() {
  const [profiles, setProfiles] = useState<FileDropProfile[]>([]);
  const [profileId, setProfileId] = useState("ur_rtde_csv_v0");
  const [inputPath, setInputPath] = useState("");
  const [runId, setRunId] = useState("");
  const [verifyPath, setVerifyPath] = useState("");
  const [stages, setStages] = useState<Record<Stage, StageState>>({
    profiles: EMPTY_STAGE,
    preflight: EMPTY_STAGE,
    evaluate: EMPTY_STAGE,
    verify: EMPTY_STAGE,
  });

  const selectedProfile = useMemo(
    () => profiles.find((profile) => profile.profile_id === profileId),
    [profileId, profiles],
  );

  function updateStage(stage: Stage, state: StageState) {
    setStages((current) => ({ ...current, [stage]: state }));
  }

  useEffect(() => {
    let active = true;
    updateStage("profiles", { loading: true });
    listFileDropProfiles().then((result) => {
      if (!active) return;
      if (!result.ok) {
        updateStage("profiles", { loading: false, error: result.error });
        return;
      }
      const nextProfiles = result.data.result?.profiles ?? [];
      setProfiles(nextProfiles);
      if (nextProfiles.length && !nextProfiles.some((profile) => profile.profile_id === profileId)) {
        setProfileId(nextProfiles[0].profile_id);
      }
      updateStage("profiles", { loading: false, response: result.data });
    });
    return () => {
      active = false;
    };
  }, [profileId]);

  async function runPreflight() {
    updateStage("preflight", { loading: true });
    const result = await preflightFileDrop({ input_path: inputPath, profile_id: profileId });
    updateStage("preflight", result.ok ? { loading: false, response: result.data } : { loading: false, error: result.error });
  }

  async function runEvaluate() {
    updateStage("evaluate", { loading: true });
    const result = await evaluateFileDrop({
      input_path: inputPath,
      profile_id: profileId,
      run_id: runId || undefined,
    });
    if (!result.ok) {
      updateStage("evaluate", { loading: false, error: result.error });
      return;
    }
    const nextRunPath = textValue(result.data.result?.run_dir);
    if (nextRunPath) setVerifyPath(nextRunPath);
    updateStage("evaluate", { loading: false, response: result.data });
  }

  async function runVerify() {
    updateStage("verify", { loading: true });
    const result = await verifyFileDrop({ run_path: verifyPath, deep_hdf5: true });
    updateStage("verify", result.ok ? { loading: false, response: result.data } : { loading: false, error: result.error });
  }

  const verifyReady = verifyPath.trim().length > 0;

  return (
    <main>
      <div className="file-drop-title-row">
        <div>
          <h1>File-Drop Evaluator</h1>
          <p className="muted">Local pre-real-log evaluation shell</p>
        </div>
        <span className="status neutral">alpha</span>
      </div>

      <section className="panel file-drop-controls">
        <div className="file-drop-field">
          <label htmlFor="profile">Profile</label>
          <select id="profile" value={profileId} onChange={(event) => setProfileId(event.target.value)}>
            {profiles.map((profile) => (
              <option key={profile.profile_id} value={profile.profile_id}>
                {profile.profile_id}
              </option>
            ))}
          </select>
        </div>
        <div className="file-drop-field file-drop-field-wide">
          <label htmlFor="input-path">Input folder or zip path</label>
          <input
            id="input-path"
            value={inputPath}
            onChange={(event) => setInputPath(event.target.value)}
            placeholder="/path/to/file-drop"
          />
        </div>
        <div className="file-drop-field">
          <label htmlFor="run-id">Run id</label>
          <input id="run-id" value={runId} onChange={(event) => setRunId(event.target.value)} placeholder="optional" />
        </div>
        <div className="file-drop-actions">
          <button type="button" onClick={runPreflight} disabled={!inputPath || !profileId || stages.preflight.loading}>
            Preflight
          </button>
          <button type="button" onClick={runEvaluate} disabled={!inputPath || !profileId || stages.evaluate.loading}>
            Evaluate
          </button>
        </div>
      </section>

      {selectedProfile ? (
        <section className="panel file-drop-profile-strip">
          <div><span className="muted">robot</span><strong>{selectedProfile.robot_family ?? "unknown"}</strong></div>
          <div><span className="muted">model</span><strong>{selectedProfile.robot_model ?? "unknown"}</strong></div>
          <div><span className="muted">dof</span><strong>{selectedProfile.dof ?? "unknown"}</strong></div>
          <div><span className="muted">live runtime</span><strong>{selectedProfile.live_runtime_support ? "metadata only" : "false"}</strong></div>
        </section>
      ) : null}

      <BridgeStatus title="Preflight" state={stages.preflight} />
      <BridgeStatus title="Evaluate" state={stages.evaluate} />

      <section className="panel file-drop-controls">
        <div className="file-drop-field file-drop-field-wide">
          <label htmlFor="verify-path">Run directory or manifest under evaluator artifact root</label>
          <input
            id="verify-path"
            value={verifyPath}
            onChange={(event) => setVerifyPath(event.target.value)}
            placeholder="/path/to/artifacts/rdf_file_drop_evaluator/run"
          />
        </div>
        <div className="file-drop-actions">
          <button type="button" onClick={runVerify} disabled={!verifyReady || stages.verify.loading}>
            Verify package
          </button>
        </div>
      </section>

      <BridgeStatus title="Verifier" state={stages.verify} verifyStage />

      <section className="panel">
        <h2>Boundary</h2>
        <p className="muted">
          Visual shell only. CLI and verifier output are the source of truth. No real-robot, external partner data,
          live hardware, live ROS2, policy uplift, production, or marketplace claim is opened here.
        </p>
      </section>
    </main>
  );
}
