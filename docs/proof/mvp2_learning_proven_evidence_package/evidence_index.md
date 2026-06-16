# Evidence Index

이 index는 외부 리뷰어가 어떤 파일을 어떤 순서로 확인해야 하는지 정리한다.
SHA-256은 2026-06-16 로컬 worktree에서 `sha256sum`으로 계산했다.

## Root Package Evidence

| Role | Path | File SHA-256 |
| --- | --- | --- |
| Root evidence manifest | `storage/proof_evidence/mvp2c_isaac_training_calibration/evidence_manifest.json` | `12678323b4796080136d75a7c8a277e812c0eedf2b46f4134345c2559302334e` |
| Internal evidence manifest hash | `evidence_manifest_sha256` field | `e3792596e9aab972c4af61896338a39b00da0c8849c672b6cdf6fa11ae123c5e` |
| Package manifest | `docs/proof/mvp2_learning_proven_evidence_package/package_manifest.json` | `54b5088f82e96c1f6565896dc1e383d3866a22d9b0217a18f4adc3dd14529c67` |

Root manifest facts:

- `schema_version`: `rdf_proof_evidence_manifest_v0.1.0`
- `policy_slice`: `v0_14`
- `runtime_backend`: `isaac_runtime`
- `proof_runtime`: `mvp2e_v14_comparator_provenance_row_balance_slice`
- `file_count`: `2587`
- `mvp2_closed`: `true`
- `policy_uplift_proven`: `true`
- `fresh_heldout_40000_40049_accessed`: `true`
- `same_heldout_reuse_allowed_for_closure`: `false`

## Closure And Calibration Gates

| Role | Path | File SHA-256 |
| --- | --- | --- |
| Held-out closure gate | `storage/proof_evidence/mvp2c_isaac_training_calibration/v0_14_comparator_provenance_row_balance/heldout_closure_gate_v0_14.json` | `ddb30bc37c8c3c79a5634680d712a836b0923ca407459415a49c1619ca0452fc` |
| Calibration pre-signal gate | `storage/proof_evidence/mvp2c_isaac_training_calibration/v0_14_comparator_provenance_row_balance/calibration_presignal_gate_v0_14.json` | `54405c4e104d6850ac2904e9c4a55dbc45e6e52a11b63781276685a674c48e12` |
| Comparator provenance row-balance gate | `storage/proof_evidence/mvp2c_isaac_training_calibration/v0_14_comparator_provenance_row_balance/v0_14_comparator_provenance_row_balance_gate.json` | `75002044909cca6b52b3e581bde060c7582f55f30af72a9a6e2a54526bd3dd2c` |

Gate facts:

- Calibration pre-signal: baseline `5 / 30`, candidate `26 / 30`,
  candidate-baseline gap `+0.70`.
- Held-out closure: baseline `5 / 50`, candidate `40 / 50`,
  absolute uplift `+0.70`.
- Closure CI: `[0.56, 0.82]`, `bootstrap_success_rate_difference`,
  2,000 iterations.
- Closure proof flags: `mvp2_closed=true`, `policy_uplift_proven=true`,
  `stronger_public_evidence_target_passed=true`.

## Comparator Provenance And Row Balance

| Role | Path | File SHA-256 |
| --- | --- | --- |
| Comparator manifest | `storage/proof_evidence/mvp2c_isaac_training_calibration/v0_14_comparator_provenance_row_balance/v0_14_comparator_provenance_row_balance_manifest.json` | `fd79e7d1f730342f19491532f53a35e9bc14e999c356377a89c3bd5df5175f4f` |
| Row-balance report | `storage/proof_evidence/mvp2c_isaac_training_calibration/v0_14_comparator_provenance_row_balance/v0_14_row_balance_report.json` | `6a489c467e067828fe94b2c37788308b835fe9df929072545d67cc82eb69e395` |
| Source provenance report | `storage/proof_evidence/mvp2c_isaac_training_calibration/v0_14_comparator_provenance_row_balance/v0_14_source_provenance_report.json` | `8f51c41483548cbd3ac80a6132dc24065a6a565ed0423bdceb8f012280316a69` |

Comparator facts:

- `parent_policy_slice`: `v0_13`
- `same_policy_influence_authority_ceiling_config_as_peer`: `true`
- `baseline_actual_failure_material_ratio`: `0.5`
- `baseline_failure_material_ratio_target`: `0.5`
- `failure_to_success_row_ratio`: `1.0`
- `duplicate_failure_rows_allowed`: `false`
- `fresh_calibration_39000_39029_accessed`: `false` before calibration gate
- `fresh_heldout_40000_40049_accessed`: `false` before closure gate

## Policy Evaluation Reports

| Role | Path | File SHA-256 |
| --- | --- | --- |
| Learning-proven report | `storage/proof_evidence/mvp2c_isaac_training_calibration/v0_14_comparator_provenance_row_balance/mvp2_learning_proven_policy_eval/mvp2_learning_proven_report.json` | `e20a27469f49ecf3b872f4ae53fcb741533a7700541cc37bcdaca52b34012cd5` |
| Policy eval report | `storage/proof_evidence/mvp2c_isaac_training_calibration/v0_14_comparator_provenance_row_balance/mvp2_learning_proven_policy_eval/mvp2_policy_eval_report.json` | `4f5a77e5665716beec66210d661a90e133f8256b24b4bb0a004d56dd74a2cea1` |
| Learning harness bridge report | `storage/proof_evidence/mvp2c_isaac_training_calibration/v0_14_comparator_provenance_row_balance/mvp2_learning_harness_bridge/mvp2_policy_ab_harness_report.json` | `2150982285b7669b46b06ce34783bb7f0fabdd3d4b147f8f69c673b6d8f82490` |

Policy eval facts:

- `evidence_tier`: `external_heldout_policy_eval`
- `primary_metric`: `policy_success_rate`
- `baseline_success_rate`: `0.1`
- `candidate_success_rate`: `0.8`
- `curated_vs_uncurated_uplift`: `0.7000000000000001`
- `learning_proven`: `true`
- `proof_eligible`: `true`

## Rollout Evidence

| Role | Path | File SHA-256 |
| --- | --- | --- |
| Baseline held-out rollouts | `storage/proof_evidence/mvp2c_isaac_training_calibration/v0_14_comparator_provenance_row_balance/external_rollouts/baseline_external_rollouts.json` | `aac10b47624de21d42fb144c333e5dc1ea7bdf0158662969e68f4a2ef5d748bf` |
| Candidate held-out rollouts | `storage/proof_evidence/mvp2c_isaac_training_calibration/v0_14_comparator_provenance_row_balance/external_rollouts/candidate_external_rollouts.json` | `6ad81c474e654489f2d098cf8f90e0f347b4a9b6e94d368642054f8acda2ca76` |
| Baseline calibration rollouts | `storage/proof_evidence/mvp2c_isaac_training_calibration/v0_14_comparator_provenance_row_balance/calibration_external_rollouts/baseline_calibration_rollouts_v0_14.json` | `499be9777604c1043f5da402df3ab92bd95824cbb4673696ae93b8891ae23cc8` |
| Candidate calibration rollouts | `storage/proof_evidence/mvp2c_isaac_training_calibration/v0_14_comparator_provenance_row_balance/calibration_external_rollouts/candidate_calibration_rollouts_v0_14.json` | `f7aacc82ddea9738c25a921bea8949802bdbfa6cfb882a9361c4db616eec6a79` |

Rollout facts:

- Held-out suite range: `held_out_40000` through `held_out_40049`.
- Baseline held-out: 50 rollouts, 5 successes.
- Candidate held-out: 50 rollouts, 40 successes.
- Baseline calibration: 30 rollouts, 5 successes.
- Candidate calibration: 30 rollouts, 26 successes.

## Audit Note

`heldout_closure_gate_v0_14.json`의 현 로컬 파일은 code-review fix 이전에 생성된
artifact라 `spent_heldout_ranges` field가 직접 포함되어 있지 않다. Root
`evidence_manifest.json`은 `40000-40049`를
`spent_for_mvp2_v0_14_closure`로 기록한다. 이후 runtime code는 closure rerun
전에 기존 root manifest가 이 spent range를 표시하면 fail closed하도록 보강됐다.
