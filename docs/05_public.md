<!--
다루는 곳: apps/cloudflared/, platform/cert-manager/
읽은 커밋: 736d833
-->
# 바깥 공개와 인증서

Cloudflare 터널로 바깥에 공개하는 길과 경로마다의 Access, cert-manager 인증서와 TLS가 끝나는 곳을 다룬다.

원고: → 「바깥 공개와 인증서」, → 「공개 경로와 내부 경로」, → 「TLS가 끝나는 곳」. 문(ingress-nginx, MetalLB)은 `docs/04_ingress.md`. [code:apps/cloudflared/]

## 지금 구성

### 터널

- 터널 `ronanlab-tunnel` 하나, locally-managed(설정 파일 방식). 터널 ID는 비밀이 아니고 자격 증명은 Secret `cloudflared/cloudflared-credentials`(키 `credentials.json`, 사람이 만든다) [code:apps/cloudflared/configmap.yaml:1-4] [code:apps/cloudflared/deployment.yaml:74-77]
- 공개 호스트 7개: petmint, argocd, harbor, jenkins, runshoes, grafana, prometheus `.ronanlab.dev`. 마지막 규칙 `http_status:404` [code:apps/cloudflared/configmap.yaml:13-44]
- 원점은 7개 모두 `https://ingress-nginx-controller.ingress-nginx.svc.cluster.local:443`, `originRequest.noTLSVerify: true`. NodePort, VIP를 쓰지 않는다. 호스트 구분은 nginx가 Host 헤더로 한다 [code:apps/cloudflared/configmap.yaml:2] [docs:history/cluster_state_20261116.md:50]
- Deployment `cloudflared/cloudflared`: replicas 2, `cloudflare/cloudflared:2026.10.0`, maxSurge 1, maxUnavailable 0, 노드 분산(선호, `nodeTaintsPolicy: Honor`) [code:apps/cloudflared/deployment.yaml:13-38]
- readiness와 liveness 모두 `/ready`(포트 2000 metrics). 엣지 연결이 하나라도 서야 200 [code:apps/cloudflared/deployment.yaml:3] [code:apps/cloudflared/deployment.yaml:43-60]
- ArgoCD Application `cloudflared`: `targetRevision: main`, path `apps/cloudflared`, 수동 Sync(automated 없음), prune 없음, finalizer 없음, `CreateNamespace=false` [code:apps/cloudflared/app.yaml:8-28]
- 클러스터 상태: cloudflared Synced, Healthy, 자동 Sync 꺼짐 [docs:history/cluster_state_20261116.md:61]
- 네임스페이스 `cloudflared`는 사람이 만든다 [code:apps/cloudflared/kustomization.yaml:6-9]

### 경로와 Access

왜 이것은 막고 저것은 열었는지를 이 표 한 곳에 둔다. 앱 쪽 까닭은 한 줄로 줄이고 그 저장소 문서를 가리킨다. 까닭은 사람이 적은 것이다 [c:57ca8a9].

| 호스트 | 무리 | Access(대시보드, 저장소 밖) | 까닭 | 근거 |
| --- | --- | --- | --- | --- |
| argocd, harbor, jenkins, grafana, prometheus | 운영 도구 | Access 앱 「운영도구」 | 터널만 뚫으면 주소를 아는 누구나 부를 수 있다. Prometheus는 자체 로그인이 없어 Access가 유일한 문이다 | [code:apps/monitoring/ingress.yaml:3] [code:apps/cloudflared/configmap.yaml:35] [docs:history/build_log/03_cloudflare_tunnel.md:175] |
| argocd `/api/webhook`, jenkins `/github-webhook/` | 웹훅 경로 둘 | 그 경로만 Bypass, HMAC SHA-256 서명이 지킨다 | GitHub 웹훅이 들어와야 한다 | [docs:history/build_log/04_argocd.md:45] [code:platform/jenkins/values.yaml:92-93] |
| runshoes | 공개 앱 | 없음 | 사람들이 실제로 와서 쓰는 공개 서비스다. 로그인 관문을 앞에 두면 서비스가 아니게 된다 | [code:apps/cloudflared/configmap.yaml:30] |
| petmint | 공개 앱 | 없음, 앱 자체 로그인(`PETMINT_AUTH=app`) | 사내에서 쓸 것이라 본래는 막아야 하지만, 데모를 보는 사람에게 사내 계정이 없어 일부러 뺐다. 앱 로그인은 그대로다. 자세한 것은 펫퍼민트 `docs/02_pipeline/13_access_and_tunnel.md` | [docs:history/build_log/03_cloudflare_tunnel.md:50] |
| ollama(호스트에 따로 도는 터널, 이 저장소 밖) | 추론 API | Service Auth, 서비스 토큰 | GPU가 한 장이라 늘 Access 뒤에 둔다 | [docs:history/build_log/03_cloudflare_tunnel.md:690] [docs:history/build_log/03_cloudflare_tunnel.md:701] |
| FOREMAN 관제 화면(터널에 없음) | 관제 | 바깥에 열지 않는다 | 관제실은 호스트 셸과 승인 권한을 쥐고 있다. 여기가 한 번 뚫리면 네 저장소 전부에 push할 수 있고, 위험 작업을 통과시킬 수 있고, 비밀값이 든 설정도 만질 수 있다. 다른 서비스는 뚫려도 그 서비스 하나지만 여기는 나머지 전부로 번진다. 그래서 Access를 앞에 두는 것으로 그치지 않고 아예 열지 않았다. 밖에서 필요한 것은 텔레그램으로 받는다. 자세한 것은 FOREMAN `README.md` 3.13 | |
- Prometheus는 자체 로그인이 없어 바깥에서는 Access가 유일한 문이다. Grafana는 자체 로그인과 Access 두 겹 [code:apps/monitoring/ingress.yaml:5-7]
- 사설망(호스트와 VM만 있는 망)에서는 MetalLB VIP 192.168.122.240으로 같은 Ingress에 Access 없이 닿는다 [code:apps/monitoring/ingress.yaml:4-6]
- 노드 containerd는 `/etc/hosts`의 `192.168.122.240 harbor.ronanlab.dev`로 Harbor에 https로 닿는다 [code:cluster/Vagrantfile:33-36] [code:platform/harbor/values.yaml:4]
- 클러스터 안 Pod는 CoreDNS rewrite로 `harbor.ronanlab.dev`를 ingress-nginx ClusterIP로 푼다 [code:platform/coredns/configmap.yaml:1-7]

### TLS

| 호스트 | Ingress tls | 브라우저 TLS 끝 | nginx → 백엔드 |
| --- | --- | --- | --- |
| petmint, runshoes | 없음 | Cloudflare 엣지 | HTTP |
| harbor, jenkins, grafana, prometheus | Let's Encrypt(cert-manager) | ingress-nginx | 따로 정하지 않음 |
| argocd | Let's Encrypt(cert-manager) | ingress-nginx | HTTPS(`backend-protocol: "HTTPS"`, argocd-server 자체 인증서) |

근거: [code:apps/petmint/app/ingress.yaml:1] [code:apps/runshoes/app/ingress.yaml:1] [code:platform/argocd/ingress.yaml:3-6] [code:platform/argocd/ingress.yaml:14] [docs:history/cluster_state_20261116.md:38-48]

| Certificate | 네임스페이스 | Secret | 파일 |
| --- | --- | --- | --- |
| argocd-ingress-tls | argocd | argocd-ingress-tls | [code:platform/cert-manager/argocd-certificate.yaml:5-14] |
| harbor-tls | harbor | harbor-tls | [code:platform/cert-manager/harbor-certificate.yaml:4-13] |
| jenkins-tls | jenkins | jenkins-tls | [code:platform/cert-manager/jenkins-certificate.yaml:4-13] |
| grafana-tls | monitoring | grafana-tls | [code:apps/monitoring/ingress.yaml:8-18] |
| prometheus-tls | monitoring | prometheus-tls | [code:apps/monitoring/ingress.yaml:20-30] |

- 다섯 개 모두 ClusterIssuer `letsencrypt-prod`, 모두 READY True [code:platform/cert-manager/argocd-certificate.yaml:12-14] [docs:history/cluster_state_20261116.md:48]
- ClusterIssuer는 `letsencrypt-staging`, `letsencrypt-prod` 둘. ACME DNS-01, Cloudflare 솔버, `dnsZones: ["ronanlab.dev"]` [code:platform/cert-manager/cluster-issuer.yaml:4-37]
- cert-manager v1.21.2(helm, 네임스페이스 `cert-manager`) [code:platform/versions.yaml:34-38]
- 모든 Ingress는 `ssl-redirect: "false"`. 터널은 https로 붙고, 사설망 http(80) 경로도 열어 둔다 [code:platform/argocd/ingress.yaml:7] [code:apps/monitoring/ingress.yaml:39] [code:platform/harbor/values.yaml:16] [code:platform/jenkins/values.yaml:10]

## 설정 자리

| 파일:줄 | 값 | 뜻 |
| --- | --- | --- |
| `apps/cloudflared/app.yaml:4-8` | `syncPolicy`에 automated 없음 | 터널이 깨지면 공개 주소 7개와 고칠 도구(ArgoCD UI), 볼 도구(Grafana)가 같이 사라지고 m-k8s kubectl로만 되돌린다. 커밋이 곧바로 반영되지 않게 사람이 Sync를 누르고 롤링을 지켜본다 [code:apps/cloudflared/app.yaml:4-8] |
| `apps/cloudflared/app.yaml:9-11` | prune 없음, finalizer 없음 | git에서 지운 리소스와 Application을 지운 뒤의 Pod가 클러스터에 남는다 [code:apps/cloudflared/app.yaml:9-11] |
| `apps/cloudflared/configmap.yaml:13-17` 외 | `service: https://…:443`, `noTLSVerify: true` | https는 학교 vcluster 시절(원점 traefik)의 301 루프를 피하려던 설정이 남은 것이다 [docs:history/build_log/03_cloudflare_tunnel.md:157-159]. 지금 Ingress 7개는 모두 `ssl-redirect: "false"`라 그 루프는 지금 ingress-nginx에는 해당하지 않는다 [code:apps/petmint/app/ingress.yaml:12] [code:apps/runshoes/app/ingress.yaml:11] [code:platform/argocd/ingress.yaml:15] [code:platform/harbor/values.yaml:16] [code:platform/jenkins/values.yaml:10] [code:apps/monitoring/ingress.yaml:39] [code:apps/monitoring/ingress.yaml:66]. `noTLSVerify`는 7개 모두에 필요하다. `originServerName`이 없어 cloudflared는 인증서에 서비스 이름을 기대하는데, ingress-nginx는 그 이름으로 물으면 Fake Certificate를, 공개 이름으로 물으면 공개 이름의 인증서(운영 도구는 Let's Encrypt, 앱은 Fake)를 낸다 [docs:history/notls_check_20261117.md:9-24] |
| `apps/cloudflared/deployment.yaml:18-19` | maxSurge 1, maxUnavailable 0 | 새 커넥터가 Ready가 된 뒤 옛 것을 내린다 [code:apps/cloudflared/deployment.yaml:4] |
| `platform/cert-manager/values.yaml:1` | DNS-01 | 인바운드 포트가 없고 Access, 터널 뒤라 HTTP-01을 못 쓴다 [code:platform/cert-manager/values.yaml:1] |
| `platform/cert-manager/values.yaml:6-7` | `dns01RecursiveNameservers: "8.8.8.8:53,8.8.4.4:53"`, `...Only: true` | 전파 확인을 공개 리졸버로만. 1.1.1.1:53은 이 망에서 시간 초과다 [code:platform/cert-manager/values.yaml:4-7] |
| `platform/cert-manager/cluster-issuer.yaml:15-17` | Secret `cert-manager/cloudflare-api-token`, 키 `api-token` | 사람이 만든다. 저장소에 값이 없다 [code:platform/cert-manager/cluster-issuer.yaml:1] |
| `platform/cert-manager/argocd-certificate.yaml:9` | `argocd-ingress-tls` | `argocd-server-tls`로 두면 argocd-server가 자기 서버 인증서로 집어 간다 [code:platform/cert-manager/argocd-certificate.yaml:2] |
| `platform/argocd/ingress.yaml:14` | `backend-protocol: "HTTPS"` | argocd-server는 `server.insecure`가 아니다. ssl-passthrough는 쓰지 않는다(켜면 nginx가 TLS를 끝내지 않아 위 인증서가 안 쓰인다) [code:platform/argocd/ingress.yaml:4-6] |
| `platform/harbor/values.yaml:5-9`, `:21` | `certSource: secret`, `harbor-tls`, `caSecretName: harbor-tls` | Harbor 차트가 cert-manager Secret을 쓴다 [code:platform/harbor/values.yaml:3] [code:platform/harbor/values.yaml:20-21] |

## 바꾸거나 다시 만들기

처음 한 번(사람이 한다). 값은 화면에 내지 않는다.

```bash
kubectl create namespace cloudflared
# 자격 증명은 표준 입력으로(README 「처음 한 번」)
# cert-manager/cloudflare-api-token 도 사람이 만든다
```

근거: [code:apps/cloudflared/README.md:28-36] [code:platform/cert-manager/cluster-issuer.yaml:1]

cert-manager 설치(ArgoCD 밖, m-k8s에서): [docs:history/build_log/02_metrics_storage_ingress.md:146-148]

```bash
helm repo add jetstack https://charts.jetstack.io && helm repo update
helm install cert-manager jetstack/cert-manager --version v1.21.2 -n cert-manager --create-namespace -f platform/cert-manager/values.yaml
kubectl apply -f platform/cert-manager/cluster-issuer.yaml
kubectl apply -f platform/cert-manager/argocd-certificate.yaml -f platform/cert-manager/harbor-certificate.yaml -f platform/cert-manager/jenkins-certificate.yaml
```

근거: [code:platform/versions.yaml:34-38] [code:platform/cert-manager/] 새 인증서는 `letsencrypt-staging`으로 먼저 확인하고 `letsencrypt-prod`로 바꾼다(운영은 주간 발급 한도) [code:platform/cert-manager/cluster-issuer.yaml:2].

터널 설정을 바꿀 때(호스트 추가 등). 공개 주소 7개가 함께 걸린 작업이라 하기 전에 알린다. [code:apps/cloudflared/app.yaml:5]

1. `apps/cloudflared/configmap.yaml`을 고쳐 커밋하고 관리자가 push한다 [code:apps/cloudflared/README.md:43]
2. ArgoCD에서 cloudflared를 수동 Sync한다. ConfigMap만 바뀌고 떠 있는 Pod는 옛 설정 그대로다 [code:apps/cloudflared/README.md:43]
3. `kubectl -n cloudflared rollout restart deploy/cloudflared`. 새 Pod가 Ready(엣지 연결)가 돼야 옛 Pod가 내려간다 [code:apps/cloudflared/README.md:44]
4. 새 설정이 깨졌으면 새 Pod가 Ready가 못 되고 롤링이 멈춘다(옛 Pod 둘이 계속 받는다). git revert, Sync, `rollout restart` [code:apps/cloudflared/README.md:45]
5. 새 공개 이름의 DNS CNAME(`<터널 ID>.cfargotunnel.com`)과 Access는 Cloudflare 대시보드에서 사람이 한다. 운영 도구는 Access를 건 뒤 DNS를 연다 [code:apps/cloudflared/README.md:46] [code:apps/monitoring/ingress.yaml:5]

근거: [code:apps/cloudflared/README.md:41-46] [code:apps/cloudflared/configmap.yaml:3] [code:apps/monitoring/ingress.yaml:5]

수동 Sync 명령:

```bash
kubectl -n argocd patch app cloudflared --type merge -p '{"operation":{"sync":{"revision":"<커밋>"}}}'
```

터널 없이 쓰는 길: m-k8s(192.168.122.10)에서 kubectl, UI는 호스트에서 VIP로 [code:apps/cloudflared/README.md:24-25].

```bash
curl --resolve argocd.ronanlab.dev:443:192.168.122.240 https://argocd.ronanlab.dev/
```

## 확인

```bash
kubectl -n argocd get app cloudflared -o jsonpath='{.spec.syncPolicy.automated}{" "}{.status.sync.status}{" "}{.status.health.status}{"\n"}'
# (비어 있음) Synced Healthy
kubectl -n cloudflared get pod -l app=cloudflared -o wide
# Ready 1/1 두 개, 서로 다른 노드
kubectl -n cloudflared logs -l app=cloudflared --since=10m | grep -E ' ERR '
# 없음
kubectl get clusterissuer
# letsencrypt-prod, letsencrypt-staging 모두 True
kubectl get certificate -A
# 다섯 개 모두 READY True
kubectl get ingress -A
# 7개. tls Secret은 petmint-app, runshoes 에 없다
```

근거: [code:apps/cloudflared/README.md:48-55] [docs:history/cluster_state_20261116.md:36-50] [docs:history/build_log/03_cloudflare_tunnel.md:707-728]

## 알려진 한계

- 터널 하나에 공개 주소 7개. 터널이 깨지면 공개 앱과 운영 도구가 함께 안 보인다 [code:apps/cloudflared/app.yaml:5-6]
- Cloudflare 쪽(DNS CNAME, Access 정책)은 저장소에 없다. 대시보드에서 정책이 빠져도 저장소로는 알 수 없다 [docs:history/build_log/03_cloudflare_tunnel.md:699]
- ConfigMap은 기동 때만 읽는다. Sync만 하고 `rollout restart`를 빠뜨리면 바뀐 설정이 안 들어간다 [code:apps/cloudflared/configmap.yaml:3]
- cloudflared에서 ingress-nginx까지는 `noTLSVerify`라 원점 인증서를 검증하지 않는다 [code:apps/cloudflared/configmap.yaml:17]
- `ssl-redirect: "false"`라 사설망에서는 http(80)로도, Access 없이 운영 도구에 닿는다. Prometheus는 자체 로그인이 없다 [code:platform/argocd/ingress.yaml:7] [code:apps/monitoring/ingress.yaml:5-6]
- `apps/cloudflared/README.md`, `configmap.yaml`이 가리키는 `docs/13`은 이 저장소가 아니라 petmint-rag-chatbot 저장소의 문서다 [code:apps/cloudflared/kustomization.yaml:1]
