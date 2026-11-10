#!/bin/bash
set -e

# 1. 커널 모듈/네트워크 설정
cat <<EOC | sudo tee /etc/modules-load.d/k8s.conf
overlay
br_netfilter
EOC
sudo modprobe overlay
sudo modprobe br_netfilter

cat <<EOC | sudo tee /etc/sysctl.d/k8s.conf
net.bridge.bridge-nf-call-iptables  = 1
net.bridge.bridge-nf-call-ip6tables = 1
net.ipv4.ip_forward                 = 1
EOC
sudo sysctl --system

# 2. swap 비활성화
sudo swapoff -a
# fstab 은 탭으로 구분돼 있다 — 공백만 찾던 옛 패턴(' swap ')은 맞지 않아 재부팅 뒤 swap 이 다시 켜졌다(2026-10-13 m · w1~w3 손으로 고침,
# 2026-11-10 w4 에서 같은 줄이 살아 있는 것을 찾아 고침). 공백 · 탭 둘 다, 이미 주석인 줄은 건드리지 않는다
sudo sed -i -E '/^[^#].*[[:space:]]swap[[:space:]]/ s/^/#/' /etc/fstab
grep -qE '^[^#].*[[:space:]]swap[[:space:]]' /etc/fstab && { echo "fstab 에 swap 줄이 남았다"; exit 1; }

# 3. containerd 설치
# 버전은 지금 돌고 있는 노드와 정확히 같게 고정한다(2026-11-10 w4 를 만들며 — 저장소만 고정하면 그날의 최신 패치가 들어온다)
CONTAINERD_VERSION="2.2.1-0ubuntu1~22.04.2"
K8S_PKG_VERSION="1.35.9-1.1"
sudo apt update
sudo apt install -y containerd=${CONTAINERD_VERSION}
sudo mkdir -p /etc/containerd
containerd config default | sudo tee /etc/containerd/config.toml
sudo sed -i 's/SystemdCgroup = false/SystemdCgroup = true/' /etc/containerd/config.toml
sudo systemctl restart containerd
sudo systemctl enable containerd

# 4. kubeadm/kubelet/kubectl 설치 (v1.35 고정)
K8S_VERSION="v1.35"
sudo apt install -y apt-transport-https ca-certificates curl gpg
sudo mkdir -p /etc/apt/keyrings
curl -fsSL https://pkgs.k8s.io/core:/stable:/${K8S_VERSION}/deb/Release.key | sudo gpg --dearmor --yes -o /etc/apt/keyrings/kubernetes-apt-keyring.gpg
echo "deb [signed-by=/etc/apt/keyrings/kubernetes-apt-keyring.gpg] https://pkgs.k8s.io/core:/stable:/${K8S_VERSION}/deb/ /" | sudo tee /etc/apt/sources.list.d/kubernetes.list
sudo apt update
sudo apt install -y kubelet=${K8S_PKG_VERSION} kubeadm=${K8S_PKG_VERSION} kubectl=${K8S_PKG_VERSION}
sudo apt-mark hold kubelet kubeadm kubectl containerd

echo "=== 설치 완료 ==="
kubeadm version
kubelet --version
kubectl version --client
