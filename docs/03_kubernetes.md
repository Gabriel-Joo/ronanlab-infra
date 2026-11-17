<!--
다루는 곳: platform/versions.yaml, platform/coredns/
읽은 커밋: 736d833
-->
# 쿠버네티스 설치와 파드 망

kubeadm으로 세운 클러스터의 판과 설치, Calico 파드 망, CoreDNS 설정을 다룬다.

원고: → 「쿠버네티스 설치와 파드 망」. VM과 노드 설치는 `docs/02_nodes.md`.

## 지금 구성

- kubeadm v1.35.9. kubelet, kubectl, 컨트롤 플레인 이미지 모두 같은 판 [code:platform/versions.yaml:9]
- containerd 2.2.1 [code:platform/versions.yaml:10] [docs:history/cluster_state_20261116.md:17]
- 컨트롤 플레인 m-k8s 1대, 워커 w1~w4 4대, 모두 v1.35.9 [docs:history/cluster_state_20261116.md:9-15]
- apiserver는 eth1 쪽 주소(192.168.122.10)로 알린다. init 때 `--apiserver-advertise-address=192.168.122.10` [docs:history/build_log/01_cluster.md:524-529] [docs:history/human_answers_20261116.md:9]
- Pod 대역 10.244.0.0/16, Service 대역 10.96.0.0/12(kubeadm 기본) [code:platform/versions.yaml:11-12] [docs:history/build_log/01_cluster.md:49]
- Calico v3.28.0, 업스트림 매니페스트 URL을 `kubectl apply`로 넣었다. 저장소에 매니페스트가 없다 [code:platform/versions.yaml:14-18]
- calico-node(DaemonSet, 노드마다 1개)와 calico-kube-controllers(1개) [docs:history/build_log/01_cluster.md:604-605]
- calico-node 환경: `IP=autodetect`, `CALICO_IPV4POOL_IPIP=Always`, `CALICO_IPV4POOL_VXLAN=Never` [docs:history/cluster_state_20261116.md:25]
- 자동 감지 결과 Calico 노드 주소는 eth1 주소다(m-k8s 192.168.122.10/24, w1 192.168.122.11/24) [docs:history/cluster_state_20261116.md:24]
- 다른 노드의 Pod 대역으로 가는 경로는 eth1 주소(192.168.122.11~14)를 다음 홉으로 `tunl0`(IPIP)을 탄다 [docs:history/cluster_state_20261116.md:23]
- 노드 InternalIP는 eth0 주소다(kubelet `--node-ip` 없음). Pod 통신 경로와 다르다 [docs:history/cluster_state_20261116.md:26]
- CoreDNS 설정은 kubeadm 기본 Corefile에 Harbor 이름 rewrite를 더한 것이다 [code:platform/coredns/configmap.yaml:1]
- `platform/`은 ArgoCD 밖이다. push로 바뀌지 않는다 [code:CLAUDE.md:13]

## 설정 자리

### platform/versions.yaml

설치기가 읽지 않는 기록이다. 클러스터에만 남아 있던 판을 다시 만들 때 같은 판을 깔려고 적었다. 판을 올리면 같은 커밋에서 고친다 [code:platform/versions.yaml:1-6] [docs:history/human_answers_20261116.md:19]

| 줄 | 값 | 뜻 |
| --- | --- | --- |
| 8-12 | kubeadm v1.35.9, containerd 2.2.1, pod_subnet, service_subnet | 클러스터 자체 [code:platform/versions.yaml:8-12] |
| 16-18 | Calico v3.28.0 매니페스트 URL | CNI [code:platform/versions.yaml:16-18] |
| 19-22 | metrics-server v0.9.0 | 설치 뒤 `kubectl patch`로 `--kubelet-insecure-tls`를 더했다 [code:platform/versions.yaml:19-22] |
| 23-26 | local-path-provisioner v0.0.30 | 설치 뒤 기본 StorageClass로 patch했다 [code:platform/versions.yaml:23-26] |
| 27-30 | ArgoCD v2.13.2 | 설치 뒤 `platform/argocd/pin-infra.sh`를 다시 돌린다. `docs/06_gitops.md` [code:platform/versions.yaml:27-30] |
| 33-53 | helm: cert-manager v1.21.2, metallb 0.16.1, harbor 1.19.2(앱 2.15.2), jenkins 5.9.68(앱 2.580.1) | 각 편. values는 `platform/<이름>/values.yaml` [code:platform/versions.yaml:32-53] |

- 판과 helm 릴리스는 클러스터에서 본 값과 같다 [docs:history/cluster_state_20261116.md:65-67]
- containerd와 k8s 패키지의 정확한 패키지 판(`2.2.1-0ubuntu1~22.04.2`, `1.35.9-1.1`)은 `cluster/setup-node.sh`가 고정한다 [code:cluster/setup-node.sh:28-29]

### platform/coredns/configmap.yaml

| 줄 | 값 | 뜻 |
| --- | --- | --- |
| 16 | `.:53` | 모든 이름, 53번 [code:platform/coredns/configmap.yaml:16] |
| 17-21 | `errors`, `health { lameduck 5s }`, `ready` | 오류 기록, 상태 확인 [code:platform/coredns/configmap.yaml:17-21] |
| 22-25 | `rewrite stop { name exact harbor.ronanlab.dev ingress-nginx-controller.ingress-nginx.svc.cluster.local; answer auto }` | Harbor 이름을 ingress-nginx 내부 Service로 풀고, 응답 이름은 harbor.ronanlab.dev로 되돌린다 [code:platform/coredns/configmap.yaml:22-25] |
| 26-30 | `kubernetes cluster.local in-addr.arpa ip6.arpa`, `pods insecure`, `ttl 30` | 클러스터 안 이름 [code:platform/coredns/configmap.yaml:26-30] |
| 31 | `prometheus :9153` | 지표 [code:platform/coredns/configmap.yaml:31] |
| 32-34 | `forward . /etc/resolv.conf`, `max_concurrent 1000` | 그 밖의 이름은 노드의 resolv.conf로 [code:platform/coredns/configmap.yaml:32-34] |
| 35-38 | `cache 30`, `disable success/denial cluster.local` | 바깥 이름만 캐시하고 클러스터 안 이름은 캐시하지 않는다 [code:platform/coredns/configmap.yaml:35-38] |
| 39-41 | `loop`, `reload`, `loadbalance` | 루프 감지, 설정 다시 읽기(30초 안), 응답 순서 섞기 [code:platform/coredns/configmap.yaml:2] [code:platform/coredns/configmap.yaml:39-41] |

- rewrite를 둔 까닭: Pod가 harbor.ronanlab.dev를 공개 DNS(Cloudflare Access)로 풀지 않게 한다. 노드 `/etc/hosts`(MetalLB VIP)와 같은 일을 클러스터 안에서 한다 [code:platform/coredns/configmap.yaml:3-4] [code:cluster/Vagrantfile:32-36]
- harbor-core Service로 바로 보내지 않는 까닭: Harbor가 토큰 주소를 `https://<요청 호스트>/service/token`으로 내려 주는데 harbor-core는 80만 연다. ingress-nginx를 거치면 Let's Encrypt 인증서로 검증된다 [code:platform/coredns/configmap.yaml:5-7]
- AAAA는 빈 응답이라 공개 IPv6로 새지 않는다 [code:platform/coredns/configmap.yaml:7]

## 바꾸거나 다시 만들기

컨트롤 플레인(처음 만들 때, m-k8s에서) [docs:history/build_log/01_cluster.md:521-561]:

```bash
sudo kubeadm init \
  --apiserver-advertise-address=192.168.122.10 \
  --pod-network-cidr=10.244.0.0/16
mkdir -p $HOME/.kube && sudo cp -i /etc/kubernetes/admin.conf $HOME/.kube/config && sudo chown $(id -u):$(id -g) $HOME/.kube/config
kubectl apply -f https://raw.githubusercontent.com/projectcalico/calico/v3.28.0/manifests/calico.yaml
kubectl apply -f platform/coredns/configmap.yaml
```

근거: [docs:history/build_log/01_cluster.md:524-526] [docs:history/build_log/01_cluster.md:543-545] [code:platform/versions.yaml:16-18] [code:platform/coredns/configmap.yaml:2]

- `--apiserver-advertise-address`를 주지 않으면 kubeadm이 eth0(DHCP) 주소를 고를 수 있다 [docs:history/build_log/01_cluster.md:529]
- Pod 대역은 Calico 기본값(192.168.0.0/16)이 사무실 망과 VM 망(192.168.122.0/24), vagrant-libvirt 관리망(192.168.121.0/24)을 덮어서 따로 골랐다 [docs:history/build_log/01_cluster.md:151-159] [docs:history/cluster_state_20261116.md:28]
- 워커 join은 `docs/02_nodes.md` 「바꾸거나 다시 만들기」. 토큰은 화면에 내지 않고 15분짜리로 새로 만든다 [docs:history/build_log/01_cluster.md:638-645]
- 저장소 밖 설치물은 `platform/versions.yaml`의 판과 URL로 다시 깐다. 판을 올리면 그 파일도 같은 커밋에서 고친다 [code:platform/versions.yaml:6]
- CoreDNS 설정을 바꾸면 `kubectl apply -f platform/coredns/configmap.yaml`. reload가 30초 안에 다시 읽는다 [code:platform/coredns/configmap.yaml:2]
- `kubeadm upgrade` 뒤에는 Corefile에 rewrite 블록이 남았는지 본다 [code:platform/coredns/configmap.yaml:8]
- k8s 판을 올리면 `cluster/setup-node.sh`(`K8S_VERSION`, `K8S_PKG_VERSION`)와 `platform/versions.yaml`을 같이 고친다 [code:cluster/setup-node.sh:29] [code:cluster/setup-node.sh:39] [code:platform/versions.yaml:6]

## 확인

m-k8s에서(`cd ~/k8s-cluster && vagrant ssh m-k8s -c '…'`) [code:CLAUDE.md:27]:

```bash
kubectl get nodes
# 5대 Ready, v1.35.9
kubectl -n kube-system get ds calico-node
# DESIRED 5 READY 5
kubectl get ippools.crd.projectcalico.org -o custom-columns=CIDR:.spec.cidr,IPIP:.spec.ipipMode
# 10.244.0.0/16 Always
kubectl -n kube-system get cm kubeadm-config -o jsonpath='{.data.ClusterConfiguration}' | grep -E 'kubernetesVersion|podSubnet|serviceSubnet'
# v1.35.9, 10.244.0.0/16, 10.96.0.0/12
kubectl -n kube-system get cm coredns -o jsonpath='{.data.Corefile}' | grep -A2 rewrite
# name exact harbor.ronanlab.dev ingress-nginx-controller.ingress-nginx.svc.cluster.local
ip route | grep tunl0     # 다른 노드 Pod 대역 via 192.168.122.1x dev tunl0
```

근거: [docs:history/build_log/01_cluster.md:711-722] [docs:history/cluster_state_20261116.md:23] [code:platform/versions.yaml:5] [code:platform/coredns/configmap.yaml:22-25]

## 알려진 한계

- 컨트롤 플레인이 한 대다. m-k8s가 죽으면 떠 있는 Pod는 돌지만 스케줄, 복구, kubectl이 멈춘다 [docs:history/build_log/01_cluster.md:700]
- Calico, metrics-server, local-path, ArgoCD 매니페스트는 저장소에 없다. 판과 URL만 `platform/versions.yaml`에 있다 [code:platform/versions.yaml:14-30]
- `platform/versions.yaml`은 손으로 맞추는 기록이라 클러스터와 저절로 맞지 않는다 [code:platform/versions.yaml:3-6]
- `kubeadm upgrade`가 Corefile을 옮겨 적는다. rewrite가 빠지면 Pod가 harbor.ronanlab.dev를 공개 DNS(Cloudflare Access)로 푼다 [code:platform/coredns/configmap.yaml:3] [code:platform/coredns/configmap.yaml:8]
- 노드 InternalIP가 eth0이다. 영향은 `docs/02_nodes.md` 「알려진 한계」 [docs:history/cluster_state_20261116.md:26]
- 저장소 매니페스트에 NetworkPolicy가 없다. Calico를 고른 까닭(NetworkPolicy 기본 포함)은 아직 쓰지 않는다 [docs:history/build_log/01_cluster.md:178] [code:apps/] [code:platform/]
- IPIP를 고른 까닭은 기록에 없다 [docs:history/cluster_state_20261116.md:25]
