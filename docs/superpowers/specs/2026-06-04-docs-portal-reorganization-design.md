# Docs Portal Reorganization Design

Date: 2026-06-04

## Purpose

Reorganize Robot Data Forge documentation around two primary audiences:

1. Buyer-facing readers who need to understand why the data can be trusted.
2. Developers and future maintainers who need implementation, validation, and research context.

The top-level entry point should be `index.html` at the repository root. It links to a structured docs portal under `docs/`, which then routes readers into buyer, developer, experiment, and archive sections.

## Narrative Source

The organization follows the public LinkedIn narrative preserved in `docs/social/linkedin_posts.md`:

- MVP-1 lesson: task success is not the same as training-eligible data.
- Gate 0 lesson: blocking bad input before collection is product behavior, not failure.
- Reset lesson: Quest/OpenXR/HMD is an experimental input adapter, while RDF's core product is the data trust layer.

The reorganized docs must keep this claim boundary explicit:

- Do not claim HMD readiness.
- Do not claim Gate A collection readiness.
- Do not claim physical collection readiness from HMD-free proof.
- Do not claim policy uplift in MVP-1.

## Target Structure

```text
robot-data-forge/
  index.html
  docs/
    index.html
    buyer/
      index.html
      data_trust_layer_reset.html
      mvp1_validated_dataset_pipeline_result.html
      mvp2_learning_proven_strategy_ko.html
      rdf_mvp1_mvp2_detailed_report_ko.html
      social_narrative.md
    developer/
      index.html
      api_spec.md
      data_schema.md
      export_format.md
      debugging_guide.md
      live_validation_checklist.md
      demo_script.md
      project_instructions.md
      worklog.md
      roadmap.md
      task_spec.md
      reference_mapping.md
      papers/
    experiments/
      hmd/
        index.html
        gate0_input_truth_work_summary_2026_06_03.html
        hmd_input_structural_analysis_2026_06_03.html
        hmd_recenter_start_box.md
        hmd_yaw_offset_ab_live_debug.md
        mvp1_next_actions_hmd_guide.html
        mvp_pre_hmd_step1_input_gates.html
        mvp_teleop_input_stream_research.html
        raw_wrist_direct_control_research.md
        ux_calibration_problem_statement.md
    archive/
      index.html
      mvp0_smoke_validation_report.md
      mvp_completion_plan.md
      mvp_progress_overview.html
      mvp1_status_dashboard.html
      mvp1c_full_proof_execution_guide.html
      mvp1c_full_proof_execution_guide.md
      robot_data_forge_mvp.md
      frontend_plan.md
      next_issues.md
      data_collection_log.md
      github_release_checklist.md
```

## Classification Rules

Buyer docs answer:

- What is RDF?
- Why should a dataset buyer trust this artifact?
- What was proven?
- What was explicitly not proven?
- How did public MVP-1 and Gate 0 lessons become the current reset?

Developer docs answer:

- How do I run, inspect, validate, debug, and extend the system?
- What are the API, schema, export, task, and validation contracts?
- What research papers and references informed the implementation?

Experiment docs answer:

- What happened in the HMD/Gate 0/Quest/OpenXR path?
- Why is this path currently experimental?
- Which failures and adapter lessons must future work respect?

Archive docs preserve:

- Older MVP and planning artifacts.
- Historical dashboards and guides that are not the current product entry point.
- Release, frontend, and next-issue notes that are useful context but not the primary current narrative.

## Portal Requirements

The repository root `index.html` must be a compact public portal with four entry points:

- Buyer Overview
- Developer Docs
- HMD / Gate 0 Experiments
- Archive

The `docs/index.html` page must be the detailed docs hub and must link to the same four sections.

Each section index must:

- State its intended reader.
- Link to all files in that section.
- Preserve the current data trust layer claim boundary.
- Prefer repo-relative links that work locally from the filesystem.

## Migration Requirements

- Move files physically into the target folders.
- Update new portal links to point at moved files.
- Update known durable references in `Handoff.md`, `docs/developer/worklog.md`, and `tasks/todo.md`.
- Preserve source content; do not rewrite historical docs except for navigation links or relocated relative links.
- Do not delete HMD/Gate 0 material. Treat it as experimental adapter history.
- Do not commit unless the user explicitly authorizes a commit in the current conversation.

## Verification

After migration:

- Parse every HTML file under `docs/` and root `index.html`.
- Verify every repo-local link exists unless it is an external URL, anchor-only URL, or generated storage artifact that is intentionally outside versioned docs.
- Run `git diff --check` on moved/modified docs.
- Search for stale references to the old reset summary path and old LinkedIn capture path.
- Confirm `docs/papers` no longer exists at the top level and papers are reachable under `docs/developer/papers`.

## Out of Scope

- Rewriting all historical documents.
- Changing runtime code or HMD behavior.
- Re-generating proof artifacts.
- Publishing, committing, or pushing changes.
