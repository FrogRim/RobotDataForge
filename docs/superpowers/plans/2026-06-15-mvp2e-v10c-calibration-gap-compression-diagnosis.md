# MVP-2E v0.10c Calibration Gap Compression Diagnosis 구현 계획

## Target

v0.10b repair 이후 실제 Isaac v0.10 calibration failure를 artifact-only로 진단하고,
held-out을 열지 않은 상태에서 다음 valid proof slice를 결정한다.

## Constraints

- v0.10 held-out `32000-32049` 접근 금지.
- actual Isaac 재실행 없음.
- policy/trainer/threshold 변경 없음.
- 기존 v0.10 artifact는 보존한다.
- 산출물은 proof authority가 아니라 diagnosis authority다.

## Tasks

1. RED tests
   - v0.10 calibration gate가 gap failure일 때 paired outcome을 계산한다.
   - `CALIBRATION_GAP_COMPRESSED_BY_BASELINE_SUCCESS_FLOOR`로 분류한다.
   - CLI `--fresh-comparator-gap-compression-diagnosis-only --policy-slice v0_10c`가 report와 evidence manifest를 쓴다.
   - held-out access flags가 모두 false인지 확인한다.

2. Implementation
   - v0.10c constants 추가.
   - rollout/trace loader 재사용.
   - paired outcome 및 failure seed summary builder 추가.
   - `build_v10c_calibration_gap_compression_diagnosis()` 구현.
   - CLI flag/validation/evidence manifest 추가.

3. Verification
   - `uv run pytest apps/api/tests/test_mvp2c_isaac_training_calibration_script.py -k "v10c or v10a or v10b" -q`
   - `uv run python scripts/run_mvp2c_isaac_training_calibration.py --scenario-profile v0_6 --policy-slice v0_10c --fresh-comparator-gap-compression-diagnosis-only --output-dir storage/proof_evidence/mvp2c_isaac_training_calibration --pretty`
   - `uv run python -m compileall -q scripts/run_mvp2c_isaac_training_calibration.py apps/api/tests/test_mvp2c_isaac_training_calibration_script.py`
   - `uvx ruff check scripts/run_mvp2c_isaac_training_calibration.py apps/api/tests/test_mvp2c_isaac_training_calibration_script.py`

4. Next automatic branch
   - If v0.10c classifies baseline floor compression, create v0.11 spec/plan next.
   - If unclassified, inspect traces for candidate-specific failure before opening any held-out.

## Done

v0.10c is done when the report exists, focused tests pass, held-out remains unopened,
and the next downstream slice recommendation is explicit.
