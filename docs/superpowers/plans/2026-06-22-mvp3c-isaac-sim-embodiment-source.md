# Plan: MVP-3C Isaac Sim Embodiment Source Closed

Date: 2026-06-22
Status: ralplan consensus approved; ready for ultragoal

Canonical ralplan artifact:

```text
.omx/plans/ralplan-mvp3c-isaac-sim-embodiment-source.md
```

This repo-tracked copy records the implementation intent for future sessions.
The active consensus gate is the `.omx/plans/` artifact plus the durable handoff
created after Architect and Critic approval.

## Target

MVP-3C closes only this claim:

```text
Franka + Universal Robots UR Isaac Sim runtime-backed command/state source logs
can be recorded, projected through RDF adapter infrastructure, packaged as
self-contained evidence, and independently verified.
```

It does not prove real robot support, live hardware readiness, ROS2-DDS bridge
readiness, policy uplift, learning-proven value, visual/HMD readiness, production,
marketplace, or universal robot support.

## Execution Shape

Use `ultragoal` after ralplan consensus. Story order:

1. Planning baseline and branch hygiene.
2. Independent verifier first.
3. Isaac Sim source-ingress profiles.
4. Package builder with controlled evidence.
5. Isaac Sim preflight and runtime capture.
6. Real package tamper matrix.
7. Documentation and handoff.
8. Final regression, independent review, PR, tag.

See `.omx/plans/ralplan-mvp3c-isaac-sim-embodiment-source.md` for acceptance
criteria and verification commands.

Architect iteration 1 tightened the plan: MVP-3C closure now requires per-row
`runtime_capture_id` binding to hash-bound runtime metadata and verifier-owned
preflight fields. Controlled/synthetic packages can test builder behavior, but cannot
verify as `isaac_sim_embodiment_source_closed`.

Architect iteration 2 tightened the wording further: synthetic fixtures are limited
to verifier mechanics and negative closure tests. A hash-refreshed synthetic package
with plausible metadata must not verify as original MVP-3C closure.
