# runshoes — V11 관리 화면 보강(수정 시각 · 바뀐 칸 · 품번 · 영구 삭제)

> 2026-11-01 — 설계 확정(사용자: 적재기 수정은 이력에서 제외, `last_change` · `shoe_purges` 승인) · 로컬 리허설 끝. 0절은 Sync 직전에 다시 읽는다.

앱 리포: 마이그레이션 `backend/src/main/resources/db/migration/V11__admin_history.sql`, 설계 `docs/ADMIN_DEMO_DESIGN.md` 19절(작성 예정).
절차는 V10(`v10-auto-increment.md`)과 같다 — **이미지 Sync 가 곧 V11 적용**. 다른 점은 Sync 뒤에 **적재기로 품번(sku)을 채우는 운영 쓰기**가 한 번 있다는 것(5절, 사용자 승인 뒤).

```bash
B=~/k8s-cluster/backup/2026-11-01-runshoes-v11   # 덤프 — 데이터가 들어 있어 git 밖
mkdir -p $B && chmod 700 $B
VIP=http://192.168.122.240; H='Host: runshoes.ronanlab.dev'
mk() { ~/k8s-cluster/backup/2026-10-15-before-metallb/mk "$@"; }
```

## 왜 (2026-11-01 사용자)

- 294켤레를 하나씩 고치는 중 — **어디까지 했는지** 목록에서 보이게(최근 수정순 · 바뀐 칸 · 날짜)
- 관리 화면 수정이 어디에도 남지 않아 카야노 32 발볼 건을 nginx 로그 크기로 추적해야 했다 → `shoe.create` · `shoe.update`(바뀐 칸 이름만) · `shoe.purge`
- 품번(sku)이 카탈로그 파일에만 있다 — 크림에서 보며 관리 화면에서 직접 넣는다
- 숨긴 신발을 정말 지울 길이 없다 — 영구 삭제, 카탈로그가 다시 넣지 않게 제외 기록

## V11

```sql
ALTER TABLE shoes
  ADD COLUMN sku         VARCHAR(50) NULL,     -- 품번(색상 포함, 예 1011C284-400). 적재기 · 관리 화면이 채운다
  ADD COLUMN updated_at  DATETIME(3) NULL,     -- 관리자 등록 · 수정 · 숨김 · 되살리기 때만 앱이 찍는다. ON UPDATE 없음. 적재기는 찍지 않는다. 기존 행 NULL
  ADD COLUMN last_change JSON        NULL;     -- 마지막 수정의 바뀐 칸 이름(예 ["width","price"]) · ["created"] · ["hidden"] · ["restored"]. 값은 넣지 않는다
CREATE TABLE shoe_purges ( … shoe_id · line_key · generation · gender · brand · model · review_count · like_count · purged_at · purged_by … );   -- 전문은 앱 리포 파일
```

- 파일 sha256 `3b4d7268f6547941fa2b6cbc7901518b6703a83e8f792be19f578a9fe10a856b` · 로컬 Flyway checksum **`308032898`**
- 앱 쪽 바뀐 것: `X-Runshoes-Client: loader` 헤더(적재기)면 이력을 찍지 않는다 · 활동 로그 `shoe.create` · `shoe.update`(칸 이름만) · `shoe.purge` · `DELETE /api/admin/shoes/{id}`(숨긴 신발만) · `GET /api/admin/shoes/purged` · 응답 키 37 → 40
- 열 추가는 MySQL 8 INSTANT(테이블을 다시 만들지 않는다). 기존 294행은 세 칸 모두 NULL

### 로컬 리허설(2026-11-01, 운영과 같은 데이터 — V10 로컬 덤프 294켤레 · 리뷰 104)

| 항목 | 결과 |
|---|---|
| 적용 | `Migrating … "11 - admin history"` → `Successfully applied 1 migration … v11` **43ms**. 294행 sku · updated_at · last_change 모두 NULL, `shoe_purges` 0, FK 10 그대로, 응답 키 40 |
| 적재기 품번 | 건조 실행 PATCH 293 → `--apply` 293 · **updated_at · last_change 는 0행**(적재기 제외) · 활동 로그 `shoe.update` via loader 293 · 다시 건조 실행 PATCH 0 |
| 찾은 것 ① | 처음 품번 규칙 `[A-Za-z0-9-]` 이 5켤레를 400 으로 막았다(온 `71.98674` 셋 · 미즈노 `411448-RBUN / U1GD241751` · `J1GC258602/411495-0090`) → `-` `.` `/` 공백 허용으로 넓힘 |
| 찾은 것 ② | ①로 적재가 220건에서 멈춘 뒤 다시 돌리자 pull-admin 이 그 220건을 **관리자 수정으로 decisions.json 에 옮겼다**(되돌림) → 적재기가 한 건 쓸 때마다 스냅숏도 고치게. 다시 재현(56건에서 죽임): 1건만 남았다 — 서버가 쓴 직후 · 스냅숏 전에 죽은 그 한 건 |
| **옛 이미지 롤백** | 운영 코드(`4ad8086`) jar 를 V11 DB 에: `validated 11 migrations` · `up to date`, 관리자 PATCH 200 · 리뷰 POST 201 · 지우기 200(응답에 V11 키만 없다) |
| 관리 화면 | 수정 → 목록 맨 위 "발볼 수정 11-01 05:44" · "발볼·가격 외 1건" · 신규 등록. 정렬 4종 · 방향 바꾸기 · 숨김 문구 · 영구 삭제(확인 창 리뷰 · 찜 수, 숨긴 목록에서 빠짐, 기록 남음) — PC · 390px |
| 계약 | v6 **78**(새 X100~X115) · v3 101/11(그대로) · v4 21 · v3-search 24 · v3-summary 5 · 단위 테스트 24(새 3) |

## 0. 출발 상태 (2026-11-01 05:4x KST, 읽기만 — Sync 직전에 다시 읽는다)

| 항목 | 값 |
|---|---|
| 운영 이미지 | `runshoes:4ad808634f07`(앱 `4ad8086`, 카탈로그 커밋 — 코드는 `597b48e` 와 같다) |
| ArgoCD | Synced · Healthy, revision `cc79c8b`, **자동 Sync 켜짐** |
| `/api/shoes` | 294켤레 · 응답 키 37 · 최대 id 294 · 숨긴 것 0 |
| `/api/reviews` | 104건 · 최대 id 105 · 짝 지문 `3e954039a1aa3f86684cd3912fc6e75a5f46027f994c9a9b7b3f13e9498f12b1` |
| Flyway | 1~10(10 `-1713919463`), FK 10 |
| 적재기 건조 실행(운영) | **PATCH 293 · `{"sku":293}` 만** — 카야노 32 발볼 · 출처(11-01 19:52 관리 화면)는 미리 pull-admin 으로 옮겼다 |

## 1. 순서 (누가 · 멈추는 곳)

| # | 할 일 | 누가 | 확인 |
|---|---|---|---|
| 1 | **자동 Sync 끄기** | **사람** | `syncPolicy` 에 `automated` 없음(Claude 확인) |
| 2 | 이 런북 커밋 · push | Claude(승인 뒤) | |
| 3 | 앱 커밋 · push → Jenkins → newTag 커밋 | Claude(승인 뒤) | 1 을 확인한 뒤. 운영은 옛 이미지(OutOfSync) |
| 4 | 이미지 안 마이그레이션 `scripts/check-image-migrations.sh <태그>` | Claude | V1~V10 그대로 · V11 `3b4d7268…` |
| 5 | **덤프** + 로컬 다른 이름으로 복원 확인 | Claude | V10 런북 2절과 같다 |
| 6 | **덤프 직후** 운영 지문 | Claude | 0절과 같다. 다르면 멈춘다 |
| 7 | Sync = V11 적용 | **사람** | 4절 |
| 8 | 적재기로 품번 채우기 — 건조 실행 → **보고 · 승인** → `--apply` | Claude(승인 뒤) | 5절 |
| 9 | 자동 Sync 다시 켜기 | **사람** | `automated` 다시 있음 |

5 → 6 → 7 은 끊지 않는다. 8 은 7 이 확인된 뒤 따로(운영 쓰기라 승인을 다시 받는다).

## 4. Sync 뒤 확인

- 로그 `Migrating … "11 - admin history"` → `Successfully applied 1 migration … v11`
- Flyway `11 1 308032898`(로컬과 같아야)
- `shoes` 열 `sku` · `updated_at` · `last_change` 있음, 294행 모두 NULL · `shoe_purges` 0행, FK 10 그대로(`SET SESSION information_schema_stats_expiry = 0` 은 필요 없다 — 열 · 행 수만 본다)
- API 리뷰 수 · 지문 그대로, 신발 294 · 응답 키 37 → 40(`sku` · `updatedAt` · `lastChange`), 공개 주소 200
- 운영 쓰기 시험은 하지 않는다

## 5. 품번 채우기(적재기)

- `node catalog/load.mjs --base $VIP --host runshoes.ronanlab.dev` 건조 실행 → **`PATCH 293 · {"sku":293}` 만**(0절과 같다). 다른 칸이 섞이면 멈춘다 — Sync 사이에 관리 화면에서 고친 것이다(pull-admin 이 먼저 옮긴다)
- **보고 · 승인 뒤** `ADMIN_EMAIL=… ADMIN_PASSWORD=… node load.mjs --base … --host … --apply`(비밀번호는 env 파일로만)
- 끝나면: `updated_at IS NOT NULL` 0행 · `last_change` 0행(적재기 제외), sku 293행, 활동 로그 `shoe.update` via loader 293, 다시 건조 실행 PATCH 0. `decisions.json` 이 바뀌지 않았는지(git status)

## 6. 실패했을 때

- R1 마이그레이션 실패 → Pod 가 뜨지 않는다(옛 Pod 유지, maxUnavailable 0). 자동 Sync 꺼진 채로 원인 확인, 덤프로 되돌릴 필요는 대개 없다(INSTANT ADD COLUMN 은 원자적)
- R2 새 앱 문제 → 옛 태그로 되돌린다(옛 jar 는 V11 DB 에서 돈다 — 리허설에서 확인)
- R3 데이터 이상 → 덤프 복원(V10 런북 5절 절차)

## 7. 실행 기록 (시각은 UTC)

| 단계 | 시각 | 결과 |
|---|---|---|
| 1 자동 Sync 끔 | 10-31 20:5x 전 | 사용자. `{"syncOptions":["CreateNamespace=false"]}`(automated 없음, Claude 확인 — 앱 push 직전에 한 번 더) |
| 2 이 런북 | 10-31 20:50 | `ec18bb8` |
| 3 앱 push | 10-31 20:5x | `a6b4031`(모달) · `a9f17e0`(V11 · 편집 폼 불러오기 전 입력 막기) · `182f6ae`(카탈로그) → Jenkins `58d3ce7`(20:56, newTag 두 줄만) `182f6aee7808` |
| 4 이미지 확인 | 10-31 20:57 | digest `sha256:d29d7962…`, V1~V11 sha256 = 커밋 파일(`diff` 없음), V11 `3b4d7268…` |
| 5 덤프 | 10-31 20:58:20 | `~/k8s-cluster/backup/2026-11-01-runshoes-v11/runshoes-before-v11-20261031T205820Z.sql` 679,756 B · 600 · `Dump completed` · err 비밀번호 경고뿐 · sha256 `9effb3cb…`. 로컬 다른 이름 DB 에 복원 — 리뷰 104 · `3e954039…` · 신발 294 · 사용자 34 · Flyway 1~10, 확인 뒤 지움 |
| 6 지문 | 10-31 20:58:20 | 리뷰 104 · `3e954039…` · 최대 id 105 / 신발 294 · 키 37 · 최대 id 294 · 숨김 0 / Flyway 1~10 그대로 / FK 10 / V11 열 없음 — 0절과 같다 |
| 7 Sync | 10-31 20:59~21:00 | 사용자. 새 Pod 21:00:02 — `Migrating … "11 - admin history"` → `Successfully applied 1 migration … v11`(**68ms**), 6.5초에 기동 |
| 4절 확인 | 10-31 21:01 | 이미지 `182f6aee7808` 둘 · 새 Pod 2/2 재시작 0 / `11 1 308032898` / 열 셋 · 294행 모두 NULL · `shoe_purges` 0 · FK 10 / 리뷰 104 · 지문 그대로 · 신발 294 · 키 40 / 공개 200 · VIP 200 · 영구 삭제 기록 비로그인 401 / ERROR · Deadlock 0줄. 운영 쓰기 시험 없음 |
| 8 품번 채우기 | 10-31 21:04:57~21:05:05 | 사용자 승인 뒤. 건조 실행 `PATCH 293 · {"sku":293}` → `--apply` **PATCH 293 · POST 0**(관리자 비밀번호는 Secret 에서 env 로만). sku 293행(엔돌핀 스피드 4 만 NULL) · **updated_at · last_change 0행**(적재기 제외) · 활동 로그 `shoe.update` via loader 293(fields `["sku"]`) · 다시 건조 실행 PATCH 0 · `decisions.json` · `shoes.jsonl` 그대로. 기록 `…/2026-11-01-runshoes-v11/2026-10-31T21-04-59-377Z.json`(600) |
| 9 자동 Sync 켬 | 10-31 21:0x | 사용자. `{"automated":{"prune":false,"selfHeal":false},…}`(Claude 확인). 그 사이 쌓인 텔레그램 커밋 `7773b76` → `89142bb` `7773b767eb2f` 배포 — 코드 · 스키마 같다, `up to date`, 7.3초에 기동, 리뷰 104 · 지문 그대로 · 신발 294 · sku 293. Synced · Healthy |
| 뒤 | 10-31 21:09 | 관리 화면에서 카야노 32 숨김(21:09:34) → 되살리기(21:09:42) — `updated_at` · `last_change ["restored"]` 가 찍혔다(설계대로, 관리자 계정) |
