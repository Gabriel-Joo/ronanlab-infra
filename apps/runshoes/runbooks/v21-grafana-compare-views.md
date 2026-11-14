# runshoes — V21 대시보드 뷰(grafana_compare_views) · actuator 를 관리 포트 9000 으로(A-2 3단계)

> 2026-11-14 — 사용자 결정(대시보드 「비교 조합 순위」 패널을 위해 뷰를 Flyway 로 넣는다). 런슈즈 관리자 부탁으로 인프라 관리자가 씀. **이미지 Sync 가 곧 V21 적용**이다(뷰 하나, 표는 바뀌지 않는다). 절차는 V19 · V20 과 같다(`v19-v20-observability.md`, 앱 리포 `docs/06_deployment.md` 1-7).
> 운영 DB · 클러스터 쓰기는 **사람이 친다**. Claude 는 명령과 순서를 주고, 읽기(공개 API · `kubectl get` · 로그)로 확인만 한다.
> 사람이 치는 명령은 **한 줄씩 · 절대 경로**다 — 터미널 패널은 `cd` · 셸 변수를 이어받지 않는다.
> **매니페스트 변경은 이번에 없다.** 9000 을 긁는 Pod 주석은 이 배포가 운영에 오른 것을 확인한 뒤 따로 부탁한다(6절).

```bash
# 이 런북에서 쓰는 자리(명령 안에 그대로 풀어 썼다)
# 덤프       /home/kopo17/k8s-cluster/backup/2026-11-14-runshoes-v21/   — 데이터가 들어 있어 git 밖
# kubectl    /home/kopo17/k8s-cluster/backup/2026-10-15-before-metallb/mk '<명령>'
# 공개 API   http://192.168.122.240 + 'Host: runshoes.ronanlab.dev'
```

## 쓰기 전 운영 상태(2026-11-14, 인프라 관리자 읽기)

- ArgoCD `runshoes`: 자동 Sync 켜짐(`{"automated":{},"syncOptions":["CreateNamespace=false"]}`), Synced/Healthy, rev `2bfbf40`(프로브 `/readyz` · `/livez`)
- 이미지: 웹 · 챗봇 · CronJob 모두 `35537160ce73`
- `flyway_schema_history`: 최대 20, 모두 success 1. 뷰 없음. 원본 · 복제본 같음
- 계정 `runshoes`@`%`: 원본 · 복제본 둘 다 있음(V21 정의자). `grafana_ro`: 아직 없음

## V21

```sql
CREATE SQL SECURITY DEFINER VIEW grafana_compare_views AS
SELECT id, occurred_at, user_id, CAST(JSON_EXTRACT(meta, '$.shoeIds') AS CHAR(200)) AS shoe_ids
FROM activity_logs WHERE event = 'compare.view';
```

- 정의자는 Flyway 를 돌리는 앱 계정 `runshoes`@`%`. 앱은 이 뷰를 읽지 않는다 — 대시보드 읽기 계정(`grafana_ro`)만 읽는다.
- `activity_logs` 의 다른 칸(`meta` 전체 등)은 뷰에 없다. 읽기 계정에는 이 뷰만 GRANT 하면 원본 표를 열지 않고 비교 조합만 보인다.
- 뷰는 데이터를 담지 않는다 — 지워도(`DROP VIEW`) 잃는 것이 없다.
- 복제본에도 복제로 생긴다(read_only 는 복제 SQL 스레드를 막지 않는다). 복제본에서 뷰를 읽으려면 정의자 계정 `runshoes`@`%` 가 복제본에 있어야 한다(위 상태에서 있음).

## 같은 이미지에 함께 오는 것

- **A-2 3단계**: actuator 를 관리 포트 9000 으로(`management.server.port`). 3000 에는 `/actuator` 가 없어지고, `/livez` · `/readyz` 는 3000 에 그대로 — **지금 프로브(2bfbf40) 그대로 뜬다.** prometheus 노출(SLO 버킷 넷).
  - 9000 은 Service · Ingress 에 없다 → 바깥에서 닿을 길이 없다. Prometheus 는 Pod IP:9000 으로 바로 긁는다(6절 주석 뒤).
- 문서(앱 리포): 대시보드 읽기 계정 `grafana_ro` SQL(07 1-6절 — 사람이 원본에서 친다, V21 뒤 뷰 GRANT 한 줄 포함), 대시보드 역할 가르기.
- 앱 커밋 넷(push 전 런슈즈 `main` 에 합친다) → 이미지 태그는 push 뒤 Jenkins 가 정한다(7절에 적는다).

## 1. 순서 (누가)

| # | 일 | 누가 | 확인 |
|---|---|---|---|
| 1 | 자동 Sync 끄기 | 사람 | — |
| 2 | **끈 것을 사람이 친 출력으로 확인 — push 전에** | 사람 → 런슈즈 관리자 | 아래 명령 출력에 `automated` 가 없다. 출력을 런슈즈 관리자에게 붙인다(인프라 관리자에게 읽어 달라고 해도 된다) |
| 3 | 앱 `main` push → Jenkins → 인프라 newTag 커밋 | 런슈즈 관리자 | 인프라에 `runshoes: 이미지 태그 <새 태그>` 커밋. ArgoCD OutOfSync 만, 운영은 옛 이미지 `35537160ce73` 그대로 |
| 4 | Sync 전 확인 — 도는 요약 Job 없음 · 덤프 | 사람(2절 (1)(2)) | 03:30 KST 근처를 피한다 |
| 5 | 복원 확인 | 사람(2절 (3)) | reviews 수 · 지문이 공개 API 와 같음, flyway 1~20, 뷰 없음 |
| 6 | Sync = V21 적용 + 새 이미지(웹 · 챗봇 · CronJob 같은 태그) | 사람 | 3절 |
| 7 | 자동 Sync 다시 켜기 | 사람 | `automated` 다시 있음 |

- 2번은 V19 · V20 때 더한 것이다 — 그때 Sync 가 ArgoCD 에 `{"automated":true}` 로 남아, push 때 자동 Sync 가 꺼져 있었는지 확인하지 못했다(`v19-v20-observability.md` 7절 메모).
- Pod 가 둘(replicas 2, maxSurge 0)이다. 옛 Pod 하나가 내려가고 새 Pod 가 V21 을 적용하며 뜬다. 그동안 남은 옛 Pod 는 뷰가 생긴 스키마에서 돈다 — 옛 이미지는 뷰를 모르고 쓰지 않는다.

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

## 2. Sync 전 확인 (사람 — 한 줄씩)

**(1) 도는 Job 이 없다**

```bash
/home/kopo17/k8s-cluster/backup/2026-10-15-before-metallb/mk 'kubectl -n runshoes get jobs,pods -l app.kubernetes.io/name=runshoes-summary'
# → 모든 Job 이 Complete/Failed. Running 이 있으면 끝날 때까지 기다린다
```

**(2) 덤프** — V19 과 같은 명령, 이름만 `runshoes-before-v21-<UTC 시각>`. 비밀번호 해시 · 활동 로그 · **챗봇 질문 · 답 원문(V19 `chatbot_turns`)** 이 들어 있다 — `chmod 600`, git 밖. 배포 날이 11-14 가 아니어도 폴더 이름은 그대로 둔다.

```bash
mkdir -p /home/kopo17/k8s-cluster/backup/2026-11-14-runshoes-v21 && chmod 700 /home/kopo17/k8s-cluster/backup/2026-11-14-runshoes-v21
F=/home/kopo17/k8s-cluster/backup/2026-11-14-runshoes-v21/runshoes-before-v21-$(date -u +%Y%m%dT%H%M%SZ); /home/kopo17/k8s-cluster/backup/2026-10-15-before-metallb/mk 'kubectl -n runshoes exec runshoes-mysql-0 -c mysql -- sh -c "exec mysqldump -uroot -p\"\$MYSQL_ROOT_PASSWORD\" --single-transaction --set-gtid-purged=OFF --routines --triggers --default-character-set=utf8mb4 runshoes"' > $F.sql 2> $F.err; chmod 600 $F.*; echo $F
tail -1 /home/kopo17/k8s-cluster/backup/2026-11-14-runshoes-v21/runshoes-before-v21-*.sql        # → -- Dump completed on …
grep -v 'Using a password' /home/kopo17/k8s-cluster/backup/2026-11-14-runshoes-v21/runshoes-before-v21-*.err   # → 아무것도 없어야
sha256sum /home/kopo17/k8s-cluster/backup/2026-11-14-runshoes-v21/runshoes-before-v21-*.sql | tee /home/kopo17/k8s-cluster/backup/2026-11-14-runshoes-v21/sha256.txt
```

- 덤프는 이 폴더에 하나만 둔다(아래 명령이 `*` 로 집는다). 다시 떠야 하면 앞의 것을 지우고 뜬다.

**(3) 복원 확인** — V19 런북 판 그대로(`group_concat_max_len` 이 들어간 것). 로컬 `runshoes-mysql-dev` 에 임시 DB `runshoes_restore_check` 를 만들었다 지운다(개발 DB `runshoes` 는 건드리지 않는다).

```bash
docker exec -i runshoes-mysql-dev sh -c 'mysql -uroot -p"$MYSQL_ROOT_PASSWORD" -e "DROP DATABASE IF EXISTS runshoes_restore_check; CREATE DATABASE runshoes_restore_check CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci"'
cat /home/kopo17/k8s-cluster/backup/2026-11-14-runshoes-v21/runshoes-before-v21-*.sql | docker exec -i runshoes-mysql-dev sh -c 'mysql -uroot -p"$MYSQL_ROOT_PASSWORD" --default-character-set=utf8mb4 runshoes_restore_check'
curl -s -H 'Host: runshoes.ronanlab.dev' http://192.168.122.240/api/reviews | node -e 'const r=JSON.parse(require("fs").readFileSync(0)).sort((a,b)=>a.id-b.id); console.log(r.length, require("crypto").createHash("sha256").update(r.map(x=>x.id+":"+x.shoeId).join(",")).digest("hex"))'
printf '%s\n' "SET SESSION group_concat_max_len = 1048576;" "SELECT COUNT(*), SHA2(GROUP_CONCAT(CONCAT(r.id, ':', r.shoe_id) ORDER BY r.id SEPARATOR ','), 256) FROM reviews r JOIN shoes s ON s.id = r.shoe_id AND s.deleted_at IS NULL;" "SELECT (SELECT COUNT(*) FROM shoes WHERE deleted_at IS NULL), (SELECT COUNT(*) FROM users), (SELECT COUNT(*) FROM chatbot_turns), (SELECT COUNT(*) FROM activity_logs WHERE event = 'compare.view'), (SELECT GROUP_CONCAT(CONCAT(version, ':', success) ORDER BY installed_rank) FROM flyway_schema_history);" "SHOW FULL TABLES WHERE Table_type = 'VIEW';" | docker exec -i runshoes-mysql-dev sh -c 'mysql -N -uroot -p"$MYSQL_ROOT_PASSWORD" runshoes_restore_check'
docker exec -i runshoes-mysql-dev sh -c 'mysql -uroot -p"$MYSQL_ROOT_PASSWORD" -e "DROP DATABASE runshoes_restore_check"'
```

- 셋째 줄(API)과 넷째 줄 첫 행(복원본)의 개수 · 지문이 같아야 한다.
- 넷째 줄 둘째 행: shoes · users · chatbot_turns · compare.view 행 수(운영 지금 수) · flyway `1:1,…,20:1`. 셋째 결과(뷰)는 비어야 한다. 21 이나 뷰가 이미 있으면 멈춘다.
- 덧: V21 뒤에 뜬 덤프를 다른 DB 이름으로 복원하면 뷰 읽기는 `ERROR 1356` 이다(정의자 권한이 `runshoes.*` 에만 있다). 그때는 표만 센다.

## 3. Sync 뒤 확인

**Claude(읽기)**

- 새 Pod 로그: `Migrating schema `runshoes` to version "21 - grafana compare views"` → `Successfully applied 1 migration`. 둘째 Pod 는 `up to date`. 2/2 Running, 재시작 0, Synced/Healthy, 공개 첫 화면 200. 프로브(`/readyz` · `/livez`) 실패 이벤트가 기동 중 connection refused 말고는 없다.
- 웹 · 챗봇 · CronJob 이 같은 새 태그:

```bash
/home/kopo17/k8s-cluster/backup/2026-10-15-before-metallb/mk 'kubectl -n runshoes get deploy/runshoes cronjob/runshoes-summary -o jsonpath="{..image}"'
```

- **A-2 3단계 — 공개 쪽이 닫혔는지:** 공개 `/actuator` · `/actuator/health` · `/actuator/prometheus` 가 200 `text/html`(SPA). **JSON 이나 `# HELP` 가 나오면 열린 것** — 그때는 바로 알린다.

```bash
for p in /actuator /actuator/health /actuator/prometheus; do printf "%s " $p; curl -s --max-time 8 -o /dev/null -w '%{http_code} %{content_type}\n' https://runshoes.ronanlab.dev$p; done
```

- Pod 안에서 9000 이 열렸는지 — 챗봇 컨테이너(파이썬)에서 본다(네트워크를 같이 쓴다). 지표는 첫 줄만, 개수는 줄 수로:

```bash
/home/kopo17/k8s-cluster/backup/2026-10-15-before-metallb/mk 'for p in $(kubectl -n runshoes get pod -l app.kubernetes.io/name=runshoes -o name); do kubectl -n runshoes exec $p -c chatbot -- python -c "import urllib.request as r;b=r.urlopen(\"http://127.0.0.1:9000/actuator/prometheus\").read().decode();print(\"$p\", len([l for l in b.splitlines() if l and not l.startswith(\"#\")]), \"lines\"); [print(\"$p\", u, r.urlopen(\"http://127.0.0.1:3000/\"+u).status) for u in (\"livez\",\"readyz\")]"; done'
```

**사람(DB, 원본 · 복제본 둘 다)**

```bash
/home/kopo17/k8s-cluster/backup/2026-10-15-before-metallb/mk 'for p in runshoes-mysql-0 runshoes-mysql-replica-0; do echo "== $p"; kubectl -n runshoes exec $p -c mysql -- sh -c "mysql -N -uroot -p\"\$MYSQL_ROOT_PASSWORD\" runshoes -e \"SELECT version, success FROM flyway_schema_history WHERE version = 21; SHOW FULL TABLES LIKE \\\"grafana_compare_views\\\"; SELECT DEFINER, SECURITY_TYPE FROM information_schema.views WHERE TABLE_NAME = \\\"grafana_compare_views\\\"; SELECT COUNT(*) FROM grafana_compare_views\""; done'
# → 두 곳 모두: 21 1 · grafana_compare_views VIEW · runshoes@% DEFINER · 숫자
```

- 복제본에서 `ERROR 1449`(정의자 계정 없음)면 복제본 다시 채우기(`docs/runbooks/mysql-replica.md` 2절) — 원본 · 앱은 영향 없음. 배포 전 읽기에서는 복제본에 `runshoes`@`%` 가 있었다.
- 그 뒤 사람: 원본에서 앱 리포 07 1-6절의 `grafana_ro` SQL 전체(뷰 GRANT 포함). 복제본으로 따라간다. 비밀번호는 표준 입력으로 넣고 화면 · 로그에 내지 않는다.

## 4. 실패했을 때

- **V21 실패**(`CREATE VIEW`, 예: 권한) → 새 Pod 가 Ready 가 안 되고 롤링이 멈춘다(남은 옛 Pod 하나가 받는다). 자동 Sync 꺼진 채로 원인 확인.
  - 바뀐 것은 `flyway_schema_history` 의 실패 행(version 21, success 0) 하나. 뷰가 생겼는지(`SHOW FULL TABLES LIKE 'grafana_compare_views'`) 사람이 보고, 생겼으면 `DROP VIEW`(데이터 없음), 실패 행만 지운 뒤(`flyway repair` 와 같다) 고친 이미지로 다시 Sync.
- **복제본에서만 `ERROR 1449`** → 복제본 다시 채우기(위). 원본 · 앱은 영향 없음.
- **공개 `/actuator` 에서 JSON 이나 `# HELP`** → 관리 포트 분리가 안 된 것. 지표가 인터넷에 열려 있으므로 바로 되돌린다(아래).
- **되돌리기** — 인프라 태그 커밋 `git revert` → push → Sync(앱 06 1-7). 옛 이미지 `35537160ce73` 은 V21 을 앞선 버전(`*:future` 무시)으로 넘겨 뜬다. **뷰는 남지만 해가 없다.** 옛 이미지는 `/actuator` 가 3000 에 다시 열린다(health 만 노출 — 배포 전과 같음). 프로브는 `/readyz` · `/livez` 라 그대로 뜬다.
- 데이터가 잘못되면 2절 (2) 덤프로 복원(사람). 이번 변경은 뷰 하나라 그럴 일은 없다고 본다.

## 5. 표 · 뷰 · 계정 메모

- `grafana_ro` 는 런슈즈 원본에서 사람이 만든다(앱 리포 07 1-6절). 펫퍼민트 `grafana_ro`(`apps/monitoring/README.md`)와 같은 꼴 — 컬럼 단위 SELECT, 질문 · 답 원문(`chatbot_turns`) 칸은 주지 않는다.
- Grafana 데이터소스(`apps/monitoring/grafana/datasource.yaml`)와 Secret · env 는 인프라 일이다 — 런슈즈 관리자가 따로 부탁한다. 읽는 곳은 복제본 `runshoes-mysql-replica.runshoes.svc:3306`.

## 6. 다음 부탁 (지금은 하지 않는다)

이 배포가 운영에 오른 것(3절, 9000 에서 지표 · 공개 쪽 닫힘)을 확인한 뒤 런슈즈 관리자가 따로 부탁한다. `apps/runshoes/app/deployment.yaml` Pod 템플릿 주석:

```yaml
prometheus.io/scrape: "true"
prometheus.io/port: "9000"
prometheus.io/path: /actuator/prometheus
```

- Prometheus job `kubernetes-pods`(`apps/monitoring/prometheus/configmap.yaml`)가 Pod IP:9000 으로 긁는다. 주석은 Pod 에 포트 하나라 챗봇 사이드카는 긁히지 않는다.
- 붙인 뒤 인프라 관리자가 시계열 수를 다시 잰다(11-14 기준 head 25,181, Prometheus limit 768Mi).

## 7. 실행 기록 (UTC)

| 단계 | 시각 | 내용 |
|---|---|---|
| 1 자동 Sync 끔 | 11-14 11:13 전 | 사용자. 정확한 시각은 ArgoCD 에 남지 않는다(필드를 지우는 patch 라 managedFields 에 자국이 없다) |
| 2 끈 것 확인(사람 출력) | 11-14 11:13 전 | 사용자가 붙인 출력 `{"syncOptions":["CreateNamespace=false"]}` 을 런슈즈 관리자가 보고 push |
| 3 push | 11-14 11:13:20 | 앱 `main` `f9ee36e` → Jenkins 인프라 태그 커밋 `78b23bb`(11:17:58), 이미지 `f9ee36e01331`. ArgoCD OutOfSync 11:17:45(사용자 확인) |
| 4 · 5 확인 · 덤프 · 복원 | 11-14 11:18:53 | 사용자. `runshoes-before-v21-20261114T111853Z.sql` 2,381,231 B · `sha256.txt` 11:19:07. 복원 확인 「맞다」(사용자) |
| 6 Sync | 11-14 11:21:01 | 사용자(수동 — history 114 `initiatedBy` `{}`). rev `78b23bb` Succeeded, Healthy 11:22:31. 새 Pod `runshoes-77dd67cbf9-7w9jx` · `-mfs59`. 런슈즈 관리자 읽기: 11:22:10부터 두 Pod 새 이미지, 공개 `/actuator` · `/actuator/health` · `/actuator/prometheus` 모두 200 `text/html` · `# HELP` 0, `/livez` · `/readyz` 200 UP, shoes 310 · reviews 1,800, 챗봇 정상. Pod 안 9000 지표 줄 199 · 285. 사용자 DB: 원본 · 복제본 둘 다 `21 1` · VIEW · `runshoes@%` DEFINER · 40 |
| 7 자동 Sync 켬 | 11-14 11:22:31 ~ 11:26:58 사이 | 사용자. 인프라 관리자가 11:22:31 뒤에 읽었을 때는 아직 꺼져 있었고, 11:26:58 에 Pod 주석 커밋 `9b57224` 를 자동 Sync 가 받았다(history 115 `{"automated":true}`). 정확한 시각은 남지 않았다(그 뒤 인프라 관리자의 수동 Sync patch 가 같은 managedFields 칸을 11:27:12 로 덮었다). 지금 `{"automated":{},"syncOptions":["CreateNamespace=false"]}` |
| grafana_ro SQL | | |
