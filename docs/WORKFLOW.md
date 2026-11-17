# 역할, 결과 반환과 검증 가능한 인계

## 세 가지 흐름

| 흐름 | 의미 | 소유권 |
|---|---|---|
| 작업 반환 | Worker 실행이 끝나 ready/blocked/failed를 코디네이터에게 보고 | 유지 |
| 체크포인트 | 같은 세션의 단계 전환/압축 대비 기록 | 유지 |
| 담당 이전 | 준비 → 후임의 상태 재확인/수신 → 원래 담당의 재확인/확정 | 확정 시 한 번 변경 |

역할은 모델과 다릅니다. Scout/Reviewer/Advisor는 읽기 전용이며 테스트 실행을 코디네이터에게 요청합니다. Builder/Deep은 배정된 범위의 수정과 테스트를 수행합니다. 코디네이터가 독립 검토 근거를 확인하고 결과를 수락하며 담당을 이전합니다. 별도 handoff 에이전트는 없습니다.

## 설치 후 스킬 사용

```text
/han-project <작업 지시>
/han-handoff <task-id> checkpoint
/han-handoff <task-id> transfer
/han-resume <handoff-id>
```

체크포인트 노트에는 목표·기존 승인 범위·결정 이유·미커밋 변경·실행한/하지 않은 검증·실행 중 Worker·다음 행동·중단 조건을 담습니다. 스킬은 이 노트와 구조화된 snapshot을 로컬에 보관합니다. 명시적인 인계 기록이 없는 주변 세션을 자동으로 후임으로 지정하지 않습니다.

`han-resume`은 후임의 수신을 기록하지만 즉시 작업을 시작하지 않습니다. 원래 세션에서 확정한 뒤 새 소유권을 확인해야 합니다. 이전 세션이 종료됐으면 먼저 원래 Claude 세션을 재개해 상태를 확인하고 확정하세요. 원래 세션을 재개할 수 없다면 자동 소유권 탈취나 중복 실행 대신 진단/수동 복구가 필요합니다. 기존 Worker 핸들이 새 세션에서 제어된다고 가정하지 않습니다.

## 결정적 CLI

소스 체크아웃에서는 `python3 han.py`, 설치 후에는 `<Claude 디렉터리>/han-project-runtime/han.py`를 사용합니다. `--session`은 실제 코디네이터 세션 ID여야 합니다. 아래 `<...>`는 실제 응답값으로 바꿔야 하는 자리표시자입니다. 이 CLI 자체는 모델이나 Worker를 실행하지 않습니다.

```bash
python3 han.py --session <source-session> start --repo <repo-root> --title "작업 제목"
python3 han.py --session <source-session> register <task-id> --agent <actual-agent-id> --role han-builder --model sonnet --effort medium
python3 han.py --session <source-session> result <attempt-id> --outcome ready --summary "변경과 검증 요약" --evidence <private-validation-log>
python3 han.py --session <source-session> review <attempt-id> --reviewer <actual-independent-id> --verdict pass --evidence <private-review-log>
python3 han.py --session <source-session> accept <attempt-id>

python3 han.py --session <source-session> handoff <task-id> --next "다음 행동" --context <private-checkpoint-note>
python3 han.py --session <successor-session> receive <handoff-id>
python3 han.py --session <source-session> commit <handoff-id>
python3 han.py status
python3 han.py show <handoff-id>
```

같은 세션 체크포인트는 `handoff` 대신 `checkpoint`를 사용합니다. 중단한 인계는 기존 담당이 `cancel <handoff-id>`로 취소하고 새 snapshot을 준비합니다. 스킬이 없는 기존 작업도 실제 작업/Worker 상태를 확인한 후 추적 task를 생성할 수 있습니다. 이때 진행 중 Worker를 누락해 인터록을 우회하지 마세요.

## 인터록과 근거

- SQLite `BEGIN IMMEDIATE`로 담당 확인·버전 변경·수신 경합을 직렬화합니다. 둘이 동시에 수신해도 한 후임만 기록됩니다.
- 준비/수신만으로 담당을 바꾸지 않습니다. 이전 담당 확인 이후 새 담당/소유권 버전이 함께 변경됩니다.
- 실행 중 또는 미확인으로 추적된 Worker, 오래된 소유권, 중복 수신, 준비 후 변경된 Worker 결과/검토 상태는 담당 이전을 막습니다.
- Git HEAD·index·미커밋/미추적 파일 내용과 근거 해시를 확인합니다. 같은 파일이 같은 dirty 표시를 유지하면서 내용만 바뀌어도 검출합니다. dirty submodule은 불완전하게 검사하는 대신 거부합니다.
- Git이 무시하는 파일은 worktree snapshot에 포함하지 않습니다. 작업에 필요한 환경 설정 등은 명시적 검증 근거로 남기세요.
- 반환/검토 로그는 private state에 불변 사본으로 보관합니다. 원본 로그를 나중에 재사용해도 과거 실패 기록은 유지됩니다. 결과 수락 시에는 원본과 사본 모두 재확인하고, 인계는 보관된 사본을 검증합니다.
- 성공적인 결과 수락에는 ready 결과, 검증 근거, 다른 ID의 독립 검토와 변경되지 않은 worktree가 필요합니다. 차단/실패는 수락할 수 없습니다. 보완/재개는 새 attempt로 기록합니다.
- Markdown 생성 실패는 인계 DB 변경도 롤백합니다. Markdown은 사람이 읽는 사본이고 DB가 소유권의 기준입니다. `show`가 현재 단계를 보여줍니다.

기본 상태 위치는 `~/.claude/han-project/`이며 `--state-dir`로 지정할 수 있습니다. 증거 파일은 저장소 또는 이 private state 안에 있어야 합니다. 증거는 10 MiB 이하 일반 파일만 허용합니다. 심볼릭 링크로 로컬 상태 밖에 문서/근거를 쓰지 않습니다. 공개 화면 캡처는 `--demo`를 사용하세요.

## 사무실에서 보이는 것

1. 책상에 역할, 모델, effort, 실행 상태와 기록된 결과를 구분합니다.
2. 결과 봉투는 검토 대기/차단/실패/보완 요청/수락을 표시합니다. 실행 종료나 봉투 도착 자체를 성공으로 세지 않습니다.
3. 인계 타임라인은 명시적 로컬 준비/수신/확정 이벤트만 표시합니다. 같은 폴더·시간상 근접만으로 세션 관계를 만들지 않습니다.
4. 종료된 이전 세션은 ‘담당 기록 · 실행 미확인’으로 남습니다. 실제 살아 있는 세션이나 관측 모델을 만들어내지 않습니다.
5. 웹은 여전히 읽기 전용입니다. 작업 반환·인수·세션 제어 버튼을 웹에 제공하지 않습니다.

## 보장하지 않는 것

이 도구는 같은 OS 사용자의 로컬 워크플로 기록입니다. `--session`은 인증 토큰이 아니고 코디네이터 ID에 대한 명시적 기록입니다. 다른 프로세스의 직접 Git 수정·추적되지 않은 Worker·CLI를 거치지 않은 작업까지 막는 보안 샌드박스가 아닙니다. 파일 해시가 테스트의 의미나 에이전트의 정직함을 증명하지도 않습니다. 코디네이터는 실제 명령 결과와 Worker 종료·독립 검토를 확인해야 합니다. 인계 문서는 사용자 승인을 새로 만들지 않습니다.
