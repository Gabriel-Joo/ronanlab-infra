# 02. 메트릭·스토리지·Ingress

metrics-server, local-path-provisioner(동적 스토리지), ingress-nginx를 2026-10-06에 넣었고, 2026-10-15 ingress-nginx를 MetalLB LoadBalancer(VIP 192.168.122.240) 뒤로 옮기며 cert-manager(Let's Encrypt DNS-01)와 CoreDNS rewrite를 더했다.
지금 ingress-nginx는 `platform/ingress-nginx`(kustomize)로, MetalLB · cert-manager는 helm과 `platform/` 매니페스트로 관리한다.

- 날짜: 2026-10-06 설치(6~8단계), 2026-10-15 MetalLB · cert-manager · CoreDNS rewrite, 2026-11-10 ingress-nginx 2개 · 메트릭, 2026-11-12 코드 · 클러스터와 맞춤
- 범위: metrics-server, local-path-provisioner, ingress-nginx, MetalLB, cert-manager, CoreDNS rewrite, 노드 `/etc/hosts`의 Harbor 줄.
  터널은 [03_cloudflare_tunnel.md](03_cloudflare_tunnel.md), Harbor 자체는 [05_harbor.md](05_harbor.md), 노드 · VM은 [01_cluster.md](01_cluster.md), 노드 배치 · 정비는 [08_scale_out.md](08_scale_out.md)
- 코드: `platform/ingress-nginx/base`, `platform/ingress-nginx/overlay`, `platform/metallb/values.yaml`, `platform/metallb/pool.yaml`, `platform/cert-manager/*.yaml`, `platform/coredns/configmap.yaml`, `cluster/Vagrantfile`(노드 `/etc/hosts`), `apps/monitoring/ingress.yaml`(Grafana · Prometheus 인증서)
  `platform/`은 ArgoCD 밖이라 push해도 클러스터에 들어가지 않는다. 사람이 helm · kubectl로 넣는다

## 1. 지금 구성

2026-11-12 09:18 KST 클러스터 조회와 저장소 파일로 확인했다.

### 한눈에

| 것 | 버전 | 설치 방식 | 저장소 |
| --- | --- | --- | --- |
| metrics-server | v0.9.0 (replicas 1) | 업스트림 `latest` 매니페스트 URL `kubectl apply` + `kubectl patch`(`--kubelet-insecure-tls`) | 없음 |
| local-path-provisioner | v0.0.30 (replicas 1, ns `local-path-storage`) | 업스트림 v0.0.30 매니페스트 URL `kubectl apply` + StorageClass 기본값 patch | 없음 |
| ingress-nginx | controller v1.11.3 (replicas 2) | kustomize: `kubectl apply -k platform/ingress-nginx/overlay` | `platform/ingress-nginx/` |
| MetalLB | 0.16.1 (helm 릴리스 `metallb`, ns `metallb-system`, 차트 metallb-0.16.1) | helm + `kubectl apply -f platform/metallb/pool.yaml` | `platform/metallb/` |
| cert-manager | v1.21.2 (helm 릴리스 `cert-manager`, ns `cert-manager`, 차트 cert-manager-v1.21.2) | helm + ClusterIssuer · Certificate 매니페스트 | `platform/cert-manager/` |
| CoreDNS | v1.13.1 (replicas 2, kubeadm 기본) | Corefile ConfigMap `kubectl apply` | `platform/coredns/configmap.yaml` |

MetalLB · cert-manager를 어떤 helm 차트 저장소 · 명령으로 넣었는지는 저장소에 적혀 있지 않다(값 파일만 있다). 정해지지 않음.

### metrics-server

- 이미지 `registry.k8s.io/metrics-server/metrics-server:v0.9.0`, ns `kube-system`
- args: `--cert-dir=/tmp`, `--secure-port=10250`, `--kubelet-preferred-address-types=InternalIP,ExternalIP,Hostname`, `--kubelet-use-node-status-port`, `--metric-resolution=15s`, `--kubelet-insecure-tls`(6단계 트러블슈팅으로 더한 것)
- `kubectl top nodes`가 5대 모두 값을 낸다

### local-path-provisioner (스토리지)

- 이미지 `rancher/local-path-provisioner:v0.0.30`
- StorageClass `local-path (default)`: provisioner `rancher.io/local-path`, reclaimPolicy `Delete`, volumeBindingMode `WaitForFirstConsumer`, 확장 불가
- 클러스터의 PVC는 모두 이 StorageClass다(Harbor · Jenkins · 모니터링 · petmint · runshoes MySQL 등). 어느 PVC가 어느 노드에 묶였는지는 [08_scale_out.md](08_scale_out.md)

### ingress-nginx

`platform/ingress-nginx/`는 kustomize 두 층이다.

| 층 | 파일 | 내용 |
| --- | --- | --- |
| base | `base/deploy.yaml`, `base/kustomization.yaml` | 업스트림 controller-v1.11.3 baremetal 매니페스트 원본 그대로(sha256 `dbf8d355…bd27`을 kustomization 주석에 적었다). 손대지 않는다 |
| overlay | `overlay/service-patch.yaml` | Service를 `LoadBalancer`로, 어노테이션 `metallb.io/address-pool: private`, `metallb.io/loadBalancerIPs: 192.168.122.240`, nodePort 80→30517 · 443→31925 고정(ports에 `protocol: TCP` 포함) |
| overlay | `overlay/deployment-patch.yaml` | `replicas: 2`, `topologySpreadConstraints`(hostname, maxSkew 1, ScheduleAnyway), 메트릭 포트 10254와 `prometheus.io/*` 어노테이션 (2026-11-10) |
| overlay | `overlay/kustomization.yaml` 인라인 JSON 패치 | 컨테이너 args 8번 `--enable-metrics=false`를 `test`로 확인한 뒤 `--enable-metrics=true`로 바꾼다. 업스트림을 올려 인자 순서가 바뀌면 test가 실패해 apply가 멈춘다 |

클러스터:

```txt
NAME                                 TYPE           CLUSTER-IP       EXTERNAL-IP       PORT(S)                      AGE
ingress-nginx-controller             LoadBalancer   10.103.155.223   192.168.122.240   80:30517/TCP,443:31925/TCP   36d
ingress-nginx-controller-admission   ClusterIP      10.108.62.95     <none>            443/TCP                      36d
```

- 컨트롤러 Pod 2개(2026-11-12 w1-k8s, w4-k8s). 노드 고정은 없고 분산만 선호한다
- IngressClass `nginx`. 이것을 쓰는 Ingress: `argocd.ronanlab.dev`, `harbor.ronanlab.dev`, `jenkins.ronanlab.dev`, `grafana.ronanlab.dev`, `prometheus.ronanlab.dev`(이상 80 · 443), `petmint.ronanlab.dev`, `runshoes.ronanlab.dev`(80)
- 들어오는 길 셋:
  - Cloudflare 터널(cloudflared): ClusterIP Service DNS `ingress-nginx-controller.ingress-nginx.svc.cluster.local:443`([03_cloudflare_tunnel.md](03_cloudflare_tunnel.md))
  - 사설망(노드 containerd, 호스트): MetalLB VIP 192.168.122.240:80/443
  - 옛 NodePort 30517/31925: 그대로 열려 있다

### MetalLB

| 항목 | 값 | 파일 |
| --- | --- | --- |
| 모드 | L2. BGP 안 쓴다: `speaker.frr.enabled: false`, `frrk8s.enabled: false`(0.16은 frr-k8s가 기본으로 켜진다) | `platform/metallb/values.yaml` |
| IP 풀 | IPAddressPool `private`: 192.168.122.240-192.168.122.250, `autoAssign: false`(Service가 어노테이션으로 이름을 집어 쓴다) | `platform/metallb/pool.yaml` |
| 알리는 인터페이스 | L2Advertisement `private`: `eth1`(사설망)만. eth0은 vagrant-libvirt 관리망(192.168.121.x) | `platform/metallb/pool.yaml` |
| 쓰는 Service | ingress-nginx-controller 하나(192.168.122.240) | `platform/ingress-nginx/overlay/service-patch.yaml` |
| Pod | controller 1개, speaker DaemonSet 5개(노드마다) | |

libvirt `default` 망(virbr0)의 DHCP 범위는 192.168.122.100~199다. 2026-10-15 MetalLB를 넣으며 .2~.254에서 줄여, 풀(.240~.250)과 노드 고정 IP(.10~.14)가 DHCP와 겹치지 않는다(`virsh net-dumpxml default`).

### cert-manager

- helm 값(`platform/cert-manager/values.yaml`): `crds.enabled: true`, `dns01RecursiveNameservers: "8.8.8.8:53,8.8.4.4:53"`, `dns01RecursiveNameserversOnly: true`(1.1.1.1:53은 이 망에서 시간 초과라 쓰지 않는다)
- ClusterIssuer 둘(`platform/cert-manager/cluster-issuer.yaml`): `letsencrypt-staging`, `letsencrypt-prod`. 둘 다 ACME DNS-01, Cloudflare, `dnsZones: ["ronanlab.dev"]`, 토큰은 Secret `cert-manager/cloudflare-api-token`(key `api-token`, 저장소에 없다. 사람이 만든다)
- Certificate 다섯, 모두 `letsencrypt-prod`, 모두 Ready:

| Certificate(= Secret 이름) | ns | 도메인 | 파일 |
| --- | --- | --- | --- |
| `argocd-ingress-tls` | argocd | argocd.ronanlab.dev | `platform/cert-manager/argocd-certificate.yaml` |
| `harbor-tls` | harbor | harbor.ronanlab.dev | `platform/cert-manager/harbor-certificate.yaml` |
| `jenkins-tls` | jenkins | jenkins.ronanlab.dev | `platform/cert-manager/jenkins-certificate.yaml` |
| `grafana-tls` | monitoring | grafana.ronanlab.dev | `apps/monitoring/ingress.yaml`(ArgoCD `monitoring` 앱, 2026-11-11) |
| `prometheus-tls` | monitoring | prometheus.ronanlab.dev | `apps/monitoring/ingress.yaml`(같음) |

- ArgoCD 쪽 이름을 `argocd-server-tls`로 두지 않은 까닭: argocd-server가 그 이름의 Secret을 자기 서버 인증서로 집어 간다(파일 주석)
- 갱신은 cert-manager가 한다

### Harbor 이름을 어디로 푸나

| 누가 | `harbor.ronanlab.dev`를 어디로 | 어떻게 | 파일 |
| --- | --- | --- | --- |
| 노드 kubelet · containerd | MetalLB VIP 192.168.122.240 | 노드 `/etc/hosts`(kubelet은 클러스터 DNS를 쓰지 않는다). 프로비저너가 옛 Harbor 줄을 지우고 `192.168.122.240 harbor.ronanlab.dev`를 넣는다 | `cluster/Vagrantfile` |
| 클러스터 안 Pod(Jenkins 빌드 등) | ingress-nginx ClusterIP Service | CoreDNS `rewrite stop { name exact harbor.ronanlab.dev ingress-nginx-controller.ingress-nginx.svc.cluster.local; answer auto }` | `platform/coredns/configmap.yaml` |

- 두 길 모두 이미지 이름이 어디서나 `harbor.ronanlab.dev`로 같고, Harbor 토큰 주소(`https://harbor.ronanlab.dev/service/token`)도 같은 길로 가며 Let's Encrypt 인증서로 검증된다
- harbor-core Service로 바로 보내지 않는 까닭: Harbor가 토큰 주소를 `https://<요청 호스트>/service/token`으로 내려주는데 harbor-core는 80만 연다
- `answer auto`는 응답 이름을 `harbor.ronanlab.dev`로 되돌린다. AAAA는 빈 응답이라 공개 IPv6로 새지 않는다
- 클러스터의 Corefile에 이 rewrite 블록이 들어 있다(2026-11-12 확인)

### 처음 한 번 (다시 세울 때)

`platform/`은 ArgoCD 밖이라 사람이 넣는다. MetalLB · cert-manager를 넣은 helm 명령은 어디에도 남아 있지 않아(호스트 `~/k8s-cluster/backup/2026-10-15-before-metallb/ROLLBACK.md`에는 순서 · 시각만), 2026-11-12 배포된 릴리스에서 차트 저장소 · 이름 · 버전 · values를 뽑아 다시 적었다. 값(토큰)은 적지 않는다.

**확인한 것(2026-11-12, 조회만)**
- helm 릴리스 넷(metallb · cert-manager · harbor · jenkins)의 사용자 values가 저장소 `platform/*/values.yaml`과 같다. 다른 것은 Harbor `registry.size`(배포 20Gi, 저장소 30Gi, existingClaim이라 쓰이지 않음) 하나와 저장소에 두지 않는 `harborAdminPassword`
- 저장소 values로 `helm template`한 매니페스트가 배포된 매니페스트(`helm get manifest`)와 같다. Secret(무작위 값) · checksum 줄을 빼고 비교했고, 렌더에만 있는 것은 hook · test(cert-manager `startupapicheck`, jenkins `jenkins-ui-test`)뿐이다
- `kubectl diff`가 0줄: `platform/metallb/pool.yaml`, `platform/cert-manager/` 다섯 파일, `platform/coredns/configmap.yaml`, `platform/argocd/ingress.yaml`, `platform/harbor/pvc-w3.yaml`, `kubectl diff -k platform/ingress-nginx/overlay`
- metallb-system · cert-manager 네임스페이스에는 helm `--create-namespace`가 붙이는 `name` 레이블이 있다(그 옵션으로 만들었다)

**저장소를 m-k8s로 옮기기**: m-k8s에는 이 저장소가 없다(옛 `~/infra`만 있다). 호스트에서 `platform/`을 묶어 넘기고, 아래 명령은 m-k8s의 `~/platform-apply`에서 친다.

```bash
# 호스트
cd ~/ronanlab-infra && tar czf - platform | (cd ~/k8s-cluster && vagrant ssh m-k8s -c 'rm -rf ~/platform-apply && mkdir ~/platform-apply && tar xzf - -C ~/platform-apply')
cd ~/k8s-cluster && vagrant ssh m-k8s        # 이후 m-k8s: cd ~/platform-apply
```

**순서**(kubeadm · Calico는 [01_cluster.md](01_cluster.md))

```bash
# 1. metrics-server: 처음엔 latest 로 깔았다(2026-10-06). 지금 이미지가 v0.9.0 이라 그 버전으로 고정해 적는다
kubectl apply -f https://github.com/kubernetes-sigs/metrics-server/releases/download/v0.9.0/components.yaml
kubectl -n kube-system patch deployment metrics-server --type=json \
  -p='[{"op":"add","path":"/spec/template/spec/containers/0/args/-","value":"--kubelet-insecure-tls"}]'

# 2. local-path-provisioner, 기본 StorageClass
kubectl apply -f https://raw.githubusercontent.com/rancher/local-path-provisioner/v0.0.30/deploy/local-path-storage.yaml
kubectl patch storageclass local-path -p '{"metadata":{"annotations":{"storageclass.kubernetes.io/is-default-class":"true"}}}'

# 3. MetalLB(먼저 호스트에서 libvirt DHCP 범위를 .100~.199 로 줄인다, 아래)
helm repo add metallb https://metallb.github.io/metallb && helm repo update
helm install metallb metallb/metallb --version 0.16.1 -n metallb-system --create-namespace -f platform/metallb/values.yaml
kubectl apply -f platform/metallb/pool.yaml                       # 컨트롤러 webhook 이 Ready 된 뒤

# 4. ingress-nginx(base 만 apply 하지 않는다. Service 가 NodePort 로 돌아간다)
kubectl apply -k platform/ingress-nginx/overlay

# 5. cert-manager
helm repo add jetstack https://charts.jetstack.io && helm repo update
helm install cert-manager jetstack/cert-manager --version v1.21.2 -n cert-manager --create-namespace -f platform/cert-manager/values.yaml
#     Cloudflare API 토큰: 대시보드 My Profile → API Tokens 에서 권한 Zone·DNS·Edit / Zone·Zone·Read, 영역 ronanlab.dev
#     (권한은 펫퍼민트 docs/02_pipeline/14_deployment.md). 값은 표준 입력으로만
read -rs CF && printf %s "$CF" | kubectl -n cert-manager create secret generic cloudflare-api-token --from-file=api-token=/dev/stdin; unset CF
kubectl apply -f platform/cert-manager/cluster-issuer.yaml       # staging · prod. 처음 발급은 staging 으로 확인(운영은 주간 한도)
#     Certificate 는 그 네임스페이스가 생긴 뒤: argocd-certificate(04) · harbor-certificate(05) · jenkins-certificate(06).
#     grafana · prometheus 인증서는 apps/monitoring/ingress.yaml 에 있어 ArgoCD 가 넣는다

# 6. CoreDNS rewrite(Harbor 를 안쪽으로). kubeadm upgrade 뒤에도 다시 확인한다
kubectl apply -f platform/coredns/configmap.yaml
```

```bash
# 호스트(libvirt 그룹, sudo 없이): MetalLB 풀 · 노드 고정 IP 와 겹치지 않게 DHCP 범위를 줄인다(2026-10-15)
virsh -c qemu:///system net-update default delete ip-dhcp-range "<range start='192.168.122.2' end='192.168.122.254'/>" --live --config
virsh -c qemu:///system net-update default add    ip-dhcp-range "<range start='192.168.122.100' end='192.168.122.199'/>" --live --config
# 노드 /etc/hosts 의 harbor.ronanlab.dev → 192.168.122.240 은 cluster/Vagrantfile 프로비저너가 넣는다(VM 을 처음 만들 때. 기존 VM 은 vagrant provision <노드>)
```

- helm 차트 버전은 `--version`으로 고정한다. 저장소 이름(`metallb` · `jetstack`)은 2026-11-12 m-k8s `helm repo list`와 같다
- 클러스터에만 있는 비밀값은 Secret `cert-manager/cloudflare-api-token`(키 `api-token`) 하나다. 나머지 cert-manager · MetalLB Secret(`letsencrypt-*-account`, `cert-manager-webhook-ca`, `metallb-memberlist`, `metallb-webhook-cert`)은 컨트롤러 · 차트가 만든다
- metrics-server를 v0.9.0 매니페스트로 깔면 지금 것과 같은지는 확인하지 않았다(처음엔 latest였다)

## 2. 왜 이렇게 했나

### metrics-server가 무엇이고 왜 필요한가

`kubectl top nodes` / `kubectl top pods`처럼 **CPU · 메모리 실시간 사용량**을 보여 주는 데 필요한 컴포넌트다. 없으면 `kubectl top`도 안 되고 HPA(Horizontal Pod Autoscaler, 자동 확장)도 못 쓴다. IT시스템엔지니어링 기초 수업 Day6에서 계획한 "각 Pod에 requests/limits를 적고 `kubectl top`으로 실측해 QoS 등급 정하기"에도 먼저 있어야 해서 미리 깔았다.

### PV/PVC와 동적 프로비저닝: 왜 local-path-provisioner인가

Pod는 기본적으로 휘발성이라, Pod가 죽었다 다시 뜨면 그 안의 데이터도 사라진다. 데이터를 영구히 두려면 PV(PersistentVolume, 실제 디스크 공간)와 PVC(PersistentVolumeClaim, Pod가 보내는 "이만큼 저장 공간 줘"라는 요청)를 쓴다.

문제는 PVC가 생겨도 그에 맞는 PV가 실제로 있어야 연결(바인딩)된다는 것이다. 관리자가 매번 PV를 손으로 만들어 두는 "정적 프로비저닝" 대신 **local-path-provisioner**는 "동적 프로비저닝"을 해 준다. PVC가 생기면 그 노드의 로컬 디스크에 디렉터리를 만들어 PV로 바로 연결한다.

"local-path"라는 이름대로 클라우드(AWS EBS 등) 스토리지가 아니라 **그 Pod가 떠 있는 노드의 로컬 디스크를 그대로 쓰는 방식**이다. 자체 서버에 VM으로 꾸린 이 환경에 맞는다. 다만 Pod가 다른 노드로 다시 스케줄되면 데이터가 있는 그 노드로 돌아가야만 쓸 수 있다(Milvus처럼 중요한 데이터는 이 특성을 생각해 설계해야 한다고 적어 두었다. Milvus는 결국 호스트 도커에서 돈다).

### Ingress Controller: 처음에 왜 baremetal provider였나

Ingress Controller는 바깥(또는 클러스터 안)에서 들어오는 HTTP 요청을 각 서비스로 보내는 역할이다. 공식 설치 매니페스트는 provider별로 나뉘는데, AWS/GCP 같은 클라우드용 `deploy.yaml`은 Service 타입이 LoadBalancer라 클라우드의 로드밸런서 자원을 자동으로 만든다. 이 환경은 클라우드가 아니라 자체 서버(물리 머신 위 VM)라 그런 로드밸런서가 없어서, **"baremetal"(직접 설치한 하드웨어 환경)용 매니페스트**를 썼다. 이 경우 Service 타입이 NodePort가 된다.

### LoadBalancer(MetalLB)로 바꾼 까닭 (2026-10-15)

배포 단계에서 NodePort로는 막히는 곳이 나왔다. **노드가 Harbor에서 이미지를 당길 때다.** Harbor는 토큰 주소를 `externalURL + /service/token`으로 알려 주는데 그 값에 포트가 없으므로 노드는 443으로 간다. NodePort(31925)로는 닿을 수 없다. 공개 주소로 나가면 Cloudflare Access에 막힌다.

| 안 | 문제 |
| --- | --- |
| 노드마다 443 → 31925 포워더 | 인증서 검증을 건너뛰어야 하고, 설정이 노드 OS에 흩어져 GitOps 밖에 남는다. 노드를 늘릴 때마다 반복 |
| Harbor `externalURL`을 내부 주소로 | Harbor 전역 값이라 웹 UI 안내 · 외부 `docker login`까지 내부 포트를 가리킨다. http라 자격 증명이 평문 |
| MetalLB L2 (채택) | 컴포넌트가 하나 늘지만, 사설망에서 누구나 표준 포트로 쓰고 설정이 매니페스트에 남는다. 클라우드의 LoadBalancer가 하던 일을 사설 환경에서 대신한다 |

| 항목 | 값 |
| --- | --- |
| VIP | `192.168.122.240` (ingress-nginx) |
| IP 풀 | `.240~.250`, `autoAssign: false`: Service가 이름으로 집어 쓴다 |
| 알리는 인터페이스 | eth1(사설망)만. eth0은 vagrant-libvirt NAT망 |
| BGP | 안 쓴다. FRR을 끈다. Calico가 노드마다 BIRD로 179를 쓴다 |
| 기존 NodePort | 30517 / 31925 그대로 |

### 왜 cert-manager + Let's Encrypt DNS-01인가

인증서는 cert-manager와 Let's Encrypt **DNS-01**로 받는다. DNS-01이라 인바운드 포트를 열 필요가 없고(Access · 터널 뒤라 HTTP-01은 못 쓴다), Cloudflare API 토큰(Secret, 저장소에는 없다)만 있으면 된다. 공인 CA라 노드에 CA를 배포하지 않고도 검증을 켜 둔 채 이미지를 당긴다([05_harbor.md](05_harbor.md)). 처음 발급은 staging으로 확인하고 운영(prod)으로 바꾼다(운영은 주간 발급 한도가 있다).

### 왜 ingress-nginx를 kustomize로 묶나

설치한 업스트림 baremetal 매니페스트(v1.11.3)를 `platform/ingress-nginx/base`에 원본 그대로 두고, 바꿀 것만 overlay로 얹는다. 업스트림을 올릴 때 base 파일만 새 태그로 갈아 끼우고 `kubectl diff -k`로 차이를 볼 수 있다.

### 왜 Harbor 이름을 두 곳에서 따로 푸나

노드의 kubelet · containerd는 클러스터 DNS(CoreDNS)를 쓰지 않고 노드 OS의 이름 해석을 쓴다. 그래서 노드는 `/etc/hosts`로 VIP에, 클러스터 안 Pod는 CoreDNS rewrite로 ingress-nginx Service에 보낸다. 둘 다 같은 이름 · 같은 인증서를 쓰게 된다.

## 3. 진행 기록

### 6단계: metrics-server 설치 (2026-10-06)

#### 설치

```bash
kubectl apply -f https://github.com/kubernetes-sigs/metrics-server/releases/latest/download/components.yaml
```

`latest`라 그날의 최신이 들어온다. 지금 돌고 있는 것은 v0.9.0이다(「1. 지금 구성」).

#### 트러블슈팅: kubelet 인증서 TLS 검증 실패

**증상**: 설치 직후 Pod는 `Running`이지만 `0/1`(준비 안 됨)이 이어지고, `kubectl top nodes`가 `error: Metrics API not available`로 실패했다. 로그:

```bash
kubectl logs -n kube-system deployment/metrics-server | tail -20
```

```txt
tls: failed to verify certificate: x509: cannot validate certificate for 192.168.121.64 because it doesn't contain any IP SANs
```

**원인**: kubeadm이 자동으로 만드는 kubelet TLS 인증서에 IP 주소가 SAN(Subject Alternative Name)으로 들어 있지 않아, metrics-server가 각 노드의 kubelet(10250 포트)에 붙을 때 인증서 검증에 실패한다. kubeadm 환경에서 흔한 문제다(192.168.121.64는 m-k8s의 InternalIP, eth0).

**해결**: metrics-server에 `--kubelet-insecure-tls`를 더했다. 학습 · 사내망 클러스터에서 흔히 쓰는 우회다. 운영이라면 진짜 인증서를 발급하는 것이 정석이지만 이 환경에는 이 정도로 충분하다고 봤다(「4. 남은 한계」).

```bash
kubectl patch deployment metrics-server -n kube-system --type='json' -p='[{"op": "add", "path": "/spec/template/spec/containers/0/args/-", "value": "--kubelet-insecure-tls"}]'
```

#### 최종 확인

```bash
kubectl get pods -n kube-system | grep metrics-server
kubectl top nodes
```

```txt
NAME     CPU(cores)   CPU(%)   MEMORY(bytes)   MEMORY(%)
m-k8s    76m          3%       1643Mi          43%
w1-k8s   69m          3%       1223Mi          32%
w2-k8s   36m          1%       1215Mi          31%
w3-k8s   39m          1%       1307Mi          34%
```

### 7단계: local-path-provisioner(스토리지) 설치 (2026-10-06)

#### 설치

```bash
kubectl apply -f https://raw.githubusercontent.com/rancher/local-path-provisioner/v0.0.30/deploy/local-path-storage.yaml
```

#### 기본 StorageClass로 지정

설치만 하면 `local-path` StorageClass가 생기지만 "기본값"은 아니라서, PVC를 쓸 때마다 `storageClassName: local-path`를 적어야 한다. 기본값으로 두면 이후 PVC가 편하다.

```bash
kubectl patch storageclass local-path -p '{"metadata": {"annotations":{"storageclass.kubernetes.io/is-default-class":"true"}}}'
```

#### 최종 확인

```bash
kubectl get pods -n local-path-storage
kubectl get storageclass
```

```txt
NAME                                     READY   STATUS    RESTARTS   AGE
local-path-provisioner-f5894569c-vp8sl   1/1     Running   0          12s

NAME                   PROVISIONER             RECLAIMPOLICY   VOLUMEBINDINGMODE      ALLOWVOLUMEEXPANSION   AGE
local-path (default)   rancher.io/local-path   Delete          WaitForFirstConsumer   false                  55s
```

### 8단계: Ingress Controller(ingress-nginx) 설치 (2026-10-06)

#### 설치

```bash
kubectl apply -f https://raw.githubusercontent.com/kubernetes/ingress-nginx/controller-v1.11.3/deploy/static/provider/baremetal/deploy.yaml
```

이 URL의 파일이 지금 `platform/ingress-nginx/base/deploy.yaml`이다(2026-10-15부터). 지금은 이 URL이나 base만 apply하지 않는다(「4. 남은 한계」).

#### 최종 확인

```bash
kubectl get pods -n ingress-nginx
kubectl get svc -n ingress-nginx
```

```txt
NAME                                        READY   STATUS      RESTARTS   AGE
ingress-nginx-admission-create-gncws        0/1     Completed   0          23s
ingress-nginx-admission-patch-fzxc5         0/1     Completed   0          23s
ingress-nginx-controller-698946b7fb-rbkmw   1/1     Running     0          23s

NAME                                 TYPE        CLUSTER-IP       EXTERNAL-IP   PORT(S)                      AGE
ingress-nginx-controller             NodePort    10.103.155.223   <none>        80:30517/TCP,443:31925/TCP   23s
ingress-nginx-controller-admission   ClusterIP   10.108.62.95     <none>        443/TCP                      23s
```

`ingress-nginx-admission-create/patch`는 Ingress Controller의 웹훅 인증서를 한 번 설정하는 1회성 Job이라 `Completed`가 정상이다(계속 떠 있는 Pod가 아니다). `ingress-nginx-controller` Service가 **HTTP는 NodePort 30517, HTTPS는 NodePort 31925**로 열렸다. 처음에는 이 포트를 다음 단계(Cloudflare Tunnel)의 대상으로 생각했지만, 실제로 터널은 NodePort가 아니라 ClusterIP Service(`ingress-nginx-controller.ingress-nginx.svc.cluster.local:443`)를 본다([03_cloudflare_tunnel.md](03_cloudflare_tunnel.md)).

이것으로 6~8단계를 마쳤다. 다음은 Cloudflare Tunnel 연결([03_cloudflare_tunnel.md](03_cloudflare_tunnel.md)).

### 2026-10-15: MetalLB LoadBalancer + 공인 인증서 + CoreDNS rewrite

까닭은 「2. 왜 이렇게 했나」. 손대기 전 상태와 되돌리기 절차는 호스트 `~/k8s-cluster/backup/2026-10-15-before-metallb/ROLLBACK.md`(git 밖)에 있다. 적용 순서(같은 날 18:34~19:04 KST):

1. libvirt `default` 망 DHCP 범위를 .2~.254에서 .100~.199로 줄였다(풀 · 고정 IP와 안 겹치게)
2. MetalLB 0.16.1을 helm으로 넣고(FRR · frr-k8s 끔) 풀 `private`(.240~.250, eth1, autoAssign false)을 apply. 0.16은 frr-k8s가 기본으로 켜져 한 번 깔렸다가 upgrade로 껐다. 그 사이 Calico BIRD(179)는 그대로였다
3. ingress-nginx Service를 LoadBalancer 192.168.122.240으로. ClusterIP 10.103.155.223 · nodePort 30517/31925는 그대로, 터널 연결도 유지됐다
4. cert-manager v1.21.2를 helm으로, ClusterIssuer staging · prod를 만들고 staging으로 시험 발급한 뒤 prod로 `harbor/harbor-tls`. DNS-01 한 번에 약 80초 걸렸다. 이어 Harbor helm에 TLS를 켰다([05_harbor.md](05_harbor.md))
5. 노드 4대 `/etc/hosts`의 Harbor 줄을 192.168.121.179(w1의 eth0 주소, 그때 ingress 컨트롤러가 있던 노드)에서 192.168.122.240으로 바꾸고, 같은 일을 Vagrantfile 프로비저너로 넣었다. kubelet pull이 443 거부에서 인증 단계까지 가게 됐다
6. ingress-nginx를 kustomize(`platform/ingress-nginx/{base,overlay}`)로 옮겨 `kubectl apply -k`. 적용 전후 차이 0, 컨트롤러 재시작 없음
7. Certificate `argocd/argocd-ingress-tls`, `jenkins/jenkins-tls`(letsencrypt-prod)

```bash
kubectl apply -k platform/ingress-nginx/overlay    # base 만 apply 하지 않는다
```

> base만 apply하면 Service가 NodePort로 돌아간다. 패치의 ports에 `protocol: TCP`가 없으면 병합 키(port+protocol)가 맞물리지 않아 nodePort가 무작위로 다시 뽑힌다.

#### 트러블슈팅: 패치에 protocol이 없으면 nodePort가 빠진다

**증상**: overlay를 처음 만들었을 때 렌더링된 Service에서 nodePort가 출력에서 빠졌다.

**원인**: Service `ports`의 전략적 병합 키가 `port`+`protocol`이다. 패치 쪽에 `protocol`이 없으면 업스트림 항목과 맞물리지 않는다.

**해결**: 패치 ports에 `protocol: TCP`를 넣었다(`platform/ingress-nginx/overlay/service-patch.yaml`).

```bash
kubectl -n ingress-nginx get svc
```

```txt
NAME                                 TYPE           CLUSTER-IP       EXTERNAL-IP       PORT(S)                      AGE
ingress-nginx-controller             LoadBalancer   10.103.155.223   192.168.122.240   80:30517/TCP,443:31925/TCP   35d
ingress-nginx-controller-admission   ClusterIP      10.108.62.95     <none>            443/TCP                      35d
```

나머지 두 길(노드 `/etc/hosts`, CoreDNS rewrite)도 같은 VIP · 인증서를 쓴다(「1. 지금 구성」 Harbor 이름 표).

> kubeadm upgrade는 Corefile을 옮겨 적는다. 업그레이드 뒤 `rewrite` 블록이 남았는지 확인한다(`platform/coredns/configmap.yaml`).

### 2026-11-10: ingress-nginx 2개 · 메트릭

`overlay/deployment-patch.yaml`과 `overlay/kustomization.yaml`의 JSON 패치를 더했다. 모든 앱의 입구라 하나가 죽어도 다른 하나가 받게 replicas 2 · 노드 분산(선호)으로, Prometheus가 호스트별 요청 수 · 상태 코드 · 지연을 긁도록 `--enable-metrics=true`와 포트 10254를 열었다(앱에 `/metrics`가 없어 HTTP 지표는 여기서 얻는다). 1개일 때 재시작이 12초 끊김을 내서, 먼저 2개로 늘린 뒤 메트릭을 켰다. 과정은 [08_scale_out.md](08_scale_out.md), 모니터링은 [09_monitoring.md](09_monitoring.md).

### 2026-11-11: Grafana · Prometheus 인증서

`apps/monitoring/ingress.yaml`에 Certificate `grafana-tls`, `prometheus-tls`(letsencrypt-prod)를 더해 인증서가 다섯이 됐다([09_monitoring.md](09_monitoring.md)).

## 4. 남은 한계

- **metrics-server · local-path-provisioner는 저장소에 없다.** URL로 `kubectl apply` 한 뒤 `kubectl patch`로 고쳤다. 다시 깔면 metrics-server는 `latest`라 다른 버전이 들어오고, `--kubelet-insecure-tls` · 기본 StorageClass 지정을 손으로 다시 해야 한다
- **metrics-server가 kubelet 인증서를 검증하지 않는다**(`--kubelet-insecure-tls`). kubelet serving 인증서에 IP SAN을 넣는 정석 방법은 아직 안 했다
- **local-path PV는 노드에 묶인다.** 그 노드가 죽으면 그 PVC를 쓰는 Pod는 다른 노드로 못 간다. 다른 노드로 옮기려면 새 PVC를 만들고 복사해야 한다([08_scale_out.md](08_scale_out.md))
- **ingress-nginx base만 apply하면 안 된다.** Service가 NodePort로 돌아가고 nodePort가 새로 뽑힌다. 반드시 `kubectl apply -k platform/ingress-nginx/overlay`
- **ingress-nginx 업스트림을 올리면 args 순서를 다시 본다.** JSON 패치가 8번 인자를 `test`하므로 순서가 바뀌면 apply가 멈춘다(의도한 안전장치)
- **ingress-nginx 재시작 때 짧은 끊김.** 2개로 늘린 뒤에도 롤링에서 1초 한 번(2026-11-10). [08_scale_out.md](08_scale_out.md) 「남은 한계」
- **MetalLB L2는 VIP를 노드 한 대가 알린다.** 그 노드가 죽으면 다른 speaker가 넘겨받을 때까지 VIP가 잠깐 끊긴다
- **kubeadm upgrade 뒤 CoreDNS rewrite가 남았는지 본다.** upgrade가 Corefile을 옮겨 적는다
- **`platform/` 값은 push로 들어가지 않는다.** 이 문서의 helm · kubectl 적용은 사람이 한다(ArgoCD 밖). MetalLB · cert-manager 설치에 쓴 helm 차트 저장소와 명령은 저장소에 적혀 있지 않다

## 5. 확인 방법

m-k8s에서(`cd ~/k8s-cluster && vagrant ssh m-k8s -c '…'`):

```bash
kubectl top nodes
# 5대 모두 CPU · MEMORY 값
kubectl -n kube-system get deploy metrics-server -o jsonpath='{.spec.template.spec.containers[0].image}{"\n"}{.spec.template.spec.containers[0].args}{"\n"}'
# v0.9.0, args 에 --kubelet-insecure-tls
kubectl get sc
# local-path (default)   rancher.io/local-path   Delete   WaitForFirstConsumer
kubectl -n ingress-nginx get svc ingress-nginx-controller
# LoadBalancer 10.103.155.223 192.168.122.240 80:30517/TCP,443:31925/TCP
kubectl -n ingress-nginx get pods -o wide
# controller 2개, 서로 다른 노드
kubectl get ipaddresspool,l2advertisement -n metallb-system
# private, AUTO ASSIGN false, 192.168.122.240-192.168.122.250, INTERFACES ["eth1"]
helm list -A
# cert-manager v1.21.2, metallb 0.16.1
kubectl get clusterissuer; kubectl get certificate -A
# letsencrypt-prod · staging True, Certificate 다섯 모두 READY True
kubectl -n kube-system get cm coredns -o jsonpath='{.data.Corefile}' | grep -A3 rewrite
# name exact harbor.ronanlab.dev ingress-nginx-controller.ingress-nginx.svc.cluster.local
```

저장소와 클러스터가 같은지(차이가 없어야 한다). m-k8s에는 이 저장소가 없으니 `platform/ingress-nginx`를 그쪽으로 옮겨 놓고 친다:

```bash
kubectl diff -k <옮겨 둔 곳>/ingress-nginx/overlay
```

노드에서(예: `vagrant ssh w1-k8s -c '…'`):

```bash
grep harbor /etc/hosts       # 192.168.122.240 harbor.ronanlab.dev
```

호스트에서:

```bash
virsh -c qemu:///system net-dumpxml default | grep range    # 192.168.122.100 ~ .199
curl -sk -o /dev/null -w '%{http_code}\n' --resolve harbor.ronanlab.dev:443:192.168.122.240 https://harbor.ronanlab.dev/api/v2.0/ping   # 200
```
