<!--
다루는 곳: bootstrap/, platform/argocd/, apps/*/app.yaml
읽은 커밋: 6290346
-->
# GitOps

ArgoCD가 `main`을 읽어 클러스터에 넣는다. `main`이 곧 운영이다. 이력은 옛 구축 기록에 있다. [docs:history/build_log/04_argocd.md] [code:bootstrap/root-app.yaml:20-24]

## 지금 구성

- ArgoCD v2.13.2, 공식 `install.yaml`을 `kubectl apply`로 넣었다. 그 매니페스트는 저장소에 없다 [code:platform/versions.yaml:27-30]
- 컴포넌트는 Deployment 여섯과 StatefulSet `argocd-application-controller` 하나다. 모두 `node.ronanlab.dev/role: infra`(w3)에 고정한다 [code:platform/argocd/pin-infra.sh:7-11]
- PVC 없음. redis는 emptyDir이고, control-plane taint 때문에 m-k8s에는 처음부터 뜨지 않았다 [code:platform/argocd/pin-infra.sh:5]
- 저장소 `git@github.com:Gabriel-Joo/ronanlab-infra.git`(private)를 읽기 전용 deploy key(Secret `argocd/repo-ronanlab-infra`, `scripts/make-deploy-keys.sh`)로 읽는다 [code:apps/petmint/app.yaml:10]
- 바깥 주소 `https://argocd.ronanlab.dev`. Ingress `argocd/argocd-server`, TLS Secret `argocd-ingress-tls`(cert-manager) [code:platform/argocd/ingress.yaml:1-3] [code:platform/argocd/ingress.yaml:18-21]
- GitHub 웹훅 `https://argocd.ronanlab.dev/api/webhook`. Cloudflare Access는 이 경로만 비켜 두고 HMAC 서명이 지킨다 [docs:history/build_log/04_argocd.md:45]

### Application

| 이름 | 경로 | 네임스페이스 | Sync |
| --- | --- | --- | --- |
| root | `apps`(`*/app.yaml`만) | argocd | 자동 |
| runshoes | `apps/runshoes` | runshoes | 자동 |
| petmint | `apps/petmint` | petmint | 자동 |
| monitoring | `apps/monitoring` | monitoring | 자동 |
| harbor-backup | `apps/harbor-backup` | harbor | 자동 |
| cloudflared | `apps/cloudflared` | cloudflared | 수동 |

- 위 Sync 열은 클러스터의 실제 값이다. 여섯 모두 Synced, Healthy였다 [docs:history/cluster_state_20261116.md:52-61]
- 모두 `targetRevision: main`, `project: default`, `destination.server: https://kubernetes.default.svc` [code:bootstrap/root-app.yaml:20-32]
- 자동 앱은 모두 `prune: false`, `selfHeal: false` [code:apps/runshoes/app.yaml:28-31]
- 앱 Application은 모두 `CreateNamespace=false`. 네임스페이스는 Application이 만들지도 소유하지도 않는다 [code:apps/cloudflared/app.yaml:26-28]
- finalizer 없음. Application을 지워도 자식 리소스와 PVC가 남는다 [code:apps/petmint/app.yaml:8]
- `platform/`(cert-manager, coredns, ingress-nginx, metallb, harbor, jenkins, argocd ingress)은 ArgoCD 밖이다 [code:bootstrap/root-app.yaml:13]

## 설정 자리

| 파일:줄 | 값 | 뜻 |
| --- | --- | --- |
| `bootstrap/root-app.yaml:25-28` | `path: apps`, `recurse: true`, `include: '*/app.yaml'` | 루트는 각 앱의 `app.yaml`만 읽는다. 앱 `kustomization.yaml`의 resources에 `app.yaml`을 넣지 않는다 [code:bootstrap/root-app.yaml:4] |
| `bootstrap/root-app.yaml:33-37` | `ignoreDifferences` `/spec/syncPolicy` | 루트가 자식 Application의 syncPolicy를 덮지 않는다 |
| `bootstrap/root-app.yaml:38-43` | `automated`(prune, selfHeal 끔), `RespectIgnoreDifferences=true` | 루트 자동 Sync. 위 무시가 Sync 때도 지켜진다 |
| `apps/<앱>/app.yaml` `syncPolicy` | `automated` 있음 또는 없음 | Application을 처음 만들 때만 쓰인다. 그 뒤로는 기록이다 [code:bootstrap/root-app.yaml:8-10] |
| `platform/argocd/ingress.yaml:14` | `backend-protocol: "HTTPS"` | argocd-server가 자체 인증서로 TLS를 받는다(`server.insecure` 아님) [code:platform/argocd/ingress.yaml:4] |
| `platform/argocd/ingress.yaml:15` | `ssl-redirect: "false"` | Harbor, Jenkins와 맞춘다 [code:platform/argocd/ingress.yaml:7] |
| `platform/argocd/notifications-cm.yaml:16-22` | `service.webhook.foreman` | FOREMAN 웹훅 `http://192.168.122.1:8001`. 토큰은 Secret `argocd/argocd-notifications-secret`의 `foreman-webhook-token` [code:platform/argocd/notifications-cm.yaml:3] |
| `platform/argocd/notifications-cm.yaml:23-26` | 구독 선택자 `app.kubernetes.io/instance=root` | 루트가 만든 Application에 트리거 여섯을 건다 |
| `platform/argocd/notifications-cm.yaml:34-53` | 트리거 여섯 | out-of-sync, sync-running, sync-succeeded, sync-failed, health-degraded, deployed |
| `platform/argocd/pin-infra.sh:7` | `nodeSelector` `node.ronanlab.dev/role: infra` | Deployment 여섯과 StatefulSet 하나에 patch |

자동 Sync를 클러스터에서 켜고 끄게 한 까닭: 스키마를 바꾸는 runshoes 배포는 자동 Sync를 잠시 끄고 한다. 루트가 자식 syncPolicy를 덮으면 Jenkins 태그 커밋 하나에 루트가 다시 Sync해 꺼 둔 자동 Sync를 도로 켠다 [code:bootstrap/root-app.yaml:8-10] [code:apps/runshoes/app.yaml:9]

cloudflared만 수동인 까닭: 터널이 깨지면 공개 주소 일곱과 ArgoCD UI, Grafana가 함께 끊기고 되돌리기는 m-k8s의 kubectl로만 된다 [code:apps/cloudflared/app.yaml:4-7]

## 바꾸거나 다시 만들기

kubectl은 m-k8s에서 친다. 호스트에는 kubectl이 없어 `cd ~/k8s-cluster && vagrant ssh m-k8s -c '…'`로 넘긴다. [docs:history/build_log/04_argocd.md:403]

새 앱 넣기: `apps/<이름>/`에 `app.yaml`과 매니페스트(`kustomization.yaml`)를 넣고 `main`에 push한다. 3분 안에 Application이 생긴다 [code:bootstrap/root-app.yaml:3]

앱 Application 지우기: 폴더를 지워도 Application은 남는다(루트 prune 끔). 직접 지운다. 자식 리소스는 남는다 [code:bootstrap/root-app.yaml:11]

```bash
kubectl -n argocd delete application <이름>
```

자동 Sync 켜고 끄기(실제 스위치). 바꾼 뒤 `app.yaml`의 기록도 맞춰 고친다 [code:apps/petmint/README.md:34-35]

```bash
kubectl -n argocd patch application <앱> --type merge -p '{"spec":{"syncPolicy":{"automated":null}}}'   # 끄기
kubectl -n argocd patch application <앱> --type merge -p '{"spec":{"syncPolicy":{"automated":{"prune":false,"selfHeal":false}}}}'   # 켜기
```

수동 Sync(커밋을 집어서):

```bash
kubectl -n argocd patch app <앱> --type merge -p '{"operation":{"sync":{"revision":"<커밋>"}}}'
```

`apps/cloudflared/configmap.yaml`을 바꾼 경우에는 Sync 뒤 `kubectl -n cloudflared rollout restart deploy/cloudflared`까지 한다 [code:apps/cloudflared/README.md:44]

ArgoCD 처음부터 다시 세우기(순서만. 비밀값은 셸 변수와 표준 입력으로만 다룬다. 웹훅 시크릿과 알림 토큰을 넣는 명령은 옛 구축 기록에 있다) [docs:history/build_log/04_argocd.md:92-109]

```bash
kubectl create namespace argocd
kubectl apply -n argocd -f https://raw.githubusercontent.com/argoproj/argo-cd/v2.13.2/manifests/install.yaml
bash platform/argocd/pin-infra.sh                       # install.yaml 을 다시 넣을 때마다 다시 돌린다
kubectl apply -f platform/cert-manager/argocd-certificate.yaml
kubectl apply -f platform/argocd/ingress.yaml
# 저장소 읽기 deploy key: scripts/make-deploy-keys.sh, 공개 키는 사람이 GitHub Deploy keys(쓰기 끔)에
kubectl apply -f platform/argocd/notifications-cm.yaml   # install.yaml 뒤에 다시 넣는다
kubectl apply -f bootstrap/root-app.yaml                 # 나머지 Application 은 루트가 만든다
```

- `install.yaml`에도 같은 이름의 빈 `argocd-notifications-cm`이 있어 다시 넣으면 알림 설정이 지워질 수 있다(확인하지 않음). 그 뒤에 `notifications-cm.yaml`을 다시 넣는다 [code:platform/argocd/notifications-cm.yaml:5]
- GitHub 웹훅 시크릿(Secret `argocd/argocd-secret` 키 `webhook.github.secret`)을 바꾸면 `kubectl -n argocd rollout restart deploy/argocd-server`로 다시 띄워야 읽는다 [docs:history/build_log/04_argocd.md:389-391]
- 판을 올리면 `platform/versions.yaml`도 같은 커밋에서 고친다 [code:platform/versions.yaml:6]

## 확인

```bash
# Application 여섯, cloudflared 만 AUTO <none>, 모두 Synced / Healthy
kubectl -n argocd get applications.argoproj.io \
  -o custom-columns=NAME:.metadata.name,PATH:.spec.source.path,REV:.spec.source.targetRevision,AUTO:.spec.syncPolicy.automated,SYNC:.status.sync.status,HEALTH:.status.health.status

# 파드 일곱이 Running, NODE 가 w3-k8s
kubectl -n argocd get pod -o wide

# 이미지 quay.io/argoproj/argocd:v2.13.2
kubectl -n argocd get deploy argocd-server -o jsonpath='{.spec.template.spec.containers[0].image}'; echo

# 알림 설정 키 이름(값은 보지 않는다)
kubectl -n argocd get cm argocd-notifications-cm -o go-template='{{range $k,$v := .data}}{{$k}}{{"\n"}}{{end}}'

# 사설망(MetalLB VIP)으로 검증된 HTTPS, HTTP/2 200
curl -sI --resolve argocd.ronanlab.dev:443:192.168.122.240 https://argocd.ronanlab.dev | head -1
```

호스트에서 공개 주소를 부르면 Cloudflare Access가 앞에 있어 `HTTP/2 302`가 나온다 [docs:history/build_log/04_argocd.md:429]

## 알려진 한계

- `install.yaml`이 저장소에 없다. 다시 넣으면 w3 고정이 사라지고 알림 설정이 지워질 수 있다. `pin-infra.sh`와 `notifications-cm.yaml`을 다시 넣는다 [code:platform/argocd/pin-infra.sh:3-4]
- ArgoCD가 w3 한 노드에만 있다. w3가 내려가면 배포가 멈춘다. 떠 있는 앱 파드는 그대로다 [code:cluster/label-nodes.sh:7]
- prune을 꺼 두어 git에서 지운 리소스는 클러스터에 남는다. 손으로 지운다 [code:apps/runshoes/app.yaml:11]
- `app.yaml`의 syncPolicy와 클러스터 값이 다를 수 있다. 실제 값은 위 확인 명령으로 본다
- 웹훅 시크릿과 알림 토큰은 저장소에 없다 [docs:history/build_log/04_argocd.md:56-59]
