# 동작 방식과 확인 범위

## 서로 독립적인 두 구성 요소

`skills/han-project/SKILL.md`는 Claude Code가 따르는 작업 정책입니다. `agents/`의 도구 권한·모델·effort 기본값을 사용하되 실제 배정 시에도 모델과 effort를 명시하도록 요청합니다. 스킬 자체는 스케줄러·프로세스·하드웨어 격리·예산 제한을 만들지 않습니다. `han-handoff`는 이미 승인된 작업의 체크포인트를 문서로 남기는 데 사용합니다. 실제 실행의 결과와 worker 상태를 확인하는 책임은 오케스트레이터에게 있습니다.

시각화는 `han-project` 사용 여부와 관계없이 로컬 Claude Code 기록을 관찰합니다. `observer.py`는 loopback HTTP만 제공하고, `collector.py`가 살아 있는 세션과 해당 에이전트를 읽습니다. `office.js`는 원본 픽셀 아트와 클릭 가능한 DOM 버튼을 그립니다. 모델 호출, 세션 제어, 사용자 메시지 전송 기능은 없습니다.

## 데이터 근거

| 표시 | 근거 | 주의점 |
|---|---|---|
| 살아 있는 메인 세션 | 세션 레지스트리 PID + 프로세스 시작 시각 | 프로세스 조회 실패 시 생존 미확인 |
| 메인 busy/idle | 레지스트리 status | 레지스트리의 최신 갱신 상태이며 실제 요청의 진행률이 아님 |
| 관측 모델 | API 요청 params.model / 응답 message.model | 두 값의 시각이 다를 수 있으므로 상세에서 분리 |
| 관측 effort | output_config.effort / 응답 effort 레코드 | 누락 시 전역 기본값으로 추정하지 않음 |
| 생성 요청값 | Agent 호출 + 에이전트 meta | 관측값과 다를 수 있음 |
| 부모 관계 | meta.toolUseId ↔ Agent/Task tool_use.id | spawnDepth만으로 추측하지 않음 |
| 에이전트 완료 | meta.finished | 없으면 완료로 확정하지 않음 |

카드의 모델은 최신 API 요청값을 우선하고 요청 기록이 없으면 응답값을 사용합니다. 상세에는 두 값을 따로 표시합니다. 기본 세션 상태/에이전트 로그에서 실행을 확정할 수 없으면 미확인 또는 활동 관측으로 표시합니다. 모델 별칭과 서버 제공자에 따른 해석은 Claude Code에 맡깁니다.

## 검증 범위

설치기 테스트는 임시 디렉터리에서 실행하며 실제 사용자 설정에 설치하지 않습니다. 시각화 수집기는 합성 fixture로 모델/effort 구분, 중첩 관계, 불완전 행, 파일 축소와 PID 재사용을 확인합니다. 데모는 파일을 읽지 않는지 확인합니다. HTTP 테스트는 Host/Origin, 정적 자산 경로와 불허 경로를 확인합니다.

실제 macOS 로그와 브라우저에서 세션 전환·완료 필터·페이지 이동·inspector·키보드 포커스·동작 줄이기·390px 레이아웃을 확인했습니다. 이 공개 패키지에서는 합성 데모를 별도 검증합니다. 다른 운영체제/Claude 버전에서의 실제 수집, 모든 모델 제공자의 호출 성공, 프롬프트 준수율과 비용 개선은 검증하지 않았습니다.

## 설치·제거

설치는 bundled 파일 7개만 복사하며 다른 에이전트·스킬·설정을 수정하지 않습니다. 동일한 파일은 건너뛰고 충돌하면 쓰기 전에 실패합니다. `--force`는 다른 파일을 먼저 `han-project-backups/<UTC timestamp>/` 아래에 보존합니다. 설치 경로 밖으로 벗어나는 심볼릭 링크는 거부합니다.

제거하려면 설치한 Claude 디렉터리에서 `skills/han-project/SKILL.md`, `skills/han-handoff/SKILL.md`, `agents/han-{scout,builder,deep,reviewer,advisor}.md`를 확인해 삭제하세요. 직접 수정한 파일은 먼저 보관하고, 덮어쓰기 설치 전에 있던 파일은 백업에서 복원하세요. 삭제를 자동화하는 명령은 제공하지 않습니다.

## 참고

- [Claude Code skills](https://code.claude.com/docs/en/skills)
- [Claude Code subagents](https://code.claude.com/docs/en/sub-agents)
- [모델과 effort 설정](https://code.claude.com/docs/en/model-config)
- [Pixel Agents](https://github.com/pablodelucca/pixel-agents): 표현 방식 참고. 코드·이미지 에셋을 가져오지 않았습니다.
