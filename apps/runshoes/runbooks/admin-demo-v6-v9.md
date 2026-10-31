# runshoes — 관리 화면 · 마이페이지 · 데모 계정(V6 스펙 출처 · V7 데모 관리자 · V8 신발 숨김 · V9 회원 탈퇴)

앱 리포: 마이그레이션 `backend/src/main/resources/db/migration/V6__spec_sources.sql` ~ `V9__user_withdraw.sql`, 설계 `docs/ADMIN_DEMO_DESIGN.md`(10 · 12절), API `docs/API_CONTRACT.md` 2.5, 적재기 `catalog/load.mjs` · `pull-admin.mjs`.
절차는 V4 · V5(`catalog-v4-v5.md`)와 같다 — **이미지 Sync 가 곧 V6~V9 적용**(새 Pod 가 뜰 때 Flyway). 그 뒤 적재기가 스펙 출처(`specSources`)를 채운다.
**한 번에 배포한다**(2026-10-30 사용자 — 관리 화면 수정 보호 스크립트도 따로 push 하지 않았다. 자동 Sync 를 두 번 껐다 켜지 않게).
명령은 호스트에서 `mk`(= `~/k8s-cluster/backup/2026-10-15-before-metallb/mk`)로 kubectl 을 부른다.

```bash
B=~/k8s-cluster/backup/2026-10-30-runshoes-admin-demo-v6v9   # 덤프 · 적재 기록 — 데이터가 들어 있어 git 밖
mkdir -p $B && chmod 700 $B
VIP=http://192.168.122.240; H='Host: runshoes.ronanlab.dev'
mk() { ~/k8s-cluster/backup/2026-10-15-before-metallb/mk "$@"; }
```

## 0. 출발 상태 (2026-10-30 04:0x KST, 읽기만으로 확인)

| 항목 | 값 |
|---|---|
| 운영 이미지 | `harbor.ronanlab.dev/runshoes/runshoes:03534b17a3ad`(앱 `03534b1`) |
| ArgoCD `runshoes` | Synced · Healthy, revision `2a79178`, **자동 Sync 켜짐**(`automated: {prune: false, selfHeal: false}`) — `kubectl get application` 으로 확인 |
| `/api/shoes` | 294켤레 · 최대 id 294 · 응답 키 36(`specSources` 없음) · `wideAvailable: false` 3켤레 |
| `/api/reviews` | 104건 · 짝 지문 `3e954039a1aa3f86684cd3912fc6e75a5f46027f994c9a9b7b3f13e9498f12b1` · **내용 최대 83자**(300자 제한에 걸리는 리뷰 없음) |
| Flyway | V4 런북 기록대로 1~5(4 `-942386036` · 5 `1378788652`). 3절에서 본다 |
| 적재기 건조 실행 | 어드민 수정 0건 · POST 0 · PATCH 293(전부 `specSources` — V6 전이라 응답에 없다) |
| 관리 화면 스냅숏 | `catalog/local/work/snapshot-runshoes.ronanlab.dev.json`(10-29, 운영 = 카탈로그일 때) |

앱 리포 쪽(로컬에서 끝낸 것, 커밋 전):
- 계약 테스트(2026-10-30, 로컬 jar · `--allow-added` 에 `specSources` 더함): v3 PASS 103 · FAIL 9 — **9건 모두 의도한 변경**(가입한 계약 계정 id 32 → 33: V7 의 데모 관리자가 32 를 가져간다 6건 · `/api/me` 에 `createdAt` · 신발 숨김으로 새 신발 id 21 → 22 두 건), v3-search 24, v3-summary 5 · INFO 5, v4 21, **새 기준선 spring-v6 57 PASS · INFO 1**(체험 카드는 무작위라 모양만)
- 마이그레이션 sha256(소스 = 로컬 jar 안): V6 `9d6599ee71554357…` · V7 `c55e21058e0c2b68…` · V8 `8f150e7981dd0f2e…` · V9 `80dbba588a8586bf…`
  로컬 Flyway checksum V6 `-1597188006` · V7 `-1950123291` · V8 `-223806260` · V9 `-371820711`
- **리허설**(로컬 V5 DB 사본 → 새 jar): `Successfully applied 4 migrations … now at version v9`, 데모 관리자 id 32 · `'!demo'`, 적재기 `--apply` → `어드민 수정 0건` · PATCH 293(specSources) → 다시 건조 실행 0. 숨기기 → 적재 → 되살리기 → 적재: 다시 넣지 않고 멈추지도 않는다
- **옛 이미지 롤백 확인**: 커밋 `03534b1` 의 jar 를 V9 DB(숨긴 신발 1 · 탈퇴 회원 1 · 데모 관리자)에 띄우면 `Successfully validated 9 migrations` · `newer than the latest available migration (5)` 경고 · `up to date`. 신발 294(**숨긴 신발이 다시 보인다**) · 리뷰 그대로("탈퇴 회원" 이름), 탈퇴 회원 · 데모 관리자 로그인 401, 관리자 로그인 200

## 1. 순서 (누가 · 멈추는 곳)

| # | 할 일 | 누가 | 확인 |
|---|---|---|---|
| 1 | **자동 Sync 끄기** — V4 런북 1.1 그대로 | **사람** | `syncPolicy` 에 `automated` 없음(Claude 도 `get application` 으로 본다) |
| 2 | 이 리포: `apps/runshoes/app/deployment.yaml` 의 env `DEMO_LOGIN_ENABLED: "true"` + 이 런북 커밋 · push | Claude(사용자 승인 뒤) | 그 두 파일만. 1 이 먼저 — 자동 Sync 가 켜져 있으면 옛 이미지에 env 만 들어간다(옛 이미지는 읽지 않는다 — 해는 없다) |
| 3 | 앱 리포 커밋 · push → Jenkins 가 이미지 빌드 → 이 리포에 newTag 커밋 | Claude(사용자 승인 뒤) | Jenkins SUCCESS, 태그 커밋은 newTag 두 줄만 |
| 4 | 이미지 안의 마이그레이션 확인 — 6절 | Claude(막히면 사람) | V1~V9 sha256 = 0절 · 앱 커밋 파일 |
| 5 | **사전 점검**(2.1) — V7 이 넣을 계정과 겹치는 이메일 · 닉네임이 없는지, CHECK 이름 | **사람**(MySQL 줄) | 0 · `ck_users_role` |
| 6 | **백업**(2절) + 로컬에 다른 이름으로 복원 확인 | **사람**(블록 그대로) → 출력을 Claude 가 확인 | 2절의 세 가지 |
| 7 | **덤프 직후** 운영 지문 재확인(3절) | 사람(Flyway 줄) · Claude(API 줄) | 신발 294 · 리뷰 104 · 지문 `3e954039…` · Flyway 1~5. 다르면 멈춘다 |
| 8 | newTag 커밋 Sync = V6~V9 적용 | **사람(Sync)** | 4절 |
| 9 | 적재 — 스펙 출처 293켤레(5절) | **사람**(관리자 비밀번호가 드는 한 줄) · Claude(건조 실행 · 확인) | 5.2 |
| 10 | 화면 확인 | 사람 | 5.3 |
| 11 | 자동 Sync 다시 켜기 | **사람** | `automated` 다시 있음 |

- **6 → 7 → 8 은 끊지 않고 잇는다.** 덤프 뒤 · Sync 전에 들어온 쓰기는 덤프에 없다 — 7절 R2 로 복원하면 사라진다. 길어졌으면 6 · 7 을 다시 한다
- 8 과 9 사이에는 급할 것이 없다 — V6~V9 는 칸을 더하고 계정 하나를 넣을 뿐이고, 화면은 그대로 보인다(스펙 출처만 빈칸 → 적재로 채운다)
- 3 의 push 는 **1 이 끝난 것을 보고** 한다. 자동 Sync 가 켜진 채 push 하면 Jenkins 태그 커밋이 3분 안에 배포돼 5~7(점검 · 백업 · 지문)을 건너뛴다
- **적재기는 V6 전 앱에는 `--apply` 하지 않는다**(응답에 `specSources` 가 없으면 exit 2) — 8 전에 실수로 적재해도 막힌다

## 2. 백업 — 운영 MySQL 덤프

V4 런북 2절과 같은 명령 · 같은 확인이다. 이름만 `runshoes-before-v6-$TS`, 폴더만 위의 `$B`.

**사람이 친다**:

```bash
B=~/k8s-cluster/backup/2026-10-30-runshoes-admin-demo-v6v9; VIP=http://192.168.122.240; H='Host: runshoes.ronanlab.dev'
mk() { ~/k8s-cluster/backup/2026-10-15-before-metallb/mk "$@"; }
TS=$(date -u +%Y%m%dT%H%M%SZ)
mk 'kubectl -n runshoes exec runshoes-mysql-0 -c mysql -- sh -c "exec mysqldump -uroot -p\"\$MYSQL_ROOT_PASSWORD\" --single-transaction --set-gtid-purged=OFF --routines --triggers --default-character-set=utf8mb4 runshoes"' \
  > $B/runshoes-before-v6-$TS.sql 2> $B/runshoes-before-v6-$TS.err
chmod 600 $B/runshoes-before-v6-$TS.*
```

**덤프에는 비밀번호 해시(BCrypt) · refresh token 해시 · 활동 로그(IP · User-Agent)가 들어 있다** — `chmod 600`, git · 공유 폴더에 두지 않는다.
확인 세 가지(끝까지 떴는가 · 로컬 `runshoes_restore_check` 에 넣어 보기 · 리뷰 지문이 운영 API 와 같은가)는 V4 런북 2절 (1)~(3) 의 파일 이름만 바꿔 그대로. (3) 의 기대값: shoes **294** · users(그때 수) · flyway `1:1,2:1,3:1,4:1,5:1`.

### 2.1 사전 점검 — V7 이 넣는 계정

V7 은 `demo-admin@runshoes.test` · 닉네임 `데모관리자` 를 넣는다(이미 있으면 건너뛴다 — 이메일 기준). **다른 계정이 그 닉네임을 쓰고 있으면 INSERT 가 UNIQUE 로 실패한다**(7절 R1).
가입 규칙은 예약어 `관리자` 만 막는다(`데모관리자` 는 가입할 수 있는 닉네임이다). **사람이 친다**:

```bash
mk 'kubectl -n runshoes exec runshoes-mysql-0 -c mysql -- sh -c "mysql -N -uroot -p\"\$MYSQL_ROOT_PASSWORD\" runshoes -e \"SELECT COUNT(*) FROM users WHERE email = '\''demo-admin@runshoes.test'\'' OR nickname = '\''데모관리자'\''; SELECT CONSTRAINT_NAME FROM information_schema.CHECK_CONSTRAINTS WHERE CONSTRAINT_SCHEMA = '\''runshoes'\''; SELECT COUNT(*), MAX(id) FROM users\""'
# → 0 / ck_users_role / (사용자 수) (최대 id) — 0 이 아니면 멈추고 Claude 와 V7 을 고친다
```

## 3. 운영 지문 재확인 (Sync 직전)

API 두 줄은 Claude, Flyway 줄은 **사람이 친다**.

```bash
curl -s -H "$H" $VIP/api/reviews | node -e '
  const r=JSON.parse(require("fs").readFileSync(0)).sort((a,b)=>a.id-b.id);
  const h=require("crypto").createHash("sha256").update(r.map(x=>x.id+":"+x.shoeId).join(",")).digest("hex");
  console.log(r.length===104 && h==="3e954039a1aa3f86684cd3912fc6e75a5f46027f994c9a9b7b3f13e9498f12b1" ? "OK" : "다름", r.length, h, "최대", Math.max(...r.map(x=>[...x.content].length)))'
curl -s -H "$H" $VIP/api/shoes | node -e 'const s=JSON.parse(require("fs").readFileSync(0)); console.log(s.length, Object.keys(s[0]).length, Math.max(...s.map(x=>x.id)))'
mk 'kubectl -n runshoes exec runshoes-mysql-0 -c mysql -- sh -c "mysql -N -uroot -p\"\$MYSQL_ROOT_PASSWORD\" runshoes -e \"SELECT version, success, checksum FROM flyway_schema_history ORDER BY installed_rank\""'
# → OK 104 3e954039… 최대 83(300 이하) / 294 36 294 / 1~5 (4 -942386036 · 5 1378788652)
```

- 리뷰가 늘었으면 멈추지 않아도 된다 — V6~V9 에는 데이터 가드가 없다. 새 값을 9절에 적고 덤프가 그 뒤에 뜬 것인지만 본다. **300자를 넘는 리뷰가 생겼으면 멈춘다**(사용자 조건 — 고칠 때 400 이 난다)

## 4. 이미지 Sync 뒤 확인 (V6~V9)

`rollout` · `logs` · `curl` 은 Claude, MySQL 줄은 **사람이 친다**.

```bash
mk 'kubectl -n runshoes rollout status deploy/runshoes --timeout=180s'
mk 'kubectl -n runshoes logs deploy/runshoes -c runshoes | grep -E "Migrating|Successfully applied|ERROR"'
#   → "6 - spec sources" / "7 - demo admin" / "8 - shoe soft delete" / "9 - user withdraw"
#     Successfully applied 4 migrations to schema `runshoes`, now at version v9
mk 'kubectl -n runshoes exec runshoes-mysql-0 -c mysql -- sh -c "mysql -N -uroot -p\"\$MYSQL_ROOT_PASSWORD\" runshoes -e \"SELECT version, success, checksum FROM flyway_schema_history ORDER BY installed_rank; SELECT id, email, role, LEFT(password_hash, 5), deleted_at FROM users WHERE role = '\''DEMO_ADMIN'\''; SELECT COUNT(*), SUM(deleted_at IS NOT NULL), SUM(spec_sources IS NOT NULL) FROM shoes; SELECT COUNT(*) FROM reviews\""'
#   → 1~5 그대로, 6 -1597188006 · 7 -1950123291 · 8 -223806260 · 9 -371820711(로컬 checksum 과 같아야 — 시험한 그 파일)
#     (새 id) demo-admin@runshoes.test DEMO_ADMIN !demo NULL / 294 0 0 / 104
curl -s -H "$H" $VIP/api/shoes/1 | node -e 'const s=JSON.parse(require("fs").readFileSync(0)); console.log(Object.keys(s).length, "specSources" in s)'   # → 37 true
curl -s -H "$H" $VIP/api/auth/demo-accounts | node -e 'const a=JSON.parse(require("fs").readFileSync(0)); console.log(a.length, a.map(x=>x.role).join(","))'
#   → 4 USER,USER,USER,DEMO_ADMIN (404 면 env DEMO_LOGIN_ENABLED 가 안 들어갔다 — 2 를 본다)
curl -s -o /dev/null -w '%{http_code}\n' https://runshoes.ronanlab.dev/   # → 200
```

## 5. 적재 — 스펙 출처(specSources) 293켤레

```bash
cd ~/AI_programming/runshoes/catalog
LOAD="node load.mjs --base $VIP --host runshoes.ronanlab.dev"
$LOAD     # 건조 실행(Claude) → 적용하면 어드민 수정 0건 … / POST 0 · PATCH 293 · 같음 0 / PATCH 필드별 {"specSources":293}
```

- 어드민 수정이 0 이 아니면 — 10-29 스냅숏 뒤 관리 화면에서 고친 것이다. **멈추지 않는다**: `--apply` 가 먼저 `decisions.json` 으로 끌어오고 진행한다(로그 "어드민 수정 N건을 decisions.json에 반영했다" + 칸별 전 → 후). 무엇이 끌려왔는지 9절에 적는다
- 새로 넣은 신발이 있으면 멈춘다(exit 3) — 사용자가 후보 목록에 넣을지 정한 뒤 `--structure-ok`

**사람이 친다**(관리자 비밀번호는 Secret 에서 파이프로만):

```bash
cd ~/AI_programming/runshoes/catalog
B=~/k8s-cluster/backup/2026-10-30-runshoes-admin-demo-v6v9
mk() { ~/k8s-cluster/backup/2026-10-15-before-metallb/mk "$@"; }
admin() { ADMIN_EMAIL=admin@runshoes.test ADMIN_PASSWORD="$(mk 'kubectl -n runshoes get secret runshoes-auth -o jsonpath={.data.ADMIN_PASSWORD}' | base64 -d)" "$@"; }
admin node load.mjs --base http://192.168.122.240 --host runshoes.ronanlab.dev --apply
#   → 어드민 수정 0건을 decisions.json에 반영했다 / 썼다: PATCH 293 · POST 0 → …/loads/<시각>.json / 스냅숏 294켤레 → …
cp -p $(ls -t loads/*.json | head -1) $B/ && chmod 600 $B/*.json
```

마지막에 Claude 가 `$LOAD` 건조 실행 → 어드민 수정 0건 · POST 0 · PATCH 0 · 같음 293.

### 5.2 확인

```bash
curl -s -H "$H" $VIP/api/shoes | node -e '
  const s=JSON.parse(require("fs").readFileSync(0)), c={};
  for (const x of s) for (const [f,v] of Object.entries(x.specSources ?? {})) c[v.code]=(c[v.code]??0)+1;
  console.log("신발", s.length, "출처 있음", s.filter(x=>x.specSources).length, JSON.stringify(c))'
#   → 294 · 출처 있음 293(엔돌핀 스피드 4 는 카탈로그 밖이라 null) · BITR · RSG · STORE · PR · WEB · MAN · DB 수
# 리뷰 지문은 3절과 같아야 한다(적재는 리뷰를 건드리지 않는다)
mk 'kubectl -n runshoes logs deploy/runshoes -c runshoes --since=5m | grep -cE "ERROR|Exception"'   # → 0
```

### 5.3 화면 (사람)

- **로그인**: "처음이세요? 회원가입 화면으로 이동합니다", 체험 카드 4장(시드 3 + 데모 관리자, 진짜 관리자 없음). 회원가입: "이미 계정이 있으세요? 로그인 화면으로 이동합니다"
- **데모 관리자 카드** → 등록·관리. 수정 폼 저장 · 삭제 · 되살리기 · 리뷰 · 찜을 누르면 "데모 관리자 계정은 할 수 없습니다"
- **관리 폼**(진짜 관리자): 용어, 세대 줄, 출처 드롭다운(WEB · MAN 이면 주소 칸), 카본 · 와이드 · 발볼 "정보 없음", 와이드 "없음" 저장에 출처 요구, 숫자 칸, 화살표 여백, 이미지 썸네일
- **삭제 확인 창**: 리뷰 N개 · 찜 M개, 현행 세대를 숨기면 "이 라인에 현행이 없어집니다". 숨긴 신발 → 되살리기. **운영 신발을 시험으로 숨겼다면 되살리고, 다음 적재가 끌어오기 전에 9절에 적는다**
- **마이페이지**(시드 체험 카드): 왼쪽 목차 · 활동 요약 · 내 리뷰 표(펼치기 · 수정 · 삭제) · 찜 목록 · 회원 탈퇴 확인 화면("계속 이용하고 싶어요"가 강조). 시드 · 관리자 계정은 탈퇴 · 닉네임 변경이 "체험 · 관리자 계정은 … 수 없어요"
- **리뷰**: 입력 중 "남은 글자 N자", 301자 이상 안 들어간다

## 6. 이미지 안의 마이그레이션 확인 (Sync 전)

```bash
apps/runshoes/scripts/check-image-migrations.sh <태그>
for v in V1__schema V2__seed_data V3__auth V4__shoe_generations V5__price_reference V6__spec_sources V7__demo_admin V8__shoe_soft_delete V9__user_withdraw; do
  git -C ~/AI_programming/runshoes show <커밋>:backend/src/main/resources/db/migration/$v.sql | sha256sum; done
# → 아홉 줄이 같고: V1 0db56bb0… · V2 9091885d… · V3 ec24e0e4… · V4 db22befe… · V5 8d512eb7… · V6 9d6599ee… · V7 c55e2105… · V8 8f150e79… · V9 80dbba58…
```

## 7. 실패했을 때

V6~V9 는 Flyway 가 한 번에 차례로 적용한다. **MySQL DDL 은 트랜잭션이 아니다** — 실패한 곳 앞까지는 남는다. 실패한 새 Pod 는 Ready 가 되지 않아 옛 Pod 가 계속 돈다(maxUnavailable 0) — 급할 것은 없다.

| 멈춘 곳 | DB 상태 | 복구 |
|---|---|---|
| **R1 V7 INSERT** — 닉네임 `데모관리자` 가 이미 있다(2.1 을 건너뛰었을 때) | V6 적용 · V7 은 CHECK 만 넓혀진 채 `success 0` 한 줄 | 옛 이미지는 V6 · 넓힌 CHECK 에서 그대로 돈다. `DELETE FROM flyway_schema_history WHERE version = 7 AND success = 0` → V7 닉네임을 고친 새 이미지(체크섬이 바뀐다 — 6절 다시) 또는 R2 |
| **R2 그 밖의 V6~V9 실패** | 일부만 적용 | **사람이 친다** — V3 런북 5.2 와 같은 순서(이름만 `runshoes-before-v6-$TS`): replicas 0 → DB 다시 만들기 → `sha256sum -c` → 2절 덤프 넣기 → 3절 지문 → newTag 커밋 revert → Sync. **그다음 적재 전에 스냅숏을 덤프 시점으로** — `node load.mjs --base … --host … --snapshot`(덤프 뒤 관리 화면 수정이 없을 때). 안 하면 적재기가 되돌린 차이를 관리 화면 수정으로 끌어온다(앱 리포 docs/CATALOG_PIPELINE.md 7.1 의 6) |
| **R3 V9 까지 됐는데 새 앱이 이상하다** | V9 그대로 둔다 | newTag 커밋만 revert → Sync. 옛 이미지가 V9 DB 에서 뜬다(0절 — 로컬 확인). 단 **숨긴 신발이 다시 보이고**, 데모 관리자 · 탈퇴 회원은 로그인할 수 없고(표식 해시), 탈퇴 회원 리뷰는 "탈퇴 회원"으로 보인다. 데모 관리자의 남은 access token(15분)은 옛 이미지에서 USER 로 보인다 — 급하면 refresh_tokens 의 그 계정 행을 폐기 |
| **R4 적재가 이상하다** | V9 + 출처 일부 | **사람이 친다**: `admin node load.mjs --base … --host … --revert $B/<시각>.json` — 바꾼 출처를 되돌린다(로컬 확인). 다음 `--apply` 는 다시 채운다 |

## 8. 덤프 보관

| 덤프 | 지우는 때 |
|---|---|
| `runshoes-before-v6-*.sql` (V6 직전, V5 상태) | V10(옛 칸 정리)을 운영에 적용하고 2주 탈 없이 돈 뒤 |
| `runshoes-before-v4-*.sql` | V4 런북 8절 — 옛 칸 정리는 V6 이 아니라 **V10** 으로 밀렸다(V6~V9 가 먼저). 그 시계도 V10 기준 |
| 적재 기록 `$B/*.json` | V10 뒤 |

## 9. 이어서 — 다듬기 배포(2026-10-30 사용자, 앱 리포 docs/ADMIN_DEMO_DESIGN.md 13절)

V6~V9 배포 뒤 화면 다듬기 10건. **마이그레이션이 없다**(V1~V9 그대로) — 덤프 · 지문은 필요 없고, 데이터는 적재기가 바꾼다(`--revert` 기록이 남는다). 자동 Sync 는 아직 꺼져 있으니 그대로 잇는다.

| # | 할 일 | 누가 | 확인 |
|---|---|---|---|
| 1 | 앱 커밋 · push → Jenkins → 태그 커밋 | Claude(승인 뒤) | newTag 두 줄만 |
| 2 | 이미지 확인(6절) | Claude | V1~V9 sha256 이 0절과 같다(바뀐 마이그레이션 없음) |
| 3 | Sync | **사람** | 새 Pod · `validated 9 migrations` · `up to date`, `/api/auth/demo-accounts` 31장(시드 30 + 데모 관리자, 찜 수 포함) |
| 4 | 적재 — 가격 종류 `정가` → `발매가` 94켤레 | **사람**(관리자 비밀번호 — Secret 을 새 비밀번호로 바꿨으면 5절 `admin()` 그대로) · Claude(건조 실행 · 확인) | 건조 실행 `PATCH 94` `{"priceKind":94}` → 적용 → 다시 0. 리뷰 지문 그대로 |
| 5 | 화면 확인(13절 열 가지) | 사람 | |
| 6 | 자동 Sync 다시 켜기 | **사람** | `automated` 다시 있음 → 이 리포 매니페스트도 되돌려 커밋 |

- 3 과 4 사이에는 옛 값 `정가` 94행이 남아 있다 — 화면은 가격 옆 "발매가"를 관리 폼에서만 보여 주므로 공개 화면에는 차이가 없다. 그 사이 관리 화면에서 가격을 저장하면 `발매가`로 저장된다(새 서버는 `정가`를 받지 않는다)

### 9.1 다듬기 2차(앱 리포 docs/ADMIN_DEMO_DESIGN.md 14절) — 같은 순서

**서버 · 마이그레이션 변경 없음**(프런트 · 카탈로그만, 계약 v3 103/9 · v4 21 · v6 60 그대로). 적재는 **페가수스 42 · 클리프톤 10 의 이미지 4장씩**(`PATCH 2`, `{"images":2}`) — 2026-10-30 운영 건조 실행으로 확인(어드민 수정 0).
Sync 뒤 화면: 두 신발 상세 모달에 화살표 · 썸네일 줄, 나머지는 사진 1장 그대로.

### 9.2 다듬기 3차(앱 리포 docs/ADMIN_DEMO_DESIGN.md 15절) — 같은 순서

프런트만(체험 카드 흐름 · 화살표 · 대표로 지정 · 행택 · 문구). **서버 · 마이그레이션 · 카탈로그 변경 없음 — 적재할 것이 없다**(Sync 뒤 건조 실행 0 만 확인).

## 10. 실행 기록 (시각은 UTC)

| 단계 | 시각 | 결과 |
|---|---|---|
| 0절 출발 상태 | 10-29 19:0x | 위 표(Claude, 읽기만) |
| 1 자동 Sync 끄기(사람) | 10-29 19:1x | `syncPolicy` = `{"syncOptions":["CreateNamespace=false"]}`(Claude 도 확인) |
| 5 사전 점검(2.1, 순서를 당겨 push 전에 — 읽기만) | 19:1x | 겹치는 이메일 · 닉네임 0, `ck_users_role`(USER · ADMIN), users 33 · 최대 id 33, Flyway 1~5 checksum 0절과 같다 |
| 2 infra `456303e`(런북 · env · 매니페스트) · 3 앱 `ccd0f20` push | 19:1x | 앱 127파일(계약 기준선 spring-v6 59 포함 — 토큰 · 비밀번호는 <가림>) |
| Jenkins → 태그 커밋 `06d7572` | 19:2x | newTag 두 줄만(`ccd0f20c3182`). 운영 이미지는 `03534b17a3ad` 그대로(OutOfSync — 자동 배포 안 됨) |
| 4 이미지 확인(6절, w2 containerd) | 19:2x | digest `sha256:16a1a1a84dfc6949…`, V1~V9 sha256 = 커밋 `ccd0f20` 파일 |
| 6 덤프(Claude) | 19:23:42 | `runshoes-before-v6-20261029T192342Z.sql` 450,868 bytes, sha256 `7a49913d502bc448400158deaf68512837ff682b16483f029d4824407450e558`, `Dump completed`, stderr 는 비밀번호 경고만 |
| 6 복원 확인(로컬 `runshoes_restore_check`) | 19:23:4x | 종료코드 0, 리뷰 104 · `3e954039…` = 운영 API, shoes 294 · users 33 · Flyway 1:1~5:1. 확인 뒤 지움 |
| 7 운영 지문 | 19:23:43 | 신발 294(키 36 · 최대 id 294) · 리뷰 104 · `3e954039…` · 최대 83자 · Flyway 1~5 checksum 그대로 · users 33 · `데모관리자` 0 |
| 8 Sync(사람) | 19:24:3x 새 Pod | `runshoes-6fdf75b6c6-fljb9`(`ccd0f20c3182`), 재시작 0 |
| V6~V9 적용 | 19:24:42.131 → .393 | `Successfully applied 4 migrations … now at version v9`(182ms). checksum 6 `-1597188006` · 7 `-1950123291` · 8 `-223806260` · 9 `-371820711`(로컬과 같다). 데모 관리자 id 34 · `!demo`, shoes 294 · 숨김 0, users 34, 리뷰 104 · 지문 그대로, `/api/shoes/1` 키 37, 체험 카드 4, 공개 주소 200 |
| 9 적재(첫 시도, Claude) | 19:27 | **관리자 로그인 401** — 10-28 20:25 에 관리 화면에서 비밀번호를 바꿨다(`auth.password.change`). Secret `ADMIN_PASSWORD` 는 옛 값. 쓴 것 없음, 실패 2건에서 멈춤 |
| 9 적재(사람, 새 비밀번호) | 19:33:42 | PATCH 293 · POST 0 · 어드민 수정 0. 다시 건조 실행 0, 출처 있는 신발 293(BITR 612 · WEB 361 · RSG 216 · STORE 86 · PR 11 · MAN 11 · DB 10 칸), 리뷰 지문 그대로, ERROR 0. 기록 → `$B`(600) |
| Secret 교체(사람) · 확인(Claude) | 20:4x | `ADMIN_PASSWORD` 를 지금 비밀번호로. `admin()` 로그인 한 번 200(user 31 ADMIN) — 실패 셈 초기화 |
| 9절 다듬기 — infra `4e6b591` · 앱 `3e04e00` push → 태그 `f7af88b` | 20:3x~20:4x | newTag 두 줄만(`3e04e0086d12`), 이미지 digest `sha256:1f98f5d4…`, V1~V9 sha256 = 커밋 파일 |
| Sync(사람) | 20:50:5x | `runshoes-5cd97f7db8-ng4hn`, `validated 9 migrations` · `up to date`, 체험 카드 31(시드 30 + 데모 관리자, 찜 수), 리뷰 지문 그대로, 공개 200 |
| 가격 종류 적재(Claude, `admin()`) | 20:51:35 | PATCH 94 · POST 0, 다시 건조 실행 0. `priceKind` 발매가 94 · null 200(정가 0), 출처 있는 신발 293 그대로, 리뷰 104 · `3e954039…`, ERROR 0. 기록 → `$B`(600) |
| 9.1 다듬기 2차 — infra `68ac88a` · 앱 `486c8d5` push → 태그 `450df4e` | 22:1x | newTag 두 줄만(`486c8d51c875`), 이미지 digest `sha256:562c970e…`, V1~V9 sha256 = 커밋 파일 |
| Sync(사람) | 22:22:0x | `runshoes-84488c587b-trq6s`, `validated 9 migrations` · `up to date`, 재시작 0 |
| 이미지 적재(Claude, `admin()`) | 22:27:21 | PATCH 2(페가수스 42 · 클리프톤 10 — 4장씩, 대표 = 첫 장) · POST 0, 다시 건조 실행 0, 리뷰 104 · `3e954039…`, ERROR 0. 기록 → `$B`(600) |
| 9.2 다듬기 3차 — infra `13617fc` · 앱 `ece18a2` push → 태그 `db803f4` | 23:0x | newTag 두 줄만(`ece18a2ed70f`), 이미지 digest `sha256:11c7bad0…`, V1~V9 sha256 = 커밋 파일 |
| Sync(사람) | 23:14:0x | `runshoes-5cc5bd6948-8hcnd`, `validated 9 migrations` · `up to date`, 재시작 0. 건조 실행 0(적재 없음), 리뷰 104 · `3e954039…`, 공개 200, 화면 묶음 `index-CrwEP8Mv.js` = 로컬 빌드 |
| 자동 Sync 다시 켜기(사람) · 확인(Claude) | 10-30 23:3x | `syncPolicy` = `{"automated":{"prune":false,"selfHeal":false},…}`, Synced · Healthy `db803f4`. 매니페스트 `platform/argocd/applications/runshoes.yaml` 에 automated 세 줄을 되돌렸다. 이 뒤의 앱 push 는 3분 안에 배포된다 |
| 다듬기 4차(자동 Sync 켠 뒤 — Sync 를 누르지 않는다) — 앱 `62f73f8` · 되돌림 `c8605c1`(헤더 이름은 닉네임 그대로) | 10-30 23:37 · 23:39 push | Jenkins 가 두 커밋을 한 번에 받아 `c8605c1` 만 빌드 → 태그 `4eed683`(`c8605c178039`) → 자동 배포. `62f73f8` 단독 이미지는 운영에 나가지 않았다 |
| 4차 확인(Claude) | 23:51:1x | `runshoes-7bfcf48bfb-hllmh`, `validated 9` · `up to date`, 재시작 0. 건조 실행 0, 리뷰 104 · `3e954039…`, 공개 200, 화면 묶음 = 로컬 HEAD 빌드 |
| 다듬기 5차(자동 Sync — Sync 를 누르지 않는다) — 앱 `d0e8c31` push → 태그 `062cb6c`(`d0e8c317a37a`) | 10-30 00:15 push · 00:20 태그 | `runshoes-9d9775b88-9f24k`, `validated 9` · `up to date`, 재시작 0. 건조 실행 0, 리뷰 104 · `3e954039…`, 공개 200, 화면 묶음 `index-C5ut7WNb.js` = 로컬 빌드 |
| 상세 모달 · 홈 카드 · 리뷰 요약 색 다듬기 여섯 번(프런트만 — 서버 · 마이그레이션 · 카탈로그 변경 없음, 자동 배포) | 10-31 13:45 ~ 15:48 | 앱 `3edf9c8` → 태그 `64421c6` · `c5e7e71` → `276d5c3`(체험 카드 터치 끌기 — 5px 만에 끊기던 것) · `6d00af6` → `d8ff310` · `714eae1` → `e85f4e5` · `2e1eee8` → `0b43f66` · `c27f77a` → `cc004a2`. 매번 새 Pod 재시작 0 · `validated 9` · `up to date`, Synced · Healthy, 공개 200, 운영 JS · CSS = 로컬 빌드(Claude) |
