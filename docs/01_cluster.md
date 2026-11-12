## 01. 클러스터

#### 0. 한 줄 요약

GPU 호스트 한 대 위에 KVM/libvirt + Vagrant로 VM 5대(컨트롤 플레인 1 · 워커 4)를 띄우고 kubeadm(1.35.9) · Calico로 묶었다.
VM 정의는 `cluster/Vagrantfile`, 노드 설치는 `cluster/setup-node.sh`(둘 다 버전 고정). 노션 「쿠버네티스 설치」 · 「01. 클러스터 구축」(2026-10-06)을 지금 상태로 옮긴 것이다.

#### 1. 최종 설계

##### 1-1. 호스트와 VM

```
[GPU 호스트 — 32코어 · RAM 61GB · RTX 5070 Ti]  Ollama · Milvus(도커), NFS(약관 ro · 백업 rw)
  └ KVM/libvirt ← Vagrant(vagrant-libvirt)   ~/k8s-cluster (저장소 사본: cluster/)
      m-k8s   192.168.122.10  2 vCPU  4GB   컨트롤 플레인
      w1-k8s  192.168.122.11  2 vCPU  8GB   워커
      w2-k8s  192.168.122.12  2 vCPU  8GB   워커
      w3-k8s  192.168.122.13  2 vCPU  8GB   워커
      w4-k8s  192.168.122.14  2 vCPU  8GB   워커(2026-11-10 추가)
```

- VM 합 36GB(2026-11-10 16GB → 36GB). 호스트에 남는 것은 약 25GB — Ollama 모델 · 학습과 같이 쓴다
- 노드마다 NIC 둘: eth0 = libvirt 기본망 192.168.121.0/24(DHCP, vagrant ssh · 바깥 인터넷), eth1 = 사설망 192.168.122.0/24(고정, Vagrantfile).
  노드 InternalIP는 eth0(121.x)로 잡혀 있다(kubelet `--node-ip` 없음). Calico 노드 간 터널은 eth1(122.x)로 간다
- Pod 대역 10.244.0.0/16(Calico IPIP) — 호스트의 192.168.0.0/24 · 172.17.0.0/16(도커) · 192.168.122.0/24와 겹치지 않게
- MetalLB L2 풀 192.168.122.240~250(`platform/metallb`), ingress-nginx VIP 192.168.122.240

##### 1-2. 버전 — 모든 노드가 같다

| 것 | 버전 | 어디서 |
| --- | --- | --- |
| 박스 | generic/ubuntu2204 4.3.12 (Ubuntu 22.04.3, 커널 5.15.0-91) | Vagrantfile |
| containerd | 2.2.1-0ubuntu1~22.04.2 (SystemdCgroup = true) | setup-node.sh |
| kubeadm · kubelet · kubectl | 1.35.9-1.1 (`apt-mark hold`) | setup-node.sh |
| Calico | v3.28.0 매니페스트 | kubeadm init 뒤 한 번 |

setup-node.sh는 처음에 저장소(`v1.35`)만 고정해 설치 날의 최신 패치가 들어오는 구조였다 — 2026-11-10 w4를 만들며 패키지 버전까지 고정했다.

##### 1-3. VM 설정 중 Vagrantfile 프로비저너가 하는 것

| 프로비저너 | 왜 |
| --- | --- |
| systemd-resolved `DNS=8.8.8.8 1.1.1.1`, `DNSSEC=no` | 박스 기본(4.2.2.x · DNSSEC=yes)이 이 망에서 잘 안 풀린다. 2026-10-13 손으로 넣은 것을 2026-11-10 여기로 옮겼다 |
| `/etc/hosts`에 `192.168.122.240 harbor.ronanlab.dev` | kubelet(containerd)은 클러스터 DNS를 쓰지 않는다 — Harbor를 ingress VIP로 고정 |
| 워커에 `nfs-common` | 약관(ro) · 백업(rw) PV가 호스트 NFS다 |

프로비저너는 VM을 처음 만들 때만 돈다(`vagrant up`은 이미 만든 VM에 다시 돌리지 않는다). 기존 노드에 새 프로비저너를 넣으려면 `vagrant provision <노드>`.

##### 1-4. 워커 추가 절차 (2026-11-10 w4로 확인)

```bash
# 0. 호스트 메모리: free -g (available 이 새 노드 메모리 + 여유보다 커야 한다)
# 1. cluster/Vagrantfile 의 NODES 에 한 줄(이름 · 192.168.122.x · cpus · memory) → ~/k8s-cluster 에도 같게
cd ~/k8s-cluster && vagrant up w5-k8s
# 2. k8s 설치 — 같은 버전
cat setup-node.sh | vagrant ssh w5-k8s -- 'bash -s'
# 3. join — 토큰을 화면에 내지 않는다(15분짜리)
J=$(vagrant ssh m-k8s -c 'sudo kubeadm token create --ttl 15m --print-join-command' 2>/dev/null | tr -d '\r')
echo "$J" | vagrant ssh w5-k8s -c 'read -r C; sudo $C'; unset J
# 4. 확인 — Ready · calico-node · metallb-speaker Running, 그 노드에 고정한 시험 Pod 로 Harbor pull · 클러스터 DNS · NFS 마운트
```

##### 1-5. 워커 메모리 늘리기 (2026-11-10 w1~w3 4 → 8GB)

vagrant-libvirt는 꺼진 도메인의 `<memory>`(최대)만 올리고 `<currentMemory>`는 그대로 둔다 — 그대로 켜면 게스트가 옛 크기만 본다(w2에서 겪음).
virsh로 둘 다 맞춘 뒤 켠다. 절차 전체(drain · 순서)는 [08_scale_out.md](08_scale_out.md) 1-5절.

```bash
D=k8s-cluster_w1-k8s
virsh -c qemu:///system setmaxmem $D 8388608 --config && virsh -c qemu:///system setmem $D 8388608 --config
vagrant up w1-k8s           # Vagrantfile memory 도 같은 값으로
# 이미 켠 뒤 알았다면: virsh setmem $D 8388608 --live --config → 노드에서 sudo systemctl restart kubelet(노드 용량은 kubelet 기동 때 읽는다)
```

#### 2. 왜 이렇게 했나

- **멀티 노드 kubeadm**: 컨트롤 플레인과 워커를 나눠야 "노드 하나가 죽어도 다른 노드가 받는다"를 실제로 보일 수 있다. kubeadm 부트스트랩 자체가 CKA 범위다
- **GPU는 호스트에**: 패스스루 없이 Pod가 192.168.122.1로 Ollama · Milvus를 부른다 — 호스트에서 이미 쓰는 GPU를 VM에 넘기지 않는다
- **버전 고정**: kubelet은 apiserver보다 높으면 안 되고 kubeadm은 같아야 한다. 노드를 나중에 더할 때 그날의 최신이 섞이지 않게 패키지 버전까지 고정한다
- **Vagrantfile을 저장소에**: 손으로 넣은 노드 설정(DNS)이 코드에 없어 w4가 처음에 apt를 못 받았다 — 노드 설정은 프로비저너로만 넣고 저장소 사본(`cluster/`)을 같이 고친다

#### 3. 시도했던 것들

- w4 첫 `vagrant up`: 박스 기본 DNS로 nfs-common 설치 실패 → 기존 노드의 손설정(resolved.conf.d/dns.conf)을 찾아 프로비저너로 옮기고 `vagrant provision w4-k8s`
- w2 메모리 증설: Vagrantfile만 고치고 `vagrant up` → 첫 실행은 Ruby 오류로 멈췄고 다시 켜니 게스트가 3.8GB만 봄(`currentMemory` 4GB) → 라이브로 `virsh setmem` + kubelet 재시작. w3 · w1은 켜기 전에 virsh로 맞춰 한 번에 됐다

#### 4. 남은 한계

- **물리 호스트가 하나다.** VM 5대가 같은 서버 · 같은 디스크에 있다 — 서버 자체가 죽으면 전부 멈춘다([08_scale_out.md](08_scale_out.md) 4절)
- **컨트롤 플레인이 한 대다.** m-k8s가 죽으면 이미 뜬 Pod는 돌지만 스케줄 · 복구 · kubectl이 멈춘다
- `~/k8s-cluster`(실제로 vagrant가 읽는 곳)와 저장소 `cluster/`가 사본이다 — 한쪽을 고치면 다른 쪽도 고친다
- 노드 InternalIP가 DHCP 대역(eth0)이다. 지금까지 주소가 바뀐 적은 없지만 libvirt DHCP 임대가 바뀌면 노드 주소가 바뀐다

#### 5. 검증 항목

- `kubectl get nodes -o wide` 5대 Ready · v1.35.9 · containerd 2.2.1
- 워커 4대 `kubectl get node -o jsonpath='{.status.capacity.memory}'` 8128536Ki 안팎, `virsh dominfo` Max = Used = 8388608 KiB
- 새 노드에 고정한 시험 Pod: Harbor private 이미지 pull · `runshoes-mysql:3306` · Service 200 · Ollama 200 · NFS 마운트(2026-11-10 w4 전부 통과)
