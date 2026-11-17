<!--
다루는 곳: cluster/
읽은 커밋: 736d833
-->
# 가상 머신과 노드

클러스터를 이루는 VM 다섯 대의 정의와 랜카드 둘, 노드 설치, 역할 라벨과 배치를 다룬다.

원고: → 「가상 머신과 노드」, → 「VM 다섯 대와 랜카드 둘」, → 「노드 설치」, → 「역할 라벨과 워커 증설」. 클러스터 설치와 Calico는 `docs/03_kubernetes.md`.

## 지금 구성

- VM 다섯 대, 박스 `generic/ubuntu2204`, provider libvirt [code:cluster/Vagrantfile:1-23]
- 다섯 대 모두 Ubuntu 22.04.3 LTS, 커널 5.15.0-91-generic, containerd 2.2.1, kubelet v1.35.9 [docs:history/cluster_state_20261116.md:9-17]
- `vagrant status`로 다섯 대 모두 running(libvirt) [docs:history/cluster_state_20261116.md:17]

| 노드 | 역할 | vCPU | 메모리(MB) | eth1(고정) | eth0(DHCP, InternalIP) | 역할 라벨 |
| --- | --- | --- | --- | --- | --- | --- |
| m-k8s | control-plane | 2 | 4096 | 192.168.122.10 | 192.168.121.64 | 없음 |
| w1-k8s | 워커 | 2 | 8192 | 192.168.122.11 | 192.168.121.179 | app |
| w2-k8s | 워커 | 2 | 8192 | 192.168.122.12 | 192.168.121.95 | app |
| w3-k8s | 워커 | 2 | 8192 | 192.168.122.13 | 192.168.121.158 | infra |
| w4-k8s | 워커 | 2 | 8192 | 192.168.122.14 | 192.168.121.46 | platform |

근거: [code:cluster/Vagrantfile:3-10] [docs:history/cluster_state_20261116.md:9-15] [code:cluster/label-nodes.sh:11-14]

- w4-k8s가 가장 늦게 더한 워커다(나이 5d11h, 나머지 40d). platform 노드 자리로 만들었다 [docs:history/cluster_state_20261116.md:11-15] [code:cluster/Vagrantfile:8-9]
- m-k8s에는 control-plane taint가 있어 일반 Pod가 뜨지 않는다 [docs:history/build_log/08_scale_out.md:17]

### 망

| NIC | libvirt 망 | 대역 | 주소 | 쓰임 |
| --- | --- | --- | --- | --- |
| eth0 | `vagrant-libvirt` | 192.168.121.0/24 | DHCP | `vagrant ssh`, 기본 경로(바깥 인터넷), 노드 InternalIP |
| eth1 | `default`(virbr0) | 192.168.122.0/24 | 고정(`private_network`) | apiserver, Calico IPIP, MetalLB L2 광고, 호스트 서비스 호출(192.168.122.1) |

근거: [docs:history/cluster_state_20261116.md:19-28] [docs:history/cluster_state_20261116.md:80] [docs:history/human_answers_20261116.md:7-13] [code:cluster/Vagrantfile:17]

- eth0은 vagrant-libvirt가 VM마다 기본으로 붙이는 관리망이다. 재부팅마다 주소가 바뀔 수 있어 노드끼리 통신에 쓰지 않는다 [docs:history/human_answers_20261116.md:7]
- eth1은 그래서 따로 붙인 사설 고정 주소망이다 [docs:history/human_answers_20261116.md:9]
- 관리망과 사설 고정망을 나누는 것은 참고한 책(《컨테이너 인프라 환경 구축을 위한 쿠버네티스/도커》, 길벗, 조훈)의 Vagrantfile과 같은 방식이다 [docs:history/human_answers_20261116.md:11]
- MetalLB L2Advertisement는 `interfaces: [eth1]`이다. VIP가 고정 대역 안에 있어서다 [docs:history/cluster_state_20261116.md:33] [docs:history/human_answers_20261116.md:13]
- kubelet에 `--node-ip`가 없어 InternalIP가 eth0 주소로 잡힌다. 의도한 것이 아니라 기본값이 남은 것이다 [docs:history/cluster_state_20261116.md:26] [docs:history/human_answers_20261116.md:15]
- Calico 노드 주소(`projectcalico.org/IPv4Address`)와 다른 노드 Pod 대역으로 가는 경로의 다음 홉은 eth1 주소다 [docs:history/cluster_state_20261116.md:23-24]

### 파일 두 벌

- `cluster/`(git): `Vagrantfile`, `setup-node.sh`, `label-nodes.sh`. 기록과 검토용 [code:CLAUDE.md:16]
- 호스트 `~/k8s-cluster/`(git 아님): `Vagrantfile`, `setup-node.sh`, `.vagrant/`(VM 상태와 SSH 키). 실제로 `vagrant`가 도는 자리 [code:CLAUDE.md:15]
- 겹치는 두 파일은 따로 복사한 파일이고 내용이 같다. `label-nodes.sh`는 저장소에만 있다 [code:CLAUDE.md:16-17]
- `Vagrantfile`은 `setup-node.sh`를 부르지 않는다. 노드 설치는 사람이 넣는다 [code:CLAUDE.md:17]

### 역할 라벨과 배치

| 라벨 값 | 노드 | 올라가는 것 | 그 노드가 죽으면 |
| --- | --- | --- | --- |
| app | w1, w2 | petmint, runshoes 앱(각 2개), MySQL(w1 Primary, w2 Replica) | 앱은 남은 노드가 받는다. w1이면 승격 전까지 DB 쓰기 실패 |
| infra | w3 | Harbor, Jenkins, ArgoCD | 배포와 빌드만 멈춘다 |
| platform | w4 | Prometheus, Grafana, Loki 등 모니터링 | 모니터링만 멈춘다 |

근거: [code:cluster/label-nodes.sh:6-8] [docs:history/build_log/08_scale_out.md:17-31]

- 라벨 키는 `node.ronanlab.dev/role` [code:cluster/label-nodes.sh:10]
- 이 라벨을 nodeSelector로 보는 곳: `apps/petmint/app/deployment.yaml:44`, `apps/runshoes/app/deployment.yaml:49`, `apps/petmint/mysql/replica.yaml:51`, `apps/runshoes/mysql/replica.yaml:45`, `platform/harbor/values.yaml:56-72`, `platform/jenkins/values.yaml:22`, `platform/argocd/pin-infra.sh:7`, `apps/monitoring/` 아래 Deployment와 StatefulSet [code:apps/petmint/app/deployment.yaml:44] [code:apps/runshoes/app/deployment.yaml:49] [code:platform/harbor/values.yaml:56] [code:platform/jenkins/values.yaml:22] [code:platform/argocd/pin-infra.sh:7] [code:apps/monitoring/prometheus/statefulset.yaml:24]
- 배치를 고정하지 않은 것: ingress-nginx, cloudflared, CoreDNS, cert-manager, MetalLB 컨트롤러, local-path-provisioner, Jenkins 빌드 Pod [docs:history/build_log/08_scale_out.md:33-34]

## 설정 자리

| 파일:줄 | 값 | 뜻 |
| --- | --- | --- |
| `cluster/Vagrantfile:1` | `generic/ubuntu2204` | 모든 VM의 박스 [code:cluster/Vagrantfile:1] |
| `cluster/Vagrantfile:3-10` | `NODES` 배열 | 노드 이름, eth1 고정 IP, cpus, memory. 노드를 더하면 여기에 한 줄 [code:cluster/Vagrantfile:3-10] |
| `cluster/Vagrantfile:17` | `private_network`, `ip: node[:ip]` | eth1을 붙이고 고정 IP를 준다 [code:cluster/Vagrantfile:17] |
| `cluster/Vagrantfile:19-23` | `lv.cpus`, `lv.memory`, `machine_virtual_size = 20` | libvirt 자원. 디스크 크기 값은 박스가 따르지 않는다 [code:cluster/Vagrantfile:19-23] [docs:history/build_log/01_cluster.md:356] |
| `cluster/Vagrantfile:25-30` | `resolved.conf.d/dns.conf`에 `DNS=8.8.8.8 1.1.1.1`, `FallbackDNS=8.8.4.4`, `DNSSEC=no` | 박스 기본 DNS(4.2.2.x, DNSSEC=yes)가 이 망에서 잘 안 풀린다 [code:cluster/Vagrantfile:25-30] |
| `cluster/Vagrantfile:32-37` | `/etc/hosts`에 `192.168.122.240 harbor.ronanlab.dev`(옛 줄은 지우고 한 줄) | containerd가 Harbor를 공개 DNS(Cloudflare Access)로 풀지 않고 ingress-nginx MetalLB VIP로 간다 [code:cluster/Vagrantfile:32-37] |
| `cluster/Vagrantfile:39-44` | 워커에만 `nfs-common` | 호스트 192.168.122.1의 NFS PV를 kubelet이 마운트하려면 필요하다 [code:cluster/Vagrantfile:39-44] |
| `cluster/setup-node.sh:2` | `set -e` | 한 줄이라도 실패하면 멈춘다 [code:cluster/setup-node.sh:2] |
| `cluster/setup-node.sh:4-17` | `overlay`, `br_netfilter`, `bridge-nf-call-iptables/ip6tables = 1`, `ip_forward = 1` | 파일로 남기고 바로 적용 [code:cluster/setup-node.sh:4-17] |
| `cluster/setup-node.sh:19-24` | `swapoff -a`, fstab swap 줄 주석(공백과 탭 모두), 남으면 `exit 1` | 박스 fstab이 탭 구분이라 공백만 찾던 옛 패턴은 재부팅 뒤 swap을 되살렸다 [code:cluster/setup-node.sh:19-24] [docs:history/build_log/01_cluster.md:500-506] |
| `cluster/setup-node.sh:28` | `CONTAINERD_VERSION="2.2.1-0ubuntu1~22.04.2"` | containerd 판 고정 [code:cluster/setup-node.sh:28] |
| `cluster/setup-node.sh:29` | `K8S_PKG_VERSION="1.35.9-1.1"` | kubelet, kubeadm, kubectl 판 고정 [code:cluster/setup-node.sh:29] |
| `cluster/setup-node.sh:34` | `SystemdCgroup = true` | kubelet과 같은 systemd cgroup 드라이버 [code:cluster/setup-node.sh:34] [docs:history/build_log/01_cluster.md:424] |
| `cluster/setup-node.sh:39` | `K8S_VERSION="v1.35"` | pkgs.k8s.io 저장소 줄기 [code:cluster/setup-node.sh:39-43] |
| `cluster/setup-node.sh:46` | `apt-mark hold kubelet kubeadm kubectl containerd` | `apt upgrade`로 오르지 않게 [code:cluster/setup-node.sh:46] |
| `cluster/label-nodes.sh:11-14` | w1, w2 `app`, w3 `infra`, w4 `platform`, `--overwrite` | 여러 번 돌려도 같다 [code:cluster/label-nodes.sh:3] [code:cluster/label-nodes.sh:11-14] |

- 패키지 판까지 고정한 까닭: 저장소 줄기(`v1.35`)만 고정하면 설치하는 날의 최신 패치가 들어와, 나중에 더한 노드의 kubelet이 apiserver보다 높아질 수 있다 [docs:history/build_log/01_cluster.md:174]
- 노드 설정은 손으로 넣지 않고 프로비저너로만 넣는다. 손으로 넣은 DNS 설정이 코드에 없어 새 노드(w4)가 처음에 apt를 받지 못한 일이 있었다 [docs:history/build_log/01_cluster.md:184] [docs:history/build_log/01_cluster.md:663]

## 바꾸거나 다시 만들기

VM 만들기, 끄기, `vagrant ssh`는 호스트 `~/k8s-cluster`에서 한다. `.vagrant/` 상태가 거기에만 있어 `cluster/`에서 `vagrant up`을 치면 기존 VM을 모르고 새로 만들려 한다 [code:CLAUDE.md:18]

설정을 바꿀 때:

```bash
# cluster/ 와 ~/k8s-cluster/ 를 같이 고치고 cluster/ 를 커밋한다
cmp ~/k8s-cluster/Vagrantfile cluster/Vagrantfile && cmp ~/k8s-cluster/setup-node.sh cluster/setup-node.sh   # 출력 없음
# 프로비저너는 VM을 처음 만들 때만 돈다. 기존 노드에 넣으려면
cd ~/k8s-cluster && vagrant provision <노드>
```

근거: [code:CLAUDE.md:17-18] [docs:history/build_log/01_cluster.md:73]

워커 더하기(w4를 더한 절차, 새 이름은 예시) [docs:history/build_log/01_cluster.md:87]:

```bash
free -g                                   # 호스트 available 이 새 노드 메모리 + 여유보다 커야 한다
# 1. 양쪽 Vagrantfile 의 NODES 에 한 줄(이름, 192.168.122.x, cpus, memory)
cd ~/k8s-cluster && vagrant up w5-k8s
# 2. 같은 판 설치
cat setup-node.sh | vagrant ssh w5-k8s -- 'bash -s'
# 3. join. 토큰을 화면에 내지 않는다(15분짜리)
J=$(vagrant ssh m-k8s -c 'sudo kubeadm token create --ttl 15m --print-join-command' 2>/dev/null | tr -d '\r')
echo "$J" | vagrant ssh w5-k8s -c 'read -r C; sudo $C'; unset J
# 4. cluster/label-nodes.sh 에 줄을 더해 m-k8s 에서 다시 돌린다
```

근거: [docs:history/build_log/01_cluster.md:89-99] [code:cluster/label-nodes.sh:3-4]

- 새 IP는 `default` 망의 DHCP 범위와 MetalLB 풀(192.168.122.240-250) 밖에서 고른다. DHCP 범위는 `docs/04_ingress.md` [docs:history/cluster_state_20261116.md:32]
- 노드를 새로 만들거나 다시 join하면 역할 라벨이 없다. `bash cluster/label-nodes.sh`를 m-k8s에서 다시 돌린다 [code:cluster/label-nodes.sh:3-4]
- 노드 정비(cordon, 앱 Pod 먼저 drain, halt, up, uncordon) 순서는 옛 기록 `docs/history/build_log/08_scale_out.md` 1-5절에 있다. VM 끄기(`vagrant halt`, `virsh` 메모리 바꾸기 포함)는 사람 승인이 필요하다 [docs:history/build_log/08_scale_out.md:81-96] [code:CLAUDE.md:37-41]

## 확인

m-k8s에서(`cd ~/k8s-cluster && vagrant ssh m-k8s -c '…'`) [code:CLAUDE.md:27]:

```bash
kubectl get nodes -o wide
# 5대 Ready, v1.35.9, containerd://2.2.1, INTERNAL-IP 는 192.168.121.x(eth0)
kubectl get nodes -L node.ronanlab.dev/role
# m-k8s 비어 있음, w1 w2 app, w3 infra, w4 platform
kubectl get nodes -o jsonpath='{range .items[*]}{.metadata.name} {.metadata.annotations.projectcalico\.org/IPv4Address}{"\n"}{end}'
# 노드마다 eth1 주소(192.168.122.x/24)
```

노드에서(`vagrant ssh <노드> -c '…'`):

```bash
ip -4 addr show eth1          # 192.168.122.1x/24
grep harbor /etc/hosts        # 192.168.122.240 harbor.ronanlab.dev
cat /etc/systemd/resolved.conf.d/dns.conf
swapon --show | wc -l         # 0
```

근거: [docs:history/cluster_state_20261116.md:9-26] [docs:history/build_log/01_cluster.md:711-737]

새 노드를 더한 뒤에는 calico-node와 metallb speaker가 그 노드에서 Running인지, 그 노드에 고정한 시험 Pod로 Harbor pull, 클러스터 DNS, NFS 마운트가 되는지 본다 [docs:history/build_log/01_cluster.md:99]

## 알려진 한계

- InternalIP가 eth0(관리망) 주소다. `kubectl get nodes -o wide`가 보여 주는 주소와 실제 클러스터 통신 주소(eth1)가 다르다 [docs:history/cluster_state_20261116.md:9-15] [docs:history/cluster_state_20261116.md:23-26]
- InternalIP를 쓰는 기능은 관리망 주소를 쓴다. 예: Prometheus `kubelet-cadvisor` 작업은 `role: node` 서비스 디스커버리로 노드 IP:10250을 긁는다 [code:apps/monitoring/prometheus/configmap.yaml:33-43]
- eth0 주소는 재부팅 때 바뀔 수 있고, 바뀌면 InternalIP도 바뀐다 [docs:history/human_answers_20261116.md:7] [docs:history/human_answers_20261116.md:15]
- 프로비저너는 VM을 처음 만들 때만 돈다 [docs:history/build_log/01_cluster.md:704]
- 같은 파일 두 벌(`cluster/`와 `~/k8s-cluster/`)이 따로 복사돼 있다. 한쪽만 고치면 어긋난다 [code:CLAUDE.md:17-18]
- infra(w3), platform(w4)은 노드가 하나씩이다. app 노드는 둘이다 [docs:history/build_log/08_scale_out.md:433-434]
- 컨트롤 플레인이 한 대다 [docs:history/build_log/01_cluster.md:700]
- VM 다섯 대가 같은 물리 서버에 있다 [docs:history/build_log/08_scale_out.md:436]
- Jenkins 빌드 Pod는 배치가 고정되지 않아 app 노드에 뜰 수 있다 [docs:history/build_log/08_scale_out.md:440]
