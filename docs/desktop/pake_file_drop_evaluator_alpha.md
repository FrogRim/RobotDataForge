# RDF File-Drop Evaluator Alpha — Pake shell runbook

이 문서는 `apps/web/app/file-drop/page.tsx`를 Pake로 감싸는 local desktop shell 절차다.

Pake는 web page를 desktop app으로 감싸는 도구다. Pake CLI 문서는 `pake [url] [options]` 형식과 `--name`, `--width`, `--height`, `--min-width`, `--min-height` 같은 옵션을 제공한다고 설명한다. 참고: <https://github.com/tw93/Pake/blob/main/docs/cli-usage.md>

## Trust boundary

Pake는 evaluator가 아니다.
Pake는 verifier가 아니다.
Pake는 PASS/FAIL을 계산하지 않는다.
Pake는 TrustPack 또는 evaluator-run package를 수정하지 않는다.

RDF alpha의 신뢰 경로는 아래 순서다.

```text
local folder/zip path
-> FastAPI command bridge
-> scripts/rdf_file_drop_evaluator.py
-> scripts/verify_rdf_file_drop_evaluator_run.py
-> browser/Pake shell displays exit code + JSON
```

`/file-drop` UI는 verifier가 `exit_code == 0`, `result.ok == true`, `result.verdict == "VERIFIED"`를 반환할 때만 package를 verified로 표시한다.
데이터가 accepted인 경우에는 `PACKAGE VERIFIED / DATA ACCEPTED`, rejected evidence package인 경우에는 `PACKAGE VERIFIED / DATA REJECTED`로 구분한다.

## Non-claims

이 alpha는 다음을 claim하지 않는다.

```text
external partner data evaluated
real robot data evaluated
real robot success
hardware readiness
live UR/RTDE support
live Franka support
live ROS2 bridge support
policy uplift
production readiness
marketplace readiness
```

## Local services

Repository root에서 backend를 시작한다.

```bash
uv run uvicorn app.main:app --app-dir apps/api --host 127.0.0.1 --port 8000
```

다른 terminal에서 web UI를 시작한다.

```bash
cd apps/web
NEXT_PUBLIC_API_BASE_URL=http://127.0.0.1:8000 npm run dev -- --hostname 127.0.0.1 --port 3000
```

브라우저에서 확인한다.

```text
http://127.0.0.1:3000/file-drop
```

## Pake wrapper

Pake를 설치하지 않고 `npx`로 실행하는 smoke command:

```bash
npx pake-cli http://127.0.0.1:3000/file-drop \
  --name "RDF File Drop Evaluator" \
  --width 1280 \
  --height 860 \
  --min-width 1040 \
  --min-height 720
```

macOS에서 설치형 DMG 대신 local `.app` smoke가 필요하면 Pake 문서 기준으로 다음 환경 변수를 사용할 수 있다.

```bash
PAKE_CREATE_APP=1 npx pake-cli http://127.0.0.1:3000/file-drop \
  --name "RDF File Drop Evaluator" \
  --width 1280 \
  --height 860 \
  --min-width 1040 \
  --min-height 720
```

## Alpha input model

현재 UI는 browser drag/drop upload를 구현하지 않는다.

사용자는 local machine의 folder 또는 zip path를 text input에 넣는다. 이 path는 FastAPI bridge가 local CLI로 전달한다. Browser file picker state는 source of truth가 아니다.

## Supported profiles

```text
ur_rtde_csv_v0
franka_state_jsonl_v0
ros2_channel_bundle_jsonl_v0
generic_command_state_jsonl_v0
```

## Smoke check

1. `/file-drop`에서 profile list가 보이는지 확인한다.
2. `scripts/rdf_file_drop_evaluator.py profiles list --json` 결과와 profile 수가 같은지 확인한다.
3. tiny golden drop path를 넣고 `Preflight`를 실행한다.
4. `Evaluate`를 실행한다.
5. `run_dir`가 verify input으로 들어갔는지 확인한다.
6. `Verify package`를 실행한다.
7. 최종 `Verifier` panel에만 녹색 `VERIFIED`가 보이는지 확인한다.

## Stop conditions

아래 조건이면 desktop shell 작업을 중단한다.

```text
Pake integration requires weakening path safety.
Pake integration requires the UI to compute PASS/FAIL.
Pake integration requires broad CORS or remote network exposure.
Pake integration rewrites package manifests or verifier output.
Local backend cannot be constrained to localhost.
```
