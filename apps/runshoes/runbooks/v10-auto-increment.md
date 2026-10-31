# runshoes — V10 id 를 DB 가 매긴다(AUTO_INCREMENT) · 찜 · 도움이 돼요 데드락

앱 리포: 마이그레이션 `backend/src/main/resources/db/migration/V10__auto_increment_ids.sql`, 계약 `docs/API_CONTRACT.md` 1.1, 계약 차이 `contract/README.md`.
절차는 V6~V9(`admin-demo-v6-v9.md`)와 같다 — **이미지 Sync 가 곧 V10 적용**(새 Pod 가 뜰 때 Flyway). 적재할 것은 없다.
명령은 호스트에서 `mk`(= `~/k8s-cluster/backup/2026-10-15-before-metallb/mk`)로 kubectl 을 부른다.

```bash
B=~/k8s-cluster/backup/2026-11-01-runshoes-v10   # 덤프 — 데이터가 들어 있어 git 밖
mkdir -p $B && chmod 700 $B
VIP=http://192.168.122.240; H='Host: runshoes.ronanlab.dev'
mk() { ~/k8s-cluster/backup/2026-10-15-before-metallb/mk "$@"; }
```

## 왜 (2026-10-31 트랜잭션 점검, 사용자)

- **데드락**: 찜 · "도움이 돼요"를 두 사람이 같은 대상에 동시에 누르면 한 사람이 500. 행 INSERT 의 FK 검사가 부모(신발 · 리뷰) 행에 공유 잠금 → 카운터 UPDATE 가 배타 잠금을 원해 서로 기다린다.
  로컬에서 10명 × 30번 동시: **옛 코드 PUT 600건 중 375건 500 · 로그 `Deadlock found` 750줄 → 새 코드 0건**, 수는 정확히 +10 · 되돌리면 원래대로.
  고침: 켜고 끄기 · 리뷰 쓰기/고치기/지우기 전에 부모 행을 `SELECT … FOR UPDATE` 로 먼저 잠근다(같은 대상끼리만 줄을 선다 — 다른 대상은 영향 없다)
- **id 충돌**: 새 id = 앱의 "max + 1" + JVM 안 잠금. 롤링(maxSurge 1)으로 Pod 가 둘 겹치면 같은 id → PK 충돌, 리뷰는 409 "이미 리뷰를 썼다"로 잘못 보였다.
  고침: V10 — `reviews.id` · `shoes.id` 를 AUTO_INCREMENT. 저장 오류는 제약 이름으로 가른다(첫 리뷰 UNIQUE 만 409)

## 0. 출발 상태 (2026-11-01 01:1x KST, 읽기만)

| 항목 | 값 |
|---|---|
| 운영 이미지 | `harbor.ronanlab.dev/runshoes/runshoes:c27f77a0b1ac`(앱 `c27f77a`) |
| ArgoCD `runshoes` | Synced · Healthy, revision `cc004a2`, **자동 Sync 켜짐**(`automated` 있음 — prune · selfHeal false) |
| `/api/shoes` | 294켤레 · 응답 키 37 · 최대 id 294 |
| `/api/reviews` | 104건 · 최대 id 105 · 짝 지문 `3e954039a1aa3f86684cd3912fc6e75a5f46027f994c9a9b7b3f13e9498f12b1` |
| Flyway · 테이블 | 1~9(6 `-1597188006` · 7 `-1950123291` · 8 `-223806260` · 9 `-371820711`), 숨긴 것까지 shoes 294 · 최대 id 294, `Auto_increment` reviews · shoes NULL, FK 10 — 3절 명령으로 읽음 |

앱 리포 쪽(로컬에서 끝낸 것):
- 계약(로컬 jar): **v3 PASS 101 · FAIL 11** — 그전 9건(가입 계정 id 32 → 33 여섯 · 신발 21 → 22 셋)에 **W46 · W47 두 건이 더해졌다**(W44 에서 지운 리뷰 id 106 을 다시 쓰지 않아 107 · 108 — 의도한 변경). v4 21 · v3-search 24 · v3-summary 5 · v6 60 그대로. 단위 테스트 21(새 3 — 제약 이름 가르기)
- V10 sha256 `545dac554f45dad821ad6465463364e53c20cfcd51ebfa2b566a3aa7390bf856` · 로컬 Flyway checksum `-1713919463`
- **리허설**(로컬 V9 DB 덤프 → 새 jar): `Successfully applied 1 migration … now at version v10`(136ms), AUTO_INCREMENT reviews 106 · shoes 301(로컬 최대 300), FK 그대로. 리뷰 새 id 107 → 108(지운 id 를 다시 쓰지 않는다), 신발 id 없이 → DB 번호 · 본문 id 5000 → 5000(다음은 5001) · 숨긴 신발 id → 500 `duplicate id` · 같은 세대 → 409. 적재기 건조 실행 0
- **옛 이미지 롤백 확인**: 커밋 `c27f77a` 의 jar 를 V10 DB 에 띄우면 `validated 10 migrations` · `up to date`(Flyway 11 은 모르는 새 마이그레이션을 무시한다), 리뷰 쓰기 201(옛 방식 max + 1 이 AUTO_INCREMENT 칸에도 들어간다) · 두 번째 409 · 지우기 200

## 1. 순서 (누가 · 멈추는 곳)

| # | 할 일 | 누가 | 확인 |
|---|---|---|---|
| 1 | **자동 Sync 끄기** — `catalog-v4-v5.md` 1.1 그대로 | **사람** | `syncPolicy` 에 `automated` 없음(Claude 도 `get application` 으로 본다) |
| 2 | 이 리포: 이 런북 커밋 · push | Claude(사용자 승인 뒤) | 이 파일 · `admin-demo-v6-v9.md` 실행 기록만 |
| 3 | 앱 리포 커밋 · push → Jenkins → 이 리포에 newTag 커밋 | Claude(사용자 승인 뒤) | **1 이 끝난 것을 보고**. newTag 두 줄만, 운영은 옛 이미지 그대로(OutOfSync) |
| 4 | 이미지 안의 마이그레이션 — `scripts/check-image-migrations.sh <태그>` | Claude | V1~V9 = 0절 · V10 `545dac55…` |
| 5 | **덤프**(2절) + 로컬 다른 이름으로 복원 확인 | Claude | 2절 |
| 6 | **덤프 직후** 운영 지문(3절) | Claude | 신발 294 · 리뷰 104 · `3e954039…` · Flyway 1~9. 다르면 멈춘다 |
| 7 | newTag 커밋 Sync = V10 적용 | **사람(Sync)** | 4절 |
| 8 | 자동 Sync 다시 켜기 | **사람** | `automated` 다시 있음 |

- **5 → 6 → 7 은 끊지 않고 잇는다** — 덤프 뒤 · Sync 전에 들어온 쓰기는 덤프에 없다
- V10 은 두 테이블을 다시 만든다(ALTER MODIFY, 리뷰 104 · 신발 294 — 로컬 0.14초). 그동안 두 테이블 쓰기가 잠깐 기다린다. 읽기는 그대로

## 2. 덤프

V4 런북(`catalog-v4-v5.md`) 2절과 같은 명령 · 같은 확인 — 이름만 `runshoes-before-v10-$TS`, 폴더만 위의 `$B`.
**덤프에는 비밀번호 해시 · refresh token 해시 · 활동 로그(IP · User-Agent)가 들어 있다** — `chmod 600`, git · 공유 폴더에 두지 않는다.
복원 확인 기대값: shoes 294 · reviews 104 · 리뷰 지문 `3e954039…` · flyway `1:1 … 9:1`.

## 3. 운영 지문 (Sync 직전)

```bash
curl -s -H "$H" $VIP/api/reviews | node -e '
  const r=JSON.parse(require("fs").readFileSync(0)).sort((a,b)=>a.id-b.id);
  const h=require("crypto").createHash("sha256").update(r.map(x=>x.id+":"+x.shoeId).join(",")).digest("hex");
  console.log(r.length===104 && h==="3e954039a1aa3f86684cd3912fc6e75a5f46027f994c9a9b7b3f13e9498f12b1" ? "OK" : "다름", r.length, h, "최대 id", Math.max(...r.map(x=>x.id)))'
curl -s -H "$H" $VIP/api/shoes | node -e 'const s=JSON.parse(require("fs").readFileSync(0)); console.log(s.length, Object.keys(s[0]).length, Math.max(...s.map(x=>x.id)))'
mk 'kubectl -n runshoes exec runshoes-mysql-0 -c mysql -- sh -c "mysql -N -uroot -p\"\$MYSQL_ROOT_PASSWORD\" runshoes -e \"SELECT version, success, checksum FROM flyway_schema_history ORDER BY installed_rank; SELECT COUNT(*), MAX(id) FROM shoes; SHOW TABLE STATUS WHERE Name IN ('\''reviews'\'', '\''shoes'\''); SELECT COUNT(*) FROM information_schema.REFERENTIAL_CONSTRAINTS WHERE CONSTRAINT_SCHEMA = '\''runshoes'\''\" 2>/dev/null"' | cut -f1-3,11
# → OK 104 3e954039… 최대 id 105 / 294 37 294 / 1~9(0절 checksum) / (숨긴 것 포함 수) (최대 id) / reviews · shoes 의 Auto_increment 칸 NULL / FK 수
```

리뷰가 늘었으면 멈추지 않아도 된다(V10 에는 데이터 가드가 없다) — 새 값을 5절에 적고 덤프가 그 뒤에 뜬 것인지만 본다.

## 4. Sync 뒤 확인

```bash
mk 'kubectl -n runshoes rollout status deploy/runshoes --timeout=180s'
mk 'kubectl -n runshoes logs deploy/runshoes -c runshoes | grep -E "Migrating|Successfully applied|ERROR"'
#   → Migrating schema `runshoes` to version "10 - auto increment ids" / Successfully applied 1 migration … now at version v10
mk 'kubectl -n runshoes exec runshoes-mysql-0 -c mysql -- sh -c "mysql -N -uroot -p\"\$MYSQL_ROOT_PASSWORD\" runshoes -e \"SELECT version, success, checksum FROM flyway_schema_history WHERE version = 10; SHOW TABLE STATUS WHERE Name IN ('\''reviews'\'', '\''shoes'\''); SELECT COUNT(*) FROM information_schema.REFERENTIAL_CONSTRAINTS WHERE CONSTRAINT_SCHEMA = '\''runshoes'\''\" 2>/dev/null"' | cut -f1,11
#   → 10 1 -1713919463(로컬과 같아야 — 시험한 그 파일) / reviews 106 · shoes 295(0절 최대 id + 1) / FK 10(Sync 전과 같다)
```

그리고 3절의 API 두 줄을 다시(리뷰 104 · 지문 그대로 · 신발 294), 공개 주소 200.
**운영에서는 쓰기 시험(동시 찜 · 시험 신발 등록)을 하지 않는다** — 로컬 리허설로 갈음. 첫 새 리뷰가 생기면 id 가 106 인지만 본다(지운 id 가 있으면 그보다 크다).

## 5. 실패했을 때

**MySQL DDL 은 트랜잭션이 아니다.** 실패한 새 Pod 는 Ready 가 되지 않아 옛 Pod 가 계속 돈다(maxUnavailable 0) — 급할 것은 없다.

| 멈춘 곳 | DB 상태 | 복구 |
|---|---|---|
| **R1 V10 중간 실패**(첫 ALTER 뒤) | reviews 만 AUTO_INCREMENT · `success 0` 한 줄 | 옛 이미지는 어느 상태에서도 돈다(max + 1 을 직접 넣는다). 원인을 본 뒤 `DELETE FROM flyway_schema_history WHERE version = 10 AND success = 0` → 같은 이미지 재시작(MODIFY 는 다시 해도 같다). 실패한 Pod 는 연결 풀째 사라진다 — `FOREIGN_KEY_CHECKS = 0` 이 남은 연결이 앱에 쓰이지 않는다 |
| **R2 V10 은 됐는데 새 앱이 이상하다** | V10 그대로 둔다 | newTag 커밋만 revert → Sync. 옛 이미지가 V10 DB 에서 뜬다(0절 — 로컬 확인). 옛 이미지에서는 다시 max + 1(지운 리뷰 id 를 다시 쓴다) · 데드락도 다시 |
| **R3 데이터가 이상하다** | — | `admin-demo-v6-v9.md` 7절 R2 와 같은 순서로 2절 덤프를 넣는다(이름만 `runshoes-before-v10-$TS`). 그다음 적재기 스냅숏을 덤프 시점으로(`node load.mjs --base … --host … --snapshot`) |

## 6. 실행 기록 (시각은 UTC)

| 단계 | 시각 | 결과 |
|---|---|---|
| 0절 출발 상태 | 10-31 16:1x | 위 표(Claude, 읽기만) |
