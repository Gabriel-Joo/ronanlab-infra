<!--
다루는 곳: platform/versions.yaml, platform/coredns/
읽은 커밋: e8e24ea
-->
# 쿠버네티스 설치와 파드 망

## kubeadm으로 직접 세운 클러스터

노드 다섯 대를 하나의 클러스터로 묶은 도구는 kubeadm이다. kubeadm은 쿠버네티스가 공식으로 내놓은 설치 도구로, 컨트롤 플레인을 세우는 일(init)과 다른 노드를 붙이는 일(join)을 맡는다. 지금 클러스터는 v1.35.9이고, 노드의 kubelet과 kubectl, 컨트롤 플레인 구성 요소의 이미지가 모두 같은 판이다. 컨테이너 런타임은 containerd 2.2.1이다. [code:platform/versions.yaml:8-10] [docs:history/cluster_state_20261116.md:9-17]

학교 수업에서 쓴 클러스터는 컨트롤 플레인과 워커가 한 몸인 단일 노드였다. 여기서는 일부러 두 역할을 나눈 여러 노드 클러스터를 손으로 세웠다. 실제 운영 클러스터가 그렇게 생겼고, 여러 노드 클러스터를 kubeadm으로 세우는 일 자체가 쿠버네티스 관리자 자격 시험의 범위이기도 하다. [docs:history/build_log/01_cluster.md:126-137] [docs:history/build_log/kubernetes_install.md:124]

컨트롤 플레인을 세울 때 API 서버가 알릴 주소를 고정 주소 망 쪽 주소로 못 박았다. m-k8s에는 관리용 망과 고정 주소 망의 주소가 하나씩 있는데, 지정하지 않으면 kubeadm이 주소를 그때그때 빌려 받는 관리용 망 쪽을 고를 위험이 있었다. 워커들은 이 고정 주소로 API 서버를 찾아 붙었다. [docs:history/build_log/01_cluster.md:524-530] [docs:history/human_answers_20261116.md:9] 두 망의 차이는 → 「VM 다섯 대와 랜카드 둘」에 있다.

## 파드와 서비스에게 주는 주소

클러스터 안에는 주소 대역이 둘 더 있다. 하나는 파드에게 주는 주소 대역이고, 다른 하나는 서비스(여러 파드 앞에 서서 하나의 고정된 이름과 주소로 요청을 받아 주는 묶음)에게 주는 주소 대역이다. [code:platform/versions.yaml:11-12] 서비스 대역은 kubeadm의 기본값을 그대로 썼다. [docs:history/build_log/01_cluster.md:49]

파드 대역은 따로 골랐다. 서버 안에는 이미 사무실 공유기 망, 호스트의 Docker 망, VM의 고정 주소 망이 있다. 파드 망 도구 Calico를 아무 설정 없이 깔면 기본으로 쓰려는 대역이 너무 넓어서 사무실 망과 VM 망을 통째로 덮어 버린다. 그래서 어느 것과도 겹치지 않고, 이 분야에서 관례처럼 쓰는 사설 대역을 파드 몫으로 떼어 kubeadm에 알려 주었다. [docs:history/build_log/01_cluster.md:151-159] [docs:history/build_log/01_cluster.md:530]

## Calico: 노드를 건너는 파드 망

파드는 저마다 주소를 갖고, 다른 노드에 있는 파드와도 그 주소로 바로 말을 주고받아야 한다. 이 약속을 지키는 것이 CNI(컨테이너를 망에 붙이는 방식에 대한 표준)이고, 이 클러스터는 그 구현체로 Calico v3.28.0을 쓴다. Calico는 공개된 설치 매니페스트(쿠버네티스에 무엇을 만들지 적은 설정 파일)를 그 주소에서 바로 한 번 적용해 넣었다. [code:platform/versions.yaml:14-18] 같은 일을 하는 더 단순한 도구도 있지만, Calico는 파드 사이 통신을 규칙으로 막고 여는 기능(NetworkPolicy)이 기본으로 들어 있어 이쪽을 골랐다. [docs:history/build_log/01_cluster.md:178]

Calico는 두 부분으로 돈다. 노드마다 하나씩 뜨는 calico-node가 그 노드 위 파드에게 주소를 나눠 주고 다른 노드로 가는 길을 깐다. 클러스터에 하나만 뜨는 calico-kube-controllers는 쿠버네티스 쪽 변화를 지켜보다 Calico 설정에 옮겨 적는다. [docs:history/build_log/01_cluster.md:604-605]

다른 노드의 파드로 가는 패킷은 IPIP 방식으로 나른다. 파드끼리 주고받는 패킷을 노드끼리 주고받는 패킷 안에 한 겹 싸서 보내고, 받는 노드가 껍질을 벗겨 자기 위 파드에게 건넨다. 다른 방식인 VXLAN은 쓰지 않는다. [docs:history/cluster_state_20261116.md:25] IPIP를 고른 까닭은 기록에 남아 있지 않다.

이때 바깥 껍질에 적히는 노드 주소가 중요하다. Calico는 노드 주소를 설정으로 못 박지 않고 스스로 찾게 두었는데, 찾은 결과는 다섯 대 모두 고정 주소 망 쪽 주소다. 실제로 다른 노드의 파드 대역으로 가는 길은 모두 상대 노드의 고정 주소를 다음 정거장으로 삼아 IPIP 터널 장치를 지난다. [docs:history/cluster_state_20261116.md:23-25] 그래서 노드가 쿠버네티스에 알리는 내부 주소는 관리용 망 쪽이지만, 파드 통신은 주소가 바뀌지 않는 망 위로 흐른다. [docs:history/cluster_state_20261116.md:26]

## CoreDNS: 클러스터 안의 이름 풀이

파드가 다른 서비스를 이름으로 부르면, 그 이름을 주소로 바꿔 주는 것이 CoreDNS다. 설정은 `platform/coredns/configmap.yaml`에 있고, kubeadm이 처음 만든 기본 설정에 한 덩어리를 더한 것이다. [code:platform/coredns/configmap.yaml:1] [code:platform/coredns/configmap.yaml:15-42]

기본 부분이 하는 일은 이렇다. 클러스터 안 이름(서비스와 파드)은 쿠버네티스에 물어 답하고, 그 밖의 이름은 노드가 쓰는 이름 풀이 서버로 넘긴다. 답은 잠깐 기억해 두되 클러스터 안 이름은 기억하지 않아 서비스가 바뀌면 바로 따라간다. 설정 파일이 바뀌면 스스로 다시 읽고, 이름 풀이가 제자리를 맴도는 고리가 생기면 멈추며, 상태와 지표를 내놓는다. [code:platform/coredns/configmap.yaml:16-41]

더한 덩어리는 이미지 저장소의 공개 이름 하나를 고쳐 쓰는 규칙이다. 파드가 그 이름을 물으면 공개 이름 풀이로 가지 않고 들어오는 문(ingress-nginx)의 클러스터 내부 서비스 주소로 답한다. 답에 적히는 이름은 원래 이름으로 되돌려, 묻는 쪽은 바뀐 줄 모른다. [code:platform/coredns/configmap.yaml:22-25] [code:platform/coredns/configmap.yaml:3] 공개 이름으로 가면 바깥의 인증 관문에 막히기 때문이다. 노드의 hosts 파일에 같은 이름을 고정해 둔 것과 같은 일을 클러스터 안에서 하는 셈이어서, 이미지 이름이 노드에서든 파드에서든 똑같다. [code:platform/coredns/configmap.yaml:4-5] [code:cluster/Vagrantfile:32-36]

이미지 저장소의 핵심 서비스로 바로 보내지 않고 들어오는 문을 거치게 한 데도 까닭이 있다. 이미지 저장소는 로그인 토큰을 받을 주소를 "요청한 이름 그대로의 HTTPS 주소"로 알려 주는데, 핵심 서비스는 암호화하지 않는 통신만 받는다. 들어오는 문을 거치면 그 주소가 공개 인증서로 검증되는 HTTPS로 이어진다. [code:platform/coredns/configmap.yaml:5-7] 들어오는 문과 인증서는 → 「들어오는 문」과 → 「TLS가 끝나는 곳」에서 다룬다.

CoreDNS 설정은 배포 도구(ArgoCD)가 지켜보는 범위 밖이라, 바꾸면 사람이 직접 클러스터에 적용한다. [code:CLAUDE.md:13] [code:platform/coredns/configmap.yaml:2]

## 저장소 밖에서 넣은 것의 판 기록

클러스터에는 저장소에 매니페스트가 없는 것이 꽤 있다. Calico처럼 공개 주소의 매니페스트를 바로 적용한 것, 패키지 관리 도구(helm)로 넣은 것, 그리고 kubeadm 자체가 그렇다. 이런 것의 판은 원래 클러스터 안에만 남는다. 클러스터가 사라지면 그 값도 함께 사라지고, 그러면 같은 환경을 다시 만들 수 없다. [docs:history/human_answers_20261116.md:19]

그래서 `platform/versions.yaml`에 그 판을 옮겨 적어 두었다. 이 파일은 어떤 설치기도 읽지 않는 기록일 뿐이고, 다시 만들 때 같은 판을 깔기 위해 둔다. 판을 올리면 같은 변경에서 이 파일도 고친다. [code:platform/versions.yaml:1-6] 이 편이 다루는 kubeadm, containerd, 두 주소 대역, Calico 말고도 지표 수집기, 노드 디스크 저장 공간 공급기, 배포 도구, 인증서 관리 도구, MetalLB, 이미지 저장소, 빌드 서버의 판과 출처가 함께 적혀 있다. [code:platform/versions.yaml:14-53] 몇몇은 설치한 뒤 손으로 덧댄 설정이 있어, 그것도 같은 자리에 한 줄씩 적어 두었다. [code:platform/versions.yaml:22] [code:platform/versions.yaml:26] [code:platform/versions.yaml:30]

## 알려진 한계

- 컨트롤 플레인이 한 대다. m-k8s가 멈추면 이미 뜬 파드는 계속 돌지만 새 배치와 복구, 사람의 명령이 멈춘다. [docs:history/build_log/01_cluster.md:700]
- Calico 매니페스트는 저장소에 없다. 다시 깔거나 올릴 때는 판 기록에 적힌 주소에서 시작한다. [code:platform/versions.yaml:16-18] [docs:history/build_log/01_cluster.md:703]
- kubeadm으로 클러스터 판을 올리면 CoreDNS 설정을 새로 옮겨 적는다. 올린 뒤에는 이미지 저장소 이름을 고쳐 쓰는 덩어리가 남았는지 확인해야 한다. [code:platform/coredns/configmap.yaml:8]
- Calico를 고른 까닭인 NetworkPolicy는 지금 저장소의 매니페스트 어디에도 없다. 기능은 들어 있지만 쓰지 않고 있다. [code:apps/] [code:platform/]
- 판 기록 파일은 사람이 손으로 맞춘다. 클러스터의 실제 판과 저절로 맞춰지지 않는다. [code:platform/versions.yaml:3-6]

## 용어 풀이

- kubeadm: 쿠버네티스 클러스터를 세우고 노드를 붙이는 공식 도구
- API 서버: 클러스터에 내리는 모든 명령을 받는 컨트롤 플레인의 창구
- 서비스: 여러 파드 앞에 서서 하나의 이름과 주소로 요청을 받아 넘기는 쿠버네티스 묶음
- CNI: 컨테이너를 망에 붙이는 방식에 대한 표준. Calico가 그 구현체다
- IPIP: 패킷을 다른 패킷 안에 한 겹 싸서 보내는 방식
- CoreDNS: 클러스터 안에서 이름을 주소로 바꿔 주는 서버
- 매니페스트: 쿠버네티스에 무엇을 만들지 적은 설정 파일
- helm: 여러 매니페스트를 한 꾸러미로 묶어 판과 함께 설치하는 도구
