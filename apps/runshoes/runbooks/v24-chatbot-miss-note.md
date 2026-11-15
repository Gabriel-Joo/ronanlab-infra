# runshoes — V24 챗봇 문의 처리 사유(chatbot_misses.decided_note)

> 2026-11-15 — 사용자 결정. 런슈즈 관리자 부탁으로 인프라 관리자가 씀. **한 push · 한 이미지 · 한 Sync** 에서 Flyway 가 24 를 적용한다. 표 맨 뒤에 NULL 열 하나를 더하기만 하고 데이터를 고치지 않는다(V23 과 같은 꼴). 절차는 V22 · V23 과 같다(`v22-v23-review-hide-miss-status.md`, 앱 리포 `docs/06_deployment.md` 1-7).
> 운영 DB · 클러스터 쓰기는 **사람이 친다**. Claude 는 명령과 순서를 주고, 읽기(공개 API · `kubectl get` · 로그)로 확인만 한다.
> 사람이 치는 명령은 **한 줄씩 · 절대 경로**다 — 터미널 패널은 `cd` · 셸 변수를 이어받지 않는다.
> **매니페스트 변경은 이번에 없다**(태그 커밋은 Jenkins 가 한다). **대시보드 권한 단계도 없다** — `grafana_ro` 는 `chatbot_misses` 권한이 없다.

```bash
# 이 런북에서 쓰는 자리(명령 안에 그대로 풀어 썼다)
# 덤프       /home/kopo17/k8s-cluster/backup/2026-11-15-runshoes-v24/   — 데이터가 들어 있어 git 밖
# kubectl    /home/kopo17/k8s-cluster/backup/2026-10-15-before-metallb/mk '<명령>'
# 공개 API   http://192.168.122.240 + 'Host: runshoes.ronanlab.dev'
```

## 쓰기 전 운영 상태(2026-11-15, 인프라 관리자 읽기)

- ArgoCD `runshoes`: 자동 Sync 켜짐(`{"automated":{},"syncOptions":["CreateNamespace=false"]}`), Synced/Healthy
- 이미지: 웹 · 챗봇 · CronJob 모두 `f0d605bc6d76`(V22 · V23). Deployment replicas 2, `maxSurge 0` · `maxUnavailable 1`
- `flyway_schema_history`: `…,21:1,22:1,23:1`. 원본 · 복제본 같음
- `chatbot_misses` 칸: `id, kind, query, message, created_at, status, decided_at, decided_by`(`decided_note` 없음) — 1행, `status` NOT NULL 0. 원본 · 복제본 같음
- 공개 `GET /api/reviews` 1,800건, `GET /api/shoes` 310켤레
- `grafana_ro`: `chatbot_misses` 권한 없음(11-15 `SHOW GRANTS` 읽기)

## V24

```sql
-- V24 chatbot miss note
ALTER TABLE chatbot_misses ADD COLUMN decided_note VARCHAR(200) NULL;
```

- 맨 뒤 열 추가뿐이다. 기존 행은 NULL(사유 없음)이고 고쳐지는 값이 없다. 1행짜리 표라 잠금이 길지 않다(MySQL 8 INSTANT).
- 복제본에도 복제로 따라간다.
- 옛 이미지(`f0d605bc6d76`)는 이 칸을 모르고 읽지도 쓰지도 않는다 — 롤링 중 남은 옛 Pod 와 되돌리기 모두 그대로 뜬다(4절).

## 같은 이미지에 함께 오는 것

- 화면 수정(인증 API 제거, 쪽 넘기기 등)과 비교하기 그래프 폭 수정. 스키마와 상관없다 — 3절의 공개 숫자 비교가 그대로 맞아야 한다.
- 앱 커밋(push 전 런슈즈 `main` 에 합친다) → 이미지 태그는 push 뒤 Jenkins 가 정한다(6절에 적는다).

## 1. 순서 (누가)

| # | 일 | 누가 | 확인 |
|---|---|---|---|
| 1 | 자동 Sync 끄기 | 사람 | — |
| 2 | **끈 것을 사람이 친 출력으로 확인 — push 전에** | 사람 → 런슈즈 관리자 | 아래 명령 출력에 `automated` 가 없다. 출력을 런슈즈 관리자에게 붙인다 |
| 3 | 앱 `main` push → Jenkins → 인프라 newTag 커밋 | 런슈즈 관리자 | 인프라에 `runshoes: 이미지 태그 <새 태그>` 커밋. ArgoCD OutOfSync 만, 운영은 옛 이미지 `f0d605bc6d76` 그대로 |
| 4 | Sync 전 확인 — 도는 요약 Job 없음 · 직전 숫자 적기 · 덤프 | 사람(2절 (1)(2)(3)) | 03:30 KST 근처를 피한다 |
| 5 | 복원 확인 | 사람(2절 (4)) | reviews 수 · 지문이 공개 API 와 같음, flyway `…23:1` 로 끝남, `decided_note` 없음 |
| 6 | Sync = V24 적용 + 새 이미지(웹 · 챗봇 · CronJob 같은 태그) | 사람 | 3절 |
| 7 | 자동 Sync 다시 켜기 | 사람 | `automated` 다시 있음 |

```bash
# 1. 끄기
/home/kopo17/k8s-cluster/backup/2026-10-15-before-metallb/mk 'kubectl -n argocd patch app runshoes --type json -p "[{\"op\":\"remove\",\"path\":\"/spec/syncPolicy/automated\"}]"'
# 2. 확인 — {"syncOptions":["CreateNamespace=false"]} 만 나와야 한다. 이 출력을 붙인다
/home/kopo17/k8s-cluster/backup/2026-10-15-before-metallb/mk 'kubectl -n argocd get app runshoes -o jsonpath="{.spec.syncPolicy}"'
# 6. Sync — <커밋> 은 3번의 Jenkins 태그 커밋
/home/kopo17/k8s-cluster/backup/2026-10-15-before-metallb/mk 'kubectl -n argocd patch app runshoes --type merge -p "{\"operation\":{\"sync\":{\"revision\":\"<커밋>\"}}}"'
# 7. 다시 켜기 — 끄기 전 값으로
/home/kopo17/k8s-cluster/backup/2026-10-15-before-metallb/mk 'kubectl -n argocd patch app runshoes --type merge -p "{\"spec\":{\"syncPolicy\":{\"automated\":{}}}}"'
```

- **1 · 2 는 반드시 push 전에.** 켜진 채 push 하면 Jenkins 태그 커밋을 자동 Sync 가 바로 받아 덤프 전에 24 가 적용된다. V22 · V23 때 push 가 먼저 나갔고, 빌드가 끝나기 전에 꺼서 겨우 피했다(`v22-v23-review-hide-miss-status.md` 6절).
- Pod 가 둘(replicas 2, maxSurge 0)이다. 옛 Pod 하나가 내려가고 새 Pod 가 24 를 적용하며 뜬다. 그동안 남은 옛 Pod 는 칸이 늘어난 스키마에서 돈다 — 옛 이미지는 새 칸을 모른다.
- 처리 사유를 적는 기능은 새 Pod 가 둘 다 뜬 뒤에 쓴다.

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

- 같은 push 에 화면 수정이 함께 나간다. 공개 API 의 응답 꼴이 바뀌면(쪽 넘기기 등) 위 명령이 Sync 뒤에 다른 수를 낼 수 있다 — 그때는 데이터가 아니라 응답 꼴 때문인지 런슈즈 관리자가 먼저 본다.

**(3) 덤프** — V22 · V23 과 같은 명령, 이름만 `runshoes-before-v24-<UTC 시각>`. 비밀번호 해시 · 활동 로그 · 챗봇 질문 · 답 원문(`chatbot_turns`) · 챗봇 놓친 질문(`chatbot_misses`)이 들어 있다 — `chmod 600`, git 밖. 배포 날이 11-15 가 아니어도 폴더 이름은 그대로 둔다.

```bash
mkdir -p /home/kopo17/k8s-cluster/backup/2026-11-15-runshoes-v24 && chmod 700 /home/kopo17/k8s-cluster/backup/2026-11-15-runshoes-v24
F=/home/kopo17/k8s-cluster/backup/2026-11-15-runshoes-v24/runshoes-before-v24-$(date -u +%Y%m%dT%H%M%SZ); /home/kopo17/k8s-cluster/backup/2026-10-15-before-metallb/mk 'kubectl -n runshoes exec runshoes-mysql-0 -c mysql -- sh -c "exec mysqldump -uroot -p\"\$MYSQL_ROOT_PASSWORD\" --single-transaction --set-gtid-purged=OFF --routines --triggers --default-character-set=utf8mb4 runshoes"' > $F.sql 2> $F.err; chmod 600 $F.*; echo $F
tail -1 /home/kopo17/k8s-cluster/backup/2026-11-15-runshoes-v24/runshoes-before-v24-*.sql        # → -- Dump completed on …
grep -v 'Using a password' /home/kopo17/k8s-cluster/backup/2026-11-15-runshoes-v24/runshoes-before-v24-*.err   # → 아무것도 없어야
sha256sum /home/kopo17/k8s-cluster/backup/2026-11-15-runshoes-v24/runshoes-before-v24-*.sql | tee /home/kopo17/k8s-cluster/backup/2026-11-15-runshoes-v24/sha256.txt
```

- 덤프는 이 폴더에 하나만 둔다(아래 명령이 `*` 로 집는다). 다시 떠야 하면 앞의 것을 지우고 뜬다.

**(4) 복원 확인** — V22 · V23 런북 판 그대로, 마지막 확인만 새 칸으로 바꿨다. 로컬 `runshoes-mysql-dev` 에 임시 DB `runshoes_restore_check` 를 만들었다 지운다(개발 DB `runshoes` 는 건드리지 않는다).

```bash
docker exec -i runshoes-mysql-dev sh -c 'mysql -uroot -p"$MYSQL_ROOT_PASSWORD" -e "DROP DATABASE IF EXISTS runshoes_restore_check; CREATE DATABASE runshoes_restore_check CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci"'
cat /home/kopo17/k8s-cluster/backup/2026-11-15-runshoes-v24/runshoes-before-v24-*.sql | docker exec -i runshoes-mysql-dev sh -c 'mysql -uroot -p"$MYSQL_ROOT_PASSWORD" --default-character-set=utf8mb4 runshoes_restore_check'
printf '%s\n' "SET SESSION group_concat_max_len = 1048576;" "SELECT COUNT(*), SHA2(GROUP_CONCAT(CONCAT(r.id, ':', r.shoe_id) ORDER BY r.id SEPARATOR ','), 256) FROM reviews r JOIN shoes s ON s.id = r.shoe_id AND s.deleted_at IS NULL;" "SELECT (SELECT COUNT(*) FROM shoes WHERE deleted_at IS NULL), (SELECT COUNT(*) FROM users), (SELECT COUNT(*) FROM chatbot_misses), (SELECT GROUP_CONCAT(CONCAT(version, ':', success) ORDER BY installed_rank) FROM flyway_schema_history);" "SELECT TABLE_NAME, COLUMN_NAME FROM information_schema.columns WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'chatbot_misses' AND COLUMN_NAME = 'decided_note';" | docker exec -i runshoes-mysql-dev sh -c 'mysql -N -uroot -p"$MYSQL_ROOT_PASSWORD" runshoes_restore_check'
docker exec -i runshoes-mysql-dev sh -c 'mysql -uroot -p"$MYSQL_ROOT_PASSWORD" -e "DROP DATABASE runshoes_restore_check"'
```

- 셋째 줄 첫 행(복원본)의 개수 · 지문이 (2) 의 reviews 줄과 같아야 한다. 숨긴 리뷰가 있으면 공개 API 는 그만큼 적다 — 그때는 복원본 수에서 `hidden_at IS NOT NULL` 수를 빼서 맞춘다.
- 둘째 행: shoes · users · chatbot_misses 행 수(운영 지금 수) · flyway `…,23:1` 로 끝남. 셋째 결과(`decided_note`)는 비어야 한다. 24 나 이 칸이 이미 있으면 멈춘다.
- 복원 DB 이름이 달라 V21 뷰를 읽으면 `ERROR 1356` 이다(V21 런북 2절 덧). 위 명령은 뷰를 읽지 않는다.

## 3. Sync 뒤 확인

**Claude(읽기)**

- 새 Pod 로그: `Migrating schema `runshoes` to version "24 - chatbot miss note"` → `Successfully applied 1 migration`. 둘째 Pod 는 `up to date`. 2/2 Running, 재시작 0, Synced/Healthy, 공개 첫 화면 200. 프로브(`/readyz` · `/livez`) 실패 이벤트가 기동 중 connection refused 말고는 없다.

```bash
/home/kopo17/k8s-cluster/backup/2026-10-15-before-metallb/mk 'for p in $(kubectl -n runshoes get pod -l app.kubernetes.io/name=runshoes -o name); do echo "== $p"; kubectl -n runshoes logs $p -c runshoes | grep -E "Migrating schema|Successfully applied|up to date|FlywayException"; done'
/home/kopo17/k8s-cluster/backup/2026-10-15-before-metallb/mk 'kubectl -n runshoes get deploy/runshoes cronjob/runshoes-summary -o jsonpath="{..image}"'
# → 웹 · 챗봇 · CronJob 이 같은 새 태그
```

- 공개 숫자: 2절 (2) 의 두 줄을 다시 친다 — reviews · shoes 의 개수와 지문이 **직전과 같아야** 한다. 다르면 자동 Sync 꺼진 채로 멈추고 알린다(응답 꼴이 바뀐 것인지는 2절 (2) 덧).

**사람(DB, 원본 · 복제본 둘 다)**

```bash
/home/kopo17/k8s-cluster/backup/2026-10-15-before-metallb/mk 'for p in runshoes-mysql-0 runshoes-mysql-replica-0; do echo "== $p"; kubectl -n runshoes exec $p -c mysql -- sh -c "mysql -N -uroot -p\"\$MYSQL_ROOT_PASSWORD\" runshoes -e \"SELECT version, success FROM flyway_schema_history WHERE version = \\\"24\\\"; SHOW COLUMNS FROM chatbot_misses LIKE \\\"decided_note\\\"; SELECT COUNT(*) FROM chatbot_misses WHERE decided_note IS NOT NULL\""; done'
# → 두 곳 모두: 24 1 · decided_note varchar(200) YES · 0
```

## 4. 실패했을 때

- **V24 실패**(`ALTER TABLE`) → 새 Pod 가 Ready 가 안 되고 롤링이 멈춘다(남은 옛 Pod 하나가 받는다). 자동 Sync 꺼진 채로 원인 확인.
  - 사람이 `flyway_schema_history` 의 24 행과 3절의 `SHOW COLUMNS` 로 칸이 생겼는지 본다. 실패 행(success 0)만 지우고(`flyway repair` 와 같다) 고친 이미지로 다시 Sync 한다. 칸이 생긴 채 실패했으면 그 칸을 지울지는 그때 사람에게 묻는다 — 이 런북에서 미리 정하지 않는다.
- **되돌리기** — 인프라 태그 커밋 `git revert` → push → Sync(앱 06 1-7). 옛 이미지 `f0d605bc6d76` 은 24 를 앞선 버전(`*:future` 무시)으로 넘겨 뜨고, 이 칸을 모른다. **칸은 지우지 않는다.**
  - 되돌리면 적힌 처리 사유는 DB 에 남고 화면에 안 보일 뿐이다. 다시 새 이미지로 올리면 그대로 보인다.
  - 같은 push 의 화면 수정(인증 API 제거, 쪽 넘기기, 비교 그래프 폭)도 함께 되돌아간다.
- 데이터가 잘못되면 2절 (3) 덤프로 복원(사람). 이번 변경은 칸 추가뿐이라 그럴 일은 없다고 본다.

## 5. 대시보드 메모

- 바꿀 것 없음. `grafana_ro` 는 `chatbot_misses` 를 읽지 못하고, 런슈즈 대시보드에도 이 표를 읽는 패널이 없다.

## 6. 실행 기록 (UTC)

| 단계 | 시각 | 내용 |
|---|---|---|
| 1 자동 Sync 끔 | 11-15 03:42 무렵 | 사용자. 정확한 시각은 ArgoCD 에 남지 않는다(V21 런북 7절) |
| 2 끈 것 확인(사람 출력) | 11-15 push 전 | 사람 출력을 런슈즈 관리자가 보고 push. 이번에는 순서대로 |
| 4 · 5 확인 · 숫자 · 덤프 · 복원 | 11-15 03:43:16 | 사용자. **태그 커밋보다 먼저 떴다**(런북은 태그 커밋 뒤). 그 사이 바뀐 스키마가 없어 덤프는 그대로 쓸 수 있다. `runshoes-before-v24-20261115T034316Z.sql` 2,397,908 B · `sha256.txt`(`77671e8e…8332`). 복원 확인: 보이는 리뷰 1,800 지문 같음 · 숨김 0 · flyway `…23:1` · `decided_note` 없음 |
| 3 push | 11-15 03:48 전 | 앱 `main` `85b9677` → Jenkins 인프라 태그 커밋 `2684851`(커밋 시각 03:47:51), 이미지 `85b9677ca8d6` |
| 6 Sync | 11-15 03:48:18 | 사용자(수동 — history 118 `initiatedBy` `{}`). rev `2684851`. 태그 커밋과 이 Sync 사이에 자동 Sync 기록이 없다. 새 Pod `runshoes-6c5595d6c8-zxwlw` 가 24 적용(`Successfully applied 1`), `-bvqzs` up to date. 웹 · 챗봇 · CronJob `85b9677ca8d6`. 원본 · 복제본 `24 1` · `decided_note varchar(200) YES` · `0`. Sync 전후 공개 reviews 1,800 · shoes 310 지문 같음, 새 `/api/admin/shoes` 로그인 없이 401 |
| 7 자동 Sync 켬 | 11-15 03:55 전(KST 12:55) | 사용자(사람 출력 확인). 인프라 관리자 읽기: `{"automated":{},"syncOptions":["CreateNamespace=false"]}`, Synced/Healthy, 두 Pod 2/2 재시작 0 |
