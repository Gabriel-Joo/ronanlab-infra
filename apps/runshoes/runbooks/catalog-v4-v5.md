# runshoes — 카탈로그 확장(V4 세대 구조 · V5 정가 메타) 적용 · 294켤레 적재

앱 리포: 마이그레이션 `backend/src/main/resources/db/migration/V4__shoe_generations.sql` · `V5__price_reference.sql`, 설계 `docs/CATALOG_PIPELINE.md`, 적재기 `catalog/load.mjs`.
절차는 V3(`auth-v3.md`)와 같다 — **이미지 Sync 가 곧 V4 · V5 적용**(새 Pod 가 뜰 때 Flyway). 그 뒤 적재기가 관리자 API 로 신발을 넣는다.
명령은 호스트에서 `mk`(= `~/k8s-cluster/backup/2026-10-15-before-metallb/mk`)로 kubectl 을 부른다.

```bash
B=~/k8s-cluster/backup/2026-10-29-runshoes-catalog-v4v5   # 덤프 · 적재 기록을 두는 곳 — 데이터가 들어 있어 git 밖
mkdir -p $B && chmod 700 $B
VIP=http://192.168.122.240; H='Host: runshoes.ronanlab.dev'
mk() { ~/k8s-cluster/backup/2026-10-15-before-metallb/mk "$@"; }   # 사람이 치는 블록마다 이 줄이 들어 있다(새 셸에서도 그대로 되게)
```

## 0. 출발 상태 (2026-10-29 02:4x KST, 읽기만으로 확인)

| 항목 | 값 |
|---|---|
| 운영 이미지 | `harbor.ronanlab.dev/runshoes/runshoes:eeffbd840964`(앱 `eeffbd8`, 로그인 3단계) · `runshoes-55db44cccb-mv9lc` |
| ArgoCD `runshoes` | Synced · Healthy, revision `f56cf8e`, **자동 Sync 켜짐**(`automated: {prune: false, selfHeal: false}`) |
| `/api/shoes` | 20켤레 — id 1~20 이 V4 가드의 시드 브랜드 · 모델과 같다. 응답 키 21개(V4 키 없음) |
| `/api/reviews` | 104건 · 최대 id 105 · 짝 지문(`id:shoeId`) `3e954039a1aa3f86684cd3912fc6e75a5f46027f994c9a9b7b3f13e9498f12b1` |
| 시드 문구 | 20켤레의 summary · description 이 로컬 백업(`catalog/local/work/copy-backup-20261028.json` 의 원본)과 같다 — 운영에서 손으로 고친 문구 없음 |
| Flyway | **확인 못 했다** — 운영 MySQL 에 `exec` 하는 읽기 명령이 이 세션의 권한 판정에서 막혔다. V3 기록대로면 1 · 2 · 3. 3절에서 본다 |

앱 리포 쪽(로컬에서 끝낸 것):
- 계약 테스트(2026-10-29, 로컬 jar · 옛 기준선 + `--allow-added` V4 키 + `priceSource` · `priceCheckedAt` · `priceKind`): v3 PASS 112 · FAIL 0 · INFO 3, v3-search PASS 24, v3-summary PASS 5 · INFO 5, v4 PASS 21
- 마이그레이션 sha256(로컬 jar 안 = 소스 파일): V4 `db22befe0a2b3a4d…` · V5 `8d512eb7883b5a57…`. 로컬 Flyway checksum V4 `-942386036` · V5 `1378788652`
  (V4 는 2026-10-29 주석만 고쳤다 — 옛 칸 정리를 "V5" 로 적었던 것을 V6 으로. SQL 본문은 같고, 고친 뒤 계약 테스트 v4 PASS 21 · v3 PASS 112)
- **리허설**(빈 DB → 새 jar 가 V1~V5 → 적재기 30 → 100 → 전체): `Successfully applied 5 migrations … v5`, 신발 47 → 109 → 294, 적재 뒤 건조 실행 0건,
  결과가 지금 로컬 DB(사용자가 화면으로 본 294켤레)와 id · 평점 · 찜 말고 모두 같다. `--revert`(마지막 묶음 185켤레 삭제 · 8켤레 되돌림) 뒤 다시 넣기도 확인
- **옛 이미지 롤백 확인**: 운영 커밋 `eeffbd8` 의 jar 를 적재 끝난 V5 DB 에 띄우면 `Successfully validated 5 migrations` · `up to date`, `/api/shoes`(294) · 검색 · 리뷰 200

## 1. 순서 (누가 · 멈추는 곳)

| # | 할 일 | 누가 | 확인 |
|---|---|---|---|
| 1 | **자동 Sync 끄기** — 1.1 | **사람**(배포를 막는 장치라 직접 — 2026-10-29 사용자) | `syncPolicy` 에 `automated` 없음 |
| 2 | 앱 리포 커밋 · push → Jenkins 가 이미지 빌드 → 이 리포에 newTag 커밋(배포는 안 된다 — 1 이 먼저) | Claude | Jenkins SUCCESS, 태그 커밋은 newTag 두 줄만 |
| 3 | 이미지 안의 마이그레이션 확인 — 6절 | Claude(막히면 사람) | V1~V5 sha256 = 0절 · 앱 커밋 파일 |
| 4 | **백업**(2절) + 로컬에 다른 이름으로 복원 확인 | **사람**(2절 블록을 그대로) → 출력을 Claude 가 확인 | 2절의 세 가지 |
| 5 | **덤프 직후** 운영 지문 재확인(3절) | **사람**(Flyway 줄) · Claude(API 줄) | 신발 20 · 리뷰 104 · 지문 `3e954039…` · Flyway 1, 2, 3. 다르면 멈춘다 |
| 6 | newTag 커밋 Sync = V4 · V5 적용 | **사람(Sync)** | 4절(MySQL 줄은 사람) |
| 7 | 적재 — 30 → 확인 → 100 → 확인 → 전체 → 확인(5절) | **사람**(관리자 비밀번호가 드는 적재 세 줄) · Claude(건조 실행 · 5.2 확인) | 묶음마다 5.2 |
| 8 | 화면 확인 | 사람 | 5.3 |
| 9 | 자동 Sync 다시 켜기 — 1.1 의 반대 | **사람** | `automated` 다시 있음 |

- **4 → 5 → 6 은 끊지 않고 잇는다.** 덤프 뒤 · Sync 전에 들어온 쓰기(리뷰 · 찜 · 공감 · 가입)는 덤프에 없다 — 7절 R2 로 복원하면 그 쓰기는 사라진다. 길어졌으면 4 · 5 를 다시 한다
- 6 과 7 사이에는 급할 것이 없다 — V4 · V5 는 칸을 더하고 시드 20켤레의 세대 값을 채울 뿐이고, 화면은 20켤레 그대로 보인다
- **운영 MySQL `exec` 와 Secret 읽기는 사람이 친다**(2026-10-29 사용자 — 권한을 여는 것보다 안전하다). 아래 "사람이 친다" 블록은 그대로 붙여 넣으면 된다.
  Claude Code 프롬프트에서 줄 앞에 `!` 를 붙여 치면 출력이 대화에 남아 Claude 가 바로 확인한다 — 블록은 비밀번호 · 덤프 내용을 화면에 내지 않는다
- 2 의 push 는 **1 이 끝난 것을 보고** 한다. 자동 Sync 가 켜진 채 push 하면 Jenkins 태그 커밋이 3분 안에 배포돼 4 · 5(백업 · 지문)를 건너뛴다

### 1.1 자동 Sync 끄기 · 켜기

Application `runshoes` 는 ArgoCD 가 관리하지 않는다(사람이 `kubectl apply` 로 넣었다 — `platform/argocd/applications/runshoes.yaml` 머리말). 그래서 **클러스터에서 바꾸는 것이 실제 스위치**이고, 매니페스트 커밋은 기록이다.

```bash
# 끄기
mk 'kubectl -n argocd patch application runshoes --type merge -p "{\"spec\":{\"syncPolicy\":{\"automated\":null}}}"'
mk 'kubectl -n argocd get application runshoes -o jsonpath="{.spec.syncPolicy}"'
#   → {"syncOptions":["CreateNamespace=false"]}  (automated 없음)
# 매니페스트: platform/argocd/applications/runshoes.yaml 의 automated 세 줄을 빼고 머리말에 "2026-10-29 V4 · V5 동안 끔" — 이 파일만 커밋
#   (이 리포 작업 트리에 apps/petmint/app/configmap.yaml 수정이 있다 — 건드리지 않는다, git add 는 파일을 지정해서)

# 켜기(9) — 지금과 같은 값
mk 'kubectl -n argocd patch application runshoes --type merge -p "{\"spec\":{\"syncPolicy\":{\"automated\":{\"prune\":false,\"selfHeal\":false}}}}"'
```

## 2. 백업 — 운영 MySQL 덤프

V3 런북 2절과 같은 명령 · 같은 확인이다. 이름만 `runshoes-before-v4-$TS`.

**사람이 친다** — (1)~(3) 을 한 번에. 끝에 나오는 두 줄(API · 복원본)의 개수 · 지문이 같아야 한다.

```bash
B=~/k8s-cluster/backup/2026-10-29-runshoes-catalog-v4v5; VIP=http://192.168.122.240; H='Host: runshoes.ronanlab.dev'
mk() { ~/k8s-cluster/backup/2026-10-15-before-metallb/mk "$@"; }
TS=$(date -u +%Y%m%dT%H%M%SZ)
mk 'kubectl -n runshoes exec runshoes-mysql-0 -c mysql -- sh -c "exec mysqldump -uroot -p\"\$MYSQL_ROOT_PASSWORD\" --single-transaction --set-gtid-purged=OFF --routines --triggers --default-character-set=utf8mb4 runshoes"' \
  > $B/runshoes-before-v4-$TS.sql 2> $B/runshoes-before-v4-$TS.err
chmod 600 $B/runshoes-before-v4-$TS.*
```

**이 덤프에는 V3 뒤라 비밀번호 해시(BCrypt) · refresh token 해시 · 활동 로그(IP · User-Agent)가 들어 있다** — `chmod 600`, git · 공유 폴더에 두지 않는다.

확인 세 가지 — 하나라도 아니면 Sync 하지 않는다:

```bash
# (1) 끝까지 떴는가 · 오류가 없는가
tail -1 $B/runshoes-before-v4-$TS.sql                       # → -- Dump completed on …
grep -v 'Using a password' $B/runshoes-before-v4-$TS.err      # → 아무것도 없어야
sha256sum $B/runshoes-before-v4-$TS.sql | tee $B/runshoes-before-v4-$TS.sql.sha256

# (2) 로컬 MySQL(runshoes-mysql-dev)에 다른 이름으로 넣어 본다 — 로컬의 runshoes DB(적재한 294켤레)는 건드리지 않는다
docker exec -i runshoes-mysql-dev sh -c 'mysql -uroot -p"$MYSQL_ROOT_PASSWORD" -e "DROP DATABASE IF EXISTS runshoes_restore_check; CREATE DATABASE runshoes_restore_check CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci"'
docker exec -i runshoes-mysql-dev sh -c 'mysql -uroot -p"$MYSQL_ROOT_PASSWORD" --default-character-set=utf8mb4 runshoes_restore_check' < $B/runshoes-before-v4-$TS.sql

# (3) 넣은 것이 운영과 같은가 — 운영 API(읽기)와 복원본(SQL)의 리뷰 지문 · 개수
curl -s -H "$H" $VIP/api/reviews | node -e '
  const r=JSON.parse(require("fs").readFileSync(0)).sort((a,b)=>a.id-b.id);
  console.log(r.length, require("crypto").createHash("sha256").update(r.map(x=>x.id+":"+x.shoeId).join(",")).digest("hex"))'
docker exec -i runshoes-mysql-dev sh -c 'mysql -N -uroot -p"$MYSQL_ROOT_PASSWORD" runshoes_restore_check' <<'SQL'
SELECT COUNT(*), SHA2(GROUP_CONCAT(CONCAT(id, ':', shoe_id) ORDER BY id SEPARATOR ','), 256) FROM reviews;
SELECT (SELECT COUNT(*) FROM shoes), (SELECT COUNT(*) FROM users), (SELECT GROUP_CONCAT(CONCAT(version, ':', success) ORDER BY installed_rank) FROM flyway_schema_history);
SQL
# → 두 줄의 개수 · 지문이 같고, shoes 20 · users(그때 수) · flyway 1:1,2:1,3:1
docker exec -i runshoes-mysql-dev sh -c 'mysql -uroot -p"$MYSQL_ROOT_PASSWORD" -e "DROP DATABASE runshoes_restore_check"'
```

## 3. 운영 지문 재확인 (Sync 직전)

API 두 줄은 Claude, Flyway 줄(`mk … exec`)은 **사람이 친다**.

```bash
curl -s -H "$H" $VIP/api/reviews | node -e '
  const r=JSON.parse(require("fs").readFileSync(0)).sort((a,b)=>a.id-b.id);
  const h=require("crypto").createHash("sha256").update(r.map(x=>x.id+":"+x.shoeId).join(",")).digest("hex");
  console.log(r.length===104 && h==="3e954039a1aa3f86684cd3912fc6e75a5f46027f994c9a9b7b3f13e9498f12b1" ? "OK" : "다름", r.length, h)'
curl -s -H "$H" $VIP/api/shoes | node -e 'const s=JSON.parse(require("fs").readFileSync(0)); console.log(s.length, s.map(x=>x.id).join(","))'
mk 'kubectl -n runshoes exec runshoes-mysql-0 -c mysql -- sh -c "mysql -N -uroot -p\"\$MYSQL_ROOT_PASSWORD\" runshoes -e \"SELECT version, success, checksum FROM flyway_schema_history ORDER BY installed_rank\""'
# → OK 104 3e954039… / 20 1,…,20 / 1 1 -1576961241 · 2 1 263137229 · 3 1 -2094729346
```

- 리뷰 수 · 지문이 달라졌으면(새 리뷰가 들어왔으면) 멈추지 않아도 된다 — **V4 가드는 신발만 본다**(20켤레 · id 1~20 의 브랜드 · 모델). 새 값을 0절에 적고 2절 덤프가 그 뒤에 뜬 것인지만 본다
- 신발이 20켤레가 아니거나 id 1~20 의 이름이 바뀌었으면 **멈춘다** — V4 가드가 실패한다(7절 R1)

## 4. 이미지 Sync 뒤 확인 (V4 · V5)

`rollout` · `logs` · `curl` 은 Claude, MySQL 줄(`exec … mysql`)은 **사람이 친다**.

```bash
mk 'kubectl -n runshoes rollout status deploy/runshoes --timeout=180s'
mk 'kubectl -n runshoes logs deploy/runshoes -c runshoes | grep -E "v4 guard|Migrating|Successfully applied|ERROR"'
#   → Migrating schema `runshoes` to version "4 - shoe generations" / "5 - price reference"
#     Successfully applied 2 migrations to schema `runshoes`, now at version v5
mk 'kubectl -n runshoes exec runshoes-mysql-0 -c mysql -- sh -c "mysql -N -uroot -p\"\$MYSQL_ROOT_PASSWORD\" runshoes -e \"SELECT version, success, checksum FROM flyway_schema_history ORDER BY installed_rank; SELECT COUNT(*), SUM(line_key IS NULL) FROM shoes; SELECT COUNT(*) FROM reviews\""'
#   → 1 · 2 · 3 그대로, 4 1 -942386036 · 5 1 1378788652(로컬 checksum 과 같아야 — 시험한 그 파일) / 20 0 / 104
curl -s -H "$H" $VIP/api/shoes/1 | node -e 'const s=JSON.parse(require("fs").readFileSync(0)); console.log(Object.keys(s).length, s.lineKey, s.generation, s.isCurrent, s.priceSource)'
#   → 36 asics:gel-kayano 32 false null
curl -s -o /dev/null -w '%{http_code}\n' https://runshoes.ronanlab.dev/   # → 200
```

## 5. 적재 — 294켤레

적재기는 운영 신발과 `lineKey:generation` 으로 맞춘다. 없으면 POST, 있으면 사실 값만 비교해 PATCH(리뷰 · 찜 · 평점은 건드리지 않는다).
**V4 전에 돌리면 시드를 새 행으로 또 넣는다** — 그래서 시드에 `lineKey` 가 없으면 적재기가 멈춘다(exit 2, 2026-10-29 운영 V3 상태에서 확인).

```bash
cd ~/AI_programming/runshoes/catalog
LOAD="node load.mjs --base $VIP --host runshoes.ronanlab.dev"
$LOAD                                   # 건조 실행(Claude, 비밀번호 없이 읽기만) → POST 274 · PATCH 21 · 같음 0 (리허설과 같아야)
```

**사람이 친다** — 묶음 하나씩. 각 줄 뒤에 Claude 가 5.2 를 보고 "다음"을 말한다. 관리자 비밀번호는 Secret 에서 파이프로만 — 화면 · 파일 · 셸 기록에 남지 않는다.

```bash
cd ~/AI_programming/runshoes/catalog
B=~/k8s-cluster/backup/2026-10-29-runshoes-catalog-v4v5
mk() { ~/k8s-cluster/backup/2026-10-15-before-metallb/mk "$@"; }
admin() { ADMIN_EMAIL=admin@runshoes.test ADMIN_PASSWORD="$(mk 'kubectl -n runshoes get secret runshoes-auth -o jsonpath={.data.ADMIN_PASSWORD}' | base64 -d)" "$@"; }
LOAD="node load.mjs --base http://192.168.122.240 --host runshoes.ronanlab.dev"

admin $LOAD --limit 30 --apply          # → 썼다: PATCH 5 · POST 27 → …/loads/<시각>.json   (신발 47)
admin $LOAD --limit 100 --apply         # → 썼다: PATCH 8 · POST 62                           (신발 109)
admin $LOAD --apply                     # → 썼다: PATCH 8 · POST 185                          (신발 294)

# 끝나면 — 세 기록을 덤프 폴더로(되돌리기 7절 R4 의 근거: 넣은 id · 바꾸기 전 값). catalog/loads/ 는 gitignore
cp -p $(ls -t loads/*.json | head -3) $B/ && chmod 600 $B/*.json && ls -l $B
```

마지막에 Claude 가 `$LOAD` 건조 실행 → POST 0 · PATCH 0 · 같음 293.

- PATCH 21 = 카탈로그 안 시드 19켤레(스펙 · 정가 메타 · 이미지 · 사용자가 고른 문구) + 카탈로그 밖 엔돌핀 스피드 4(id 10)의 이미지 · 문구 2건
- 로그인은 묶음마다 한 번(세 번). 실패가 아니라 시도 제한(429)에 걸릴 일은 없다
- 묶음 사이 몇 초 동안 화면에 일부만 보인다 — 공개 사이트라 그대로 둔다
- `--limit` 은 카탈로그 순서의 앞 N행이다(아식스 → 나이키 → 아디다스 …)

### 5.2 묶음마다 확인

```bash
curl -s -H "$H" $VIP/api/shoes | node -e '
  const s=JSON.parse(require("fs").readFileSync(0)), k=new Set();
  const dup=s.filter(x=>x.lineKey && k.size===k.add(x.lineKey+":"+x.generation+":"+x.gender).size).length;
  console.log("신발", s.length, "lineKey 없음", s.filter(x=>!x.lineKey).length, "중복", dup, "정가 메타", s.filter(x=>x.priceSource).length)'
#   → 47 · 109 · 294 / lineKey 없음 0 / 중복 0
curl -s -H "$H" $VIP/api/reviews | node -e '
  const r=JSON.parse(require("fs").readFileSync(0)).sort((a,b)=>a.id-b.id);
  console.log(r.length, require("crypto").createHash("sha256").update(r.map(x=>x.id+":"+x.shoeId).join(",")).digest("hex"))'
#   → 3절과 같다(적재는 리뷰를 건드리지 않는다)
mk 'kubectl -n runshoes logs deploy/runshoes -c runshoes --since=5m | grep -cE "ERROR|Exception"'   # → 0
```

### 5.3 화면 (사람)

- 홈 카드 294켤레 · 이미지가 뜨는지(StockX), 시드 20켤레의 리뷰 · 평점이 그대로인지
- 모달: 정가 옆 "공식몰 / ABC마트 YYYY/MM/DD 기준", 정보 없는 칸은 "정보 없음"
- 시드 문구: 재작성 15 · 원본 5(페가수스 42 는 1983년)
- 세대 비교 · 추천 화면

## 6. 이미지 안의 마이그레이션 확인 (Sync 전)

```bash
apps/runshoes/scripts/check-image-migrations.sh <태그>
for v in V1__schema V2__seed_data V3__auth V4__shoe_generations V5__price_reference; do
  git -C ~/AI_programming/runshoes show <커밋>:backend/src/main/resources/db/migration/$v.sql | sha256sum; done
# → 다섯 줄이 같고: V1 0db56bb0… · V2 9091885d… · V3 ec24e0e4… · V4 db22befe… · V5 8d512eb7…
```

V3 런북 6절과 같은 방법(Harbor 왕복, w2 containerd). 스크립트가 Secret `harbor-pull` 을 읽는다 — 권한 판정에서 막히면 **사람이 친다**(출력은 파일명 · sha256 · digest 뿐이다). 안 되면 "Harbor 왕복 검증은 못 했다"고 8절에 남긴다.

## 7. 실패했을 때

| 멈춘 곳 | DB 상태 | 복구 |
|---|---|---|
| **R1 V4 첫 가드** — `v4 guard: shoes differ from seed`, `Error Code : 1242` | V3 그대로. `flyway_schema_history` 에 version 4 · success 0 한 줄 | 실패 행을 지우고(`DELETE FROM flyway_schema_history WHERE version = 4 AND success = 0`) newTag 커밋 revert → Sync. 원인(신발이 바뀐 이유)은 사람이 정한다 |
| **R2 가드 뒤 V4 어디든 · V5** | 일부만 적용 — 되돌릴 수 없다(MySQL DDL 은 트랜잭션이 아니다) | **사람이 친다** — V3 런북 5.2 와 같은 순서(이름만 `runshoes-before-v4-$TS`): replicas 0 → DB 다시 만들기 → `sha256sum -c` → 2절 덤프 넣기 → 3절 지문 → newTag 커밋 revert → Sync |
| **R3 V4 · V5 는 됐는데 새 앱이 이상하다** | V5 그대로 둔다 | newTag 커밋만 revert → Sync. 옛 이미지가 V5 DB 에서 뜬다(0절 — 로컬 확인). 단 옛 화면은 카본 NULL 을 "없음", 토박스 NULL 을 빈칸으로, 정가 출처는 안 보인다 |
| **R4 적재가 이상하다** | V5 + 일부 적재 | **사람이 친다**, 묶음을 거꾸로: `admin $LOAD --revert $B/<시각>.json`(5절 블록의 `admin` · `LOAD`) — 넣은 신발을 지우고 바꾼 값을 되돌린다(로컬 확인). 새 신발에 리뷰 · 찜이 붙기 전에만 깔끔하다 |

실패한 새 Pod 는 Ready 가 되지 않아 옛 Pod 가 계속 돈다(maxUnavailable 0) — R1 · R2 에서 급하게 할 것은 없다.
V4 · V5 는 Flyway 가 한 번에 차례로 적용한다. V5(ALTER 한 문장)가 실패하면 V4 는 적용된 채 남는다 — R3 처럼 옛 이미지로 뜨고, V5 를 고쳐 다시 배포한다.

## 8. 덤프 보관

| 덤프 | 지우는 때 |
|---|---|
| `runshoes-before-v4-*.sql` (V4 직전, V3 상태) | V6(옛 칸 정리)를 운영에 적용하고 2주 탈 없이 돈 뒤 — V6 이 지우는 `weight` · `drop_mm` · `stack_height` · `width` 와 공용 `liked` 의 원래 값이 여기 남는다 |
| `runshoes-before-v3-*.sql` | V3 런북 7절 그대로 — "V4 를 운영에 적용하고 2주 탈 없이 돈 뒤, 그리고 2026-11-21 이후". 이번 적용이 그 시계를 시작한다 |
| 적재 기록 `$B/*.json` | V6 뒤. 넣은 id 와 바꾸기 전 값(시드 19 · 엔돌핀 스피드 4)이다 |

## 9. 실행 기록 (시각은 UTC)

| 단계 | 시각 | 결과 |
|---|---|---|
| 0절 출발 상태 | 10-28 17:4x | 위 표. 운영 MySQL `exec` 읽기는 권한 판정에서 막혀 Flyway 를 못 봤다 |
