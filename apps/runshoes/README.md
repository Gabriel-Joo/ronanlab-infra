# apps/runshoes — RUNSHOES K8s 매니페스트

러닝화 스펙 아카이브(앱 리포 GitHub `Gabriel-Joo/runshoes` — Spring Boot + MySQL + React). 네임스페이스 `runshoes`, 주소 `runshoes.ronanlab.dev`.
ArgoCD Application `runshoes`(`app.yaml`, 루트 `bootstrap/root-app.yaml`이 만든다)가 이 디렉터리를 보고, 이미지 태그는 Jenkins `runshoes-app`이 바꾼다.

```
kustomization.yaml       이미지 둘(runshoes, runshoes-chatbot) — 같은 태그. Jenkins가 커밋 해시 12자리로 두 줄을 함께 바꾼다
mysql/statefulset.yaml   runshoes-mysql — MySQL 8.0.46, local-path 2Gi(Retain), w1 선호
mysql/service.yaml       runshoes-mysql:3306 (headless)
mysql/replica.yaml       runshoes-mysql-replica — Replica(w2, 2026-11-10), 수동 승격: docs/runbooks/mysql-replica.md
app/deployment.yaml      replicas 2 · app 노드(w1 · w2) + required anti-affinity · RollingUpdate(maxSurge 0, maxUnavailable 1 — 2026-11-10). runshoes(Spring, :3000) + chatbot(:8766)
                         activity_logs 정리(ACTIVITY_CLEANUP_CRON "-")는 꺼 둠 — ShedLock 전까지(2026-11-10)
app/pdb.yaml             PDB minAvailable 1 — drain 때 하나는 남긴다(petmint 와 같다)
app/cronjob.yaml         리뷰 요약 배치 runshoes-summary(V14) — 웹과 같은 이미지에 batch 프로필, 매일 03:30 KST(runbooks/v14-shoe-summaries.md)
app/service.yaml         포트 http(80→3000) · chatbot(8766)
app/ingress.yaml         / → http, /ws/chat → chatbot
scripts/                 create-secrets.sh (runshoes-mysql · harbor-pull · runshoes-auth)
runbooks/                운영 절차 — auth-v3.md(로그인 V3 적용 · MySQL 백업 · 복구)
```

## 배포 — ArgoCD가 관리한다

apps/petmint와 같다 — `kubectl apply`로 넣지 않는다.

| 하고 싶은 것 | 하는 방법 |
| --- | --- |
| 새 이미지 배포 | 앱 리포 main에 push → Jenkins `runshoes-app`(2분 폴링) → `newTag` 커밋 → ArgoCD 자동 Sync(3분 안) |
| 설정 변경 | 이 디렉터리를 고쳐 push → Sync |
| 되돌리기 | 이 저장소 커밋을 revert해 push → Sync. DB는 되돌아가지 않는다(스키마 변경은 Flyway 다음 버전으로) |

- **배포 때 끊기지 않는다.** 새 Pod가 Ready(DB 접속까지)가 된 뒤 옛 Pod를 내린다. 옛 Pod는 preStop 5초 동안 엔드포인트에서 빠지고
  그 뒤 graceful shutdown. 열려 있던 챗봇 WebSocket은 한 번 끊기고 프런트가 다시 붙는다
- 새 Pod가 Ready가 못 되면(DB · Flyway · probe) 롤링이 멈추고 옛 Pod가 계속 받는다 — 고쳐서 다시 Sync하거나 revert
- **Sync는 자동(prune · selfHeal 없음), finalizer 없음, Namespace는 사람이 만든다** — Jenkins 태그 커밋이 3분 안에 배포된다. 스키마를 바꾸는 배포는 자동 Sync를 잠시 끄고 런북(runbooks/auth-v3.md)대로. Namespace는 petmint와 같은 이유(Secret).
  Application 객체는 사람이 `kubectl apply`로 넣는다(git push만으로는 바뀌지 않는다)

## 처음 만드는 순서

```bash
# 1. Harbor: 프로젝트 runshoes(private), robot$runshoes+jenkins(push·pull), robot$runshoes+pull(pull)
# 2. 네임스페이스와 Secret — 사람이 만든다(runshoes-mysql · runshoes-auth 는 무작위, harbor-pull 은 robot 값)
HARBOR_USER='robot$runshoes+pull' HARBOR_PASSWORD=... apps/runshoes/scripts/create-secrets.sh
# 3. Jenkins push 자격 증명 — Secret jenkins/harbor-robot-runshoes-jenkins(키 username·password), platform/jenkins/values.yaml이 읽는다
# 4. ArgoCD Application → 첫 Jenkins 빌드로 newTag가 바뀐 뒤 Sync. MySQL 이 먼저 Ready 가 되고 앱이 Flyway 로 스키마·시드를 넣는다
# Application 은 루트(bootstrap/root-app.yaml)가 app.yaml 로 만든다 — 손으로 apply 하지 않는다(2026-11-02 App of Apps)
```

## 데이터 — MySQL

- 데이터베이스 `runshoes`, 계정 `runshoes`(Secret `runshoes-mysql` 의 `MYSQL_PASSWORD`). MySQL 이미지가 빈 데이터 디렉터리에서 처음 뜰 때 만든다
- 스키마 · 시드는 앱(Spring)이 기동 때 Flyway 로 넣는다(앱 리포 `backend/src/main/resources/db/migration`). 적용된 버전은 다시 돌지 않는다
- 시드로 다시 시작하려면(데이터가 지워진다): StatefulSet 을 0 으로 → PVC `data-runshoes-mysql-0` 삭제 → Sync(빈 DB) → 앱 `rollout restart`(Flyway 가 다시 시드)
- **정기 백업이 없다.** local-path는 노드 디스크 한 곳이다 — 스키마를 바꾸기 전에는 덤프를 뜨고 복원까지 확인한다: [runbooks/auth-v3.md](runbooks/auth-v3.md) 2절
- **노드 drain**: MySQL Pod는 PV 가 있는 노드(w1)에 묶인다 — w1 drain 동안 DB 가 멈추고 앱은 Ready 가 빠진다

## Ollama — 호스트 직접 연결

리뷰 요약(앱)과 챗봇(`chatbot_server.py`)이 `OLLAMA_URL=http://192.168.122.1:11434`(VM 사설망의 GPU 호스트)를 부른다 — petmint와 같은 길.
**두 기능 다 GPU를 쓴다** — GPU 실험 중 확인은 `/`, `/api/*`, WebSocket 연결·환영 메시지까지만 한다(환영 메시지는 Ollama를 부르지 않는다).

## 되돌리기

- **이미지만**(DB 는 그대로): 이 저장소의 태그 커밋을 `git revert` → push(자동 Sync). 옛 이미지가 지금 DB 위에서 뜨는지는 스키마 변경마다 확인해 둔다 — V3 위에서 V3 전 이미지가 뜨는 것은 확인했다(runbooks/auth-v3.md 5.3)
- **DB 까지**: 스키마를 바꾸는 배포 직전에 뜬 mysqldump 로 복원(runbooks/auth-v3.md 5.2). 그 덤프 뒤에 들어온 쓰기는 사라진다
- 전환 전(Node · db.json) 배포로 돌아가는 길은 2026-10-21 에 닫았다 — PVC `runshoes-data`(시드와 같은 db.json 하나)를 지웠다. DB 가 V3(계정 · 리뷰 재배분)라 그 배포는 지금 데이터와 맞지 않는다. 시드 원본은 앱 리포 `db.json`
