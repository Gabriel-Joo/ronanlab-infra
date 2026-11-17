<!--
다루는 곳: apps/petmint/app/, apps/petmint/jobs/, apps/petmint/scripts/, apps/petmint/README.md, apps/runshoes/app/, apps/runshoes/scripts/, apps/runshoes/README.md, apps/runshoes/runbooks/
읽은 커밋: 6290346
-->
# 앱이 올라가는 길

petmint와 runshoes 두 앱의 매니페스트, 처음 세우는 순서와 Secret, 버전을 바꾸는 절차를 적는다. 이미지 빌드와 `newTag` 커밋은 `docs/08_build.md`, ArgoCD Application과 자동 Sync 스위치는 `docs/06_gitops.md`, MySQL과 복제본은 `docs/10_database.md`다. 앱별 운영 문서의 원본은 `apps/<앱>/README.md`와 `apps/runshoes/runbooks/`다. [code:apps/runshoes/README.md:1-19]

## 지금 구성

| 항목 | petmint | runshoes |
| --- | --- | --- |
| 네임스페이스, Application | `petmint`, `petmint` [code:apps/petmint/kustomization.yaml:6] | `runshoes`, `runshoes` [code:apps/runshoes/kustomization.yaml:6] |
| 이미지 | `harbor.ronanlab.dev/petmint/petmint-app:<newTag>` [code:apps/petmint/kustomization.yaml:30-32] | `harbor.ronanlab.dev/runshoes/runshoes`, `runshoes-chatbot`(같은 태그) [code:apps/runshoes/kustomization.yaml:27-31] |
| 앱 Pod | Deployment `petmint-app`, replicas 2 [code:apps/petmint/app/deployment.yaml:11-23] | Deployment `runshoes`, replicas 2, 컨테이너 `runshoes`(:3000) + `chatbot`(:8766) [code:apps/runshoes/app/deployment.yaml:18-28] [code:apps/runshoes/app/deployment.yaml:84-88] [code:apps/runshoes/app/deployment.yaml:138-142] |
| 배치 | `node.ronanlab.dev/role: app`(w1, w2), required anti-affinity [code:apps/petmint/app/deployment.yaml:43-51] | 같다 [code:apps/runshoes/app/deployment.yaml:48-56] |
| 롤링 | `maxSurge: 0`, `maxUnavailable: 1` [code:apps/petmint/app/deployment.yaml:19-23] | 같다 [code:apps/runshoes/app/deployment.yaml:24-28] |
| PDB | `minAvailable: 1` [code:apps/petmint/app/pdb.yaml:11] | 같다 [code:apps/runshoes/app/pdb.yaml:9] |
| Service | `petmint-app` 80 → http(8000) [code:apps/petmint/app/service.yaml:12-15] [code:apps/petmint/app/deployment.yaml:74-76] | `runshoes` 80 → http, 8766 → chatbot [code:apps/runshoes/app/service.yaml:11-17] |
| Ingress | `petmint.ronanlab.dev` `/` [code:apps/petmint/app/ingress.yaml:16-28] | `runshoes.ronanlab.dev` `/ws/chat` → chatbot, `/` → http [code:apps/runshoes/app/ingress.yaml:14-33] |
| 스키마 | 초기화 Job `petmint-init-db`(Sync hook, wave 1) [code:apps/petmint/jobs/init-db.yaml:8-17] | 앱 기동 때 Flyway [code:apps/runshoes/README.md:52] |
| 그 밖 | ConfigMap `petmint-app-config`, `petmint-init-config` [code:apps/petmint/app/configmap.yaml:4-5] [code:apps/petmint/app/configmap.yaml:72-73] | CronJob `runshoes-summary`(`30 3 * * *` Asia/Seoul, batch 프로필) [code:apps/runshoes/app/cronjob.yaml:10-17] |
| Secret(이름) | `mysql-root`, `petmint-db`, `insurance-seed-db`, `harbor-pull`, `mysql-repl` [code:apps/petmint/scripts/create-secrets.sh:26-38] [code:apps/petmint/mysql/replica.yaml:6] | `runshoes-mysql`, `harbor-pull`, `runshoes-auth`, `mysql-repl` [code:apps/runshoes/scripts/create-secrets.sh:25-50] [code:apps/runshoes/mysql/replica.yaml:5] |
| 자동 Sync | 켜짐, prune과 selfHeal 끔 [code:apps/petmint/app.yaml:25-28] | 켜짐, 같다 [code:apps/runshoes/app.yaml:28-31] |

- 두 `kustomization.yaml`에는 Namespace와 Secret이 없다. 사람이 만든다 [code:apps/petmint/kustomization.yaml:13-14] [code:apps/petmint/kustomization.yaml:28]
- petmint 적용 순서(sync-wave): MySQL, 볼륨, ConfigMap 0 → 초기화 Job 1(hook, 끝날 때까지 기다림) → 앱 2 [code:apps/petmint/README.md:59-62]
- 초기화 Job은 `BeforeHookCreation`으로 Sync마다 다시 돈다. bootstrap과 migrate는 멱등, 시드는 `--if-empty` [code:apps/petmint/README.md:64-66] [code:apps/petmint/jobs/init-db.yaml:35-42]
- 앱 Pod는 GPU 호스트를 `192.168.122.1`로 부른다(Ollama 11434, Milvus 19530, search 8100, model-service 8200) [code:apps/petmint/app/configmap.yaml:23-26] [code:apps/runshoes/app/deployment.yaml:98-99] [code:apps/runshoes/app/deployment.yaml:148-149]
- runshoes 앱 컨테이너의 actuator는 관리 포트 9000이고 Service와 Ingress에 없다. Prometheus가 Pod 주석으로 긁는다 [code:apps/runshoes/app/deployment.yaml:36-42]
- runshoes MySQL에 정기 백업이 없다. 스키마 변경 전 덤프가 백업이다 [code:apps/runshoes/README.md:54]

### runshoes 런북

`apps/runshoes/runbooks/`에 스키마를 바꾼 배포마다 한 편씩 있다. 지금 순서는 `v24-chatbot-miss-note.md` 1절이다 [code:apps/runshoes/runbooks/v24-chatbot-miss-note.md:40-65]

| 런북 | 스키마 | 배포 구조에서 다른 점 |
| --- | --- | --- |
| `auth-v3.md` | V3 | 원형. Secret과 envFrom을 이미지 전에 Sync, 실패 복구 5절, 덤프 보관 7절 [code:apps/runshoes/runbooks/auth-v3.md:14-32] |
| `catalog-v4-v5.md` | V4, V5 | Sync 뒤 관리자 API 적재, 자동 Sync 스위치 1.1절 [code:apps/runshoes/runbooks/catalog-v4-v5.md:33-67] |
| `admin-demo-v6-v9.md` | V6 ~ V9 | 넷을 한 Sync에, env 커밋 먼저 [code:apps/runshoes/runbooks/admin-demo-v6-v9.md:36-53] |
| `v10-auto-increment.md` | V10 | 테이블 재생성(ALTER MODIFY) [code:apps/runshoes/runbooks/v10-auto-increment.md:51-52] |
| `v11-admin-history.md` | V11 | Sync 뒤 적재기 운영 쓰기를 따로 승인 [code:apps/runshoes/runbooks/v11-admin-history.md:61-73] |
| `v12-wide-scope.md` | V12 | 열 추가, 짧은 판 [code:apps/runshoes/runbooks/v12-wide-scope.md:22-31] |
| `v13-model-en.md` | V13 | 열 추가, 짧은 판 [code:apps/runshoes/runbooks/v13-model-en.md:22-31] |
| `v14-shoe-summaries.md` | V14 | 같은 Sync에 CronJob(suspend), 뒤에 git에서 해제 [code:apps/runshoes/runbooks/v14-shoe-summaries.md:54-64] |
| `v15-weight-norm.md` | V15, V16 | 생성 열, V16 첫 구문 가드 [code:apps/runshoes/runbooks/v15-weight-norm.md:12-23] |
| `v17-v18-chatbot.md` | V17, V18 | 값 변경 가드, 사이드카 구조 변경에도 매니페스트 그대로 [code:apps/runshoes/runbooks/v17-v18-chatbot.md:14-28] |
| `v19-v20-observability.md` | V19, V20 | 프로브 경로 변경은 이미지 뒤 따로 [code:apps/runshoes/runbooks/v19-v20-observability.md:152-163] |
| `v21-grafana-compare-views.md` | V21 | 끈 것을 사람 출력으로 확인하는 단계 추가, Pod 주석은 이미지 뒤 [code:apps/runshoes/runbooks/v21-grafana-compare-views.md:42-56] [code:apps/runshoes/runbooks/v21-grafana-compare-views.md:150-158] |
| `v22-v23-review-hide-miss-status.md` | V22, V23 | 자동 Sync가 켜진 채 push가 먼저 나간 기록 [code:apps/runshoes/runbooks/v22-v23-review-hide-miss-status.md:147-158] |
| `v24-chatbot-miss-note.md` | V24 | 지금 순서 [code:apps/runshoes/runbooks/v24-chatbot-miss-note.md:40-65] |
| `reviews-1500.md` | 없음 | 이미지와 Sync 없이 운영 DB에 SQL 한 트랜잭션, 덤프로 되돌림 [code:apps/runshoes/runbooks/reviews-1500.md:5] [code:apps/runshoes/runbooks/reviews-1500.md:69-73] |

## 설정 자리

| 파일:줄 | 값 | 뜻 |
| --- | --- | --- |
| `apps/petmint/app/deployment.yaml:22-23` | `maxSurge: 0`, `maxUnavailable: 1` | app 노드가 둘이라 새 Pod를 먼저 띄울 자리가 없다 [code:apps/petmint/app/deployment.yaml:4-7] |
| `apps/petmint/app/deployment.yaml:86-89` | startupProbe 5초 × 36 | 기동 3분까지 liveness가 죽이지 않는다 [code:apps/petmint/app/deployment.yaml:86-89] |
| `apps/petmint/app/deployment.yaml:96-99` | preStop `sleep 5` | Ingress가 엔드포인트를 뺄 시간 [code:apps/petmint/app/deployment.yaml:96-99] |
| `apps/runshoes/app/deployment.yaml:121-130` | `/readyz`, `/livez` on http | 이미지와 묶인 경로. 옛 이미지로 되돌리면 경로도 [code:apps/runshoes/app/deployment.yaml:117-130] |
| `apps/runshoes/app/deployment.yaml:61-73` | initContainer `wait-mysql` 2초 × 90 | MySQL 3306이 열릴 때까지 [code:apps/runshoes/app/deployment.yaml:57-73] |
| `apps/runshoes/app/deployment.yaml:106-107` | `ACTIVITY_CLEANUP_CRON: "-"` | Pod 둘의 정리 경합을 피해 끔. ShedLock 뒤 뺀다 [code:apps/runshoes/app/deployment.yaml:103-107] |
| `apps/runshoes/app/deployment.yaml:111-113` | `envFrom secretRef runshoes-auth`(optional 아님) | Secret이 없으면 새 Pod `CreateContainerConfigError` [code:apps/runshoes/app/deployment.yaml:108-113] |
| `apps/petmint/app/ingress.yaml:12-15` | ssl-redirect false, proxy read/send 3600, buffering off | 터널 https, WebSocket 1시간 [code:apps/petmint/app/ingress.yaml:1-15] |
| `apps/petmint/app/configmap.yaml:38-53` | 검색과 답 플래그 | 되돌리기는 이 줄을 지우고 Sync 뒤 rollout restart [code:apps/petmint/app/configmap.yaml:38-39] |
| `apps/petmint/jobs/init-db.yaml:15-17` | hook Sync, BeforeHookCreation, wave 1 | Sync마다 새 Job [code:apps/petmint/jobs/init-db.yaml:15-17] |
| `apps/petmint/jobs/init-db.yaml:19-20` | backoffLimit 10, ttl 86400 | 첫 배포는 MySQL을 재시도로 기다림, 끝난 Job은 하루 뒤 지움 [code:apps/petmint/jobs/init-db.yaml:19-20] |
| `apps/runshoes/app/cronjob.yaml:14-27` | Forbid, suspend false, backoffLimit 0, activeDeadline 7200 | 겹치면 GET_LOCK으로 뒤 쪽 종료, 재시도는 stale 플래그 [code:apps/runshoes/app/cronjob.yaml:1-6] [code:apps/runshoes/app/cronjob.yaml:14-27] |
| `apps/runshoes/scripts/check-image-migrations.sh:13-16` | `TAG`, `MK`, `NODE`(기본 w2) | 이미지를 받을 노드와 kubectl 래퍼 [code:apps/runshoes/scripts/check-image-migrations.sh:13-16] |

## 바꾸거나 다시 만들기

kubectl은 m-k8s에서 친다. 런북의 `mk`는 호스트용 kubectl 래퍼 `~/k8s-cluster/backup/2026-10-15-before-metallb/mk`다 [code:apps/runshoes/runbooks/v24-chatbot-miss-note.md:9-12]

### 처음 세우기

```bash
# petmint. 0은 호스트에서 사람이(sudo). 스크립트는 앱 저장소 deploy/scripts에 있다
sudo <petmint-rag-chatbot>/deploy/scripts/host-nfs-setup.sh
kubectl create namespace petmint
HARBOR_USER='robot$petmint+pull' HARBOR_PASSWORD=... apps/petmint/scripts/create-secrets.sh
# Application은 루트가 apps/petmint/app.yaml로 만든다. 생기면 Sync
```

명령 출처: [code:apps/petmint/README.md:47-55]. `app/fixtures/customers.json`은 git에 없다. 호스트 앱 저장소의 예시 파일을 복사해 채운다 [code:apps/petmint/README.md:44-45]

```bash
# runshoes. Harbor에 프로젝트 runshoes(private), robot$runshoes+jenkins(push, pull), robot$runshoes+pull(pull)을 먼저
HARBOR_USER='robot$runshoes+pull' HARBOR_PASSWORD=... apps/runshoes/scripts/create-secrets.sh
# Secret jenkins/harbor-robot-runshoes-jenkins를 만든다(docs/08_build.md)
# 첫 Jenkins 빌드로 newTag가 실제 태그가 된 뒤 Sync
```

명령 출처: [code:apps/runshoes/README.md:38-47] [code:apps/runshoes/kustomization.yaml:29]

- 스크립트는 네임스페이스가 없으면 만들고, 있는 Secret은 건드리지 않는다. MySQL root 비밀번호는 데이터 디렉터리를 처음 만들 때만 쓰인다 [code:apps/petmint/scripts/create-secrets.sh:2-4] [code:apps/petmint/scripts/create-secrets.sh:12-24]
- petmint 앱 계정 비밀번호 바꾸기: Secret 삭제 → 스크립트 → 초기화 Job(ALTER USER로 맞춘다) [code:apps/petmint/scripts/create-secrets.sh:4]
- runshoes `runshoes-auth`를 바꾸면 `rollout restart`. JWT_SECRET을 바꾸면 발급된 토큰이 모두 무효 [code:apps/runshoes/scripts/create-secrets.sh:9-10]
- `mysql-repl`은 복제본 런북 1절에서 만든다 [code:apps/petmint/mysql/replica.yaml:6]

### 평소 배포와 설정 변경

- 새 이미지: 앱 저장소 main push → Jenkins → `newTag` 커밋 → 자동 Sync [code:apps/petmint/README.md:25] [code:apps/runshoes/README.md:27]
- 설정: 이 저장소를 고쳐 push. ConfigMap만 바뀌면 `kubectl -n petmint rollout restart deploy/petmint-app` [code:apps/petmint/README.md:26] [code:apps/petmint/app/configmap.yaml:28]
- kubectl로 replicas, 이미지, env를 바꾸지 않는다. 손으로 넣은 변경은 다음 Sync에 사라진다 [code:apps/petmint/README.md:18-28]
- 앱 Pod만 다른 노드로: `kubectl drain <노드> --pod-selector=app.kubernetes.io/name=petmint-app --ignore-daemonsets` → `kubectl uncordon <노드>` [code:apps/petmint/README.md:89-90]

### 스키마를 바꾸는 배포(runshoes)

`v24-chatbot-miss-note.md` 1절 순서를 따른다. 새 배포는 그 런북을 복사해 새 런북을 만들고 실행 기록을 남긴다 [code:apps/runshoes/runbooks/v24-chatbot-miss-note.md:40-61]

```bash
# 1. 자동 Sync 끄기, 2. 확인(automated가 없어야 한다). push 전에
kubectl -n argocd patch app runshoes --type json -p '[{"op":"remove","path":"/spec/syncPolicy/automated"}]'
kubectl -n argocd get app runshoes -o jsonpath='{.spec.syncPolicy}'
# → {"syncOptions":["CreateNamespace=false"]}
# 3. 앱 push → Jenkins newTag 커밋. 이미지 안 마이그레이션 확인(호스트에서)
apps/runshoes/scripts/check-image-migrations.sh <태그>
# 4, 5. 도는 요약 Job 없음, 공개 숫자 적기, 덤프, 로컬 복원 확인(런북 2절)
kubectl -n runshoes get jobs,pods -l app.kubernetes.io/name=runshoes-summary
# 6. Jenkins 태그 커밋으로 Sync
kubectl -n argocd patch app runshoes --type merge -p '{"operation":{"sync":{"revision":"<커밋>"}}}'
# 7. 다시 켜기
kubectl -n argocd patch app runshoes --type merge -p '{"spec":{"syncPolicy":{"automated":{}}}}'
```

명령 출처: [code:apps/runshoes/runbooks/v24-chatbot-miss-note.md:52-61] [code:apps/runshoes/runbooks/v24-chatbot-miss-note.md:71-73] [code:apps/runshoes/scripts/check-image-migrations.sh:7-9]

- 덤프는 `mysqldump --single-transaction --set-gtid-purged=OFF --routines --triggers --default-character-set=utf8mb4 runshoes`를 `runshoes-mysql-0` 안에서 뜨고 `chmod 600`, git 밖 `~/k8s-cluster/backup/<날짜>-runshoes-<일>/` [code:apps/runshoes/runbooks/v24-chatbot-miss-note.md:85-93]
- 복원 확인은 로컬 `runshoes-mysql-dev`에 `runshoes_restore_check`로 넣어 리뷰 수와 지문을 공개 API와 견준다. 리뷰가 많으면 `group_concat_max_len`을 먼저 늘린다 [code:apps/runshoes/runbooks/v24-chatbot-miss-note.md:97-107]
- 요약 CronJob 시각(03:30 KST) 근처는 피한다 [code:apps/runshoes/runbooks/v15-weight-norm.md:44]
- petmint도 되돌리기 어려운 스키마 변경과 DB 복구 때는 자동 Sync를 끈다. 끄기 `{"spec":{"syncPolicy":{"automated":null}}}`, 켜기 `{"automated":{"prune":false,"selfHeal":false}}` [code:apps/petmint/README.md:30-36]

### 되돌리기

- 이미지만: 이 저장소의 태그 커밋 `git revert` → push → Sync. 옛 이미지는 Flyway `*:future` 무시와 `ddl-auto: validate`로 새 스키마 위에서 뜬다 [code:apps/runshoes/runbooks/auth-v3.md:154-158] [code:apps/runshoes/runbooks/v24-chatbot-miss-note.md:135]
- 마이그레이션 첫 가드에서 멈춤: `flyway_schema_history`의 실패 행(success 0)만 지운다 [code:apps/runshoes/runbooks/auth-v3.md:132-138]
- 일부만 적용: replicas 0 → DB 다시 만들기 → `sha256sum -c` → 덤프 넣기 → 지문 확인 → 태그 커밋 revert → Sync [code:apps/runshoes/runbooks/auth-v3.md:140-152]
- DB는 태그 revert로 돌아가지 않는다 [code:apps/runshoes/README.md:29] [code:apps/petmint/README.md:27]

## 확인

```bash
kubectl -n petmint get pod -o wide; kubectl -n runshoes get pod -o wide
# petmint-app-* w1-k8s, w2-k8s / runshoes-* w1-k8s, w2-k8s
kubectl -n petmint get deploy petmint-app -o jsonpath='{.spec.strategy.rollingUpdate}{"\n"}'
kubectl -n runshoes get deploy runshoes -o jsonpath='{.spec.strategy.rollingUpdate}{"\n"}'
# {"maxSurge":0,"maxUnavailable":1}
kubectl get pdb -A
# petmint-app 1, runshoes 1 (ALLOWED DISRUPTIONS 1)
kubectl get cronjob -A
# harbor    harbor-db-backup  45 3 * * *  Asia/Seoul
# petmint   mysql-backup      30 3 * * *  Asia/Seoul
# runshoes  runshoes-summary  30 3 * * *  Asia/Seoul
kubectl -n runshoes get secret; kubectl -n petmint get secret
# 이름만 본다
```

기대 결과 출처: [docs:history/build_log/07_project_deploy.md:589-621]. CronJob 셋은 저장소 [code:apps/harbor-backup/cronjob.yaml:13-18] [code:apps/petmint/backup/cronjob.yaml:12-17] [code:apps/runshoes/app/cronjob.yaml:10-15]

```bash
# 이미지가 newTag와 같은지(웹, 챗봇, CronJob이 같은 태그)
grep newTag apps/petmint/kustomization.yaml apps/runshoes/kustomization.yaml
kubectl -n runshoes get deploy/runshoes cronjob/runshoes-summary -o jsonpath="{..image}"
# 스키마 변경 뒤: 새 Pod는 Successfully applied, 둘째 Pod는 up to date
for p in $(kubectl -n runshoes get pod -l app.kubernetes.io/name=runshoes -o name); do kubectl -n runshoes logs $p -c runshoes | grep -E "Migrating schema|Successfully applied|up to date|FlywayException"; done
# 바깥에서(호스트)
curl -sI https://petmint.ronanlab.dev | head -1; curl -sI https://runshoes.ronanlab.dev | head -1
```

명령 출처: [code:apps/runshoes/runbooks/v24-chatbot-miss-note.md:114-119] [docs:history/build_log/07_project_deploy.md:633-646]

## 알려진 한계

- 롤링 동안 앱 Pod가 잠깐 하나다. app 노드 하나가 빠지면 두 번째 Pod가 Pending이고 롤링이 멈춘다 [code:apps/petmint/app/deployment.yaml:6-7]
- 자동 Sync인 petmint는 초기화 Job 마이그레이션까지 push만으로 운영 DB에 들어간다 [code:apps/petmint/README.md:31]
- runshoes 스키마 변경은 자동 Sync 끄기를 사람이 잊으면 덤프 없이 들어갈 수 있다 [code:apps/runshoes/runbooks/v22-v23-review-hide-miss-status.md:158]
- 자동 Sync를 끈 시각은 ArgoCD에 남지 않는다 [code:apps/runshoes/runbooks/v21-grafana-compare-views.md:167]
- `check-image-migrations.sh`는 w2에서 pull robot 비밀번호가 ctr 인자로 잠깐 보인다 [code:apps/runshoes/scripts/check-image-migrations.sh:11]
- `ACTIVITY_CLEANUP_CRON`을 꺼 activity_logs가 쌓인다 [code:apps/runshoes/app/deployment.yaml:105]
- runshoes MySQL에 정기 백업이 없다 [code:apps/runshoes/README.md:54]
- 옛 런북의 값은 그때 기준이다. `auth-v3.md`, `catalog-v4-v5.md`, `v11-admin-history.md`의 `maxUnavailable 0`, `auth-v3.md` 5.2의 replicas 1, `catalog-v4-v5.md` 1.1의 `platform/argocd/applications/runshoes.yaml`은 지금과 다르다(지금은 maxUnavailable 1, replicas 2, `apps/runshoes/app.yaml`) [code:apps/runshoes/runbooks/auth-v3.md:122] [code:apps/runshoes/runbooks/v11-admin-history.md:91] [code:apps/runshoes/runbooks/auth-v3.md:151] [code:apps/runshoes/runbooks/catalog-v4-v5.md:55] [code:apps/runshoes/app/deployment.yaml:22-28]
