# MVP-1+ UR File-Backed Lineage Design

## Goal

MVP-1+의 신뢰도 보강을 위해 Universal Robots UR industrial-arm adapter에
file-backed recorded-log evidence path를 추가한다.

## Scope

이 작업은 실제 UR runtime, RTDE live control, physical robot readiness,
real robot success, policy uplift를 구현하거나 주장하지 않는다. 목적은
나중에 실제 UR recorded log가 들어왔을 때 같은 data trust layer path를
그대로 통과시킬 수 있는 import boundary와 lineage evidence를 증명하는 것이다.

## Design

- `scripts/run_mvp1plus_embodiment_proof.py`에 `--ur-recorded-log-dir` 옵션을
  추가한다.
- 옵션이 없을 때는 repo-local
  `fixtures/mvp1plus/universal_robots_ur_recorded_log_fixture/`를 사용한다.
- 이 fixture는 `metadata.json`, `accepted_command_state.jsonl`,
  `rejected_command_state.jsonl`로 구성한다.
- `universal_robots_ur_industrial_arm` source logs는 generated sample 대신
  file-backed fixture에서 복사한다.
- source log와 projected artifact의 SHA-256 lineage를 proof, contract
  evidence, buyer summary에 기록한다.
- buyer-facing 문구는 `file-backed recorded-log fixture`로 제한한다.

## Non-Claims

- `real_robot_success=false`
- `physical_robot_readiness=false`
- `live_runtime_support=false`
- `hmd_readiness=false`
- `policy_uplift=false`
- `marketplace_readiness=false`
- `db_migration=false`
- `production_auth=false`

## Acceptance Criteria

- UR industrial adapter가 기본 proof에서 repo-local file-backed fixture를
  사용한다.
- `--ur-recorded-log-dir`로 외부 source directory를 지정할 수 있다.
- fixture source와 projected artifact hash lineage가 buyer summary와 proof에
  남는다.
- MVP-1+ proof, 기존 MVP-1 proof, audit/policy-boundary tests가 계속 통과한다.
