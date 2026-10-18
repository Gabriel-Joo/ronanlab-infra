# apps/runshoes — RUNSHOES K8s 매니페스트

러닝화 스펙 아카이브(앱 리포 GitHub `Gabriel-Joo/runshoes`). 네임스페이스 `runshoes`, 주소 `runshoes.ronanlab.dev`.
2026-10-18 학교 환경(std-gitlab gitops 레포 `apps/runshoes`, RKE2 vcluster, std-harbor)에서 옮겼다 — 구조는 그대로(db.json + PVC).
ArgoCD Application `runshoes`(`platform/argocd/applications/runshoes.yaml`)가 이 디렉터리를 보고, 이미지 태그는 Jenkins `runshoes-app`이 바꾼다.

```
kustomization.yaml     이미지 둘(runshoes, runshoes-chatbot) — 같은 태그. Jenkins가 커밋 해시 12자리로 두 줄을 함께 바꾼다
app/pvc.yaml           db.json(local-path 1Gi, RWO)
app/deployment.yaml    replicas 1 · Recreate. 컨테이너 runshoes(:3000) + chatbot(:8766), initContainer seed-db
app/service.yaml       포트 http(80→3000) · chatbot(8766)
app/ingress.yaml       / → http, /ws/chat → chatbot
scripts/               create-secrets.sh (harbor-pull)
```

## 배포·되돌리기 — ArgoCD가 관리한다

apps/petmint와 같다 — `kubectl apply`로 넣지 않는다.

| 하고 싶은 것 | 하는 방법 |
| --- | --- |
| 새 이미지 배포 | 앱 리포 main에 push → Jenkins `runshoes-app`(2분 폴링) → `newTag` 커밋 → ArgoCD에서 Sync |
| 설정 변경 | 이 디렉터리를 고쳐 push → Sync |
| 되돌리기 | 이 저장소 커밋을 revert해 push → Sync. db.json은 되돌아가지 않는다(PVC) |

- **배포 때 수십 초 끊긴다.** Pod 하나·Recreate라 옛 Pod가 내려간 뒤 새 Pod가 뜬다. 열려 있던 챗봇 WebSocket도 끊긴다
- **Sync는 수동, prune·finalizer 없음, Namespace는 사람이 만든다** — petmint와 같은 이유(Secret)

## 처음 만드는 순서

```bash
# 1. Harbor: 프로젝트 runshoes(private), robot$runshoes+jenkins(push·pull), robot$runshoes+pull(pull)
# 2. 네임스페이스와 pull Secret — 사람이 만든다
HARBOR_USER='robot$runshoes+pull' HARBOR_PASSWORD=... apps/runshoes/scripts/create-secrets.sh
# 3. Jenkins push 자격 증명 — Secret jenkins/harbor-robot-runshoes-jenkins(키 username·password), platform/jenkins/values.yaml이 읽는다
# 4. ArgoCD Application → 첫 Jenkins 빌드로 newTag가 바뀐 뒤 Sync
kubectl apply -f platform/argocd/applications/runshoes.yaml
```

## 데이터 — db.json 한 파일

- 이미지에 시드(`db.json.seed` = 앱 리포 `db.json`)가 들어 있고, initContainer `seed-db`가 PVC에 `db.json`이 **없을 때만** 복사한다. 그 뒤로는 앱(json-server)이 PVC의 파일을 읽고 쓴다
- 앱 리포의 `db.json`을 고쳐 배포해도 이미 있는 PVC 파일은 바뀌지 않는다. 시드로 다시 시작하려면 파일을 지우고 Pod를 다시 띄운다:
  `kubectl -n runshoes exec deploy/runshoes -c runshoes -- rm /data/db.json && kubectl -n runshoes rollout restart deploy/runshoes`
- 2026-10-18 이주는 git `db.json`(리뷰 105건)으로 시작했다. 학교 PVC의 데이터(리뷰 71건, 테스트 흔적)는 가져오지 않았다
- **백업이 없다.** local-path는 노드 디스크 한 곳이다 — 필요하면 `kubectl -n runshoes cp runshoes-<pod>:/data/db.json -c runshoes ./db.json`

## Ollama — 호스트 직접 연결

리뷰 요약(`server.cjs`)과 챗봇(`chatbot_server.py`)이 `OLLAMA_URL=http://192.168.122.1:11434`(VM 사설망의 GPU 호스트)를 부른다 — petmint와 같은 길.
학교 때는 `https://ollama.ronanlab.dev`(Cloudflare 터널 + Access Service Token)로 나갔다 들어왔다. 직접 가므로 `CF_ACCESS_*`는 주지 않는다.
**두 기능 다 GPU를 쓴다** — GPU 실험 중 확인은 `/`, `/api/*`, WebSocket 연결·환영 메시지까지만 한다(환영 메시지는 Ollama를 부르지 않는다).
