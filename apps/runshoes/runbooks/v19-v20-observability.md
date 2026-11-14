# runshoes — V19 · V20 관측 1차: 챗봇 턴 기록(chatbot_turns) · 요약 배치 실행 기록(summary_batch_runs · summary_batch_failures)

> 2026-11-14 — 사용자 결정(런슈즈 관측 작업 1차를 한 번에 배포). 런슈즈 관리자 부탁으로 인프라 관리자가 씀. **이미지 Sync 가 곧 V19 · V20 적용**이다(한 이미지 · 한 Sync — 자동 Sync 를 끄고 켜는 일은 한 번). 절차는 V17 · V18 과 같다(`v17-v18-chatbot.md`, 앱 리포 `docs/06_deployment.md` 1-7).
> 운영 DB · 클러스터 쓰기는 **사람이 친다**. Claude 는 명령과 순서를 주고, 읽기(공개 API · `kubectl get` · 로그)로 확인만 한다.
> 사람이 치는 명령은 **한 줄씩 · 절대 경로**다 — 터미널 패널은 `cd` · 셸 변수를 이어받지 않는다.
> **매니페스트 변경은 이번에 없다.** 프로브를 `/livez` · `/readyz` 로 옮기는 일(A-2 2단계)은 이 배포가 운영에 오른 것을 확인한 뒤 따로 한다(6절).

```bash
# 이 런북에서 쓰는 자리(명령 안에 그대로 풀어 썼다)
# 덤프       /home/kopo17/k8s-cluster/backup/2026-11-14-runshoes-v19/   — 데이터가 들어 있어 git 밖
# kubectl    /home/kopo17/k8s-cluster/backup/2026-10-15-before-metallb/mk '<명령>'
# 공개 API   http://192.168.122.240 + 'Host: runshoes.ronanlab.dev'
```

## 쓰기 전 운영 상태(2026-11-14, Claude 읽기)

- ArgoCD `runshoes`: 자동 Sync 켜짐(`{"automated":{},"syncOptions":["CreateNamespace=false"]}`), Synced/Healthy, rev `e0ded6a`
- 이미지: 웹 · 챗봇 · CronJob 모두 `ccb74d00c5f3`
- `flyway_schema_history`: 1 ~ 18 모두 success 1. `chatbot_turns` · `summary_batch_runs` · `summary_batch_failures` 없음
- Replica(`runshoes-mysql-replica-0`, w2) 복제 IO · SQL Yes, 지연 0 — 새 표도 따라간다

## V19

- 새 표 `chatbot_turns` — 챗봇 한 턴에 한 줄(질문 · 답 · 갈래 · 단계별 시간 칸들). 기존 표 · 행은 건드리지 않는다.
- **질문 · 답 원문이 DB 에 쌓이기 시작한다.** 이 뒤 덤프에는 대화가 들어 있다(덤프는 이미 `chmod 600` · git 밖). 나중에 Grafana 읽기 계정을 붙일 때는 petmint `grafana_ro` 처럼 질문 · 답 칸을 빼고 컬럼 단위로 준다(`apps/monitoring/README.md` 「petmint DB 읽기 계정」). Loki 에는 대화를 넣지 않는다(CLAUDE.md 4절).

## V20

- 새 표 `summary_batch_runs` · `summary_batch_failures` — 리뷰 요약 배치(CronJob `runshoes-summary`, 매일 03:30 KST) 실행 기록. 새 표만.
- CronJob 은 같은 이미지 태그(`kustomization.yaml` images)를 받는다 → **배포 다음 날 03:30 회차부터** 기록이 쌓인다.

## 같은 이미지에 함께 오는 것

- 챗봇 카탈로그 캐시: 같은 Pod Spring 의 새 내부 `GET /api/internal/catalog-version`(루프백만, 밖에서는 404).
- A-2 1단계: 앱 포트 3000 에 `/livez` · `/readyz` 를 더한다(`management.endpoint.health.probes.add-additional-paths`). 기존 `/actuator/health` · `liveness` · `readiness` 는 그대로 — **지금 프로브에 영향 없음**. 챗봇 사이드카의 백엔드 준비 확인은 `/readyz` 로 옮긴다.
- 앱 커밋 6개(push 전 런슈즈 `main` 에 합친다) → 이미지 태그는 push 뒤 Jenkins 가 정한다(7절에 적는다).

## 1. 순서 (누가)

| # | 일 | 누가 | 확인 |
|---|---|---|---|
| 0 | 미리 알림: 마이그레이션 둘이 든 push. 웹 · 챗봇 · 요약 CronJob 이미지가 같은 커밋 태그로 함께 바뀜 | 런슈즈 관리자 → 사람 | — |
| 1 | 자동 Sync 끄기 | 사람 | `automated` 없음(Claude 확인) — **push 전에** |
| 2 | 앱 `main` push → Jenkins → 인프라 newTag 커밋 | 런슈즈 관리자 | 인프라에 `runshoes: 이미지 태그 <새 태그>` 커밋. ArgoCD OutOfSync(보기만), 운영은 옛 이미지 `ccb74d00c5f3` 그대로 |
| 3 | Sync 전 확인 — 도는 Job 없음 · 덤프 | 사람(명령은 2절) · Claude(읽기) | 2절 (1)(2) |
| 4 | 복원 확인 — 로컬 MySQL 에 다른 이름으로 복원해 행 수 대조 | 사람 | 2절 (3) |
| 5 | Sync = V19 · V20 적용 + 새 이미지 | 사람 | 3절 |
| 6 | 자동 Sync 다시 켜기 | 사람 | `automated` 다시 있음(Claude 확인) |
| 7 | 다음 날 03:30 KST 배치 뒤 | Claude(읽기) · 사람(DB) | `summary_batch_runs` 에 `result='ran'` 1줄 |

- **03:30 KST(18:30 UTC, 요약 CronJob) 근처를 피한다.** 배치가 도는 중에 Sync 하면 해는 없지만 그 실행은 기록되지 않는다(옛 이미지 Job 이 돌고 있으므로).
- Pod 가 둘(replicas 2, maxSurge 0)이다. 옛 Pod 하나가 내려가고 새 Pod 가 마이그레이션을 적용하며 뜬다. 그동안 남은 옛 Pod 는 새 스키마에서 돈다 — 옛 이미지는 새 표 셋을 모르고 쓰지 않는다.

자동 Sync 끄기 · 켜기 · Sync(사람, m-k8s 의 kubectl):

```bash
/home/kopo17/k8s-cluster/backup/2026-10-15-before-metallb/mk 'kubectl -n argocd patch app runshoes --type json -p "[{\"op\":\"remove\",\"path\":\"/spec/syncPolicy/automated\"}]"'
/home/kopo17/k8s-cluster/backup/2026-10-15-before-metallb/mk 'kubectl -n argocd get app runshoes -o jsonpath="{.spec.syncPolicy}"'   # → automated 가 없어야
# Sync(5단계) — <커밋> 은 2단계의 Jenkins 태그 커밋
/home/kopo17/k8s-cluster/backup/2026-10-15-before-metallb/mk 'kubectl -n argocd patch app runshoes --type merge -p "{\"operation\":{\"sync\":{\"revision\":\"<커밋>\"}}}"'
# 다시 켜기(6단계) — 끄기 전 값으로
/home/kopo17/k8s-cluster/backup/2026-10-15-before-metallb/mk 'kubectl -n argocd patch app runshoes --type merge -p "{\"spec\":{\"syncPolicy\":{\"automated\":{}}}}"'
```

## 2. Sync 전 확인 (사람 — 한 줄씩)

**(1) 도는 Job 이 없다**

```bash
/home/kopo17/k8s-cluster/backup/2026-10-15-before-metallb/mk 'kubectl -n runshoes get jobs,pods -l app.kubernetes.io/name=runshoes-summary'
# → 모든 Job 이 Complete/Failed. Running 이 있으면 끝날 때까지 기다린다
```

**(2) 덤프** — V17 과 같은 명령, 이름만 `runshoes-before-v19-<UTC 시각>`. 비밀번호 해시 · 활동 로그가 들어 있다 — `chmod 600`, git 밖. 배포 날이 11-14 가 아니어도 폴더 이름은 그대로 둔다(명령이 모두 이 자리를 본다).

```bash
mkdir -p /home/kopo17/k8s-cluster/backup/2026-11-14-runshoes-v19 && chmod 700 /home/kopo17/k8s-cluster/backup/2026-11-14-runshoes-v19
F=/home/kopo17/k8s-cluster/backup/2026-11-14-runshoes-v19/runshoes-before-v19-$(date -u +%Y%m%dT%H%M%SZ); /home/kopo17/k8s-cluster/backup/2026-10-15-before-metallb/mk 'kubectl -n runshoes exec runshoes-mysql-0 -c mysql -- sh -c "exec mysqldump -uroot -p\"\$MYSQL_ROOT_PASSWORD\" --single-transaction --set-gtid-purged=OFF --routines --triggers --default-character-set=utf8mb4 runshoes"' > $F.sql 2> $F.err; chmod 600 $F.*; echo $F
tail -1 /home/kopo17/k8s-cluster/backup/2026-11-14-runshoes-v19/runshoes-before-v19-*.sql        # → -- Dump completed on …
grep -v 'Using a password' /home/kopo17/k8s-cluster/backup/2026-11-14-runshoes-v19/runshoes-before-v19-*.err   # → 아무것도 없어야
sha256sum /home/kopo17/k8s-cluster/backup/2026-11-14-runshoes-v19/runshoes-before-v19-*.sql | tee /home/kopo17/k8s-cluster/backup/2026-11-14-runshoes-v19/sha256.txt
```

- 덤프는 이 폴더에 하나만 둔다(아래 명령이 `*` 로 집는다). 다시 떠야 하면 앞의 것을 지우고 뜬다.

**(3) 복원 확인** — V17 런북 판 그대로(`group_concat_max_len` 이 들어간 것). 로컬 `runshoes-mysql-dev` 에 임시 DB `runshoes_restore_check` 를 만들었다 지운다(개발 DB `runshoes` 는 건드리지 않는다). 꺼져 있으면 앱 리포 원본 폴더에서 `docker compose up -d`.

```bash
docker exec -i runshoes-mysql-dev sh -c 'mysql -uroot -p"$MYSQL_ROOT_PASSWORD" -e "DROP DATABASE IF EXISTS runshoes_restore_check; CREATE DATABASE runshoes_restore_check CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci"'
cat /home/kopo17/k8s-cluster/backup/2026-11-14-runshoes-v19/runshoes-before-v19-*.sql | docker exec -i runshoes-mysql-dev sh -c 'mysql -uroot -p"$MYSQL_ROOT_PASSWORD" --default-character-set=utf8mb4 runshoes_restore_check'
curl -s -H 'Host: runshoes.ronanlab.dev' http://192.168.122.240/api/reviews | node -e 'const r=JSON.parse(require("fs").readFileSync(0)).sort((a,b)=>a.id-b.id); console.log(r.length, require("crypto").createHash("sha256").update(r.map(x=>x.id+":"+x.shoeId).join(",")).digest("hex"))'
printf '%s\n' "SET SESSION group_concat_max_len = 1048576;" "SELECT COUNT(*), SHA2(GROUP_CONCAT(CONCAT(r.id, ':', r.shoe_id) ORDER BY r.id SEPARATOR ','), 256) FROM reviews r JOIN shoes s ON s.id = r.shoe_id AND s.deleted_at IS NULL;" "SELECT (SELECT COUNT(*) FROM shoes WHERE deleted_at IS NULL), (SELECT COUNT(*) FROM users), (SELECT COUNT(*) FROM chatbot_misses), (SELECT GROUP_CONCAT(CONCAT(version, ':', success) ORDER BY installed_rank) FROM flyway_schema_history);" "SHOW TABLES LIKE 'chatbot_turns';" "SHOW TABLES LIKE 'summary_batch%';" | docker exec -i runshoes-mysql-dev sh -c 'mysql -N -uroot -p"$MYSQL_ROOT_PASSWORD" runshoes_restore_check'
docker exec -i runshoes-mysql-dev sh -c 'mysql -uroot -p"$MYSQL_ROOT_PASSWORD" -e "DROP DATABASE runshoes_restore_check"'
```

- 셋째 줄(API)과 넷째 줄 첫 행(복원본)의 개수 · 지문이 같아야 한다.
- 넷째 줄 둘째 행: shoes · users · chatbot_misses 수(운영 지금 수) · flyway `1:1,…,18:1`. 셋째 · 넷째 결과(새 표)는 비어야 한다. 19 · 20 이나 새 표가 이미 있으면 멈춘다.

## 3. Sync 뒤 확인

**Claude(읽기)**

- 새 Pod 로그: `Current version of schema `runshoes`: 18` → `Migrating schema `runshoes` to version "19 - chatbot turns"` → `"20 - summary batch runs"` → `Successfully applied 2 migrations`. 둘째 Pod 는 `up to date`. 2/2 Running, Synced/Healthy, 공개 첫 화면 200. 챗봇 컨테이너 로그에 오류 없음, 백엔드 준비 확인이 `/readyz` 로 통과.
- 웹 · 챗봇 · CronJob 이 같은 새 태그:

```bash
/home/kopo17/k8s-cluster/backup/2026-10-15-before-metallb/mk 'kubectl -n runshoes get deploy/runshoes cronjob/runshoes-summary -o jsonpath="{..image}"'
```

- Pod 안에서 3000 의 `/livez` · `/readyz` 200 — 앱 이미지에 HTTP 도구가 있는지 모르므로 같은 Pod 의 챗봇 컨테이너(파이썬)에서 본다(네트워크를 같이 쓴다):

```bash
/home/kopo17/k8s-cluster/backup/2026-10-15-before-metallb/mk 'for p in $(kubectl -n runshoes get pod -l app.kubernetes.io/name=runshoes -o name); do for u in livez readyz; do kubectl -n runshoes exec $p -c chatbot -- python -c "import urllib.request as r;print(\"$p $u\", r.urlopen(\"http://127.0.0.1:3000/$u\").status)"; done; done'
```

- 공개 API:

| 확인 | 기대 |
|---|---|
| `GET /` | 200 |
| `GET /api/internal/catalog-version`(밖에서, `X-Forwarded-For: 127.0.0.1` 을 붙여도) | 404 |
| `/actuator/health` | 그대로 200 `UP` (프로브는 아직 이 경로) |
| shoes · reviews 수 | 2절과 같다 |

- 챗봇: 웹소켓 `ws://192.168.122.240/ws/chat`(Host 헤더)에 등록된 신발의 스펙 질문 하나. **없는 신발 질문은 보내지 않는다**(운영 `chatbot_misses` 에 기록이 남는다). 이 질문이 `chatbot_turns` 첫 줄이 된다.

**사람(DB, 한 줄씩)**

```bash
/home/kopo17/k8s-cluster/backup/2026-10-15-before-metallb/mk 'kubectl -n runshoes exec runshoes-mysql-0 -c mysql -- sh -c "mysql -N -uroot -p\"\$MYSQL_ROOT_PASSWORD\" runshoes -e \"SELECT version, success FROM flyway_schema_history WHERE version IN (19,20); SELECT COUNT(*) FROM chatbot_turns\""'
# → 19 1 · 20 1, 챗봇에 한 번 물은 뒤 chatbot_turns 1 이상
```

- 질문 · 답 원문은 화면에 띄우지 않는다 — 개수만 센다.

## 4. 다음 날 03:30 KST 뒤 (7단계)

```bash
/home/kopo17/k8s-cluster/backup/2026-10-15-before-metallb/mk 'kubectl -n runshoes get jobs -l app.kubernetes.io/name=runshoes-summary'   # Claude — 새 회차 Complete
/home/kopo17/k8s-cluster/backup/2026-10-15-before-metallb/mk 'kubectl -n runshoes exec runshoes-mysql-0 -c mysql -- sh -c "mysql -N -uroot -p\"\$MYSQL_ROOT_PASSWORD\" runshoes -e \"SELECT result, COUNT(*) FROM summary_batch_runs GROUP BY result; SELECT COUNT(*) FROM summary_batch_failures\""'   # 사람 — ran 1줄
```

## 5. 실패했을 때

- **마이그레이션 실패** → 새 Pod 가 Ready 가 안 되고 롤링이 멈춘다(남은 옛 Pod 하나가 계속 서비스). 자동 Sync 꺼진 채로 원인 확인.
  - Flyway 는 파일마다 따로 적용한다 — **V19 만 성공하고 V20 이 실패할 수 있다.** MySQL DDL 은 되돌려지지 않는다.
  - 사람이 `flyway_schema_history` 의 실패 행(success 0)만 정리하고(`flyway repair` 와 같다 — 그 행 삭제), 반쯤 생긴 표가 있으면(`SHOW TABLES LIKE 'summary_batch%'` · `'chatbot_turns'`) 지운 뒤 고친 이미지로 다시 Sync. 성공한 행(success 1)과 그 표는 그대로 둔다.
- **기록만 문제**(내부 POST 404, 배치 기록 실패) → 챗봇 답과 요약 만들기는 그대로 돈다. 챗봇 로그 「[turn] 기록 실패」, 배치 로그 「실행 기록 … 넣지 못했다」. 되돌리지 않고 앱 쪽에서 고친다.
- **되돌리기** — 인프라 태그 커밋 `git revert` → push → Sync(앱 06 1-7). 옛 이미지 `ccb74d00c5f3` 은 새 표 셋을 모르지만 해가 없고, Flyway 는 모르는 앞선 버전(19 · 20)을 기본값(`*:future` 무시)으로 넘겨 뜬다. **새 표 셋은 남는다**(해가 없다). 새 표만 생기므로 덤프 복원이 필요한 일은 없다. 챗봇은 `/actuator/health/readiness` 를 보던 옛 판으로 돌아간다.
- 데이터가 잘못되면 2절 (2) 덤프로 복원(사람).

## 6. 다음 부탁 (지금은 하지 않는다 — A-2 2단계)

이 배포가 운영에 오른 것(3절 `/livez` · `/readyz` 200)을 확인한 뒤 런슈즈 관리자가 따로 부탁한다. `apps/runshoes/app/deployment.yaml` 앱 컨테이너 프로브:

| 프로브 | 지금 | 바꿀 것 |
|---|---|---|
| startupProbe | `/actuator/health` | `/readyz` |
| readinessProbe | `/actuator/health/readiness` | `/readyz` |
| livenessProbe | `/actuator/health/liveness` | `/livez` |

- 포트 `http`(3000) · 주기 · 임계값은 그대로.
- **1단계 이미지보다 먼저 나가면 404 로 롤링이 멈춘다** — 운영 이미지에 `/livez` · `/readyz` 가 있는 것을 확인한 뒤에만.

## 7. 실행 기록 (UTC)

| 단계 | 시각 | 내용 |
|---|---|---|
| 1 자동 Sync 끔 | 11-14 저녁 | 사용자. 정확한 시각은 ArgoCD 에 남지 않았다(아래 메모) |
| 3 · 4 확인 · 덤프 · 복원 | 11-14 10:15:22 | 사용자. **push 전에 떴다**(런북은 push 뒤). `runshoes-before-v19-20261114T101522Z.sql` 2,376,234 B · `sha256.txt` 10:17:42. 복원본: reviews 1,800 지문이 운영 API 와 같음 · shoes 310 · users 204 · chatbot_misses 1 · flyway 1~18 |
| 2 push | 11-14 10:19:52 | 앱 `main` `3553716` → Jenkins 인프라 태그 커밋 `2466479`, 이미지 `35537160ce73` |
| 5 Sync | 11-14 10:21:03 ~ 10:21:04 | rev `2466479` Succeeded, Healthy 10:22 무렵. 새 Pod `runshoes-69cc5784f6-rwmmg`(w2) · `-jq7x5`(w1). 웹 · 챗봇 · CronJob 이미지 `35537160ce73`. DB: flyway 19 · 20 success 1, `chatbot_turns` 1 이상(사용자 확인). 런슈즈 관리자 읽기: 10:21:57부터 두 Pod 모두 새 이미지, `/livez` · `/readyz` · `/actuator/health` 200 UP, 내부 `catalog-version` · `chatbot-turns` 밖에서 404(`X-Forwarded-For: 127.0.0.1` 위조도 404), shoes 310 · reviews 1,800, 챗봇 스펙 질문 정상 |
| 6 자동 Sync 켬 | 11-14 10:24:10 | 사용자(`kubectl patch`). `{"automated":{},"syncOptions":["CreateNamespace=false"]}` · Synced/Healthy(인프라 관리자 확인 10:25) |
| 7 첫 03:30 배치 | | 11-15 03:30 KST 회차 뒤 런슈즈 관리자가 알린다 |

- 메모(인프라 관리자, ArgoCD 이력 읽음): 처음에 「5단계 Sync 가 자동 Sync 로 남아 1단계 끄기를 확인하지 못했다」고 적었는데 **틀렸다(11-14 V21 배포 뒤 고침)**. 그때 읽은 `status.operationState.operation.initiatedBy` 는 `kubectl patch` 로 넣은 수동 Sync 에도 `{"automated":true}` 로 나온다(V21 수동 Sync 도 같았다). 믿을 곳은 `status.history[].initiatedBy` 다 — 이 Sync(history 112)는 `{}`(수동), 자동 Sync 였던 2bfbf40(history 113)은 `{"automated":true}`. 그러니 이 배포의 Sync 는 사람이 친 수동 Sync 였다. 끄기가 push 때 걸려 있었는지는 여전히 출력으로 남지 않아, V21 부터는 사람이 끈 출력을 붙이고 push 한다.
