# runshoes — V12 와이드 모델 넷(있음 · 국외에만 있음 · 없음 · 정보 없음)

> 2026-11-02 — 사용자 결정. 절차는 V11(`v11-admin-history.md`)과 같다 — **이미지 Sync 가 곧 V12 적용**.

```bash
B=~/k8s-cluster/backup/2026-11-02-runshoes-v12   # 덤프 — 데이터가 들어 있어 git 밖
```

## V12

- `shoes.wide_scope VARCHAR(10) NULL` — 와이드가 있을 때(`wide_available = TRUE`) 어디에 나오나: `domestic` 국내(공식몰 · ABC마트 · 무신사 · 코오롱몰 같은 정식 판매처) · `overseas` 해외에만. 없음 · 정보 없음이면 NULL.
- `wide_available` 은 그대로(와이드가 어디에든 있으면 TRUE) — 추천 · 계약 시험이 참 · 거짓을 쓴다.
- 스펙 출처 코드 `NOTFOUND`(검색 결과 없음) — 와이드 모델만. 다섯 단계(KicksDB 캐시 · 국내 공식몰 · ABC마트 · BITR/RSG 리뷰 · 웹 검색)를 다 찾아도 안 나와 "없음"으로 둔 근거.
- 맨 뒤 열 추가라 MySQL 8 INSTANT. 기존 행은 NULL — 재조사(배포 뒤 적재기)가 채운다.
- 앱 커밋 `8a4d4a4` → 이미지 `8a4d4a42508b`(infra `4a54ca7`).

### 로컬 확인(2026-11-02)

- 백엔드 테스트 24/24, 로컬 DB Flyway `12:1`, API: `wideScope` overseas 200 · 잘못된 값 400 · `NOTFOUND` 와이드 200 · 다른 칸 400 · 되돌림.
- 계약: v3-search 24/24 · v3 101/11(V11 과 같은 11건) · v6 77/1(X101 품번 오류 문구 — 11-01 문구 변경, 이번과 무관).

## 1. 순서 (누가)

| # | 일 | 누가 | 확인 |
|---|---|---|---|
| 1 | 자동 Sync 끄기 | 사람 | `automated` 없음(Claude 확인) |
| 2 | 앱 커밋 · push → Jenkins → newTag 커밋 | Claude | 운영은 옛 이미지 |
| 3 | 덤프 + 로컬 다른 이름으로 복원 확인 | Claude | V4 런북 2절과 같은 명령 |
| 4 | Sync = V12 적용 | 사람 | 2절 |
| 5 | 자동 Sync 다시 켜기 | 사람 | `automated` 다시 있음 |
| 6 | 와이드 재조사 적재(`scripts/load-prod.sh --apply`) | Claude | 사용자 승인 뒤 |

## 2. Sync 뒤 확인

- 새 Pod 로그에 `Successfully applied 1 migration … v12`, 2/2 Running, 공개 200.
- `/api/shoes` 302켤레 · 응답 키 41(`wideScope` 추가) · 모두 `wideScope: null`.
- 적재기 건조 실행 PATCH 0(관리 화면 수정이 그 사이 있으면 그것만).

## 3. 실패했을 때

- 마이그레이션 실패 → Pod 가 뜨지 않는다(옛 Pod 유지). 자동 Sync 꺼진 채로 원인 확인. ADD COLUMN 이라 덤프 복원은 대개 필요 없다.
- 데이터 이상 → 덤프 복원(V10 런북 5절).

## 4. 실행 기록 (UTC)

| 단계 | 시각 | 내용 |
|---|---|---|
| 1 자동 Sync 끔 | 11-01 22:0x 전 | 사용자. `automated` 없음(Claude 확인, push 직전에 한 번 더) |
| 2 push | 11-01 22:0x | `8a4d4a4` → infra `4a54ca7` 이미지 `8a4d4a42508b` |
| 3 덤프 | 11-01 22:03:57 | `$B/runshoes-before-v12-20261101T220357Z.sql` 1,019,337 B · 600 · `Dump completed` · err 비밀번호 경고뿐 · sha256 `ab9bd03e987a9f6745e5…`. 복원본: reviews 104 · 지문 `3e954039…`(운영 API 와 같음) · shoes 302 · users 34 · flyway 1~11 |
| 4 Sync | 11-01 22:12 | 사용자. 새 Pod 22:12:23 — `Migrating … "12 - wide scope"` → `Successfully applied 1 migration … v12`(**36ms**), 7.5초에 기동. 이미지 `8a4d4a42508b` 2/2 · Synced/Healthy(rev `4a54ca7`) · 공개 200 · `/api/shoes` 302켤레 · 키 41 · `wideScope` 모두 null. 적재기 건조 실행 PATCH 3 — 모두 관리 화면 수정(880 v15 중량 · 클라우드몬스터 2 가격 · 님버스 27 발볼 · 가격), 다음 적재가 먼저 옮긴다 |
| 5 자동 Sync 켬 | 11-01 22:14 | 사용자. `{"automated":{"prune":false,"selfHeal":false},…}`(Claude 확인) |
