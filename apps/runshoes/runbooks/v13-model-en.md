# runshoes — V13 영어 이름 · 검색용 다른 표기

> 2026-11-03 — 사용자 결정. 절차는 V12(`v12-wide-scope.md`)와 같다 — **이미지 Sync 가 곧 V13 적용**.

```bash
B=~/k8s-cluster/backup/2026-11-03-runshoes-v13   # 덤프 — 데이터가 들어 있어 git 밖
```

## V13

- `shoes.model_en VARCHAR(100) NULL` — 상세 모달 브랜드 줄에 가운뎃점으로 붙는 영어 이름(처음에는 카드 · 모달에 모델명 아래 한 줄 — 적재 뒤 사용자가 옮김)(`FuelCell SuperComp Elite v6`).
- `shoes.model_alias VARCHAR(255) NULL` — 검색에만 쓰는 다른 표기, 쉼표로 나눈다(`SC Elite v6, 퓨어셀`). 화면에 보이지 않는다.
- 검색(`?search=`)이 두 칸도 본다 — 홈 · 관리 화면 둘 다.
- 맨 뒤 열 추가라 MySQL 8 INSTANT. 기존 행은 NULL — 배포 뒤 적재기가 채운다(앱 `catalog/names.mjs` 규칙, 01c 1-3 #8).
- 앱 커밋 `39332f7` · `53a6969` → 이미지 `53a696940398`(infra `8d63c78`).

### 로컬 확인(2026-11-03)

- 백엔드 단위 시험 통과(검색 — "SC 페이서" · "퓨어셀" · "supercomp pacer"), 로컬 DB Flyway `13`.
- 계약: v3-search 24/24 · v3 101/11(V11 · V12 와 같은 11건) · v6 92/0(V13 시나리오 X123~X129 — PATCH 200 · lastChange · 다른 표기 · 영어 이름 검색 · 101자 400 · 데모 관리자 403 · 빈 칸 null, X122 updatedAt 을 volatile 로 다시 녹화).

## 1. 순서 (누가)

| # | 일 | 누가 | 확인 |
|---|---|---|---|
| 1 | 자동 Sync 끄기 | 사람 | `automated` 없음(Claude 확인) |
| 2 | 앱 커밋 · push → Jenkins → newTag 커밋 | Claude | 운영은 옛 이미지 |
| 3 | 덤프 + 로컬 다른 이름으로 복원 확인 | Claude | V4 런북 2절과 같은 명령 |
| 4 | Sync = V13 적용 | 사람 | 2절 |
| 5 | 자동 Sync 다시 켜기 | 사람 | `automated` 다시 있음 |
| 6 | 영어 이름 · 다른 표기 적재(`scripts/load-prod.sh --apply`) | Claude | 건조 실행을 보이고 사용자 승인 뒤 |

## 2. Sync 뒤 확인

- 새 Pod 로그에 `Successfully applied 1 migration … v13`, 2/2 Running, 공개 200.
- `/api/shoes` 302켤레 · 응답 키 43(`modelEn` · `modelAlias` 추가) · 모두 null.
- 적재기 건조 실행 — PATCH 는 `modelEn` · `modelAlias` 칸뿐(관리 화면 수정이 그 사이 있으면 그것도).

## 3. 실패했을 때

- 마이그레이션 실패 → Pod 가 뜨지 않는다(옛 Pod 유지). 자동 Sync 꺼진 채로 원인 확인. ADD COLUMN 이라 덤프 복원은 대개 필요 없다.
- 데이터 이상 → 덤프 복원(V10 런북 5절). 적재만 되돌리려면 `scripts/load-prod.sh --revert loads/<시각>.json`.

## 4. 실행 기록 (UTC)

| 단계 | 시각 | 내용 |
|---|---|---|
| 1 자동 Sync 끔 | 11-02 23:59 전 | 사용자. `automated` 없음(Claude 확인, push 직전) |
| 2 push | 11-02 23:59 | `39332f7` · `53a6969` → infra `8d63c78`(00:04) 이미지 `53a696940398`. 운영은 옛 이미지 `e9dd648afa57` · OutOfSync |
| 3 덤프 | 11-03 00:00:06 | `$B/runshoes-before-v13-20261103T000006Z.sql` 1,111,388 B · 600 · `Dump completed` · err 비밀번호 경고뿐 · sha256 `bb4339f6995aeec6d55a…`. 복원본: reviews 104 · 지문 `3e954039…`(운영 API 와 같음) · shoes 302 · users 34 · flyway 1~12 |
| 4 Sync | 11-03 00:05 | 사용자. 새 Pod 00:05:14 — `Migrating … "13 - model en"` → `Successfully applied 1 migration … v13`(**60ms**), 6.6초에 기동. 이미지 `53a696940398` 2/2 · Synced/Healthy(rev `8d63c78`) · 공개 200 · `/api/shoes` 302켤레 · 키 43 · `modelEn` · `modelAlias` 모두 null. 건조 실행 PATCH 301(modelEn 301 · modelAlias 108 + 관리 화면 수정 22건) |
| 5 자동 Sync 켬 | 11-03 00:06 | 사용자. `{"automated":{"prune":false,"selfHeal":false},…}`(Claude 확인) |
| 6 적재 | 11-03 00:07:07 | `scripts/load-prod.sh --apply` — 관리 화면 수정 22건을 먼저 판단으로, PATCH 301(modelEn 301 · modelAlias 108 · specSources 1 — 클리프톤 11 발볼 출처 MAN(관리 화면에서 넣은 값) · sku 1 — 발로스 v1 MBALCE1 → MBALLA1, 관리 화면에서 바꾼 대표 이미지의 품번). 다시 건조 실행 PATCH 0. 기록 `~/k8s-cluster/backup/2026-11-03-runshoes-load/2026-11-03T00-07-07-422Z.json`(600). 운영 검색: "SC 페이서" 2 · "퓨어셀" 8 · "베이퍼플라이 넥스트" 2 · "겔 카야노" 2 · "supercomp elite" 2 · "에스랩" 4. 영어 이름 301 · 다른 표기 108(엔돌핀 스피드 4 는 카탈로그 밖이라 비어 있다) |
