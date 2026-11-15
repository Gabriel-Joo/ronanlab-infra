# runshoes — V22 리뷰 숨기기(reviews.hidden_at) · V23 챗봇 문의 처리 상태(chatbot_misses)

> 2026-11-15 — 사용자 결정. 런슈즈 관리자 부탁으로 인프라 관리자가 씀. **한 push · 한 이미지 · 한 Sync** 에서 Flyway 가 22, 23 을 차례로 적용한다. 둘 다 표 맨 뒤에 NULL 열을 더하기만 하고 데이터를 고치지 않는다. 절차는 V21 과 같다(`v21-grafana-compare-views.md`, 앱 리포 `docs/06_deployment.md` 1-7).
> 운영 DB · 클러스터 쓰기는 **사람이 친다**. Claude 는 명령과 순서를 주고, 읽기(공개 API · `kubectl get` · 로그)로 확인만 한다.
> 사람이 치는 명령은 **한 줄씩 · 절대 경로**다 — 터미널 패널은 `cd` · 셸 변수를 이어받지 않는다.
> **매니페스트 변경은 이번에 없다**(태그 커밋은 Jenkins 가 한다).

```bash
# 이 런북에서 쓰는 자리(명령 안에 그대로 풀어 썼다)
# 덤프       /home/kopo17/k8s-cluster/backup/2026-11-15-runshoes-v22-v23/   — 데이터가 들어 있어 git 밖
# kubectl    /home/kopo17/k8s-cluster/backup/2026-10-15-before-metallb/mk '<명령>'
# 공개 API   http://192.168.122.240 + 'Host: runshoes.ronanlab.dev'
```

## 쓰기 전 운영 상태(2026-11-15, 인프라 관리자 읽기)

- ArgoCD `runshoes`: 자동 Sync 켜짐(`{"automated":{},"syncOptions":["CreateNamespace=false"]}`), Synced/Healthy
- 이미지: 웹 · 챗봇 · CronJob 모두 `f9ee36e01331`(V21). Deployment replicas 2, `maxSurge 0` · `maxUnavailable 1`
- `flyway_schema_history`: 실패 행 0. 원본 · 복제본 같음
- `reviews` 칸: `id … first_shoe_id`(17칸, `hidden_at` 없음) — 1,800행. `chatbot_misses` 칸: `id, kind, query, message, created_at` — 1행. 원본 · 복제본 같음
- 공개 `GET /api/reviews` 1,800건, `GET /api/shoes` 310켤레
- `grafana_ro` 의 `reviews` 권한: `id, shoe_id, user_id, rating, review_type, created_at` 여섯 칸(`hidden_at` 은 아직 없는 칸이라 당연히 없다)

## V22 · V23

```sql
-- V22 review hide
ALTER TABLE reviews ADD COLUMN hidden_at DATETIME(3) NULL;
-- V23 chatbot miss status
ALTER TABLE chatbot_misses ADD COLUMN status VARCHAR(10) NULL, ADD COLUMN decided_at DATETIME(3) NULL, ADD COLUMN decided_by BIGINT NULL;
```

- 맨 뒤 열 추가뿐이다. 기존 행은 모두 NULL(숨기지 않음 · 처리 전)이고 고쳐지는 값이 없다.
- 두 표 모두 작다(1,800행 · 1행). MySQL 8 은 맨 뒤 NULL 열 추가를 INSTANT 로 하므로 표 잠금이 길지 않다.
- 복제본에도 복제로 따라간다.
- 옛 이미지(`f9ee36e01331`)는 늘어난 열을 모르고 읽지도 쓰지도 않는다 — 롤링 중 남은 옛 Pod 와 되돌리기 모두 그대로 뜬다(4절).

## 1. 순서 (누가)

| # | 일 | 누가 | 확인 |
|---|---|---|---|
| 1 | 자동 Sync 끄기 | 사람 | — |
| 2 | **끈 것을 사람이 친 출력으로 확인 — push 전에** | 사람 → 런슈즈 관리자 | 아래 명령 출력에 `automated` 가 없다. 출력을 런슈즈 관리자에게 붙인다 |
| 3 | 앱 `main` push → Jenkins → 인프라 newTag 커밋 | 런슈즈 관리자 | 인프라에 `runshoes: 이미지 태그 <새 태그>` 커밋. ArgoCD OutOfSync 만, 운영은 옛 이미지 `f9ee36e01331` 그대로 |
| 4 | Sync 전 확인 — 도는 요약 Job 없음 · 직전 숫자 적기 · 덤프 | 사람(2절 (1)(2)(3)) | 03:30 KST 근처를 피한다 |
| 5 | 복원 확인 | 사람(2절 (4)) | reviews 수 · 지문이 공개 API 와 같음, flyway 1~21, 새 열 없음 |
| 6 | Sync = V22 · V23 적용 + 새 이미지(웹 · 챗봇 · CronJob 같은 태그) | 사람 | 3절 |
| 7 | 대시보드 권한(GRANT 한 줄) | 사람 | 3절 끝. **6 의 확인이 끝난 뒤**(열이 있어야 GRANT 가 된다). 대시보드 쪽 결정은 5절 |
| 8 | 자동 Sync 다시 켜기 | 사람 | `automated` 다시 있음 |

```bash
# 1. 끄기
/home/kopo17/k8s-cluster/backup/2026-10-15-before-metallb/mk 'kubectl -n argocd patch app runshoes --type json -p "[{\"op\":\"remove\",\"path\":\"/spec/syncPolicy/automated\"}]"'
# 2. 확인 — {"syncOptions":["CreateNamespace=false"]} 만 나와야 한다. 이 출력을 붙인다
/home/kopo17/k8s-cluster/backup/2026-10-15-before-metallb/mk 'kubectl -n argocd get app runshoes -o jsonpath="{.spec.syncPolicy}"'
# 6. Sync — <커밋> 은 3번의 Jenkins 태그 커밋
/home/kopo17/k8s-cluster/backup/2026-10-15-before-metallb/mk 'kubectl -n argocd patch app runshoes --type merge -p "{\"operation\":{\"sync\":{\"revision\":\"<커밋>\"}}}"'
# 8. 다시 켜기 — 끄기 전 값으로
/home/kopo17/k8s-cluster/backup/2026-10-15-before-metallb/mk 'kubectl -n argocd patch app runshoes --type merge -p "{\"spec\":{\"syncPolicy\":{\"automated\":{}}}}"'
```

- Pod 가 둘(replicas 2, maxSurge 0)이다. 옛 Pod 하나가 내려가고 새 Pod 가 22 · 23 을 적용하며 뜬다. 그동안 남은 옛 Pod 는 열이 늘어난 스키마에서 돈다 — 옛 이미지는 새 열을 모르고, 새 열이 모두 NULL 이라 옛 Pod 가 보여 주는 리뷰 · 평점도 같다.
- 숨기기 기능은 새 Pod 가 둘 다 뜬 뒤에 쓴다. 롤링 중 옛 Pod 는 `hidden_at` 을 보지 않으므로, 그 사이에 숨긴 리뷰는 옛 Pod 가 받은 요청에서 보인다.

## 2. Sync 전 확인 (사람 — 한 줄씩)

**(1) 도는 Job 이 없다**

```bash
/home/kopo17/k8s-cluster/backup/2026-10-15-before-metallb/mk 'kubectl -n runshoes get jobs,pods -l app.kubernetes.io/name=runshoes-summary'
# → 모든 Job 이 Complete/Failed. Running 이 있으면 끝날 때까지 기다린다
```

**(2) 직전 숫자 적기** — 3절에서 같은지 본다. 리뷰는 개수와 지문(id:shoeId), 신발은 개수와 지문(id:평점:리뷰 수).

```bash
curl -s -H 'Host: runshoes.ronanlab.dev' http://192.168.122.240/api/reviews | node -e 'const r=JSON.parse(require("fs").readFileSync(0)).sort((a,b)=>a.id-b.id); console.log("reviews", r.length, require("crypto").createHash("sha256").update(r.map(x=>x.id+":"+x.shoeId).join(",")).digest("hex"))'
curl -s -H 'Host: runshoes.ronanlab.dev' http://192.168.122.240/api/shoes | node -e 'const r=JSON.parse(require("fs").readFileSync(0)).sort((a,b)=>a.id-b.id); console.log("shoes", r.length, require("crypto").createHash("sha256").update(r.map(x=>x.id+":"+x.rating+":"+x.reviewCount).join(",")).digest("hex"))'
```

**(3) 덤프** — V21 과 같은 명령, 이름만 `runshoes-before-v22-v23-<UTC 시각>`. 비밀번호 해시 · 활동 로그 · 챗봇 질문 · 답 원문(`chatbot_turns`) · 챗봇 놓친 질문(`chatbot_misses`)이 들어 있다 — `chmod 600`, git 밖. 배포 날이 11-15 가 아니어도 폴더 이름은 그대로 둔다.

```bash
mkdir -p /home/kopo17/k8s-cluster/backup/2026-11-15-runshoes-v22-v23 && chmod 700 /home/kopo17/k8s-cluster/backup/2026-11-15-runshoes-v22-v23
F=/home/kopo17/k8s-cluster/backup/2026-11-15-runshoes-v22-v23/runshoes-before-v22-v23-$(date -u +%Y%m%dT%H%M%SZ); /home/kopo17/k8s-cluster/backup/2026-10-15-before-metallb/mk 'kubectl -n runshoes exec runshoes-mysql-0 -c mysql -- sh -c "exec mysqldump -uroot -p\"\$MYSQL_ROOT_PASSWORD\" --single-transaction --set-gtid-purged=OFF --routines --triggers --default-character-set=utf8mb4 runshoes"' > $F.sql 2> $F.err; chmod 600 $F.*; echo $F
tail -1 /home/kopo17/k8s-cluster/backup/2026-11-15-runshoes-v22-v23/runshoes-before-v22-v23-*.sql        # → -- Dump completed on …
grep -v 'Using a password' /home/kopo17/k8s-cluster/backup/2026-11-15-runshoes-v22-v23/runshoes-before-v22-v23-*.err   # → 아무것도 없어야
sha256sum /home/kopo17/k8s-cluster/backup/2026-11-15-runshoes-v22-v23/runshoes-before-v22-v23-*.sql | tee /home/kopo17/k8s-cluster/backup/2026-11-15-runshoes-v22-v23/sha256.txt
```

- 덤프는 이 폴더에 하나만 둔다(아래 명령이 `*` 로 집는다). 다시 떠야 하면 앞의 것을 지우고 뜬다.

**(4) 복원 확인** — V21 런북 판 그대로, 마지막 확인만 새 열로 바꿨다. 로컬 `runshoes-mysql-dev` 에 임시 DB `runshoes_restore_check` 를 만들었다 지운다(개발 DB `runshoes` 는 건드리지 않는다).

```bash
docker exec -i runshoes-mysql-dev sh -c 'mysql -uroot -p"$MYSQL_ROOT_PASSWORD" -e "DROP DATABASE IF EXISTS runshoes_restore_check; CREATE DATABASE runshoes_restore_check CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci"'
cat /home/kopo17/k8s-cluster/backup/2026-11-15-runshoes-v22-v23/runshoes-before-v22-v23-*.sql | docker exec -i runshoes-mysql-dev sh -c 'mysql -uroot -p"$MYSQL_ROOT_PASSWORD" --default-character-set=utf8mb4 runshoes_restore_check'
printf '%s\n' "SET SESSION group_concat_max_len = 1048576;" "SELECT COUNT(*), SHA2(GROUP_CONCAT(CONCAT(r.id, ':', r.shoe_id) ORDER BY r.id SEPARATOR ','), 256) FROM reviews r JOIN shoes s ON s.id = r.shoe_id AND s.deleted_at IS NULL;" "SELECT (SELECT COUNT(*) FROM shoes WHERE deleted_at IS NULL), (SELECT COUNT(*) FROM users), (SELECT COUNT(*) FROM chatbot_misses), (SELECT GROUP_CONCAT(CONCAT(version, ':', success) ORDER BY installed_rank) FROM flyway_schema_history);" "SELECT TABLE_NAME, COLUMN_NAME FROM information_schema.columns WHERE TABLE_SCHEMA = DATABASE() AND COLUMN_NAME IN ('hidden_at', 'status', 'decided_at', 'decided_by') AND TABLE_NAME IN ('reviews', 'chatbot_misses');" | docker exec -i runshoes-mysql-dev sh -c 'mysql -N -uroot -p"$MYSQL_ROOT_PASSWORD" runshoes_restore_check'
docker exec -i runshoes-mysql-dev sh -c 'mysql -uroot -p"$MYSQL_ROOT_PASSWORD" -e "DROP DATABASE runshoes_restore_check"'
```

- 셋째 줄 첫 행(복원본)의 개수 · 지문이 (2) 의 reviews 줄과 같아야 한다.
- 둘째 행: shoes · users · chatbot_misses 행 수(운영 지금 수) · flyway `…,21:1` 로 끝남. 셋째 결과(새 열)는 비어야 한다. 22 · 23 이나 새 열이 이미 있으면 멈춘다.
- 복원 DB 이름이 달라 V21 뷰를 읽으면 `ERROR 1356` 이다(V21 런북 2절 덧). 위 명령은 뷰를 읽지 않는다.

## 3. Sync 뒤 확인

**Claude(읽기)**

- 새 Pod 로그: `Migrating schema `runshoes` to version "22 - review hide"` → `Migrating schema `runshoes` to version "23 - chatbot miss status"` → `Successfully applied 2 migrations`. 둘째 Pod 는 `up to date`. 2/2 Running, 재시작 0, Synced/Healthy, 공개 첫 화면 200. 프로브(`/readyz` · `/livez`) 실패 이벤트가 기동 중 connection refused 말고는 없다.

```bash
/home/kopo17/k8s-cluster/backup/2026-10-15-before-metallb/mk 'for p in $(kubectl -n runshoes get pod -l app.kubernetes.io/name=runshoes -o name); do echo "== $p"; kubectl -n runshoes logs $p -c runshoes | grep -E "Migrating schema|Successfully applied|up to date|FlywayException"; done'
/home/kopo17/k8s-cluster/backup/2026-10-15-before-metallb/mk 'kubectl -n runshoes get deploy/runshoes cronjob/runshoes-summary -o jsonpath="{..image}"'
# → 웹 · 챗봇 · CronJob 이 같은 새 태그
```

- 공개 숫자: 2절 (2) 의 두 줄을 다시 친다 — reviews · shoes 의 개수와 지문이 **직전과 같아야** 한다(아직 아무것도 숨기지 않았으므로). 다르면 숨기기 쿼리가 NULL 을 잘못 거르는 것 — 자동 Sync 꺼진 채로 멈추고 알린다.

**사람(DB, 원본 · 복제본 둘 다)**

```bash
/home/kopo17/k8s-cluster/backup/2026-10-15-before-metallb/mk 'for p in runshoes-mysql-0 runshoes-mysql-replica-0; do echo "== $p"; kubectl -n runshoes exec $p -c mysql -- sh -c "mysql -N -uroot -p\"\$MYSQL_ROOT_PASSWORD\" runshoes -e \"SELECT version, success FROM flyway_schema_history WHERE version IN (\\\"22\\\", \\\"23\\\") ORDER BY installed_rank; SHOW COLUMNS FROM reviews LIKE \\\"hidden_at\\\"; SHOW COLUMNS FROM chatbot_misses WHERE Field IN (\\\"status\\\", \\\"decided_at\\\", \\\"decided_by\\\"); SELECT (SELECT COUNT(*) FROM reviews WHERE hidden_at IS NOT NULL), (SELECT COUNT(*) FROM chatbot_misses WHERE status IS NOT NULL)\""; done'
# → 두 곳 모두: 22 1 · 23 1 · hidden_at datetime(3) YES · status varchar(10) YES · decided_at datetime(3) YES · decided_by bigint YES · 0 0
```

**사람(대시보드 권한 — 1절 7번, 원본에서만)** — 위 확인에서 원본 · 복제본 모두 `hidden_at` 이 보인 뒤에 친다. 복제본으로 따라간다.

```bash
/home/kopo17/k8s-cluster/backup/2026-10-15-before-metallb/mk 'kubectl -n runshoes exec runshoes-mysql-0 -c mysql -- sh -c "mysql -uroot -p\"\$MYSQL_ROOT_PASSWORD\" -e \"GRANT SELECT (hidden_at) ON runshoes.reviews TO \\\"grafana_ro\\\"@\\\"%\\\"\""'
/home/kopo17/k8s-cluster/backup/2026-10-15-before-metallb/mk 'for p in runshoes-mysql-0 runshoes-mysql-replica-0; do echo "== $p"; kubectl -n runshoes exec $p -c mysql -- sh -c "mysql -N -uroot -p\"\$MYSQL_ROOT_PASSWORD\" -e \"SHOW GRANTS FOR grafana_ro@\\\"%\\\"\" | grep runshoes.\\\`reviews\\\`"; done'
# → 두 곳 모두 reviews 줄에 `hidden_at` 이 들어 있다(칸 일곱)
```

- 앱 리포 `docs/07_database.md` 1-6절의 `grafana_ro` SQL 에도 이 칸을 더해야 다음에 계정을 다시 만들 때 빠지지 않는다(런슈즈 관리자 일).

## 4. 실패했을 때

- **V22 또는 V23 실패**(`ALTER TABLE`) → 새 Pod 가 Ready 가 안 되고 롤링이 멈춘다(남은 옛 Pod 하나가 받는다). 자동 Sync 꺼진 채로 원인 확인.
  - V22 가 성공하고 V23 이 실패할 수 있다(Flyway 는 MySQL 에서 버전마다 따로 커밋한다 — DDL 은 되돌려지지 않는다). 사람이 `flyway_schema_history` 의 22 · 23 행과 2절 끝의 새 열 확인 쿼리로 어디까지 들어갔는지 본다.
  - 실패 행(success 0)만 지우고(`flyway repair` 와 같다), 그 버전의 열이 일부 생겼으면 그대로 두고 고친 이미지(마이그레이션이 이미 있는 열을 견디게)로 다시 Sync 하거나, 사람 승인을 받아 그 열만 지운 뒤 다시 Sync 한다. 열 지우기는 이 런북에서 미리 정하지 않는다 — 그때 사람에게 묻는다.
- **되돌리기** — 인프라 태그 커밋 `git revert` → push → Sync(앱 06 1-7). 옛 이미지 `f9ee36e01331` 은 22 · 23 을 앞선 버전(`*:future` 무시)으로 넘겨 뜨고, 늘어난 열을 모른다. **열은 지우지 않는다**(남아도 해가 없다).
  - **되돌리면 숨긴 리뷰가 다시 보이고 신발 평점에도 다시 든다.** 되돌리기 전에 사람이 원본에서 숨긴 수를 센다 — 0 이 아니면 되돌리기 전에 사람에게 알리고 결정을 받는다.

```bash
/home/kopo17/k8s-cluster/backup/2026-10-15-before-metallb/mk 'kubectl -n runshoes exec runshoes-mysql-0 -c mysql -- sh -c "mysql -N -uroot -p\"\$MYSQL_ROOT_PASSWORD\" runshoes -e \"SELECT COUNT(*) FROM reviews WHERE hidden_at IS NOT NULL; SELECT COUNT(*) FROM chatbot_misses WHERE status IS NOT NULL\""'
```

  - 챗봇 문의 처리 상태(`status` · `decided_*`)도 옛 이미지에서는 보이지 않을 뿐 남는다. 다시 새 이미지로 올리면 그대로 보인다.
- 데이터가 잘못되면 2절 (3) 덤프로 복원(사람). 이번 변경은 열 추가뿐이라 그럴 일은 없다고 본다.

## 5. 대시보드 메모 (2026-11-15 인프라 관리자 읽기)

- 런슈즈 관리자 부탁: Grafana 리뷰 수에서 숨긴 리뷰를 빼려고 생성기(`apps/monitoring/grafana/dashboards/gen_runshoes.py`)의 `reviews` 쿼리에 `hidden_at IS NULL` 을 더한다 — **권한(1절 7번) 확인 뒤에 반영한다.** 권한 전에 새 쿼리가 나가면 칸 권한 오류(`ERROR 1143`)로 패널이 깨진다. `monitoring` 앱은 자동 Sync 라 push 가 곧 반영이다.
- 그런데 **지금 대시보드에는 `reviews` 표를 읽는 패널이 없다.** 런슈즈 DB 패널이 읽는 곳은 `activity_logs` · `chatbot_turns` · `grafana_compare_views` · `summary_batch_runs` 뿐이다(`runshoes.json` 의 `FROM` 을 셈). 리뷰 패널 「리뷰 쓰기 (일별 …)」는 `activity_logs` 의 `review.create` 이벤트(화면에서 새로 쓴 횟수)를 센다 — 지금 남아 있는 리뷰 수가 아니다.
- 그래서 생성기를 고칠지, 고친다면 무엇을(「리뷰 쓰기」에서 나중에 숨긴 것을 뺄지, 남아 있는 리뷰 수 패널을 새로 만들지) 런슈즈 관리자 결정을 기다린다. 결정이 나기 전에는 7번 GRANT 를 쳐도 해가 없다(쓰지 않는 칸 하나를 더 읽게 될 뿐).

## 6. 실행 기록 (UTC)

| 단계 | 시각 | 내용 |
|---|---|---|
| 1 자동 Sync 끔 | | |
| 2 끈 것 확인(사람 출력) | | |
| 3 push | | |
| 4 · 5 확인 · 숫자 · 덤프 · 복원 | | |
| 6 Sync | | |
| 7 대시보드 권한 | | |
| 8 자동 Sync 켬 | | |
