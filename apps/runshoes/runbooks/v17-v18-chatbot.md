# runshoes — V17 · V18 챗봇 1단계(작업 5-1): 아웃솔 용어 id 12 → 13 · 챗봇 문의 기록 표(chatbot_misses)

> 2026-11-12 — 사용자 결정(앱 리포 `docs/09_chatbot_rag.md` 15절). **이미지 Sync 가 곧 V17 · V18 적용**이다(한 이미지 · 한 Sync — 자동 Sync 를 끄고 켜는 일은 한 번). 절차는 V14 · V15 와 같다(앱 리포 `docs/06_deployment.md` 1-7).
> 운영 DB · 클러스터 쓰기는 **사람이 친다**. Claude 는 명령과 순서를 주고, 읽기(공개 API · `kubectl get` · 로그)로 확인만 한다.
> 사람이 치는 명령은 **한 줄씩 · 절대 경로**다 — 터미널 패널은 `cd` · 셸 변수를 이어받지 않는다. 그래서 아래 명령은 앞 줄의 변수에 기대지 않는다.

```bash
# 이 런북에서 쓰는 자리(명령 안에 그대로 풀어 썼다)
# 덤프       /home/kopo17/k8s-cluster/backup/2026-11-12-runshoes-v17/   — 데이터가 들어 있어 git 밖
# kubectl    /home/kopo17/k8s-cluster/backup/2026-10-15-before-metallb/mk '<명령>'
# 공개 API   http://192.168.122.240 + 'Host: runshoes.ronanlab.dev'
```

## V17

- 아웃솔 용어(`terms.term_key = 'outsole'`)의 `id` 를 12 → 13. 시드(V2)에 id 12 가 둘(weight · outsole)이었다 — 챗봇이 용어를 id 로 참조하면 둘이 섞인다.
- **키는 `row_no` 그대로** — 바뀌는 것은 응답에 나가는 `id` 값 하나. 화면은 용어를 `term_key` 로 찾아 바뀌는 것이 없다.
- **첫 구문이 가드** — 아웃솔 행이 하나이고 그 id 가 12, id 13 이 비어 있을 때만 진행. 누가 먼저 고쳤으면 `ERROR 1242` 로 멈추고 아무것도 바꾸지 않는다(그러면 새 Pod 가 뜨지 않는다 — 4절).

## V18

- 새 표 `chatbot_misses`(id · kind · query · message · created_at, `kind` 는 CHECK 로 `shoe` · `term` · `feature`). 기존 표는 건드리지 않는다.
- 쓰는 길은 챗봇 사이드카의 내부 POST `/api/internal/chatbot-misses` 하나 — 같은 Pod 안 `127.0.0.1` 로 들어온 연결만(`localAddr` 를 본다, `X-Forwarded-For` 를 믿지 않는다). 밖에서 오면 404. 읽기는 관리 화면 "챗봇 문의" 탭(`GET /api/admin/chatbot-misses`, 관리자 · 데모 관리자).
- 누가 물었는지는 남기지 않는다(사용자 id · IP 없음).

## 같은 이미지에 함께 오는 것

- 챗봇 이미지가 한 파일(`chatbot_server.py`)에서 `chatbot/` 패키지로(`python -m chatbot.server`, 포트 8766 그대로). 말투 · 갈래 · 검사가 모두 바뀐다(09 15절). **manifest 는 바꾸지 않는다** — 읽는 env 는 `OLLAMA_URL`(지금 값 그대로) · `RUNSHOES_API`(없으면 `http://127.0.0.1:3000` — 같은 Pod 의 Spring) · `CHATBOT_MODEL`(없으면 `gemma4:e4b`, 옛 서버와 같은 모델).
- `GET /api/recommend` 에 `budget`(원, 1 ~ 1억) — 지금 운영은 400.
- 관리 화면 "챗봇 문의" 탭.
- 배치(CronJob, batch 프로필)는 Flyway 를 돌리지 않고 `validate` 만 한다. V18 표는 JdbcTemplate 으로만 써서 엔티티가 없다 — 배치의 `validate` 에 영향 없음.
- 앱 커밋 `bff482c`(cc/runshoes-3 합침) + 그 뒤 문서 커밋 → 이미지 태그는 push 뒤 Jenkins 가 정한다(5절에 적는다).

### 로컬 확인(2026-11-12)

- 백엔드 단위 시험(`ChatbotMissTest` · `PolicyTest.budgetInWon` 포함) 통과. 계약: 녹화는 따로 띄운 임시 MySQL(`runshoes-mysql-contract`, 127.0.0.1:3309, tmpfs) — 개발 DB 를 건드리지 않는다. spring-v3 R03 다시 녹화(terms 응답의 outsole id 13), spring-v6 X154 ~ X156(budget).
- V17: 새 시드 DB 에서 가드 통과 · outsole id 13, 이미 고친 DB 에 가드를 다시 치면 `ERROR 1242`.
- 내부 POST: 쿠버네티스 env(`KUBERNETES_SERVICE_HOST`)를 켠 로컬에서 `X-Forwarded-For: 127.0.0.1` 을 붙여도 밖에서 오면 404(고치기 전 204).
- 챗봇 평가: 경계 15문항 두 번 15/15, 기존 45문항 45/45(사용자 확인 2026-11-12).

## 1. 순서 (누가)

| # | 일 | 누가 | 확인 |
|---|---|---|---|
| 1 | 자동 Sync 끄기 | 사람 | `automated` 없음(Claude 확인) — **push 전에** |
| 2 | 앱 `main` push → Jenkins → newTag 커밋, infra 커밋(이 런북) push | Claude(사용자가 push 하라고 할 때) | 운영은 옛 이미지 `4f57bc0e1537` |
| 3 | Sync 전 확인 — 도는 Job 없음 · 덤프 · 복원 확인 | 사람(명령은 2절) · Claude(읽기) | 2절 |
| 4 | Sync = V17 · V18 적용 + 새 이미지(웹 · 챗봇 · CronJob 같은 태그) | 사람 | 3절 |
| 5 | 자동 Sync 다시 켜기 | 사람 | `automated` 다시 있음 |

- **03:30 KST(18:30 UTC, 요약 CronJob) 근처를 피한다.** 그 시각에 Sync 하면 옛 이미지 Job 이 도는 중에 스키마가 바뀐다.
- Pod 가 둘(replicas 2)이다. 새 Pod 하나가 먼저 뜨며 마이그레이션을 적용하고, 그 사이 옛 Pod 는 새 스키마에서 돈다 — 옛 이미지는 `chatbot_misses` 를 모르고(쓰지 않는다), outsole 은 id 13 으로 응답한다(화면은 `term_key` 로 찾아 영향 없음).

## 2. Sync 전 확인 (사람 — 한 줄씩)

**(1) 도는 Job 이 없다**

```bash
/home/kopo17/k8s-cluster/backup/2026-10-15-before-metallb/mk 'kubectl -n runshoes get jobs,pods -l app.kubernetes.io/name=runshoes-summary'
# → 모든 Job 이 Complete/Failed. Running 이 있으면 끝날 때까지 기다린다
```

**(2) 덤프** — V14 · V15 와 같은 명령, 이름만 `runshoes-before-v17-<UTC 시각>`. 비밀번호 해시 · 활동 로그가 들어 있다 — `chmod 600`, git 밖.

```bash
mkdir -p /home/kopo17/k8s-cluster/backup/2026-11-12-runshoes-v17 && chmod 700 /home/kopo17/k8s-cluster/backup/2026-11-12-runshoes-v17
F=/home/kopo17/k8s-cluster/backup/2026-11-12-runshoes-v17/runshoes-before-v17-$(date -u +%Y%m%dT%H%M%SZ); /home/kopo17/k8s-cluster/backup/2026-10-15-before-metallb/mk 'kubectl -n runshoes exec runshoes-mysql-0 -c mysql -- sh -c "exec mysqldump -uroot -p\"\$MYSQL_ROOT_PASSWORD\" --single-transaction --set-gtid-purged=OFF --routines --triggers --default-character-set=utf8mb4 runshoes"' > $F.sql 2> $F.err; chmod 600 $F.*; echo $F
tail -1 /home/kopo17/k8s-cluster/backup/2026-11-12-runshoes-v17/runshoes-before-v17-*.sql        # → -- Dump completed on …
grep -v 'Using a password' /home/kopo17/k8s-cluster/backup/2026-11-12-runshoes-v17/runshoes-before-v17-*.err   # → 아무것도 없어야
sha256sum /home/kopo17/k8s-cluster/backup/2026-11-12-runshoes-v17/runshoes-before-v17-*.sql | tee /home/kopo17/k8s-cluster/backup/2026-11-12-runshoes-v17/sha256.txt
```

- 덤프는 이 폴더에 하나만 둔다(아래 명령이 `*` 로 집는다). 다시 떠야 하면 앞의 것을 지우고 뜬다.

**(3) 복원 확인** — **V14 런북 판 그대로**(`group_concat_max_len` 이 들어간 것). 빠뜨리면 지문이 1,024바이트에서 잘려 개수는 같고 지문만 다르다. 로컬 `runshoes-mysql-dev` 에 임시 DB `runshoes_restore_check` 를 만들었다 지운다(개발 DB `runshoes` 는 건드리지 않는다). 꺼져 있으면 앱 리포 원본 폴더에서 `docker compose up -d`.

```bash
docker exec -i runshoes-mysql-dev sh -c 'mysql -uroot -p"$MYSQL_ROOT_PASSWORD" -e "DROP DATABASE IF EXISTS runshoes_restore_check; CREATE DATABASE runshoes_restore_check CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci"'
cat /home/kopo17/k8s-cluster/backup/2026-11-12-runshoes-v17/runshoes-before-v17-*.sql | docker exec -i runshoes-mysql-dev sh -c 'mysql -uroot -p"$MYSQL_ROOT_PASSWORD" --default-character-set=utf8mb4 runshoes_restore_check'
curl -s -H 'Host: runshoes.ronanlab.dev' http://192.168.122.240/api/reviews | node -e 'const r=JSON.parse(require("fs").readFileSync(0)).sort((a,b)=>a.id-b.id); console.log(r.length, require("crypto").createHash("sha256").update(r.map(x=>x.id+":"+x.shoeId).join(",")).digest("hex"))'
printf '%s\n' "SET SESSION group_concat_max_len = 1048576;" "SELECT COUNT(*), SHA2(GROUP_CONCAT(CONCAT(r.id, ':', r.shoe_id) ORDER BY r.id SEPARATOR ','), 256) FROM reviews r JOIN shoes s ON s.id = r.shoe_id AND s.deleted_at IS NULL;" "SELECT (SELECT COUNT(*) FROM shoes WHERE deleted_at IS NULL), (SELECT COUNT(*) FROM users), (SELECT GROUP_CONCAT(CONCAT(id, ':', term_key) ORDER BY row_no) FROM terms), (SELECT GROUP_CONCAT(CONCAT(version, ':', success) ORDER BY installed_rank) FROM flyway_schema_history);" | docker exec -i runshoes-mysql-dev sh -c 'mysql -N -uroot -p"$MYSQL_ROOT_PASSWORD" runshoes_restore_check'
docker exec -i runshoes-mysql-dev sh -c 'mysql -uroot -p"$MYSQL_ROOT_PASSWORD" -e "DROP DATABASE runshoes_restore_check"'
```

- 셋째 줄(API)과 넷째 줄 첫 행(복원본)의 개수 · 지문이 같아야 한다.
- 넷째 줄 둘째 행: shoes 310 · users(지금 수) · terms `1:drop,…,12:weight,12:outsole`(id 12 둘 — V17 전) · flyway `1:1,…,16:1`. 17 · 18 이 이미 있으면 멈춘다.

## 3. Sync 뒤 확인 (Claude — 읽기)

- 새 Pod 로그: `Migrating … to version "17 - terms outsole id"`(그 사이 `v17 guard ok`) → `"18 - chatbot misses"` → `Successfully applied 2 migrations … v18`. 2/2 Running, Synced/Healthy, 공개 200. 챗봇 컨테이너 로그에 오류 없음.
- 웹 · 챗봇 · CronJob 이 같은 태그(`kubectl -n runshoes get deploy runshoes,cronjob runshoes-summary -o jsonpath='{..image}'`). 다음 03:30 KST 회차가 Complete 인지도 본다.
- 공개 API:

| 확인 | 기대 |
|---|---|
| `GET /api/terms` | 13개, id 겹침 없음, outsole id 13(나머지 12개의 id · 순서 · 글은 그대로) |
| `GET /api/recommend?purpose=daily&budget=150000` | 200(전에는 400) |
| `GET /api/admin/chatbot-misses`(로그인 없이) | 401(전에는 404 — 경로가 없었다) |
| `POST /api/internal/chatbot-misses`(밖에서, `X-Forwarded-For: 127.0.0.1` 을 붙여도) | 404 — 표에 들어가지 않는다 |
| shoes · reviews 수 | 310 · 1,800 그대로 |

- 챗봇: 웹소켓 `ws://192.168.122.240/ws/chat`(Host 헤더)에 등록된 신발의 스펙 질문 하나 — 해요체 · 이모지 없음 · `links` 에 "보러 가기". **없는 신발 질문은 보내지 않는다**(운영 표에 기록이 남는다).
- 화면: 관리 화면 "챗봇 문의" 탭이 열린다(사용자 — 처음엔 비어 있다).

## 4. 실패했을 때

- 마이그레이션 실패 → 새 Pod 가 뜨지 않는다(옛 Pod 유지). 자동 Sync 꺼진 채로 원인 확인.
  - V17 가드(`ERROR 1242`, `v17 guard: outsole id is not the seed 12`): 운영 outsole 의 id 가 12 가 아니거나 id 13 이 이미 있다. 아무것도 바뀌지 않았다(UPDATE 전). 바뀐 것은 `flyway_schema_history` 의 실패 행(version 17, success 0) 하나 — V15 런북 4절 V16 과 같다. 지금 terms 를 사람이 읽어 알리고, V17 을 어떻게 할지 정한 뒤 실패 행만 지우고(`flyway repair` 와 같다) 고친 이미지로 다시. V18 은 적용되지 않았다.
  - V18 실패(`CREATE TABLE`): V17 은 적용됐다. MySQL DDL 은 되돌려지지 않는다 — 표가 반쯤 생겼는지(`SHOW TABLES LIKE 'chatbot_misses'`) 사람이 보고, 실패 행(version 18) 정리 뒤 다시.
- 새 챗봇만 이상하다(웹은 정상) → 되돌리기는 이미지 전체라 스키마 쪽과 같다(아래). 챗봇만 따로 되돌리는 길은 없다.
- 되돌리기 — infra 태그 커밋 `git revert` → push → Sync(06 1-7). 옛 이미지 `4f57bc0e1537` 은 `chatbot_misses` 를 모르지만 엔티티가 없는 표라 `validate` 와 상관없고, Flyway 는 자기가 모르는 앞선 버전(17 · 18)을 기본값(`*:future` 무시)으로 넘겨 뜬다. **스키마는 돌아오지 않는다** — outsole 은 id 13 그대로(화면 영향 없음), 표는 남는다(해가 없다). 옛 챗봇(`chatbot_server.py`)으로 돌아간다.
- 데이터가 잘못되면 2절 (2) 덤프로 복원(사람).

## 5. 실행 기록 (UTC)

| 단계 | 시각 | 내용 |
|---|---|---|
| 1 자동 Sync 끔 | | |
| 2 push | | |
| 3 확인 · 덤프 | | |
| 4 Sync | | |
| 5 자동 Sync 켬 | | |
