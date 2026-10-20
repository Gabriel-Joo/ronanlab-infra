# runshoes — 로그인(V3) 적용 · MySQL 백업 · 복구

앱 리포: 설계 `docs/AUTH_DESIGN.md`, 마이그레이션 `backend/src/main/resources/db/migration/V3__auth.sql`.
명령은 호스트에서 `mk`(= `~/k8s-cluster/backup/2026-10-15-before-metallb/mk`, m-k8s 로 ssh)로 kubectl 을 부른다.

**V3 는 MySQL 을 Sync 해서 들어가는 것이 아니다.** 새 앱 이미지의 Pod 가 뜰 때 Flyway 가 적용한다 — 이미지 Sync 가 곧 V3 적용이다.
MySQL StatefulSet 은 바뀌지 않는다. 그래서 백업은 이미지 Sync 바로 앞에 뜬다.

```bash
B=~/k8s-cluster/backup/2026-10-21-runshoes-auth-v3   # 덤프를 두는 곳 — 데이터가 들어 있어 git 밖
mkdir -p $B
```

## 1. 순서 (누가 · 멈추는 곳)

| # | 할 일 | 누가 | 확인 |
|---|---|---|---|
| 1 | Secret `runshoes-auth` 만들기 — `apps/runshoes/scripts/create-secrets.sh` | 사람 | `mk 'kubectl -n runshoes get secret runshoes-auth -o go-template="{{range \$k,\$v := .data}}{{\$k}} {{end}}"'` → `ADMIN_PASSWORD JWT_SECRET SEED_USER_PASSWORD` |
| 2 | 이 리포의 envFrom 커밋 Sync — **이미지는 그대로**(V3 전 이미지는 이 env 를 읽지 않는다) | 사람(Sync) | 1.1 — "아무 일도 없었다"를 확인한다 |
| 3 | 앱 리포 push → Jenkins 가 이미지 빌드 → 이 리포에 newTag 커밋(Sync 는 아직) | Claude | 6절 — Harbor 에서 받은 이미지 안의 V3 sha256 = 앱 리포 파일 |
| 4 | **백업**(2절) + 복원 확인 | Claude | 2절의 세 가지 |
| 5 | **덤프 직후** 운영 지문 재확인(3절) → 보고 | Claude | 리뷰 105건 · 지문 `166db588…` · Flyway 1, 2. 다르면 멈춘다 |
| 6 | 5 에 이어 바로 newTag 커밋 Sync = V3 적용 | 사람(Sync) | 4절 |

**4 → 5 → 6 은 끊지 않고 잇는다.** 덤프 시점 뒤 · Sync 전에 들어온 쓰기(리뷰 · 찜 · 공감)는 덤프에 없다 — 5.2 로 복원하면 **이 구간의 쓰기는 사라진다**.
공개 사이트라 드물지만 0 은 아니다. 그래서 구간을 짧게 두고, 길어졌으면(보고를 기다리는 사이 시간이 흘렀으면) 4 · 5 를 다시 한다.

**Jenkins 가 newTag 를 직접 push 한다**(앱 리포 Jenkinsfile "매니페스트 태그") — 3 을 하면 이 리포 main 에 envFrom 과 새 태그가 함께 있다.
그래서 2(envFrom 만 Sync)를 3 보다 먼저 끝낸다. 순서가 바뀌면 main 을 Sync 하는 순간 백업 없이 V3 가 들어간다.

### 1.1 envFrom Sync 직후 — 아무 일도 없었는지

이미지는 그대로지만 Pod 템플릿이 바뀌어 롤링은 돈다(새 ReplicaSet · 새 Pod).

```bash
# 롤링이 끝났는가 — ReplicaSet revision 이 하나 늘고(2026-10-21 지금 8) 새 것만 READY 1
mk 'kubectl -n runshoes rollout status deploy/runshoes --timeout=180s'
mk 'kubectl -n runshoes get rs -l app.kubernetes.io/name=runshoes -o custom-columns=NAME:.metadata.name,REV:.metadata.annotations.deployment\\.kubernetes\\.io/revision,READY:.status.readyReplicas --sort-by=.metadata.creationTimestamp | tail -2'
# 새 Pod 의 이미지가 그대로인가(지금 0f789ad645bc) · 이름 · 나이
mk "kubectl -n runshoes get pod -l app.kubernetes.io/name=runshoes -o jsonpath='{range .items[*]}{.metadata.name} {.status.startTime} {.spec.containers[0].image}{\"\\n\"}{end}'"
# env 3개가 들어갔는가 — 키 이름만(값은 m-k8s 의 파이프에서 잘려 화면에 오지 않는다)
mk 'kubectl -n runshoes exec deploy/runshoes -c runshoes -- env | cut -d= -f1 | grep -xE "JWT_SECRET|SEED_USER_PASSWORD|ADMIN_PASSWORD" | sort'
#   → ADMIN_PASSWORD / JWT_SECRET / SEED_USER_PASSWORD
# 서비스는 그대로인가
curl -s -o /dev/null -w '%{http_code}\n' -H 'Host: runshoes.ronanlab.dev' http://192.168.122.240/api/shoes   # → 200
```

Secret 이 없었다면 새 Pod 가 `CreateContainerConfigError` 로 멈추고 옛 Pod 가 계속 돈다(maxUnavailable 0) — Secret 을 만들면 새 Pod 가 이어서 뜬다.

## 2. 백업 — 운영 MySQL 덤프

```bash
TS=$(date -u +%Y%m%dT%H%M%SZ)
mk 'kubectl -n runshoes exec runshoes-mysql-0 -c mysql -- sh -c "exec mysqldump -uroot -p\"\$MYSQL_ROOT_PASSWORD\" --single-transaction --set-gtid-purged=OFF --routines --triggers --default-character-set=utf8mb4 runshoes"' \
  > $B/runshoes-before-v3-$TS.sql 2> $B/runshoes-before-v3-$TS.err
```

- `--single-transaction`: InnoDB 를 잠그지 않고 한 시점으로 뜬다 — 앱은 그대로 돈다
- DB 이름을 `--databases` 없이 준다 — 덤프에 `CREATE DATABASE` · `USE` 가 없어 다른 이름의 DB 로 넣어 볼 수 있다(복원 확인)
- root 비밀번호는 Pod 안의 env 로만 쓴다 — 명령 · 화면 · 파일에 나오지 않는다. `.err` 에는 `Using a password…` 경고 한 줄만 있어야 한다

확인 세 가지 — 하나라도 아니면 Sync 하지 않는다:

```bash
# (1) 끝까지 떴는가 · 오류가 없는가
tail -1 $B/runshoes-before-v3-$TS.sql             # → -- Dump completed on …
grep -v 'Using a password' $B/runshoes-before-v3-$TS.err   # → 아무것도 없어야
sha256sum $B/runshoes-before-v3-$TS.sql | tee $B/runshoes-before-v3-$TS.sql.sha256

# (2) 로컬 MySQL(docker compose, runshoes-mysql-dev)에 다른 이름으로 넣어 본다
docker exec -i runshoes-mysql-dev sh -c 'mysql -uroot -p"$MYSQL_ROOT_PASSWORD" -e "DROP DATABASE IF EXISTS runshoes_restore_check; CREATE DATABASE runshoes_restore_check CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci"'
docker exec -i runshoes-mysql-dev sh -c 'mysql -uroot -p"$MYSQL_ROOT_PASSWORD" --default-character-set=utf8mb4 runshoes_restore_check' < $B/runshoes-before-v3-$TS.sql

# (3) 넣은 것이 운영과 같은가 — 운영(API, 읽기만)과 복원본(SQL)의 리뷰 지문 · 개수
curl -s -H 'Host: runshoes.ronanlab.dev' http://192.168.122.240/api/reviews | node -e '
  const r=JSON.parse(require("fs").readFileSync(0)).sort((a,b)=>a.id-b.id);
  console.log(r.length, require("crypto").createHash("sha256").update(r.map(x=>x.id+":"+x.shoeId).join(",")).digest("hex"))'
docker exec -i runshoes-mysql-dev sh -c 'mysql -N -uroot -p"$MYSQL_ROOT_PASSWORD" runshoes_restore_check' <<'SQL'
SELECT COUNT(*), SHA2(GROUP_CONCAT(CONCAT(id, ':', shoe_id) ORDER BY id SEPARATOR ','), 256) FROM reviews;
SELECT (SELECT COUNT(*) FROM shoes), (SELECT COUNT(*) FROM terms), (SELECT GROUP_CONCAT(CONCAT(version, ':', success)) FROM flyway_schema_history);
SQL
# → 두 줄의 개수 · 지문이 같고, shoes 20 · terms 13 · flyway 1:1,2:1
docker exec -i runshoes-mysql-dev sh -c 'mysql -uroot -p"$MYSQL_ROOT_PASSWORD" -e "DROP DATABASE runshoes_restore_check"'
```

같은 옵션의 덤프 · 다른 이름 복원 · 비교를 로컬 dev MySQL 에서 먼저 돌려 봤다(2026-10-21): 행 수 · Flyway 이력 · 리뷰 내용 해시가 원본과 같았다.

## 3. 운영 지문 재확인 (Sync 직전)

```bash
# V3 첫 가드와 같은 조건 — 105건 · 짝 지문 · #29 와 #81 의 작성자
curl -s -H 'Host: runshoes.ronanlab.dev' http://192.168.122.240/api/reviews | node -e '
  const r=JSON.parse(require("fs").readFileSync(0)).sort((a,b)=>a.id-b.id), a=(id)=>r.find(x=>x.id===id)?.author;
  const h=require("crypto").createHash("sha256").update(r.map(x=>x.id+":"+x.shoeId).join(",")).digest("hex");
  console.log(r.length===105 && h==="166db588ff3f29d0c747f7cf23ce42e9e868f1fcb04fda3f558c84bba6f180d8" && a(29)==="회복주전용" && a(81)==="회복주전용" ? "OK" : "다름", r.length, h)'
mk 'kubectl -n runshoes exec runshoes-mysql-0 -c mysql -- sh -c "mysql -N -uroot -p\"\$MYSQL_ROOT_PASSWORD\" runshoes -e \"SELECT version, success FROM flyway_schema_history\""'
# → OK 105 166db588… / 1 1, 2 1
```

## 4. 이미지 Sync 뒤 확인

```bash
mk 'kubectl -n runshoes rollout status deploy/runshoes --timeout=180s'
mk 'kubectl -n runshoes logs deploy/runshoes -c runshoes | grep -E "Migrating|Successfully applied|비밀번호가 없던|ERROR"'
#   → Successfully applied 1 migration … now at version v3 / 비밀번호가 없던 계정 31개 중 31개를 Secret 값으로 채웠다
mk 'kubectl -n runshoes exec runshoes-mysql-0 -c mysql -- sh -c "mysql -N -uroot -p\"\$MYSQL_ROOT_PASSWORD\" runshoes -e \"SELECT version, success FROM flyway_schema_history; SELECT COUNT(*), SUM(user_id IS NULL) FROM reviews; SELECT COUNT(*) FROM users\""'
#   → 1 1, 2 1, 3 1 / 104 0 / 31
```

`SUM(user_id IS NULL)` 이 0 이 아니면: 롤링 중(새 Pod 가 Ready 가 되기 전 1분 남짓) **옛 Pod** 가 받은 리뷰다 — 옛 코드는 user_id 를 모른다.
**어느 계정에 붙일지는 사람에게 묻는다 — admin 이든 누구든 자동으로 붙이지 않는다.** 정해지면 SQL 로 채운다(V4 의 NOT NULL 전에).
보고할 때 그 리뷰의 id · 신발 · author(옛 화면에서 쓴 닉네임) · 시각을 같이 낸다:
`SELECT id, shoe_id, author, created_at FROM reviews WHERE user_id IS NULL`.
같은 창에서 옛 Pod 가 받은 찜은 `shoes.liked`(공용 칸)에만 남는다 — 새 코드는 읽지 않는다.

## 5. 실패했을 때

Pod 로그의 `Script V3__auth.sql failed` 아래 `Error Code` · `Line` 으로 어디서 멈췄는지 본다.
실패한 새 Pod 는 Ready 가 되지 않아 옛 Pod 가 계속 돈다(maxUnavailable 0) — 급하게 할 것은 없다.

| 멈춘 곳 | DB 상태 | 복구 |
|---|---|---|
| **첫 가드** — Line 14, `Error Code : 1242` | **V2 그대로.** 바뀐 것은 `flyway_schema_history` 의 실패 행(version 3, success 0) 하나 | 5.1 |
| **그 뒤 어디든**(테이블 · 데이터 · 끝 가드) | 일부만 적용된 채 — 되돌릴 수 없다 | 5.2 백업에서 복원 |
| V3 는 됐는데 새 앱이 이상하다 | V3 그대로 둔다 | 5.3 이미지만 되돌린다 |

실패 행이 남아 있으면 같은 이미지는 다시 떠도 `Detected failed migration to version 3 (auth)` 로 계속 죽는다(로컬에서 확인).

### 5.1 첫 가드에서 멈춤

원인(배포 전에 생긴 리뷰 · 바뀐 짝)을 어떻게 할지 정한 뒤 — V3 를 고칠지, 그 리뷰를 어떻게 할지 — 실패 행만 지운다(`flyway repair` 와 같다):

```bash
mk 'kubectl -n runshoes exec runshoes-mysql-0 -c mysql -- sh -c "mysql -uroot -p\"\$MYSQL_ROOT_PASSWORD\" runshoes -e \"DELETE FROM flyway_schema_history WHERE version = 3 AND success = 0\""'
```

### 5.2 백업에서 복원

```bash
# 1) 앱을 내린다 — 복원 중에 쓰지 않게(자동 Sync 가 꺼져 있어 되돌아오지 않는다)
mk 'kubectl -n runshoes scale deploy/runshoes --replicas=0'
# 2) DB 를 비우고 다시 만든다 — runshoes 계정의 권한(GRANT ALL ON runshoes.*)은 mysql.db 에 남아 그대로 쓴다
mk 'kubectl -n runshoes exec runshoes-mysql-0 -c mysql -- sh -c "mysql -uroot -p\"\$MYSQL_ROOT_PASSWORD\" -e \"DROP DATABASE runshoes; CREATE DATABASE runshoes CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci\""'
# 3) 덤프를 넣는다(ssh 가 stdin 을 kubectl exec -i 로 넘긴다)
sha256sum -c $B/runshoes-before-v3-$TS.sql.sha256
mk 'kubectl -n runshoes exec -i runshoes-mysql-0 -c mysql -- sh -c "mysql -uroot -p\"\$MYSQL_ROOT_PASSWORD\" --default-character-set=utf8mb4 runshoes"' < $B/runshoes-before-v3-$TS.sql
# 4) 3절의 지문 확인(OK 105 · flyway 1, 2)
# 5) 이 리포의 newTag 커밋을 revert(옛 태그로) → Sync — replicas 도 매니페스트대로 1 로 돌아온다
```

### 5.3 이미지만 되돌린다 (DB 는 V3 그대로)

newTag 커밋을 revert → Sync. V3 전 이미지는 V3 DB 위에서 뜬다 — Flyway 는 모르는 future 마이그레이션을 넘기고, `ddl-auto: validate` 는 늘어난 테이블 · 컬럼을 문제 삼지 않는다.
로컬에서 확인(2026-10-21): 운영 이미지와 같은 커밋(`0f789ad`)의 jar 를 V3 DB 에 띄우면 `Successfully validated 3 migrations` · `up to date`, GET 200, 리뷰 POST(user_id NULL) · 신발 PATCH 가 된다.
되돌린 동안 받은 리뷰는 user_id 가 비고 찜은 공용 칸에 남는다 — 다시 올릴 때 4절의 확인을 한다.

## 6. 이미지 안의 마이그레이션 확인 (Sync 전)

배포할 이미지에 로컬에서 시험한 그 V3 가 들어갔는지 — SQL 만 고치고 jar 를 다시 빌드하지 않아 어긋난 적이 있다(2026-10-21 로컬).

```bash
apps/runshoes/scripts/check-image-migrations.sh <태그>
git -C ~/AI_programming/runshoes show <커밋>:backend/src/main/resources/db/migration/V3__auth.sql | sha256sum
# → V3__auth.sql 의 두 sha256 이 같고, V1 · V2 도 같은 커밋 파일과 같다
```

- **Harbor 를 왕복한 이미지**를 본다 — 워커 노드(w2)의 containerd 가 kubelet 과 같은 길(내부 VIP)·같은 pull robot 으로 받는다. 받은 것은 ctr 네임스페이스 `rs-check` 에만 두고 끝나면 지운다
- 이 호스트의 docker 로는 받을 수 없다: 호스트 DNS 로는 `harbor.ronanlab.dev` 가 Cloudflare 로 가고, Cloudflare Access 가 `/v2/` 에 로그인 페이지(302 HTML)를 준다 —
  `docker pull` 의 `failed size validation` 은 그 HTML 을 레이어로 받으려다 난 것이다. runshoes 만이 아니라 petmint 도 같다. 노드는 `/etc/hosts` 로 VIP 에 붙어 상관없다 — Sync 는 영향이 없다
- 2026-10-21 운영 태그 `0f789ad645bc` 로 시험: V1 `0db56bb0…` · V2 `9091885d…` 가 커밋 `0f789ad` 의 파일과 같았다
- 이 방법이 안 되면 빌드 직후 로컬 이미지에서 꺼내 보는 것으로 대신하고, **"Harbor 왕복 검증은 못 했다"고 여기에 남긴다**

## 7. 덤프 보관

| 덤프 | 보관 | 지우는 때 |
|---|---|---|
| `runshoes-before-v3-*.sql` (V3 직전, V2 상태) | `$B`(호스트 디스크 한 곳, git 밖) | **V4 를 운영에 적용하고 2주 탈 없이 돈 뒤**, 그리고 **2026-11-21(V3 적용 30일) 이후** — 둘 중 늦은 때 |

- 쓸 데: 5.2(V3 전으로 되돌리기)와 "V3 전 데이터가 어땠는지"의 근거. V4 가 `shoes.liked` · `reviews.liked` 를 지우면 공용 찜 · 공감의 원래 값은 이 덤프에만 남는다 — 그래서 V4 뒤에도 2주를 더 둔다
- 내용: 신발 · 리뷰(공개 데이터) · 용어 · Flyway 이력. **비밀번호 · 토큰은 없다**(V2 상태라 users · refresh_tokens 가 없다).
  V3 뒤에 뜨는 덤프에는 비밀번호 해시(BCrypt) · refresh token 해시 · 활동 로그(IP · User-Agent)가 들어간다 — 같은 곳에 두되 `chmod 600`, 지우는 때는 그때 정한다
- 지우기 전에 `sha256sum -c` 로 기록과 같은 파일인지 확인하고, 지운 날을 아래 8절에 적는다

## 8. 실행 기록 — 2026-10-21 (KST, 시각은 UTC)

| 단계 | 시각(UTC) | 결과 |
|---|---|---|
| Secret `runshoes-auth` 생성 · envFrom Sync(`62a0515`) | 10-20 21:4x | 사람. 롤링 정상, 이미지 `0f789ad645bc` 그대로, env 키 3개(1.1 로 확인), `/api/shoes` 200 |
| 앱 push `9659f13` → Jenkins #9 | 21:47:20 → 21:53:17 | SUCCESS. 경고는 직전 #8 과 같다(yarn Workspaces 10줄 · pip root 1줄), error 0. Jenkins 가 newTag 커밋 `1801f12`(`9659f1346681`, newTag 두 줄만) |
| 6절 이미지 확인(Harbor 왕복, w2 containerd) | 21:5x | digest `sha256:a693813d…` · V3 `ec24e0e4d5085d91…` = 커밋 9659f13 파일 = 로컬 검증 파일. V1 `0db56bb0…` · V2 `9091885d…` 도 같다 |
| 2절 덤프 | 21:55:30 | `runshoes-before-v3-20261020T215530Z.sql` 41,093 bytes, sha256 `5bb023a30c7fe8bc95291630e0fc146c405e1d83c6710aded590fb0439b78a23`. `Dump completed`, stderr 는 비밀번호 경고만 |
| 2절 복원 확인(로컬 `runshoes_restore_check`) | 21:55:30 | 종료코드 0, 리뷰 105 · 지문 `166db588…` = 운영 API, shoes 20 · terms 13 · Flyway 1:1, 2:1. 확인 뒤 지움 |
| 3절 운영 지문 | 21:55:31 | OK — 105 · `166db588…80d8` · #29 · #81 회복주전용 · Flyway 1, 2 |
| 이미지 Sync(`1801f12`) | 사람 | 새 Pod `runshoes-8475b6f79d-tfpr2`(21:56:22 시작, ReplicaSet revision 10) |
| V3 적용(Flyway) | 21:56:28.795 → 21:56:29.061 | `Successfully applied 1 migration … now at version v3`(241ms). 덤프에서 적용까지 59초 — 그 사이 쓰기 없음(아래 user_id NULL 0) |
| 4절 확인 | 21:56:32~ | `비밀번호가 없던 계정 31개 중 31개를 Secret 값으로 채웠다`, Flyway 1 · 2 · 3 success, 리뷰 104 · user_id NULL 0 · users 31, `/api/shoes` 200. 처리할 리뷰 없음 |

- 운영 Flyway checksum(V1 `-1576961241` · V2 `263137229` · V3 `-2094729346`)이 로컬 시험 DB 와 같다 — 시험한 그 파일이 들어갔다
- 덤프 보관: 7절. 지운 날: (아직)
