# runshoes — V15 · V16 무게를 270mm(M9)로 맞춘 값(weight_norm_270) · 무게 용어 설명

> 2026-11-10 — 사용자 결정(앱 리포 `docs/09_chatbot_rag.md` 4절 · 환산 규칙 `docs/01a_catalog_sources.md` 1-3a). **이미지 Sync 가 곧 V15 · V16 적용**이다(한 이미지 · 한 Sync — 자동 Sync 를 끄고 켜는 일은 한 번).
> 운영 DB · 클러스터 쓰기는 **사람이 친다**. Claude 는 명령과 순서를 주고, 읽기(공개 API · `kubectl get` · 로그)로 확인만 한다.

```bash
B=~/k8s-cluster/backup/2026-11-10-runshoes-v15   # 덤프 — 데이터가 들어 있어 git 밖
VIP=http://192.168.122.240; H='Host: runshoes.ronanlab.dev'
mk() { ~/k8s-cluster/backup/2026-10-15-before-metallb/mk "$@"; }
```

## V15

- `shoes.weight_norm_270 DOUBLE GENERATED ALWAYS AS (CASE official_weight_size WHEN 'M8.5' THEN ×1.026 WHEN 'M9' THEN 그대로 WHEN 'M9.5' THEN ÷1.026 WHEN 'M10' THEN ÷1.026² WHEN 'M10.5' THEN ÷1.026³ END) VIRTUAL` — 맨 뒤에 더한다.
- **VIRTUAL 이라 행을 다시 쓰지 않는다** — 값은 읽을 때 계산한다. 데이터는 바뀌지 않지만 Sync 가 곧 DDL 이라 절차는 V14 와 같다(06 1-7).
- 기준 사이즈가 없거나 다섯 값 밖이면 NULL. 실측 무게(`measured_weight_g`)는 쓰지 않는다.
- API 응답 끝에 `weightNorm270` 키가 더해진다. 비교하기의 등수 · 그래프 · 비슷한 신발이 이 값을 쓴다(화면은 같은 이미지에 들어 있다).

## V16

- 무게 용어(`terms.term_key = 'weight'`) 설명을 환산 규칙(반 사이즈당 약 2.6%)에 맞춘다 — 옛 "10mm 커질 때마다 5~10g" · "220g 이하 가벼운 편"을 바꾼다. name · short 는 그대로.
- **첫 구문이 가드** — 무게 설명이 시드(V2) 원문 그대로인 행이 정확히 하나일 때만 진행. 누가 먼저 고쳤으면 `ERROR 1242` 로 멈추고 아무것도 바꾸지 않는다(그러면 새 Pod 가 뜨지 않는다 — 4절).
- id 12 가 둘(weight · outsole)이라 id 가 아니라 `term_key` 로 고친다. 중복은 고치지 않는다.

- 앱 커밋 `1ba998b` · `83213c2` · `40586d6` → 이미지 `40586d6eb722`(infra `4ebbb11`).

### 로컬 확인(2026-11-10)

- 백엔드 단위 시험 통과(`ChangedFieldsTest` — weightNorm270 은 수정 이력에 넣지 않는다), 프런트 `npm test` 11건.
- 계약: v6 에 X136 ~ X146(기준 M10.5 · 무게 300 · M8.5 · 실측 PATCH 는 그대로 · 본문의 weightNorm270 은 버림 · W7.5 → null · M10 · 기준 지우기 → null · 새 신발 POST M9.5 · PUT M9 · 끝 상태). 저장 직후 응답에 새 값이 나오고 값이 계수와 같다(297 ÷ 1.026³ = 274.988…, 300 × 1.026 = 307.8 …). 결과 수는 앱 리포 `contract/README.md`.
- 화면: 운영 공개 API 에 같은 식으로 값을 붙여 1440 · 390px 캡처(281켤레가 그래프에 들어간다).
- V16: 새 시드 DB 에서 가드 통과 · 설명 바뀜(계약 v3 R03 의 다른 칸은 weight description 하나 — v3 100/12), 이미 고친 DB 에 가드를 다시 치면 `ERROR 1242`.

## 1. 순서 (누가)

| # | 일 | 누가 | 확인 |
|---|---|---|---|
| 1 | 자동 Sync 끄기 | 사람 | `automated` 없음(Claude 확인) — **push 전에** |
| 2 | 앱 커밋 push → Jenkins → newTag 커밋, infra 커밋(이 런북) push | Claude(사용자가 push 하라고 할 때) | 운영은 옛 이미지 |
| 3 | Sync 전 확인 — 도는 Job 없음 · 덤프 | 사람(명령은 2절) · Claude(읽기) | 2절 |
| 4 | Sync = V15 · V16 적용 + 새 이미지(웹 · CronJob 같은 태그) | 사람 | 3절 |
| 5 | 자동 Sync 다시 켜기 | 사람 | `automated` 다시 있음 |

- **03:30 KST(요약 CronJob) 근처를 피한다.** 그 시각에 Sync 하면 옛 이미지 Job 이 도는 중에 스키마가 바뀐다 — 2절 (1).

## 2. Sync 전 확인

**(1) 도는 Job 이 없다**

```bash
mk 'kubectl -n runshoes get jobs,pods -l app.kubernetes.io/name=runshoes-summary'
# → 모든 Job 이 Complete/Failed. Running 이 있으면 끝날 때까지 기다린다
```

**(2) 덤프** — V14 런북 2절 (3) 과 같은 명령, 이름만 `runshoes-before-v15-$TS`. 비밀번호 해시 · 활동 로그가 들어 있다 — `chmod 600`, git 밖.

```bash
mkdir -p $B && chmod 700 $B
TS=$(date -u +%Y%m%dT%H%M%SZ)
mk 'kubectl -n runshoes exec runshoes-mysql-0 -c mysql -- sh -c "exec mysqldump -uroot -p\"\$MYSQL_ROOT_PASSWORD\" --single-transaction --set-gtid-purged=OFF --routines --triggers --default-character-set=utf8mb4 runshoes"' \
  > $B/runshoes-before-v15-$TS.sql 2> $B/runshoes-before-v15-$TS.err
chmod 600 $B/runshoes-before-v15-$TS.*
tail -1 $B/runshoes-before-v15-$TS.sql                        # → -- Dump completed on …
grep -v 'Using a password' $B/runshoes-before-v15-$TS.err       # → 아무것도 없어야
sha256sum $B/runshoes-before-v15-$TS.sql | tee $B/runshoes-before-v15-$TS.sql.sha256
```

복원 확인 — **V14 런북 판 그대로**(`group_concat_max_len` 이 들어간 것). 빠뜨리면 지문이 1,024바이트에서 잘려 개수는 같고 지문만 다르다.

```bash
docker exec -i runshoes-mysql-dev sh -c 'mysql -uroot -p"$MYSQL_ROOT_PASSWORD" -e "DROP DATABASE IF EXISTS runshoes_restore_check; CREATE DATABASE runshoes_restore_check CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci"'
docker exec -i runshoes-mysql-dev sh -c 'mysql -uroot -p"$MYSQL_ROOT_PASSWORD" --default-character-set=utf8mb4 runshoes_restore_check' < $B/runshoes-before-v15-$TS.sql
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
# → 첫 두 줄(API · 복원본)의 개수 · 지문이 같고, 셋째 줄 shoes 310 · users(지금 수) · flyway 1:1 … 14:1
docker exec -i runshoes-mysql-dev sh -c 'mysql -uroot -p"$MYSQL_ROOT_PASSWORD" -e "DROP DATABASE runshoes_restore_check"'
```

- 로컬 `runshoes-mysql-dev` 는 앱 리포 원본 폴더의 compose 컨테이너다. 꺼져 있으면 원본 폴더에서 `docker compose up -d`.

## 3. Sync 뒤 확인(Claude — 읽기)

- 새 Pod 로그 `Migrating … "15 - weight norm 270"` · `Migrating … "16 - weight term"`(그 사이 `v16 guard ok`) → `Successfully applied 2 migrations … v16`, 2/2 Running, Synced/Healthy, 공개 200.
- 공개 API `/api/terms` 의 weight 설명이 "…약 2.6% 정도 무거워집니다. … 통상적으로 240g 이하면 가벼운 편이고, 300g 이상이면 무거운 편입니다."이고 용어 13개 그대로(id 12 둘):

```bash
curl -s -H "$H" $VIP/api/terms | node -e 'const t=JSON.parse(require("fs").readFileSync(0));console.log(t.length, t.find(x=>x.key==="weight").description)'
```
- `kubectl -n runshoes get cronjob runshoes-summary -o jsonpath='{..image}'` — 웹과 같은 태그(배치도 새 엔티티로 `validate` 를 통과해야 한다 — 다음 03:30 회차가 Complete 인지도 본다).
- 공개 API — 환산값 수 · 계수:

```bash
curl -s -H "$H" $VIP/api/shoes | node -e '
  const a=JSON.parse(require("fs").readFileSync(0));
  const F={"M8.5":1.026,M9:1,"M9.5":1/1.026,M10:1/1.026**2,"M10.5":1/1.026**3};
  const bad=a.filter(s=>{const e=s.weight!=null&&F[s.weightSize]?s.weight*F[s.weightSize]:null;return e==null?s.weightNorm270!=null:Math.abs(e-s.weightNorm270)>1e-6});
  const sizes={};for(const s of a)sizes[s.weightSize??"null"]=(sizes[s.weightSize??"null"]||0)+1;
  console.log("신발",a.length,"· 환산값",a.filter(s=>s.weightNorm270!=null).length,"· null",a.filter(s=>s.weightNorm270==null).length,"· 식과 다름",bad.length,JSON.stringify(sizes))'
# → 신발 310 · 환산값 281 · null 29 · 식과 다름 0 · {"M9":211,"M9.5":16,"null":29,"M10":37,"M10.5":9,"M8.5":8}(2026-11-10 기준)
```

- null 이 29 와 다르면 기준 사이즈에 다섯 값 밖의 글자가 들어간 것 — 사람에게 알린다(숨긴 신발은 API 에 없어 세지 않는다).
- 화면: `/compare?ids=210,1,53,10,227` — 클라우드붐 에코 3 "265mm 기준 · 270mm로 약 221g" + 위치 · "환산" 배지, 엔돌핀 스피드 4 "기준 모름"(배지 없음), 무게 줄 아래 "기준 사이즈가 다른 신발이 있어서 환산값을 적용했어요", 그래프 "270mm로 맞춘 무게가 있는 신발 281켤레".

## 4. 실패했을 때

- 마이그레이션 실패 → 새 Pod 가 뜨지 않는다(옛 Pod 유지). 자동 Sync 꺼진 채로 원인 확인.
  - V15 실패: 생성 컬럼 추가뿐이라 기존 데이터는 그대로 — 덤프 복원은 대개 필요 없다.
  - V16 첫 가드(`ERROR 1242`, `v16 guard: weight term differs from seed`): 운영 무게 설명이 시드와 다르다. V15 는 적용됐고 V16 은 아무것도 바꾸지 않았다(UPDATE 전). 바뀐 것은 `flyway_schema_history` 의 실패 행(version 16, success 0) 하나 — V3 런북 5.1 과 같다. 지금 설명을 사람이 읽어 알리고, V16 을 어떻게 할지 정한 뒤 실패 행만 지우고(`flyway repair` 와 같다) 고친 이미지로 다시. 그동안 웹은 옛 Pod 로 돈다.
- 되돌리기 — infra 태그 커밋 `git revert` → push → Sync. 옛 이미지는 `weight_norm_270` 을 모르지만 `validate` 는 엔티티에 있는 칸만 보므로 뜬다(컬럼은 남는다, 해가 없다). 화면은 옛 동작(M9 끼리만)으로 돌아간다. 무게 용어 설명은 V16 그대로 남는다(되돌리려면 옛 설명으로 UPDATE — 사람이).
- 배치 Job 이 `Schema-validation` 으로 실패 → 이미지와 스키마가 다르다(웹 Pod 의 Sync 가 먼저여야 한다).

## 5. 실행 기록 (UTC)

| 단계 | 시각 | 내용 |
|---|---|---|
| 1 자동 Sync 끔 | 11-10 06:45 전 | 사용자. `{"syncOptions":["CreateNamespace=false"]}` — `automated` 없음(Claude 확인, push 직전). 운영 `1a4304e5baae` Synced/Healthy |
| 2 push | 11-10 06:45:01 | 앱 `e3b9e8a..40586d6`(worktree 브랜치를 fast-forward — `0c40cf9` · `1ba998b` · `83213c2` · `40586d6`) · infra `f0fd28b..5908d50` → Jenkins infra `4ebbb11`(06:49:17) 이미지 `40586d6eb722`. ArgoCD OutOfSync(보기만) · 운영 옛 이미지 그대로 |
| 3 확인 · 덤프 | 11-10 07:02:00 | 사용자. (1) 도는 Job 없음(`summary-manual-20261110-1353` Complete 뿐) (2) `$B/runshoes-before-v15-20261110T070200Z.sql` 2,356,761 B · `Dump completed on 2026-11-10  7:02:00` · err 비어 있음 · sha256 `7dbce284a4a7dbcc…`. 복원본: reviews 1,800 · 지문 `5b90995f…`(운영 API 와 같음, `group_concat_max_len` 판) · shoes 310 · users 204 · flyway 1~14 |
| 4 Sync | 11-10 07:04:43 | 사용자. 새 Pod `runshoes-7687cc5dcb-pcmw9`(w2) `Migrating … "15 - weight norm 270"` → `"16 - weight term"`(`v16 guard ok`) → `Successfully applied 2 migrations … v16`(**54ms**), 7.3초에 기동, ERROR · WARN 없음. Synced/Healthy/Succeeded(rev `4ebbb11`), 웹 · 챗봇 · CronJob 이미지 `40586d6eb722`(CronJob suspend false 그대로). 공개 API: 신발 310 · 환산값 281 · null 29 · 식과 다름 0 · 기준 사이즈 분포 그대로 · id 210 215g M8.5 → 220.59 · terms 13(id 12 둘) weight 설명 새 문구 · reviews 1,800. `/compare?ids=210,1,53,10,227` 1440px 캡처 — 환산 배지 · 아래 문구 · 그래프 281켤레 · 가로 넘침 없음 |
| 5 자동 Sync 켬 | 11-10 07:2x | 사용자. `{"automated":{},…}` · Synced/Healthy(Claude 확인 07:21) |
