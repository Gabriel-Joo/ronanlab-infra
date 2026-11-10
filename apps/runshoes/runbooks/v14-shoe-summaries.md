# runshoes — V14 리뷰 요약을 배치로(shoe_summaries + CronJob)

> 2026-11-10 — 사용자 결정(앱 리포 `docs/09_chatbot_rag.md` 5절). **이미지 Sync 가 곧 V14 적용**이고, 같은 Sync 에 CronJob `runshoes-summary`(suspend) 가 들어간다.
> 운영 DB · 클러스터 쓰기는 **사람이 친다**. Claude 는 명령과 순서를 주고, 읽기(공개 API · `kubectl get` · 로그 · Ollama 로그)로 확인만 한다.

```bash
B=~/k8s-cluster/backup/2026-11-10-runshoes-v14   # 덤프 — 데이터가 들어 있어 git 밖
VIP=http://192.168.122.240; H='Host: runshoes.ronanlab.dev'
mk() { ~/k8s-cluster/backup/2026-10-15-before-metallb/mk "$@"; }
```

## V14

- `shoe_summaries(shoe_id PK · FK shoes ON DELETE CASCADE, positive, negative, review_count, avg_rating DOUBLE, is_stale, generated_at)` — 새 표라 기존 행을 건드리지 않는다.
- 지금 리뷰 3건 이상인 **보이는** 신발을 "아직 만들지 않은" 행(`positive NULL`, `is_stale TRUE`)으로 넣는다 — 운영 예상 212행(공개 API 2026-11-10).
- 조회 `GET /api/shoes/{id}/summary` 는 이 표만 읽는다 — **Sync 뒤 첫 생성 전까지 상세 모달에 요약이 보이지 않는다**(빈 응답, 화면은 숨김). 응답에 `reviewCount` · `generatedAt` 이 더해진다.
- 리뷰 쓰기 · 고치기 · 지우기는 같은 트랜잭션에서 stale 만 판단한다(리뷰 수 ±10% · 평균 ±0.3 · 처음 3건 · 3건 미만이면 행 삭제). 30일 조건은 배치 시작의 전체 재판단이 본다.
- 관리 화면 제목 옆에 요약 건수(읽기 전용, `GET /api/admin/summaries`). 수동 실행 버튼은 없다 — 아래 5절 명령으로 한다.
- 앱 커밋 `________` → 이미지 `________`(infra `________`).

### CronJob `runshoes-summary`(`app/cronjob.yaml`)

| 칸 | 값 | 왜 |
|---|---|---|
| schedule · timeZone | `30 3 * * *` · Asia/Seoul | 04:00 활동 로그 정리와 겹치지 않게 |
| concurrencyPolicy | Forbid | 정기 Job 끼리. **손으로 띄운 Job 은 못 막는다** → 앱이 MySQL `GET_LOCK('runshoes.summary_batch')` 으로 뒤에 온 쪽을 바로 끝낸다(exit 0) |
| suspend | **true** 로 들어간다 | 첫 전체 생성 시각은 사용자가 고른다. 4절 뒤 git 에서 false(클러스터에서 patch 하지 않는다) |
| backoffLimit | 0 | 다시 시도는 stale 플래그가 한다 — 바로 다시 돌면 GPU 를 한 번 더 붙잡을 뿐 |
| activeDeadlineSeconds | 7200 | Ollama 가 매달려도 2시간이면 끝난다. 첫 전체 생성(예상 35분~1시간)도 들어간다 |
| startingDeadlineSeconds | 3600 | 컨트롤러가 놓친 회차는 한 시간 안에만 |
| successful · failedJobsHistoryLimit | 3 · 3 | 로그를 읽을 수 있게 Pod 를 남긴다(Loki 없음) |
| 이미지 · 인자 | 웹과 같은 이미지(태그는 `images` 가 함께) · `--spring.profiles.active=batch` | Jenkins 는 그대로 |
| env | DB(웹과 같은 Secret `runshoes-mysql`) · `OLLAMA_URL=http://192.168.122.1:11434` · `envFrom runshoes-auth` | **배치는 인증을 쓰지 않는다.** 같은 이미지라 신뢰 범위가 같고 JWT 키 빈이 `JWT_SECRET` 없이 뜨지 않아 받는다 — 최소 권한으로 좁힐 때 이 줄이 근거다 |
| resources | 100m / 512Mi, limit 1Gi | 웹 컨테이너와 같은 메모리. 워커 메모리 사용 47~65%(2026-11-10 `kubectl top nodes`) |

**batch 프로필이 끄는 것 — 배치를 더할 때마다 같은 점검을 한다**

| # | 끄는 것 | 어떻게 | 끄지 않으면 |
|---|---|---|---|
| 1 | 웹 서버 | `application-batch.yml` `spring.main.web-application-type: none` | Job 이 포트를 열고 끝나지 않는다 |
| 2 | **Flyway** | `application-batch.yml` `spring.flyway.enabled: false` | Job 이 스키마를 바꿀 수 있다 — 스키마는 웹 Pod 의 Sync 만 바꾼다. `ddl-auto: validate` 는 남아, 스키마가 맞지 않으면 Job 이 바로 실패한다(맞는 동작) |
| 3 | `SeedPasswords`(ApplicationRunner) | `@Profile("!batch")` | 매 회차 시드 계정 비밀번호 칸을 본다 |
| 4 | `ActivityCleanup`(@Scheduled 04:00) | `@Profile("!batch")` | 배치 안에서 활동 로그 정리가 돈다 |
| 5 | 웹 보안 필터 체인(`SecurityConfig.securityFilterChain`) | `@ConditionalOnWebApplication` | **Job 이 뜨지 않는다** — 웹 서버가 없으면 `HttpSecurity` 빈이 없다(2026-11-10 로컬에서 실패 확인). JWT 키 · 인코더 빈은 남는다(그래서 `runshoes-auth` 를 받는다) |

### 로컬 확인(2026-11-10)

- 백엔드 단위 시험(`StaleRuleTest` 6 포함) 통과, 로컬 DB Flyway `14`(20행 · stale 20).
- 배치(jar, batch 프로필, mock Ollama 700ms 지연): 20켤레 · 성공 20 · 동시 요청 최대 1 · Flyway 돌지 않음. 9초 뒤 띄운 두 번째 배치는 GET_LOCK 에서 끝(exit 0).
- 쓰기 시점: 4건 신발에 1건 → stale, 11건 신발에 1건(9.1%) → 그대로, 3건 미만으로 지우면 행 삭제 · 다시 3건이면 "아직 만들지 않음". 리뷰 POST 응답 16~61ms(배치가 Ollama 를 기다리는 중에도 16ms).
- 저장 직후 재비교: 만드는 사이 리뷰를 쓰면 저장 뒤 다시 stale(로그 남음). mock 500 → 실패 1 · stale 그대로 · exit 1. SQL 로 직접 넣은 리뷰 · `generated_at` 31일 전 → 배치 시작 재판단으로 stale 2.
- 계약: v14-summary 20/0(+ 녹화 중 Ollama 호출 0 · 동시 최대 1) · v6 98/0 · v3 101/11(그대로) · v3-search 24 · v4 21. v3-summary 는 V14 전 계약이라 이력.

## 1. 순서 (누가)

| # | 일 | 누가 | 확인 |
|---|---|---|---|
| 1 | 자동 Sync 끄기 | 사람 | `automated` 없음(Claude 확인) |
| 2 | 앱 커밋 push → Jenkins → newTag 커밋, infra 커밋(cronjob · 이 런북) push | Claude(사용자가 push 하라고 할 때) | 운영은 옛 이미지 · CronJob 없음 |
| 3 | Sync 전 확인 — 도는 Job 없음 · 세 워커에서 Ollama · 덤프 | 사람(명령은 2절) · Claude(읽기) | 2절 |
| 4 | Sync = V14 적용 + 새 이미지 + CronJob(suspend) | 사람 | 3절 |
| 5 | 자동 Sync 다시 켜기 | 사람 | `automated` 다시 있음 |
| 6 | 첫 전체 생성 — 사용자가 고른 시각에 손으로 Job | 사람 | 4절 — 약 35분, 넉넉히 1시간. 그동안 챗봇이 느려진다(감수) |
| 7 | `suspend: false` 를 git 에 · push | Claude(사용자가 말할 때) | 5절 — 다음 03:30 회차가 실제로 도는지 |

## 2. Sync 전 확인

**(1) 도는 Job 이 없다** — 스키마를 바꾸는 순간 옛 이미지 Job 이 돌면 깨질 수 있다. V14 는 CronJob 이 처음 들어가는 배포라 지금은 없지만, 앞으로 스키마 Sync 마다 본다.

```bash
mk 'kubectl -n runshoes get jobs,pods -l app.kubernetes.io/name=runshoes-summary'
# → No resources found, 또는 모든 Job 이 Complete/Failed(COMPLETIONS 1/1 · 0/1). Running 이 있으면 끝날 때까지 기다린다
```

**(2) 세 워커 모두에서 Ollama 에 닿는다** — Job Pod 는 어느 워커에나 뜬다. 웹 Pod 가 지금 있는 워커(2026-11-10 w2)만 확인돼 있다.

```bash
for n in w1-k8s w2-k8s w3-k8s; do
  mk "kubectl -n runshoes run ollama-check-\$RANDOM --rm -i --restart=Never --image=docker.io/library/busybox:1.37.0 \
      --overrides='{\"spec\":{\"nodeName\":\"$n\"}}' -- wget -qO- -T 5 http://192.168.122.1:11434/api/version" | sed "s/^/$n /"
done
# → 세 줄 모두 {"version":"…"}. 하나라도 안 닿으면 Sync 하지 않는다(그 워커에 뜬 Job 은 전부 실패한다)
```

**(3) 덤프** — V4 런북(`catalog-v4-v5.md`) 2절과 같은 명령 · 같은 확인, 이름만 `runshoes-before-v14-$TS`. 비밀번호 해시 · 활동 로그가 들어 있다 — `chmod 600`, git 밖.

```bash
mkdir -p $B && chmod 700 $B
TS=$(date -u +%Y%m%dT%H%M%SZ)
mk 'kubectl -n runshoes exec runshoes-mysql-0 -c mysql -- sh -c "exec mysqldump -uroot -p\"\$MYSQL_ROOT_PASSWORD\" --single-transaction --set-gtid-purged=OFF --routines --triggers --default-character-set=utf8mb4 runshoes"' \
  > $B/runshoes-before-v14-$TS.sql 2> $B/runshoes-before-v14-$TS.err
chmod 600 $B/runshoes-before-v14-$TS.*
tail -1 $B/runshoes-before-v14-$TS.sql                        # → -- Dump completed on …
grep -v 'Using a password' $B/runshoes-before-v14-$TS.err       # → 아무것도 없어야
sha256sum $B/runshoes-before-v14-$TS.sql | tee $B/runshoes-before-v14-$TS.sql.sha256
```

복원 확인 — 로컬 `runshoes_restore_check` 에 넣고 리뷰 개수 · 지문을 공개 API 와 대조(V4 런북 2절 (2) · (3) 을 고쳐 쓴 것).

```bash
docker exec -i runshoes-mysql-dev sh -c 'mysql -uroot -p"$MYSQL_ROOT_PASSWORD" -e "DROP DATABASE IF EXISTS runshoes_restore_check; CREATE DATABASE runshoes_restore_check CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci"'
docker exec -i runshoes-mysql-dev sh -c 'mysql -uroot -p"$MYSQL_ROOT_PASSWORD" --default-character-set=utf8mb4 runshoes_restore_check' < $B/runshoes-before-v14-$TS.sql
curl -s -H "$H" $VIP/api/reviews | node -e '
  const r=JSON.parse(require("fs").readFileSync(0)).sort((a,b)=>a.id-b.id);
  console.log(r.length, require("crypto").createHash("sha256").update(r.map(x=>x.id+":"+x.shoeId).join(",")).digest("hex"))'
docker exec -i runshoes-mysql-dev sh -c 'mysql -N -uroot -p"$MYSQL_ROOT_PASSWORD" runshoes_restore_check' <<'SQL'
SET SESSION group_concat_max_len = 1048576;
SELECT COUNT(*), SHA2(GROUP_CONCAT(CONCAT(r.id, ':', r.shoe_id) ORDER BY r.id SEPARATOR ','), 256)
  FROM reviews r JOIN shoes s ON s.id = r.shoe_id AND s.deleted_at IS NULL;
SELECT (SELECT COUNT(*) FROM shoes WHERE deleted_at IS NULL), (SELECT COUNT(*) FROM users),
       (SELECT GROUP_CONCAT(CONCAT(version, ':', success) ORDER BY installed_rank) FROM flyway_schema_history);
SQL
# → 첫 두 줄(API · 복원본)의 개수 · 지문이 같고, 셋째 줄 shoes 310 · users(지금 수) · flyway 1:1 … 13:1
docker exec -i runshoes-mysql-dev sh -c 'mysql -uroot -p"$MYSQL_ROOT_PASSWORD" -e "DROP DATABASE runshoes_restore_check"'
```

- **`SET SESSION group_concat_max_len` 이 꼭 있어야 한다.** MySQL 기본 1,024바이트에서 `GROUP_CONCAT` 이 잘린다 — 리뷰 1,800건은 14,131바이트라 V4 런북 그대로 치면 개수는 같고 지문만 다르다(2026-11-10 실제로 겪음. API 데이터를 1,024바이트에서 자르면 복원본의 틀린 지문과 똑같았다). V4 때는 104건(약 700바이트)이라 걸리지 않았다.
- 복원본은 숨긴 신발의 리뷰를 빼고 센다 — 공개 API 가 V8 부터 숨긴 신발의 리뷰를 내주지 않는다.

## 3. Sync 뒤 확인(Claude — 읽기)

- 새 Pod 로그 `Migrating … "14 - shoe summaries"` → `Successfully applied 1 migration … v14`, 2/2 Running, Synced/Healthy, 공개 200.
- `kubectl -n runshoes get cronjob runshoes-summary` — `SUSPEND True` · `SCHEDULE 30 3 * * *` · 이미지 태그가 웹과 같다.
- 공개 API: `/api/shoes` 310 · `/api/reviews` 1,800(그 사이 쓰인 것 빼고 그대로), `/api/shoes/<리뷰 3건 이상 id>/summary` → `{"summary":null,"reason":"요약을 아직 만들지 않았습니다"}` — **이제 상세 모달 · 요약 조회가 GPU 를 쓰지 않는다**.
- `docker logs ollama` 에 그 사이 `/api/generate` 가 늘지 않았다(웹 Pod 는 더 부르지 않는다. 챗봇은 따로 부른다).
- 관리 화면 제목 옆 "리뷰 요약 0켤레 · 다시 만들 것 212 (아직 없음 212)" 쯤.

## 4. 첫 전체 생성(사람 — 고른 시각에)

**Job 이름 규칙**: `summary-manual-<KST YYYYMMDD-HHMM>` — 정기 Job(`runshoes-summary-<숫자>`)과 이름으로 갈린다. 같은 분에 두 번 띄우지 않는다(이름이 겹치면 kubectl 이 거절한다).

```bash
NAME=summary-manual-$(TZ=Asia/Seoul date +%Y%m%d-%H%M)
mk "kubectl -n runshoes create job --from=cronjob/runshoes-summary $NAME"
mk "kubectl -n runshoes logs -f job/$NAME" | grep --line-buffered -E 'summary-batch|ERROR'
# → 시작 — 만들 신발 212켤레: 쓰기 시점에 이미 서 있던 stale 212 · 재판단으로 새로 선 stale 0 …
#   진행 10/212 · 20/212 … (10켤레마다 — 아무 줄 없이 몇 분이 지나면 멈춘 것을 의심)
#   끝 — 대상 212 · 성공 212 · 실패 0 · … · N분 M초
mk "kubectl -n runshoes get job $NAME"          # → COMPLETIONS 1/1(실패가 있으면 0/1 · Failed — 남은 것은 stale 로 다음 회차가)
```

도는 동안 볼 것(함께 본다):

- 진행 줄이 10켤레마다 찍힌다 — 한 켤레 약 9.8초(최근 30일 Ollama `/api/generate` 중앙값)면 약 100초마다 한 줄, 전체 약 35분. 첫 켤레는 모델을 올리느라 1분쯤 더 걸릴 수 있다
- 진행 줄의 `실패 N` — 0 이 아니면 그 줄 위 `shoeId=… 실패` 의 이유(연결 · 시간 초과 40초 · 500)
- 한 켤레 시간 — 진행 줄의 초 ÷ 켤레 수. 15초를 넘게 이어지면 GPU 를 다른 일(펫퍼민트 학습 · 챗봇)이 쓰고 있다

- suspend 인 CronJob 에서도 `--from` 은 된다(suspend 는 정기 실행만 멈춘다).
- 실패가 있으면 같은 명령으로 다시 띄워도 된다 — stale 인 것만 다시 한다.

끝난 뒤 확인(Claude — 읽기):

- 관리 화면 "리뷰 요약 212켤레 · 다시 만들 것 0"(그 사이 쓰인 리뷰로 stale 이 섰으면 그만큼)
- 공개 API 로 요약이 212켤레 — 조회는 이제 DB 만 읽어 GPU 를 쓰지 않는다:
  ```bash
  # 공개 주소로(Node fetch 는 Host 헤더를 바꿀 수 없어 VIP 로는 못 부른다)
  curl -s https://runshoes.ronanlab.dev/api/shoes | node -e '
    const ids = JSON.parse(require("fs").readFileSync(0)).map((s) => s.id);
    (async () => {
      let n = 0; const blob = [];
      for (const id of ids) {
        const j = await (await fetch("https://runshoes.ronanlab.dev/api/shoes/" + id + "/summary")).json();
        if (j.summary) { n++; if (/^\s*[{\[]|"positive"\s*:/.test(j.summary.positive)) blob.push(id); }
      }
      console.log("요약", n, "· positive 에 JSON 덩어리", blob.length, blob.join(","));
    })()'
  # → 요약 212 · JSON 덩어리 0
  ```
- **positive 에 JSON 덩어리가 통째로 든 행** — 모델 응답에서 JSON 을 못 읽었거나 `positive` 키가 없어 응답 전문을 담은 것(파싱 실패, 2026-11-10 사용자). 몇 건이면 그 신발만 6절로 다시, 많으면 프롬프트를 본다(프롬프트를 바꾸는 것은 따로 정한다)
- `docker logs ollama` 의 `/api/generate` 가 그 시간대에 212번(실패 · 다시 한 것만큼 더)
- 상세 모달 몇 켤레에 요약과 "리뷰 N건 기준"

## 5. suspend 를 끈다(git)

```bash
# infra 리포 — app/cronjob.yaml 의 suspend: true → false, 커밋 · push(자동 Sync 가 3분 안에 적용)
```

확인: `kubectl -n runshoes get cronjob runshoes-summary` 의 `SUSPEND False`, **다음 03:30(KST) 뒤** `kubectl -n runshoes get jobs` 에 `runshoes-summary-<숫자>` 가 Complete 이고 로그 끝 줄이 `끝 — 대상 N …`(리뷰가 거의 안 쓰였으면 대상 0 이 정상).

## 6. 운영 작업 — 화면 버튼 대신

```bash
# 특정 신발만 다시 — stale 을 세우고 다음 회차(또는 4절의 수동 Job)를 기다린다
mk 'kubectl -n runshoes exec runshoes-mysql-0 -c mysql -- sh -c "mysql -uroot -p\"\$MYSQL_ROOT_PASSWORD\" runshoes -e \"UPDATE shoe_summaries SET is_stale = TRUE WHERE shoe_id = <id>\""'
# 프롬프트를 바꾼 뒤 전량 — WHERE 없이. 그 뒤 4절 수동 Job
```

## 7. 실패했을 때

- 마이그레이션 실패 → 새 Pod 가 뜨지 않는다(옛 Pod 유지). 자동 Sync 꺼진 채로 원인 확인. 새 표라 기존 데이터는 그대로 — 덤프 복원은 대개 필요 없다.
- Job 이 `CreateContainerConfigError` → Secret(`runshoes-auth` · `runshoes-mysql` · `harbor-pull`) 이름을 본다.
- Job 이 바로 실패하고 로그에 `Schema-validation` → 이미지와 스키마가 다르다(웹 Pod 의 Sync 가 먼저여야 한다).
- 실패가 많고 Ollama 연결 오류 → 2절 (2) 를 그 워커에서 다시. 남은 것은 stale 이라 고친 뒤 4절로 다시.
- 되돌리기 — 옛 이미지로 롤백하면 옛 앱은 `shoe_summaries` 를 모른 채 조회 때 Ollama 를 다시 부른다(표는 남는다, 해가 없다). CronJob 은 `suspend: true` 로.

## 8. 실행 기록 (UTC)

| 단계 | 시각 | 내용 |
|---|---|---|
| 1 자동 Sync 끔 | | |
| 2 push | | |
| 3 확인 · 덤프 | | |
| 4 Sync | | |
| 5 자동 Sync 켬 | | |
| 6 첫 전체 생성 | | |
| 7 suspend false | | |
