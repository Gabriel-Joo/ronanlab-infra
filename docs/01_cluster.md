# 01. 클러스터 구축

GPU 호스트 한 대 위에 KVM/libvirt와 Vagrant로 VM 5대(컨트롤 플레인 1, 워커 4)를 띄우고 kubeadm 1.35.9와 Calico로 묶었다.
VM 정의는 `cluster/Vagrantfile`, 노드 설치는 `cluster/setup-node.sh`이고 둘 다 버전을 고정했다.

- 날짜: 2026-10-06 구축(VM 4대), 2026-11-10 증설(w4 추가, 워커 4GB에서 8GB로), 2026-11-12 코드 · 클러스터와 맞춤
- 범위: 호스트 가상화, VM, 노드 설치(containerd · kubeadm · kubelet · kubectl), kubeadm init · join, CNI(Calico).
  metrics-server · 스토리지 · Ingress · MetalLB는 [02_metrics_storage_ingress.md](02_metrics_storage_ingress.md), 노드 역할 배치 · 장애 시나리오 · 정비 절차는 [08_scale_out.md](08_scale_out.md)
- 코드: `cluster/Vagrantfile`, `cluster/setup-node.sh`, `cluster/label-nodes.sh`. 앞의 둘은 호스트 `~/k8s-cluster/`에 따로 복사한 같은 파일이 있다(실제로 `vagrant`가 도는 곳)

## 1. 지금 구성

2026-11-12 기준. `kubectl get nodes -o wide`, `virsh net-list`, 노드 `df -h /`로 확인했다.

### 호스트와 VM

```
[GPU 호스트: Ubuntu 26.04.1, 32코어, RAM 61GB, RTX 5070 Ti]  Ollama · Milvus(도커), NFS(약관 ro, 백업 rw)
  └ KVM/libvirt ← Vagrant 2.4.9 + vagrant-libvirt 0.12.2   ~/k8s-cluster (저장소 사본: cluster/)
      m-k8s   192.168.122.10  2 vCPU  4GB   컨트롤 플레인
      w1-k8s  192.168.122.11  2 vCPU  8GB   워커(역할 app)
      w2-k8s  192.168.122.12  2 vCPU  8GB   워커(역할 app)
      w3-k8s  192.168.122.13  2 vCPU  8GB   워커(역할 infra)
      w4-k8s  192.168.122.14  2 vCPU  8GB   워커(역할 platform, 2026-11-10 추가)
```

- VM 합계 10 vCPU / 36GB(2026-11-10에 16GB에서 36GB로). 호스트에 남는 메모리는 약 25GB(`free -g` available)이고 Ollama 모델 · 학습과 같이 쓴다
- 노드 역할 라벨 `node.ronanlab.dev/role`은 `cluster/label-nodes.sh`가 붙인다. 무엇을 어디에 두는지는 [08_scale_out.md](08_scale_out.md) 「1. 지금 구성」
- 디스크: 박스 가상 디스크 128GiB(씬 프로비저닝), LVM VG 126GB. 루트 `/`는 m · w1 · w2 · w4가 62GB, w3만 92GB다(2026-11-10 Harbor 이사 때 VG 남은 공간에서 30GB를 붙였다, 08 참고)

### 네트워크

노드마다 NIC가 둘이다.

| NIC | libvirt 망 | 대역 | 쓰임 |
| --- | --- | --- | --- |
| eth0 | `vagrant-libvirt`(virbr1) | 192.168.121.0/24, DHCP | `vagrant ssh`, 바깥 인터넷(NAT). 노드 InternalIP가 이쪽으로 잡혀 있다(kubelet `--node-ip` 없음) |
| eth1 | `default`(virbr0) | 192.168.122.0/24, 노드는 고정 IP(Vagrantfile `private_network`) | apiserver(192.168.122.10:6443), Calico 노드 간 IPIP 터널, MetalLB VIP, 호스트 서비스(192.168.122.1) |

| 노드 | eth0(DHCP) | eth1(고정) |
| --- | --- | --- |
| m-k8s | 192.168.121.64 | 192.168.122.10 |
| w1-k8s | 192.168.121.179 | 192.168.122.11 |
| w2-k8s | 192.168.121.95 | 192.168.122.12 |
| w3-k8s | 192.168.121.158 | 192.168.122.13 |
| w4-k8s | 192.168.121.46 | 192.168.122.14 |

- `default` 망의 DHCP 범위는 192.168.122.100~199다(2026-10-15 MetalLB를 넣으며 .2~.254에서 줄였다). 노드 고정 IP(.10~.14)와 MetalLB 풀(.240~.250)은 그 밖이다
- Pod 대역 10.244.0.0/16(Calico IPPool `default-ipv4-ippool`, IPIP Always, VXLAN Never). Service 대역 10.96.0.0/12(kubeadm 기본)
- Calico는 노드 주소를 eth1(192.168.122.x)로 잡는다(노드 어노테이션 `projectcalico.org/IPv4Address`, `tunl0` 경로가 `via 192.168.122.x`)
- MetalLB L2 풀 192.168.122.240~250, ingress-nginx VIP 192.168.122.240(02 문서)

### 버전: 모든 노드가 같다

| 것 | 버전 | 어디서 |
| --- | --- | --- |
| 박스 | generic/ubuntu2204 4.3.12 (Ubuntu 22.04.3, 커널 5.15.0-91) | Vagrantfile |
| containerd | 2.2.1-0ubuntu1~22.04.2 (`SystemdCgroup = true`) | setup-node.sh |
| kubeadm · kubelet · kubectl | 1.35.9-1.1 (`apt-mark hold`) | setup-node.sh |
| Calico | v3.28.0 매니페스트(calico-node DaemonSet, calico-kube-controllers) | kubeadm init 뒤 한 번 |
| CoreDNS | v1.13.1 (kubeadm 기본, Corefile은 `platform/coredns/configmap.yaml`) | kubeadm |

### Vagrantfile(지금 판)

`NODES` 배열에 다섯 노드(이름 · eth1 IP · cpus · memory)를 적고, 노드마다 같은 박스 · 호스트 이름 · `private_network` · libvirt 자원(cpus · memory · `machine_virtual_size = 20`)을 준다. 거기에 셸 프로비저너 셋이 붙는다.

| 프로비저너 | 하는 일 | 왜 |
| --- | --- | --- |
| DNS | `/etc/systemd/resolved.conf.d/dns.conf`에 `DNS=8.8.8.8 1.1.1.1`, `FallbackDNS=8.8.4.4`, `DNSSEC=no` 쓰고 systemd-resolved 재시작 | 박스 기본(4.2.2.x, DNSSEC=yes)이 이 망에서 잘 안 풀린다. 2026-10-13 손으로 넣은 것을 2026-11-10 여기로 옮겼다 |
| Harbor 이름 | `/etc/hosts`의 기존 `harbor.ronanlab.dev` 줄을 지우고 `192.168.122.240 harbor.ronanlab.dev`를 넣는다(여러 번 돌려도 한 줄) | kubelet(containerd)은 클러스터 DNS를 쓰지 않는다. Harbor를 ingress-nginx의 MetalLB VIP로 고정한다. 옛 줄(192.168.121.179, w1의 eth0)이 있어도 바꿔 쓴다 |
| NFS 클라이언트(워커만) | `nfs-common`이 없으면 설치 | 약관(ro) · 백업(rw) PV가 호스트 NFS다 |

프로비저너는 VM을 처음 만들 때만 돈다(`vagrant up`은 이미 만든 VM에 다시 돌리지 않는다). 기존 노드에 새 프로비저너를 넣으려면 `vagrant provision <노드>`.

### setup-node.sh(지금 판)

노드 안에서 `bash -s`로 돈다. `set -e`라 한 줄이라도 실패하면 멈춘다.

1. 커널 모듈(`overlay`, `br_netfilter`)과 sysctl(`bridge-nf-call-iptables/ip6tables = 1`, `ip_forward = 1`)을 파일로 남기고 바로 적용
2. `swapoff -a`, `/etc/fstab`의 swap 줄을 공백 · 탭 둘 다 맞춰 주석 처리하고, 남아 있으면 실패
3. containerd `2.2.1-0ubuntu1~22.04.2` 설치, 기본 설정 파일을 뽑아 `SystemdCgroup = true`, 재시작 · enable
4. pkgs.k8s.io `v1.35` 저장소 키(`gpg --dearmor --yes`) · 목록 추가, kubelet · kubeadm · kubectl `1.35.9-1.1` 설치, 넷과 containerd를 `apt-mark hold`
5. 설치된 버전 출력

블록별 설명과 처음 판(2026-10-06)과 다른 곳은 「3. 진행 기록」의 4단계.

### 워커 추가 절차 (2026-11-10 w4로 확인)

```bash
# 0. 호스트 메모리: free -g (available 이 새 노드 메모리 + 여유보다 커야 한다)
# 1. cluster/Vagrantfile 의 NODES 에 한 줄(이름, 192.168.122.x, cpus, memory) → ~/k8s-cluster 에도 같게
cd ~/k8s-cluster && vagrant up w5-k8s
# 2. k8s 설치: 같은 버전
cat setup-node.sh | vagrant ssh w5-k8s -- 'bash -s'
# 3. join: 토큰을 화면에 내지 않는다(15분짜리)
J=$(vagrant ssh m-k8s -c 'sudo kubeadm token create --ttl 15m --print-join-command' 2>/dev/null | tr -d '\r')
echo "$J" | vagrant ssh w5-k8s -c 'read -r C; sudo $C'; unset J
# 4. 역할 라벨: cluster/label-nodes.sh 에 줄을 더해 m-k8s 에서 다시 돌린다
# 5. 확인: Ready, calico-node · metallb-speaker Running, 그 노드에 고정한 시험 Pod 로 Harbor pull · 클러스터 DNS · NFS 마운트
```

### 워커 메모리 늘리기 (2026-11-10 w1~w3 4GB에서 8GB로)

vagrant-libvirt는 꺼진 도메인의 `<memory>`(최대)만 올리고 `<currentMemory>`는 그대로 둔다. 그대로 켜면 게스트가 옛 크기만 본다(w2에서 겪었다, 「3. 진행 기록」 트러블슈팅).
virsh로 둘 다 맞춘 뒤 켠다. drain · 순서까지 포함한 절차 전체는 [08_scale_out.md](08_scale_out.md) 「1. 지금 구성」 안 노드 정비 절차.

```bash
D=k8s-cluster_w1-k8s
virsh -c qemu:///system setmaxmem $D 8388608 --config && virsh -c qemu:///system setmem $D 8388608 --config
vagrant up w1-k8s           # Vagrantfile memory 도 같은 값으로
# 이미 켠 뒤 알았다면: virsh setmem $D 8388608 --live --config → 노드에서 sudo systemctl restart kubelet(노드 용량은 kubelet 기동 때 읽는다)
```

## 2. 왜 이렇게 했나

### KVM/libvirt는 왜 쓰나

서버 PC 한 대에 VM 여러 대를 만들려면 가상화 소프트웨어가 필요하다. 역할 분담은 이렇다.

- **KVM**(Kernel-based Virtual Machine): 리눅스 커널에 내장된 가상화 엔진 자체. CPU의 하드웨어 가상화 기능(Intel VT-x 등)을 직접 써서 VM이 거의 진짜 하드웨어처럼 빠르게 돈다
- **libvirt**: KVM을 사람이 다루기 쉽게 관리해 주는 도구(API/CLI). Vagrant도 이 libvirt를 통해 KVM에게 "VM 만들어줘"라고 지시한다
- 전체 흐름: Vagrant(설정을 코드로 관리) → libvirt(관리 인터페이스) → KVM(실제 가상화 엔진) → VM

### 왜 VM 여러 대인가 (싱글 노드가 아닌 이유)

수업에서 쓴 k3s, 학교 vcluster는 컨트롤 플레인과 워커가 한 몸인 **싱글 노드**였다. 편의를 위한 축약판이다. 실제 운영 K8s는 보통 나뉘어 있다.

```
m-k8s   (컨트롤 플레인): "두뇌" 역할. apiserver · etcd · scheduler 등
w1-k8s  (워커): 실제 Pod(컨테이너)가 돌아가는 "일꾼" 노드
w2-k8s  (워커)
w3-k8s  (워커)
w4-k8s  (워커, 2026-11-10 추가)
```

- **이유 1**: CKA가 요구하는 것이 이 구조다. "컨트롤 플레인 1대 + 워커 여러 대"의 멀티 노드 클러스터를 kubeadm으로 직접 부트스트랩하는 것이 시험 범위 자체다. 싱글 노드로는 이 경험을 증명하지 못한다
- **이유 2**: 실제 운영 K8s가 이렇게 생겼다. 일꾼 노드 하나가 죽어도 다른 노드가 대신 Pod를 받게 짜여 있다. 포트폴리오에 "싱글 노드 k3s"보다 "멀티 노드 kubeadm 클러스터"가 훨씬 설득력 있다
- **이유 3(워커가 여럿인 이유)**: 워커 1대로는 "분산"을 보여줄 수 없다(그냥 VM이 2대인 것과 같다). 최소 2~3대는 있어야 "Pod가 여러 노드에 흩어져 배치되는 것", "한 노드 장애 때 다른 노드가 받는 것" 같은 K8s의 핵심 가치를 실제로 보여줄 수 있다. 처음에 3대로 시작했고, 2026-11-10 노드를 정비하는 동안에도 서비스가 돌게 하려고 w4를 더했다(08)

### 네트워크 대역: 왜 192.168.122.0/24이고 공유기 설정이 필요 없나

호스트 네트워크(`ip addr` / `ip route`)를 보니 이미 쓰는 대역은 `192.168.0.0/24`(공유기, 호스트 실제 IP)와 `172.17.0.0/16`(Docker)이었고, libvirt가 기본으로 주는 `virbr0` 망이 `192.168.122.0/24`로 떠 있었다. 그래서 VM의 고정 IP도 이 대역에 맞췄다(m-k8s .10, 워커 .11부터).

`192.168.122.0/24`는 공유기가 전혀 모르는 대역이다. `virbr0`라는 서버 PC 안에만 있는 가상 네트워크 장치가 만든 것이고, libvirt 자체가 이 대역의 작은 DHCP 서버 역할을 한다. Vagrantfile에 IP를 적은 것이 이미 "고정"이라 공유기에 따로 설정할 것이 없다.
외부 접근도 포트포워딩이 필요 없다. Cloudflare Tunnel(cloudflared)은 아웃바운드 연결만 만들기 때문에 공유기가 이 경로에 끼지 않고(NAT가 자동으로 통과시킨다), cloudflared가 서버 위에서 돌면서 VM 망(`192.168.122.x`)으로 직접 갈 수 있다(같은 패턴 사례를 웹 검색으로 확인했다). 터널은 [03_cloudflare_tunnel.md](03_cloudflare_tunnel.md).

### Pod 네트워크 CIDR: 왜 10.244.0.0/16인가

K8s 안에서 실제로 도는 것은 Pod이고, Pod도 각자 IP가 있어야 서로 통신한다. 이 "Pod 전용 IP 대역"을 누가 나눠 줄지 맡는 것이 **CNI**(Container Network Interface, "컨테이너가 네트워크에 연결될 때 따라야 하는 표준 규격")이고, Calico가 그 구현체 중 하나다. CNI를 설치하려면 미리 Pod에게 어느 대역을 나눠 줄지 정해야 하는데, 이것이 Pod 네트워크 CIDR이다.

서버 안에서 이미 쓰는 대역:

```txt
192.168.0.0/24    (공유기, 호스트 실제 IP)
172.17.0.0/16     (Docker)
192.168.122.0/24  (VM들)
```

Calico를 아무 설정 없이 설치하면 기본값으로 `192.168.0.0/16`을 쓰려고 한다. 이 대역은 192.168.0.0~192.168.255.255 전체라 이미 쓰는 `192.168.0.0/24`(공유기)와 `192.168.122.0/24`(VM)를 집어삼켜 겹친다. 그래서 아무도 안 쓰는 새 대역을 Pod 전용으로 떼어 줘야 하고, `10.244.0.0/16`은 Calico/Flannel 생태계에서 관례처럼 쓰는 안전한 선택(기존 대역 어디와도 안 겹침)이라 이것으로 정했다.

### 버전 스큐: 왜 버전을 고정하나 (CKA 핵심 주제, Version Skew Policy)

K8s는 컴포넌트별로 허용되는 버전 차이(skew)를 엄격히 정해 둔다.

| 컴포넌트 | kube-apiserver 대비 허용 차이 |
| --- | --- |
| kubelet | 최대 2개 마이너 버전 낮게까지만 허용(최신 정책 기준), 더 높으면 절대 안 된다 |
| kubectl | 1개 마이너 버전(위아래 모두 허용) |
| kubeadm | apiserver와 정확히 일치하는 것을 강력 권장 |

- 처음 구축은 "업그레이드"가 아니라 "새로 설치"라 더 단순했다. 모든 노드에 **정확히 같은 마이너 버전**의 kubeadm · kubelet · kubectl을 설치하면 스큐 문제 자체가 생기지 않는다. 서로 다른 버전이 섞이면 `kubeadm join`이 실패하거나, join은 되는데 나중에 이상하게 동작할 수 있다
- 그래서 설치 스크립트에 버전 변수를 두고 모든 노드에 같은 값을 쓰고, 설치 뒤 `apt-mark hold`로 패키지를 고정한다(실수로 `apt upgrade`를 돌려도 K8s 패키지는 안 올라간다)
- 2026년 10월 기준 최신은 v1.36까지 나왔지만(웹 검색), 안정성 위주로 **v1.35**로 정했다
- 처음에는 저장소(`v1.35`)만 고정해 설치하는 날의 최신 패치가 들어오는 구조였다. 노드를 나중에 더하면 그날의 최신이 섞인다(kubelet이 apiserver보다 높아질 수 있다). 2026-11-10 w4를 만들며 패키지 버전(`1.35.9-1.1`, containerd `2.2.1-0ubuntu1~22.04.2`)까지 고정했다

### 왜 Calico인가

Flannel이라는 CNI도 있지만, Calico는 네트워크 정책(NetworkPolicy) 기능이 기본으로 들어 있다. CKA 시험에도 NetworkPolicy가 나오므로 Calico로 갔다.

### 그 밖의 설계 결정

- **멀티 노드 kubeadm**: 컨트롤 플레인과 워커를 나눠야 "노드 하나가 죽어도 다른 노드가 받는다"를 실제로 보일 수 있다. kubeadm 부트스트랩 자체가 CKA 범위다
- **GPU는 호스트에**: 패스스루 없이 Pod가 192.168.122.1로 Ollama · Milvus를 부른다. 호스트에서 이미 쓰는 GPU를 VM에 넘기지 않는다
- **Vagrantfile을 저장소에**: 손으로 넣은 노드 설정(DNS)이 코드에 없어 w4가 처음에 apt를 못 받았다. 노드 설정은 프로비저너로만 넣고 저장소 사본(`cluster/`)을 같이 고친다
- **Vagrantfile은 선언형이다**: "이런 VM들을 원한다"고 코드로 적어 두면 `vagrant up`이 그 차이를 보고 만든다. `kubectl apply`와 같은 철학이다(명령이 아니라 상태 선언)

## 3. 진행 기록

VM 생성 → containerd · kubeadm · kubelet · kubectl 설치 → kubeadm init(m-k8s) → kubeadm join(워커 3대) → CNI(Calico) 설치까지 2026-10-06에 끝냈다. 2026-11-10 워커 추가 · 메모리 증설은 이 절 끝.

### 1단계: 가상화 환경 구축 (2026-10-06)

설치한 패키지:

| 패키지 | 역할 |
| --- | --- |
| qemu-system-x86 | VM의 CPU · 디스크 · 네트워크 장치를 흉내 내는 "틀". KVM 가속을 받아 실제로 VM을 돌리는 핵심 실행기 |
| libvirt-daemon-system | libvirt의 "관리 서버"(데몬, libvirtd). VM 생성 · 삭제 · 시작 · 중지 명령을 받아 실제로 처리하는 백그라운드 서비스 |
| libvirt-clients | virsh 같은 명령어 도구. 터미널에서 VM 목록 보기, 수동 제어 등 |
| bridge-utils | VM들이 서로 통신하고 외부 네트워크에 연결되도록 가상 네트워크 브리지를 만드는 도구 |
| virtinst | virt-install 명령으로 VM을 쉽게 만드는 도구(Vagrant를 쓰므로 직접 쓸 일은 적지만 보조 도구로 설치) |

`qemu-kvm` 패키지는 요즘 우분투에서 가상 패키지로 바뀌어 `qemu-system-x86`으로 명시해 설치해야 한다.

추가 설정:

- `sudo usermod -aG libvirt,kvm $USER`로 계정을 두 그룹에 넣었다(sudo 없이 virsh를 쓰려고). 새 셸에서 `newgrp libvirt`로 바로 적용했다(새로 로그인하지 않아도 된다)
- 확인: `virsh list --all`이 권한 오류 없이 빈 목록(아직 VM 없음)을 내면 성공

### 2단계: Vagrant 설치 (2026-10-06, Vagrant 2.4.9 / vagrant-libvirt 0.12.2)

```bash
# Vagrant 설치 (HashiCorp 공식 저장소)

# 1) HashiCorp의 GPG 서명 키를 받아서, apt가 검증용으로 쓸 수 있게 파일로 저장
wget -O- https://apt.releases.hashicorp.com/gpg | sudo gpg --dearmor -o /usr/share/keyrings/hashicorp-archive-keyring.gpg

# 2) "HashiCorp 저장소를 apt 목록에 추가"하는 설정 파일을 만듦 (1번에서 저장한 키로 서명 검증하겠다고 명시)
echo "deb [signed-by=/usr/share/keyrings/hashicorp-archive-keyring.gpg] https://apt.releases.hashicorp.com $(lsb_release -cs) main" | sudo tee /etc/apt/sources.list.d/hashicorp.list

# 3) 방금 추가한 저장소 포함해서 패키지 목록을 새로 받아옴
sudo apt update

# 4) Vagrant 설치 (이제 HashiCorp 저장소에서 받아올 수 있게 됨)
sudo apt install -y vagrant

# vagrant-libvirt 플러그인 설치에 필요한 빌드 도구
# 5) vagrant-libvirt 플러그인은 C 확장을 컴파일해야 해서, libvirt 개발 헤더(libvirt-dev)와 컴파일 도구모음(build-essential)이 필요
sudo apt install -y libvirt-dev build-essential

# vagrant-libvirt 플러그인 설치
# 6) Vagrant가 기본적으로는 VirtualBox용인데, 이 플러그인을 넣어야 libvirt/KVM을 provider로 쓸 수 있음
vagrant plugin install vagrant-libvirt
```

GPG 키는 `wget -O-`로 받은 뒤 `-o` 옵션으로 파일까지 저장해야 하는데, 처음 시도에서는 출력만 되고 파일이 만들어지지 않았다(`ls`로 확인해야 한다). 다시 해서 됐다.

### 3단계: Vagrantfile 작성 → VM 4대 생성 (2026-10-06)

```bash
nproc
#32
free -h

# total        used        free      shared  buff/cache   available
# Mem:            61Gi        14Gi       2.5Gi        82Mi        44Gi        46Gi
# Swap:          8.0Gi       3.8Gi       4.2Gi
```

서버 사양: 32코어, RAM 61GB(당시 가용 46GB).

리소스 배분(처음):

| VM | vCPU | RAM | 역할 |
| --- | --- | --- | --- |
| m-k8s | 2 | 4GB | 컨트롤 플레인(kubeadm 공식 최소 권장 2 CPU/2GB, 여유를 두고 4GB) |
| w1-k8s | 2 | 4GB | 워커 |
| w2-k8s | 2 | 4GB | 워커 |
| w3-k8s | 2 | 4GB | 워커 |

합계 8 vCPU / 16GB, 호스트에 24코어 / 약 45GB를 남겼다(Ollama · Jupyter 작업과 같이 쓸 수 있게). 디스크는 VM당 20GB(kubeadm 공식 최소 권장)로 적었지만 실제로는 박스 기본 디스크가 쓰였다(아래 「디스크 크기 정리」).

#### Vagrantfile 처음 판 해설 (2026-10-06)

```rb
IMAGE_NAME = "generic/ubuntu2204"
# ↑ 모든 VM이 쓸 "틀"(OS 이미지). Vagrant Cloud의 "generic" 계열 박스는
#   특정 가상화 provider(libvirt, virtualbox 등) 여러 개를 다 지원해서 범용적으로 쓰임

NODES = [
  { name: "m-k8s",  ip: "192.168.122.10", cpus: 2, memory: 4096 },
  { name: "w1-k8s", ip: "192.168.122.11", cpus: 2, memory: 4096 },
  { name: "w2-k8s", ip: "192.168.122.12", cpus: 2, memory: 4096 },
  { name: "w3-k8s", ip: "192.168.122.13", cpus: 2, memory: 4096 },
]
# ↑ VM 4대의 "설계도"를 배열로 미리 적어둠: 이름, 고정 IP, CPU/메모리

Vagrant.configure("2") do |config|
  NODES.each do |node|
    # ↑ 배열을 하나씩 돌면서 VM을 "정의"함(실제로 만드는 건 아직 아님)
    config.vm.define node[:name] do |n|
      n.vm.box = IMAGE_NAME            # 이 VM이 쓸 OS 이미지
      n.vm.hostname = node[:name]      # VM 안에서 `hostname` 쳤을 때 나오는 이름
      n.vm.network "private_network", ip: node[:ip]
      # ↑ "사설 네트워크"를 추가로 붙이고, 그 안에서 고정 IP를 줌
      #   (없으면 VM끼리 서로 통신할 고정 주소가 없음)

      n.vm.provider :libvirt do |lv|
        lv.cpus = node[:cpus]
        lv.memory = node[:memory]
        lv.machine_virtual_size = 20
        # ↑ 이 VM을 "libvirt"로 돌릴 때만 적용되는 세부 설정(CPU/메모리/디스크)
      end
    end
  end
end
```

지금 판(`cluster/Vagrantfile`)과 다른 곳:

| 처음 판 | 지금 판 | 언제 |
| --- | --- | --- |
| 워커 `memory: 4096` | w1~w3 `memory: 8192` | 2026-11-10 |
| 노드 4대 | `w4-k8s`(192.168.122.14, 2 vCPU, 8192) 추가 | 2026-11-10 |
| 프로비저너 없음 | DNS(resolved.conf.d), `/etc/hosts`의 Harbor 줄, 워커 `nfs-common` 셋 | Harbor 줄 2026-10-15, DNS · nfs-common 2026-11-10 |

`machine_virtual_size = 20`은 지금 판에도 그대로 있지만 박스가 무시한다(아래).

#### VM 4대 기동

```bash
# 1) m-k8s 단독 기동 (문제 생기면 1대에서만 디버깅하도록)
vagrant up m-k8s --provider=libvirt

# 2) SSH 접속 확인
vagrant ssh m-k8s
# 안에서:
hostname                 # m-k8s
cat /etc/os-release      # Ubuntu 22.04.3 LTS
ip addr show
# eth0: 192.168.121.x (vagrant-libvirt 관리망, Vagrant SSH용)
# eth1: 192.168.122.10 (우리가 지정한 고정 IP, 정확히 붙음)
exit

# 3) 나머지 워커 3대 동시 기동
vagrant up w1-k8s w2-k8s w3-k8s --provider=libvirt

# 4) 디스크 실제 사용량 확인 ("Ignoring requested virtual disk size" 메시지 나왔을 때)
sudo du -sh /var/lib/libvirt/images/k8s-cluster_*.img
# 46M~287M: 128GB는 씬 프로비저닝 상한선일 뿐, 실제 사용량은 작음
df -h /
# 462GB 여유 확인, 문제없음

# 5) 최종 확인
vagrant status
# m-k8s, w1-k8s, w2-k8s, w3-k8s 모두 running (libvirt)

# 6) 각 VM의 고정 IP(eth1) 최종 확인
for vm in m-k8s w1-k8s w2-k8s w3-k8s; do
  echo "=== $vm ==="
  vagrant ssh $vm -c "hostname && ip -4 addr show eth1 | grep inet"
done
```

IP 매핑(2026-10-06):

| 노드 | eth0 (NAT, SSH용) | eth1 (고정 IP, 클러스터 통신용) |
| --- | --- | --- |
| m-k8s | 192.168.121.64 | 192.168.122.10 |
| w1-k8s | 192.168.121.179 | 192.168.122.11 |
| w2-k8s | 192.168.121.95 | 192.168.122.12 |
| w3-k8s | 192.168.121.158 | 192.168.122.13 |

#### 디스크 크기 정리 (2026-11-10 확인)

`machine_virtual_size = 20`은 박스가 무시했다("Ignoring requested virtual disk size"). 층마다 크기가 다르다.

| 층 | 크기 | 확인 |
| --- | --- | --- |
| 가상 디스크(호스트 이미지) | 128GiB 상한, 씬 프로비저닝. 호스트 실제 할당은 쓴 만큼(8~29GiB) | `virsh vol-info` |
| LVM 볼륨 그룹 | 126GB (63GB 비어 있음) | `vgs` |
| 루트 `/` | 62GB | `df -h /` |

게스트가 쓸 수 있는 것은 루트 62GB다. 모자라면 VG에 남은 63GB를 `lvextend`로 붙일 수 있다. 2026-11-10 Harbor를 w3로 옮기며 w3에 30GB를 붙였다(w3 루트 92GB, VG 남은 공간 33GB, [08_scale_out.md](08_scale_out.md)). [04_argocd.md](04_argocd.md) 끝의 디스크 이야기도 같은 내용이다.

### 4단계: 각 VM에 containerd · kubeadm · kubelet · kubectl 설치 (2026-10-06)

전체 흐름:

```
m-k8s에서 먼저 수동으로 한 블록씩 시험 → 성공 확인
→ 시험한 명령을 하나의 스크립트(setup-node.sh)로 합침
→ w1~w3-k8s 3대에 그 스크립트를 반복 실행(복붙 실수 방지)
```

#### setup-node.sh 처음 판: 블록별 주석 (2026-10-06)

아래는 2026-10-06에 쓴 처음 판이다. 지금 판과 다른 곳은 바로 아래 표에 있다.

```bash
#!/bin/bash
set -e
# ↑ 에러가 하나라도 나면 스크립트를 즉시 중단하는 안전장치

# ===== 1. 커널 모듈 + 네트워크 설정 =====
cat <<EOC | sudo tee /etc/modules-load.d/k8s.conf
overlay
br_netfilter
EOC
# overlay       : containerd가 이미지 레이어를 쌓는 파일시스템 방식
# br_netfilter  : 브리지를 지나는 패킷도 iptables 규칙을 거치게 함(Pod 간 통신 누락 방지)

sudo modprobe overlay
sudo modprobe br_netfilter
# → 재부팅 없이 지금 당장 적용

cat <<EOC | sudo tee /etc/sysctl.d/k8s.conf
net.bridge.bridge-nf-call-iptables  = 1
net.bridge.bridge-nf-call-ip6tables = 1
net.ipv4.ip_forward                 = 1
EOC
# ip_forward: 이 노드가 Pod들의 "교차로" 역할(패킷 라우팅)을 하게 허용

sudo sysctl --system
# → 위 설정을 즉시 반영

# ===== 2. swap 비활성화 =====
sudo swapoff -a
# → kubelet은 메모리 자원을 정확히 계산해 스케줄링해야 하는데 swap이 켜져있으면 이 계산이 꼬여 kubeadm이 설치를 거부함

sudo sed -i '/ swap / s/^/#/' /etc/fstab
# → 재부팅 시 swap이 다시 자동으로 켜지지 않도록 fstab에서 주석 처리 (이 패턴은 틀렸다: 아래 트러블슈팅)

# ===== 3. containerd 설치 =====
sudo apt update
sudo apt install -y containerd
# → containerd: 실제로 컨테이너를 실행하는 런타임(엔진)

sudo mkdir -p /etc/containerd
containerd config default | sudo tee /etc/containerd/config.toml
# → containerd 기본 설정값 전체를 파일로 뽑아냄(수정하려면 일단 파일로 있어야 함)

sudo sed -i 's/SystemdCgroup = false/SystemdCgroup = true/' /etc/containerd/config.toml
# → cgroup 드라이버를 kubelet과 동일한 systemd 방식으로 맞춤(안 맞으면 자원 관리 충돌 가능성)

sudo systemctl restart containerd
sudo systemctl enable containerd
# restart: 바뀐 설정 적용 / enable: 재부팅 시 자동 시작 등록

# ===== 4. kubeadm/kubelet/kubectl 설치 (버전 고정) =====
K8S_VERSION="v1.35"
# → 모든 노드가 정확히 같은 값을 써야 하는 핵심 변수(버전 스큐 방지)

sudo apt install -y apt-transport-https ca-certificates curl gpg

curl -fsSL https://pkgs.k8s.io/core:/stable:/${K8S_VERSION}/deb/Release.key | sudo gpg --dearmor -o /etc/apt/keyrings/kubernetes-apt-keyring.gpg
# → 공식 K8s 저장소 GPG 서명 키를 받아 파일로 저장

echo "deb [signed-by=/etc/apt/keyrings/kubernetes-apt-keyring.gpg] https://pkgs.k8s.io/core:/stable:/${K8S_VERSION}/deb/ /" | sudo tee /etc/apt/sources.list.d/kubernetes.list
# → 이 저장소를 apt 목록에 추가

sudo apt update
sudo apt install -y kubelet kubeadm kubectl
# kubelet: 각 노드에서 Pod를 실제로 띄우는 에이전트(전 노드 필수)
# kubeadm: 클러스터 초기화 도구(init/join)
# kubectl: 사람이 명령 내리는 CLI

sudo apt-mark hold kubelet kubeadm kubectl
# → 이 셋을 고정해서 나중에 apt upgrade를 돌려도 버전이 안 올라가게 함(노드 간 버전 어긋남 방지)

echo "=== 설치 완료 ==="
kubeadm version
kubelet --version
kubectl version --client
```

지금 판(`cluster/setup-node.sh`)과 다른 곳:

| 블록 | 처음 판 | 지금 판 | 까닭 |
| --- | --- | --- | --- |
| 2. swap | `sed -i '/ swap / s/^/#/'` | `sed -i -E '/^[^#].*[[:space:]]swap[[:space:]]/ s/^/#/'` + 남았으면 `exit 1` | 공백만 찾아 탭 구분 fstab에 안 맞았다(아래 트러블슈팅) |
| 3. containerd | `apt install -y containerd`(그날의 최신) | `containerd=2.2.1-0ubuntu1~22.04.2` | 노드를 나중에 더해도 같은 버전 |
| 4. 키 저장 | `gpg --dearmor -o …` | `sudo mkdir -p /etc/apt/keyrings` 뒤 `gpg --dearmor --yes -o …` | 디렉터리가 없는 박스에서도, 다시 돌려도 멈추지 않게 |
| 4. k8s 패키지 | `apt install -y kubelet kubeadm kubectl`(저장소 `v1.35`의 최신 패치) | `kubelet=1.35.9-1.1 kubeadm=… kubectl=…` | 패치 버전까지 같게(2. 버전 스큐) |
| 4. hold | `kubelet kubeadm kubectl` | `kubelet kubeadm kubectl containerd` | containerd도 `apt upgrade`로 안 오르게 |

#### 실행 방법

```bash
# 1) 호스트에서 스크립트 파일 작성(cat > setup-node.sh << 'EOF' ... EOF)

# 2) 워커 3대에 순서대로 실행
for vm in w1-k8s w2-k8s w3-k8s; do
  echo "=== $vm 설치 시작 ==="
  cat setup-node.sh | vagrant ssh $vm -- 'bash -s'
done
```

#### 확인: 4대 전부 버전 일치

```bash
for vm in m-k8s w1-k8s w2-k8s w3-k8s; do
  echo "=== $vm ==="
  vagrant ssh $vm -c "kubeadm version -o short && kubelet --version && kubectl version --client -o yaml | grep gitVersion"
done
```

결과: 4대 전부 `v1.35.9`로 정확히 같았다. 설치는 문제없이 끝났다.

#### 트러블슈팅: 재부팅 뒤 swap이 다시 켜졌다 (2026-10-13, 2026-11-10)

**증상**: 설치 때는 문제가 없었다. VM을 재부팅한 뒤에 드러났다([03_cloudflare_tunnel.md](03_cloudflare_tunnel.md)의 DNS 문제와 같은 날). `swapoff -a`는 지금 켜진 swap만 끄고, 재부팅 뒤에는 `/etc/fstab`이 다시 켠다. kubelet은 기본값에서 swap이 켜져 있으면 뜨지 않는다.

**원인**: fstab을 주석 처리하는 `sed` 패턴이 맞지 않았다.

```bash
sudo sed -i '/ swap / s/^/#/' /etc/fstab
```

패턴은 양쪽 공백(`' swap '`)을 찾는데, 박스의 fstab은 **탭**으로 구분돼 있다.

```txt
/swap.img	none	swap	sw	0	0
```

`sed`는 아무것도 못 바꿔도 성공으로 끝난다. 그래서 스크립트는 "완료"를 찍었고, 재부팅 전까지는 아무 일도 없었다.

**해결**: 2026-10-13에는 4대의 fstab을 손으로 고쳤다. 스크립트는 그대로 남아, 2026-11-10 같은 스크립트로 설치한 w4의 fstab에서 같은 줄이 살아 있는 것을 찾았다(재부팅 전에 고쳤다). 스크립트를 고쳐 공백 · 탭 둘 다 맞추고, 남아 있으면 실패하게 했다.

```bash
sudo sed -i -E '/^[^#].*[[:space:]]swap[[:space:]]/ s/^/#/' /etc/fstab
grep -qE '^[^#].*[[:space:]]swap[[:space:]]' /etc/fstab && { echo "fstab 에 swap 줄이 남았다"; exit 1; }
```

> 손으로 고친 것은 그 노드에만 남고, 스크립트는 틀린 채로 남는다. 다음 노드를 만들 때 같은 문제가 돌아온다. 고친 것은 코드에 되돌려 넣는다. DNS 설정도 같은 까닭으로 2026-11-10 Vagrantfile 프로비저너로 옮겼다(이 절 끝).

### 5단계: kubeadm init(m-k8s) → kubeadm join(워커 3대) → CNI(Calico) 설치 (2026-10-06)

Pod 네트워크 CIDR을 왜 10.244.0.0/16으로 정했는지는 「2. 왜 이렇게 했나」.

#### kubeadm init (컨트롤 플레인 초기화)

```bash
sudo kubeadm init \
  --apiserver-advertise-address=192.168.122.10 \
  --pod-network-cidr=10.244.0.0/16
```

- `--apiserver-advertise-address=192.168.122.10`: m-k8s는 IP가 둘(eth0 = vagrant-libvirt 관리망 192.168.121.x, eth1 = 고정 IP 192.168.122.10)이라, 워커가 붙을 주소를 고정 IP로 못 박았다. 없으면 kubeadm이 아무 IP(어쩌면 DHCP로 받는 eth0 주소)를 골라 버릴 위험이 있다
- `--pod-network-cidr=10.244.0.0/16`: 위에서 정한 Pod 전용 대역

성공하면 마지막에 `kubeadm join ...` 명령(토큰 포함)이 찍힌다. 워커 3대를 join할 때 그대로 썼다. 이 토큰은 기본 24시간 뒤 만료된다.

#### 트러블슈팅: kubeadm init 직후 kubectl이 connection refused (kubeconfig 설정)

**증상**: `kubeadm init` 직후 `kubectl get nodes`가 `connection refused`(localhost:8080)로 실패한다.

**원인**: kubectl이 클러스터 인증 정보(kubeconfig)를 아직 못 찾는다. 흔한 문제다.

**해결**: `/etc/kubernetes/admin.conf`(root 권한의 클러스터 인증 정보)를 홈으로 복사하고 소유권을 내 계정으로 바꿔 sudo 없이 kubectl을 쓴다.

```bash
mkdir -p $HOME/.kube
sudo cp -i /etc/kubernetes/admin.conf $HOME/.kube/config
sudo chown $(id -u):$(id -g) $HOME/.kube/config
```

#### kubeadm join (워커 3대)

```bash
for vm in w1-k8s w2-k8s w3-k8s; do
  echo "=== $vm join 시작 ==="
  vagrant ssh $vm -c "sudo kubeadm join 192.168.122.10:6443 --token <토큰> --discovery-token-ca-cert-hash sha256:<해시>"
done
```

#### CNI(Calico) 설치

```bash
kubectl apply -f https://raw.githubusercontent.com/projectcalico/calico/v3.28.0/manifests/calico.yaml
```

Calico의 전체 리소스(DaemonSet, ConfigMap 등)를 클러스터에 배포한다. 적용 직후에는 노드가 아직 `NotReady`일 수 있고, Calico Pod가 뜨는 데 1~2분쯤 걸린다.

#### 최종 확인

```bash
kubectl get nodes
```

```txt
NAME     STATUS   ROLES           AGE     VERSION
m-k8s    Ready    control-plane   3m58s   v1.35.9
w1-k8s   Ready    <none>          2m42s   v1.35.9
w2-k8s   Ready    <none>          2m39s   v1.35.9
w3-k8s   Ready    <none>          2m37s   v1.35.9
```

4개 노드 전부 Ready, 1~5단계 완료.

```bash
kubectl get pods -A
```

```txt
NAMESPACE     NAME                                       READY   STATUS    RESTARTS   AGE
kube-system   calico-kube-controllers-79fcb48598-x7gn4   1/1     Running   0          11m
kube-system   calico-node-ld8q9                          1/1     Running   0          11m
kube-system   calico-node-qkn2z                          1/1     Running   0          11m
kube-system   calico-node-svqs5                          1/1     Running   0          11m
kube-system   calico-node-xht7s                          1/1     Running   0          11m
kube-system   coredns-7d764666f9-5wl4x                   1/1     Running   0          14m
kube-system   coredns-7d764666f9-blb2d                   1/1     Running   0          14m
kube-system   etcd-m-k8s                                 1/1     Running   0          14m
kube-system   kube-apiserver-m-k8s                       1/1     Running   0          14m
kube-system   kube-controller-manager-m-k8s              1/1     Running   0          14m
kube-system   kube-proxy-bpxdn                           1/1     Running   0          13m
kube-system   kube-proxy-pnmhk                           1/1     Running   0          12m
kube-system   kube-proxy-rg8fn                           1/1     Running   0          13m
kube-system   kube-proxy-w56mc                           1/1     Running   0          14m
kube-system   kube-scheduler-m-k8s                       1/1     Running   0          14m
```

- **`calico-node`**: 노드마다 **1개씩 떠 있는 DaemonSet**. 그 노드 위 Pod들의 네트워크(라우팅 규칙, IP 할당 등)를 실제로 관리하는 "에이전트"다. 이때는 노드가 4개라 4개였다(지금은 5개)
- **`calico-kube-controllers`**: 클러스터 전체에 **딱 1개** 떠서, K8s의 상태 변화(네임스페이스 삭제, 서비스 변경 등)를 감지해 네트워크 정책을 동기화하는 "중앙 관리자"다

비유하면:

- `calico-node` = 건물(노드)마다 있는 "경비실"(실제 출입 · 통신 통제)
- `calico-kube-controllers` = 단지 전체를 관리하는 "관리사무소"(정책 결정, 경비실에 지시)

Calico가 `10.244.0.0/16` 대역으로 실제로 하는 일:

1. 새 Pod가 뜨면 그 Pod에게 `10.244.x.x` 대역의 IP를 하나 준다
2. 그 Pod가 다른 노드의 Pod와도 통신하도록 노드 간 라우팅 규칙을 자동으로 넣는다(이 클러스터는 IPIP 터널, `tunl0`)
3. (NetworkPolicy를 쓰면) "이 네임스페이스의 Pod는 저 네임스페이스와 통신 금지" 같은 방화벽 규칙도 처리한다

### 2026-11-10: 워커 추가 · 메모리 증설

노드 하나를 정비하는 동안에도 서비스가 돌게 하려고 워커를 늘렸다. 왜 늘렸는지 · 어떤 순서로 내렸는지는 [08_scale_out.md](08_scale_out.md)에 있고, 여기에는 이 문서의 설치 절차가 어떻게 바뀌었는지만 남긴다.

| VM | vCPU | RAM | 바뀐 것 |
| --- | --- | --- | --- |
| m-k8s | 2 | 4GB | 그대로 |
| w1-k8s · w2-k8s · w3-k8s | 2 | 8GB | 4GB → 8GB |
| w4-k8s | 2 | 8GB | 새로(192.168.122.14) |

합계 10 vCPU / 36GB. 호스트에 남는 메모리는 약 25GB다.

**Vagrantfile과 `setup-node.sh`를 코드로 남겼다.** 둘 다 호스트 `~/k8s-cluster`에만 있었다. 이제 `ronanlab-infra/cluster/`에 사본이 있다. 고치면 양쪽 다 고친다.

| 바뀐 것 | 왜 |
| --- | --- |
| Vagrantfile 프로비저너에 DNS 설정(`DNS=8.8.8.8 1.1.1.1`, `DNSSEC=no`) | 2026-10-13 손으로 넣었던 것([03_cloudflare_tunnel.md](03_cloudflare_tunnel.md))이 코드에 없어, w4가 처음 뜰 때 apt가 이름을 못 풀었다 |
| `setup-node.sh`가 패키지 버전까지 고정: containerd `2.2.1-0ubuntu1~22.04.2`, kubelet · kubeadm · kubectl `1.35.9-1.1` | 저장소(`v1.35`)만 고정하면 그날의 최신 패치가 들어온다. kubelet은 apiserver보다 높으면 안 된다(버전 스큐) |
| `setup-node.sh`의 swap 주석 패턴 | 4단계 「트러블슈팅: 재부팅 뒤 swap이 다시 켜졌다」 |

**join 토큰은 화면에 내지 않는다.** 5단계에서는 `kubeadm init`이 찍은 join 명령을 그대로 썼다. 노드를 나중에 더할 때는 짧은 토큰을 새로 만들어 바로 넘긴다.

```bash
cd ~/k8s-cluster
vagrant up w4-k8s
cat setup-node.sh | vagrant ssh w4-k8s -- 'bash -s'
J=$(vagrant ssh m-k8s -c 'sudo kubeadm token create --ttl 15m --print-join-command' 2>/dev/null | tr -d '\r')
echo "$J" | vagrant ssh w4-k8s -c 'read -r C; sudo $C'; unset J
```

```txt
NAME     STATUS   ROLES           AGE   VERSION
m-k8s    Ready    control-plane   35d   v1.35.9
w1-k8s   Ready    <none>          35d   v1.35.9
w2-k8s   Ready    <none>          35d   v1.35.9
w3-k8s   Ready    <none>          35d   v1.35.9
w4-k8s   Ready    <none>          14s   v1.35.9
```

w4를 만든 뒤 시험 Pod(그 노드에 고정)로 Harbor private 이미지 pull, `runshoes-mysql:3306`, Service 200, Ollama 200, NFS 마운트를 확인했다(전부 통과).

#### 트러블슈팅: w4 첫 vagrant up에서 nfs-common 설치 실패

**증상**: w4를 처음 `vagrant up` 했을 때 nfs-common 설치 프로비저너가 실패했다. apt가 이름을 못 풀었다.

**원인**: 박스 기본 DNS(4.2.2.x, DNSSEC=yes)가 이 망에서 잘 안 풀린다. 기존 노드는 2026-10-13 손으로 `/etc/systemd/resolved.conf.d/dns.conf`를 넣어 두었고, 그것이 코드에 없었다.

**해결**: 기존 노드의 손설정을 찾아 Vagrantfile DNS 프로비저너로 옮기고 `vagrant provision w4-k8s`.

#### 트러블슈팅: 메모리를 올렸는데 게스트가 4GB만 본다

**증상**: w2에서 Vagrantfile의 `memory`만 8192로 고치고 `vagrant up` 했더니 첫 실행은 Ruby 오류로 멈췄고, 다시 켜니 게스트의 `free -m`이 3,842MB였다.

```bash
virsh -c qemu:///system dumpxml k8s-cluster_w2-k8s | grep -i memory
```

```txt
  <memory unit='KiB'>8388608</memory>
  <currentMemory unit='KiB'>4194304</currentMemory>
```

**원인**: vagrant-libvirt가 꺼진 도메인의 `<memory>`(최대)만 올리고 `<currentMemory>`(지금 크기)는 그대로 두었다. 게스트는 virtio balloon으로 4GB만 받는다.

**해결**: 켜기 전에 virsh로 둘 다 맞춘다. 이미 켰다면 라이브로 올리고, 노드 용량은 kubelet이 기동 때 읽으므로 kubelet을 다시 띄운다(Pod는 그대로 돈다). w2는 라이브로 `virsh setmem` 뒤 kubelet 재시작으로, w3 · w1은 켜기 전에 virsh로 맞춰 한 번에 됐다.

```bash
D=k8s-cluster_w1-k8s
virsh -c qemu:///system setmaxmem $D 8388608 --config
virsh -c qemu:///system setmem $D 8388608 --config
vagrant up w1-k8s

# 이미 켠 뒤라면
virsh -c qemu:///system setmem $D 8388608 --live --config
vagrant ssh w1-k8s -c 'sudo systemctl restart kubelet'
```

> 처음 나온 Ready만 보고 다음으로 넘어가면 안 된다. VM을 막 끈 직후에는 노드 상태가 아직 Ready로 남아 있다. NotReady를 거쳐 다시 Ready가 된 것을 보고 uncordon한다.

## 4. 남은 한계

- **물리 호스트가 하나다.** VM 5대가 같은 서버 · 같은 디스크에 있다. 서버 자체가 죽으면 전부 멈춘다([08_scale_out.md](08_scale_out.md) 「남은 한계」)
- **컨트롤 플레인이 한 대다.** m-k8s가 죽으면 이미 뜬 Pod는 돌지만 스케줄 · 복구 · kubectl이 멈춘다
- `~/k8s-cluster`(실제로 vagrant가 읽는 곳)와 저장소 `cluster/`가 따로 복사한 파일이다. 한쪽을 고치면 다른 쪽도 고친다(2026-11-12 `cmp`로 같음)
- 노드 InternalIP가 DHCP 대역(eth0, vagrant-libvirt 관리망)이다. 지금까지 주소가 바뀐 적은 없지만 libvirt DHCP 임대가 바뀌면 노드 주소가 바뀐다
- Calico는 매니페스트를 URL로 한 번 `kubectl apply` 했을 뿐 저장소에 없다. 다시 깔거나 올릴 때는 v3.28.0 URL에서 시작한다
- 프로비저너는 VM을 처음 만들 때만 돈다. Vagrantfile을 고쳐도 기존 노드에는 `vagrant provision <노드>`를 따로 해야 들어간다
- w3를 뺀 노드 루트가 62GB다. 모자라면 VG 남은 공간을 `lvextend`로 붙인다(w3는 이미 92GB)

## 5. 확인 방법

m-k8s에서(`cd ~/k8s-cluster && vagrant ssh m-k8s -c '…'`):

```bash
kubectl get nodes -o wide
# 5대 Ready, VERSION v1.35.9, CONTAINER-RUNTIME containerd://2.2.1, INTERNAL-IP 192.168.121.x
kubectl get nodes -L node.ronanlab.dev/role
# w1 · w2 app, w3 infra, w4 platform
kubectl get nodes -o custom-columns=N:.metadata.name,MEM:.status.capacity.memory
# 워커 4대 8128536Ki 안팎, m-k8s 4005904Ki 안팎
kubectl -n kube-system get ds calico-node
# DESIRED 5 READY 5
kubectl get ippools.crd.projectcalico.org -o custom-columns=CIDR:.spec.cidr,IPIP:.spec.ipipMode
# 10.244.0.0/16 Always
```

호스트에서:

```bash
virsh -c qemu:///system dominfo k8s-cluster_w1-k8s | grep -i memory   # Max = Used = 8388608 KiB
virsh -c qemu:///system net-dumpxml default | grep range               # 192.168.122.100 ~ .199
cmp ~/k8s-cluster/Vagrantfile cluster/Vagrantfile && cmp ~/k8s-cluster/setup-node.sh cluster/setup-node.sh   # 출력 없음
```

노드에서(예: `vagrant ssh w1-k8s -c '…'`):

```bash
grep harbor /etc/hosts                       # 192.168.122.240 harbor.ronanlab.dev
cat /etc/systemd/resolved.conf.d/dns.conf    # DNS=8.8.8.8 1.1.1.1, DNSSEC=no
swapon --show | wc -l                        # 0
```

새 노드를 더했을 때는 그 노드에 고정한 시험 Pod로 Harbor private 이미지 pull, `runshoes-mysql:3306`, Service 200, Ollama 200, NFS 마운트를 본다.
