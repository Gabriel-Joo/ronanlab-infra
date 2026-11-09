# runshoes — 리뷰 1,500건 · 찜 · 도움이 돼요 다시 만들기(2026-11-09)

앱 리포 작업 폴더(git 밖, 데이터 · 생성 스크립트): `catalog/local/work/reviews-20261109/` — `DESIGN.md`(설계 · 사용자 결정) · `plan.py` · `rate.py` · `engage.py` · `make_sql.py` · `check.py` · `out-*.jsonl`(글) · `apply.sql` · `verify.sql` · `dump.sh` · `apply.sh`

설계 `DESIGN.md`, SQL 은 `make_sql.py` 가 만든 `apply.sql`(한 트랜잭션) · `verify.sql`(읽기만). 스키마는 바꾸지 않는다 — 이미지 · Sync 와 상관없다.
운영 MySQL `exec` 는 **사람이 친다**(V3 이후 런북과 같은 규칙). Claude Code 프롬프트에서 줄 앞에 `!` 를 붙이면 출력이 대화에 남는다.

```bash
B=~/k8s-cluster/backup/2026-11-09-runshoes-reviews     # 덤프를 두는 곳 — 비밀번호 해시 · 활동 로그가 들어 있어 git 밖, 권한 700/600
W=~/AI_programming/runshoes/catalog/local/work/reviews-20261109
mk() { ~/k8s-cluster/backup/2026-10-15-before-metallb/mk "$@"; }
```

## 0. 지우고 남기는 것
- **지운다**: `reviews` 104 · `likes` · `review_likes` 전부 — 관리자 · 데모 관리자의 찜 · 도움이 돼요도(11-09 사용자, 계정은 남긴다)
- **남긴다**: 관리자 · 데모 관리자 · 시드 30명 계정(시드 30명은 가입일만 첫 리뷰 앞으로), 사용자 테스트 계정 id 32 · 33(11-09 사용자 확인 — 계정은 남고 찜 1개만 지워진다), 신발 · 활동 로그
- **넣는다**: 새 계정 170(`reviewer001~170@runshoes.test`, 비밀번호 칸 `!seed-reviewer` — 로그인 불가 · 체험 카드에 안 나옴), 리뷰 1,500 · 찜 1,734 · 도움이 돼요 3,257, 신발 `rating` · `review_count` · `like_count` 와 리뷰 `like_count` 다시 세기
- 가드 12개 — 하나라도 틀리면 그 문장에서 오류로 멈추고 롤백된다(쓰기 전: 신발 246켤레 id · line_key · generation, 시드 30, 시드 밖 USER 는 허용 목록뿐, 새 이메일 · 닉네임 없음 / 쓴 뒤: 행 수 · 관리자의 찜 · 도움이 돼요 0 · 작성자 = 닉네임 · 가입일 < 첫 리뷰 · 리뷰 수 합)

## 1. 순서

| # | 할 일 | 누가 | 확인 |
|---|---|---|---|
| 1 | 덤프(2절) | **사람** | 덤프 끝 줄 · 오류 없음 · sha256 |
| 2 | 덤프를 로컬 MySQL 에 다른 이름(`rehprod`)으로 복원 → `apply.sql` → `verify.sql` | Claude | 가드 12 통과 · 3절 숫자 |
| 3 | 운영 적용(4절) | **사람** | `적용 끝` |
| 4 | 확인(5절) | 사람(verify) · Claude(API · 화면) | 3절 숫자 · 체험 카드 31 |

- 1 → 3 사이에 들어온 쓰기(리뷰 · 찜 · 가입)는 가드가 잡는다(시드 밖 USER · 행 수) — 멈추면 1부터 다시
- AI 리뷰 요약은 앱 메모리 캐시(리뷰 수가 바뀌면 다시 만든다) — 재시작할 필요 없다. 첫 상세 열기마다 Ollama 를 한 번씩 부른다

## 2. 덤프 — 사람이 친다

```bash
B=~/k8s-cluster/backup/2026-11-09-runshoes-reviews; mkdir -p $B && chmod 700 $B
mk() { ~/k8s-cluster/backup/2026-10-15-before-metallb/mk "$@"; }
TS=$(date -u +%Y%m%dT%H%M%SZ)
mk 'kubectl -n runshoes exec runshoes-mysql-0 -c mysql -- sh -c "exec mysqldump -uroot -p\"\$MYSQL_ROOT_PASSWORD\" --single-transaction --set-gtid-purged=OFF --routines --triggers --default-character-set=utf8mb4 runshoes"' \
  > $B/runshoes-before-reviews-$TS.sql 2> $B/runshoes-before-reviews-$TS.err
chmod 600 $B/runshoes-before-reviews-$TS.*
tail -1 $B/runshoes-before-reviews-$TS.sql; grep -v 'Using a password' $B/runshoes-before-reviews-$TS.err; sha256sum $B/runshoes-before-reviews-$TS.sql | tee $B/runshoes-before-reviews-$TS.sql.sha256
```
→ `-- Dump completed on …`, 오류 줄 없음.

## 3. 리허설 기대값(11-03 운영 덤프 복원본에서 확인, 2026-11-09)
- 11-03 덤프 그대로: 가드 1(신발)에서 멈춤 · 롤백(리뷰 104 · 계정 34 그대로) — 그 덤프에 11-05 뒤 신발이 없어서. 리허설용으로 빠진 신발 행을 채운 뒤: 가드 11 통과 · 0.35초
- 리뷰 1,500(08-09 21:11Z ~ 11-08 14:48Z, 평균 3.96) · 별점 581 · 516 · 229 · 107 · 67 · USER 202(시드 30 + 새 170 + 테스트 2) · ADMIN 1 · DEMO_ADMIN 1 · 찜 1,734 · 도움이 돼요 3,257
- 리뷰 많은 순: 노바블라스트 6(38, 4.4) · 페가수스 42(34, 3.9) · 젤 카야노 33(31, 4.3) · 젤 님버스 28(29) · 젤 큐뮬러스 28(27, 3.7) …

## 4. 운영 적용 — 사람이 친다(2 가 끝난 뒤)

```bash
W=~/AI_programming/runshoes/catalog/local/work/reviews-20261109
mk() { ~/k8s-cluster/backup/2026-10-15-before-metallb/mk "$@"; }
sha256sum $W/apply.sql      # → 리허설 때 Claude 가 적은 값과 같아야 한다(DESIGN.md 10절 마지막 sha256)
mk 'kubectl -n runshoes exec -i runshoes-mysql-0 -c mysql -- sh -c "exec mysql -uroot -p\"\$MYSQL_ROOT_PASSWORD\" --default-character-set=utf8mb4 runshoes"' < $W/apply.sql 2>&1 | grep -v 'Using a password' | tail -3
```
→ 마지막 줄 `적용 끝`. `ERROR 1242 … guard` 가 나오면 바로 위 줄이 걸린 가드다 — 롤백됐으니 운영은 그대로, Claude 에게 출력을 보인다.

## 5. 확인

```bash
mk 'kubectl -n runshoes exec -i runshoes-mysql-0 -c mysql -- sh -c "exec mysql -uroot -p\"\$MYSQL_ROOT_PASSWORD\" --default-character-set=utf8mb4 -t runshoes"' < $W/verify.sql 2>&1 | grep -v 'Using a password'
```
- 3절 숫자와 같다
- Claude(공개 API): `/api/reviews` 1,500 · `/api/auth/demo-accounts` 31(시드 30 + 데모 관리자 — 새 170 은 안 나온다) · 신발 리뷰 수 · 평점
- 화면: 상세 모달 맨 위 리뷰(S 15켤레는 `top-candidates.json` 의 글) · AI 요약이 뜨는지 · 체험 카드 리뷰 수

## 6. 되돌리기
2절 덤프를 그대로 넣는다(덤프 뒤의 쓰기는 사라진다 — 바로 확인해서 문제가 있을 때만):
```bash
mk 'kubectl -n runshoes exec -i runshoes-mysql-0 -c mysql -- sh -c "exec mysql -uroot -p\"\$MYSQL_ROOT_PASSWORD\" --default-character-set=utf8mb4 runshoes"' < $B/runshoes-before-reviews-<TS>.sql
```

## 7. 실행 기록 (UTC)

| 단계 | 시각 | 내용 |
|---|---|---|
| 0 리허설(옛 덤프) | 11-09 | 11-03 덤프 `2026-11-03-runshoes-v13/…T000006Z.sql` 를 로컬 `reh1103` 에 복원 — 그대로는 가드 1(신발 id)에서 멈추고 롤백(리뷰 104 · 계정 34 그대로). 빠진 신발 행을 채운 뒤 가드 통과 0.35초. 시드 밖 USER 2(id 32 · 33)를 찾아 사용자 확인 → 허용 목록 |
| 1 덤프 | 11-09 04:18:22 | 사용자(`dump.sh`, 다른 터미널 — 프롬프트 `!` 줄 앞에 공백이 붙어 세 번 실행되지 않았다). `$B/runshoes-before-reviews-20261109T041822Z.sql` 1,590,141 B · 600 · `Dump completed` · err 비밀번호 경고뿐 · sha256 확인 |
| 2 리허설(새 덤프) | 11-09 04:19 | Claude — 로컬 `rehprod` 복원: 출발 신발 310 · 리뷰 104 · 찜 10(관리자 2) · 도움이 돼요 6 · USER 32 · ADMIN 1 · DEMO_ADMIN 1. `apply.sql` sha256 `e92b86ab95f1bd41…` → 가드 12 통과 · `적용 끝` · 3절과 같은 숫자 · S 맨 위 후보 15/15 · 관리자 찜 0 |
| 3 적용 | 11-09 04:2x | 사용자(`apply.sh` — sha256 확인 뒤 한 트랜잭션). `적용 끝`. verify: 리뷰 1,500(08-09 21:11Z ~ 11-08 14:48Z, 평균 3.96) · 별점 581 · 516 · 229 · 107 · 67 · USER 202(시드 30 · 새 170 · 테스트 2) · ADMIN 1 · DEMO_ADMIN 1 · 찜 1,734 · 도움이 돼요 3,256 · 리뷰 많은 순 노바블라스트 6(38, 4.4) · 페가수스 42(34, 3.9) · 젤 카야노 33(31, 4.3) |
| 4 확인 | 11-09 04:21 | Claude(공개 API): `/api/reviews` 1,500 · 작성자 200 · 최대 id 1500, 체험 카드 31(USER 30 · DEMO_ADMIN 1, 리뷰 4~28건, 새 170 은 안 나옴), 신발 리뷰 수 합 1,500 · 찜 합 1,734, S 15켤레 맨 위(도움이 돼요 최다)가 `top-candidates.json` 과 15/15. AI 요약 노바블라스트 6: 첫 호출 16.2초(Ollama, 리뷰 38) · 다음 0.29초(캐시) |

## 8. 2차 — 리뷰 없던 지난 세대 73켤레에 300건(2026-11-09)

넣기만 한다(기존 리뷰 · 찜 · 도움이 돼요는 그대로). 스크립트 `plan2.py` · `rate2.py` · `engage2.py` · `make_sql2.py` → `apply2.sql`(한 트랜잭션, 리뷰 id 는 DB 가 매김) · `verify2.sql` · `apply2.sh`(sha256 고정).
- 배분: 인기 8켤레 86 · 보통 34켤레 153 · 마이너 31켤레 61. 같은 라인 사용자 21%(그 라인 새 세대 리뷰어 + 기존 글에서 이 세대를 언급한 6명 + 73켤레 안의 짝 벨로시티 니트로 3 → 4), 같은 사람 · 같은 라인은 옛 세대 리뷰가 날짜상 먼저
- 사용자 결정: 옛 세대를 낮게 두지 않는다(알파플라이 3 μ 4.5 · 페레그린 15 4.3 > 16), 웨이브 레벨리온 프로 2 는 3세대 설명문과 맞춰 3.4, "언제 샀다" 쓰지 않음
- 가드(쓰기 전): 73켤레 id · line_key · generation, 73켤레에 리뷰 0, 계정 있음 · 탈퇴 아님 / (쓴 뒤): 리뷰 +300, 찜 +356, 도움이 돼요 +637, 관리자 찜 · 도움이 돼요 0, 작성자 = 닉네임, 가입일 < 첫 리뷰, 리뷰 수 합

| 단계 | 시각(UTC) | 내용 |
|---|---|---|
| 리허설(옛 덤프) | 11-09 | 04:18 덤프 → `apply.sql` → `apply2.sql`(로컬 `reh2`): 통과, 기존 리뷰 1,500 · 찜 1,734 · 도움이 돼요 3,256 한 건도 안 바뀜. 알파플라이 3 이 4.4 로 4(4.5, 리뷰 2)보다 낮게 보여 불만 없는 ★4 두 칸을 ★5 로 → 4.5 |
| 덤프 | 11-09 05:34:01 | 사용자(`dump.sh`, 다른 터미널). `runshoes-before-reviews-20261109T053401Z.sql` 2,133,179 B · 600 · `Dump completed` · sha256 확인 |
| 리허설(새 덤프) | 11-09 05:35 | Claude — 로컬 `rehprod2`: 출발 리뷰 1,500(최대 id 1500) · 찜 1,734 · 도움이 돼요 3,256 · 계정 204 · 리뷰 없는 신발 73(1차 뒤 방문자 쓰기 없음). `apply2.sql` sha256 `767dbf83f06debb1…` → 가드 통과 · `적용 끝` |
| 적용 | 11-09 05:3x | 사용자(`apply2.sh`). `적용 끝`. 리뷰 1,800(평균 3.96) · 별점 689 · 622 · 288 · 125 · 76 · 리뷰 있는 신발 310 · 찜 2,090 · 도움이 돼요 3,893 |
| 확인 | 11-09 05:4x | Claude(공개 API): 리뷰 1,800 · 최대 id 1800 · id ≤ 1500 은 1,500 그대로 · 리뷰 0 인 신발 0 · 리뷰 수 합 1,800 · 찜 합 2,090 · 체험 카드 31(시드 리뷰 6~30). 알파플라이 3 · 4 4.5 · 웨이브 레벨리온 프로 2 3.3 < 3 4.0 · 페레그린 15 4.3 > 16 3.3 |
