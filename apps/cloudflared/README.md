# apps/cloudflared — 클러스터 공용 Cloudflare 터널

터널 `ronanlab-tunnel`(`02ad6a13-ce45-4262-a32a-40241bf034dc`, 2026-10-18 전 이름 `petmint-tunnel`) 하나가 공개 주소 일곱을 받는다 — `petmint`·`argocd`·`harbor`·`jenkins`·`runshoes`·`grafana`·`prometheus` `.ronanlab.dev`(runshoes는 2026-10-18 추가, Access 없음. grafana · prometheus는 2026-11-11 추가).
원점은 전부 ingress-nginx ClusterIP(`ingress-nginx-controller.ingress-nginx.svc.cluster.local:443`), 앞단은 Cloudflare Access(petmint-rag-chatbot docs/13).
ArgoCD Application `cloudflared`(`app.yaml`, 루트 `bootstrap/root-app.yaml`이 만든다)가 이 디렉터리를 본다. 네임스페이스 `cloudflared`.
2026-11-02 `platform/cloudflared`에서 옮겼다(App of Apps — 호스트 `~/k8s-cluster/backup/2026-11-02-app-of-apps/ROLLBACK.md`).

2026-10-18 `petmint` 네임스페이스에서 옮겼다. 그 전에는 m-k8s `~/cloudflared-deploy.yaml`과 손으로 만든 ConfigMap을 `kubectl apply`했고, git에 없었다.
옮긴 기록·되돌리기는 호스트 `~/k8s-cluster/backup/2026-10-18-cloudflared-platform/ROLLBACK.md`.

```
kustomization.yaml   Namespace·Secret 없음(아래)
configmap.yaml       터널 설정 config.yaml — 호스트 일곱이 한 파일. 기동 때만 읽는다
deployment.yaml      커넥터 2개. readinessProbe /ready · maxUnavailable 0 · 노드 분산(선호)
```

## 이 터널이 끊기면 작업 도구도 끊긴다

ArgoCD·Jenkins·Harbor UI가 전부 이 터널로 들어온다. 그래서:

- **Sync는 수동이고 자동으로 바꾸지 않는다(2026-11-11 다시 정함 — 다른 Application은 자동).** 터널이 깨지면 공개 주소 7개(petmint · runshoes · argocd · harbor · jenkins · grafana · prometheus)가
  한꺼번에 안 보인다. 서비스만이 아니라 고칠 도구(ArgoCD UI)와 볼 도구(Grafana)도 같이 사라지고, 되돌리기는 m-k8s에서 kubectl로만 된다(아래 「설정 바꾸기」).
  잘못된 커밋이 바로 반영되면 이 상태가 사람 손을 거치지 않고 온다 — 그래서 사람이 Sync를 누르고 롤링을 지켜본다
- **터널 없이 쓰는 길**: m-k8s(`192.168.122.10`)에 ssh로 `kubectl`. UI는 호스트에서 MetalLB VIP로 —
  `curl --resolve argocd.ronanlab.dev:443:192.168.122.240 https://argocd.ronanlab.dev/` (Let's Encrypt 인증서 그대로, Access를 거치지 않는다)
- **커넥터가 여럿이어도 된다.** 같은 터널에 붙은 커넥터는 엣지가 나눠 받는다. 설정이 다르면 요청마다 결과가 달라지므로 커넥터끼리 설정은 늘 같아야 한다

## 처음 한 번 (사람이 한다)

```
kubectl create namespace cloudflared
# 자격 증명 — 터널을 만든 호스트의 ~/.cloudflared/<터널 ID>.json. 디스크·화면에 평문을 남기지 않게 표준 입력으로 넣는다
ssh <m-k8s> 'kubectl -n cloudflared create secret generic cloudflared-credentials --from-file=credentials.json=/dev/stdin' \
  < ~/.cloudflared/02ad6a13-ce45-4262-a32a-40241bf034dc.json
# Application 은 루트(bootstrap/root-app.yaml)가 app.yaml 로 만든다 — 손으로 apply 하지 않는다(2026-11-02 App of Apps)
```

그다음 ArgoCD에서 cloudflared만 Sync한다. 2026-10-18에는 옛 `petmint/cloudflared-credentials`에서 같은 방법(`base64 -d | … /dev/stdin`)으로 복사했다 —
두 값과 호스트 파일의 sha256이 같다.

## 바꿀 때 (호스트 추가 등)

1. `configmap.yaml`을 고쳐 push → ArgoCD에서 cloudflared Sync (ConfigMap만 바뀐다. 떠 있는 Pod는 옛 설정 그대로)
2. `kubectl -n cloudflared rollout restart deploy/cloudflared` — 한 Pod씩 바뀐다. 새 Pod가 Ready(엣지 연결)가 돼야 옛 Pod가 내려간다
3. 새 설정이 깨졌으면 새 Pod가 Ready가 못 되고 롤링이 멈춘다(옛 Pod 둘이 계속 받는다) → git revert → Sync → `rollout restart`
4. 공개 주소에 새 이름을 붙이는 것(DNS CNAME → `<터널 ID>.cfargotunnel.com`)은 Cloudflare 쪽에서 따로 한다

## 확인

```
kubectl -n cloudflared get pod -l app=cloudflared -o wide            # Ready 2/2, 노드 둘
kubectl -n cloudflared logs -l app=cloudflared --since=10m | grep -E ' ERR '
~/k8s-cluster/backup/2026-10-15-before-metallb/health.sh             # 커넥터마다 ha_connections=4, 공개 주소 302(Access 로그인)
cloudflared tunnel --config /dev/null info 02ad6a13-ce45-4262-a32a-40241bf034dc   # 호스트에서 — 커넥터 목록
```
