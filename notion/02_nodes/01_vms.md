<!--
다루는 곳: cluster/Vagrantfile
읽은 커밋: 736d833
-->
# 02-01 VM 다섯 대와 랜카드 둘

## 다섯 대의 크기

노드 다섯 대는 모두 `cluster/Vagrantfile` 한 파일에 적혀 있다. 파일 앞부분의 목록에 노드마다 이름, 고정 주소, CPU 수, 메모리 크기를 한 줄씩 적고, 그 아래에서 목록을 돌며 같은 틀로 VM을 하나씩 정의한다. [code:cluster/Vagrantfile:3-23] 다섯 대 모두 같은 박스(VM을 찍어 내는 OS 이미지)인 Ubuntu 22.04 이미지에서 만들어졌고, 커널과 컨테이너 런타임 판도 모두 같다. [code:cluster/Vagrantfile:1] [docs:history/cluster_state_20261116.md:17]

| 노드 | 하는 일 | CPU | 메모리 |
| --- | --- | --- | --- |
| m-k8s | 컨트롤 플레인 | 2 | 4GB |
| w1-k8s ~ w4-k8s | 워커 | 2 | 8GB씩 |

컨트롤 플레인은 쿠버네티스 설치 도구가 권하는 최소치(CPU 둘, 메모리 2GB)에 여유를 두어 4GB로 잡았다. [docs:history/build_log/01_cluster.md:256] [code:cluster/Vagrantfile:4] 워커는 앱과 데이터베이스, 이미지 저장소, 모니터링 같은 실제 일을 받으므로 한 대에 8GB씩 준다. [code:cluster/Vagrantfile:5-9] 다섯 대를 합쳐도 서버 전체 메모리의 일부만 쓰는데, 남은 메모리는 같은 서버에서 도는 추론 서버와 학습 작업이 쓴다. [docs:history/build_log/01_cluster.md:27]

## VM을 만들 때 함께 넣는 설정

Vagrantfile에는 VM 정의 말고도 VM을 처음 만들 때 안에서 한 번 도는 짧은 셸 명령(프로비저너)이 셋 있다. [code:cluster/Vagrantfile:25-44]

첫째는 이름 풀이 서버 설정이다. 박스에 기본으로 들어 있는 이름 풀이 서버가 이 망에서 잘 응답하지 않아, 널리 쓰는 공개 이름 풀이 서버로 바꾸고 서명 검증을 끈다. [code:cluster/Vagrantfile:25-30] 이 설정은 처음에 기존 노드에 손으로 넣었던 것인데, 코드에 없다 보니 나중에 새로 만든 노드가 첫 부팅에서 꾸러미를 내려받지 못했다. 그 뒤로 노드에 넣는 설정은 손이 아니라 프로비저너로만 넣는다. [docs:history/build_log/01_cluster.md:184]

둘째는 이미지 저장소 이름을 노드의 hosts 파일(이름과 주소를 직접 짝지어 두는 파일)에 고정하는 줄이다. 노드에서 컨테이너를 띄우는 런타임은 클러스터 안의 이름 풀이를 쓰지 않기 때문에, 이미지 저장소의 공개 이름을 그대로 풀면 바깥 인증 관문으로 가 버린다. 그래서 그 이름을 클러스터의 들어오는 문이 쓰는 고정 주소로 직접 적어 둔다. [code:cluster/Vagrantfile:32-37] 들어오는 문은 → 「들어오는 문」, 이미지 저장소는 → 「이미지 저장소」에서 다룬다.

셋째는 워커에만 도는 것으로, 네트워크 파일 시스템(NFS)을 붙이는 도구를 설치한다. 일부 볼륨이 호스트가 내놓는 공유 폴더라서, 워커에 이 도구가 없으면 그 볼륨을 쓰는 파드가 뜨지 못한다. [code:cluster/Vagrantfile:39-44] 공유 폴더는 → 「공유 저장소」에 있다.

## 노드마다 랜카드가 둘인 까닭

노드마다 랜카드(네트워크 연결 장치)가 둘 붙어 있다. [docs:history/cluster_state_20261116.md:19-22] 첫째 랜카드(eth0)는 VM을 만드는 도구가 스스로 붙이는 관리용 망이다. 주소를 DHCP(망에 붙는 장치에게 주소를 그때그때 빌려 주는 방식)로 받고, 사람이 노드에 접속할 때 쓰는 명령(`vagrant ssh`)이 이 길로 들어온다. 문제는 이 주소가 다시 켤 때마다 바뀔 수 있다는 점이다. [docs:history/human_answers_20261116.md:7]

쿠버네티스의 노드들은 쉬지 않고 서로 말을 주고받고, 상대를 주소로 찾는다. 주소가 바뀔 수 있는 망 위에 클러스터를 세울 수는 없어서, 둘째 랜카드(eth1)로 사설 고정 주소 망을 따로 붙였다. Vagrantfile의 노드 목록에 적힌 주소가 바로 이 랜카드의 주소다. [docs:history/human_answers_20261116.md:9] [code:cluster/Vagrantfile:17] 컨트롤 플레인의 API 서버(클러스터에 내리는 모든 명령을 받는 창구), 노드 사이로 파드 통신을 나르는 Calico, 바깥 요청을 받을 대표 주소를 알리는 MetalLB, 그리고 파드가 호스트의 추론 서버를 부르는 길이 모두 이 고정 주소 망을 탄다. [docs:history/human_answers_20261116.md:9] [docs:history/cluster_state_20261116.md:23-24] [docs:history/cluster_state_20261116.md:80]

관리용 망과 사설 고정 주소 망을 나누는 것은 Vagrant로 쿠버네티스 연습 클러스터를 만들 때 흔히 쓰는 방식이다. 이 클러스터를 세울 때 참고한 책 《컨테이너 인프라 환경 구축을 위한 쿠버네티스/도커》(길벗, 조훈)의 Vagrantfile도 두 망을 이렇게 나눈다. [docs:history/human_answers_20261116.md:11] MetalLB가 대표 주소를 알릴 랜카드를 eth1 하나로 묶어 둔 것도 같은 까닭이다. 대표 주소가 고정 주소 망 안에 있으니, 그 망이 붙은 랜카드로만 알려야 한다. [docs:history/human_answers_20261116.md:13] [docs:history/cluster_state_20261116.md:33]

고정 주소 망은 호스트의 가상화 도구가 처음부터 만들어 두는 기본 가상 망을 그대로 쓴다. 서버 안에만 있는 가상 망이라 공유기는 이 망을 모르고, 주소를 Vagrantfile에 적는 것만으로 고정이 끝나 공유기에 따로 설정할 것이 없다. [docs:history/build_log/01_cluster.md:142-144] [docs:history/cluster_state_20261116.md:28] 반면 바깥 인터넷으로 나가는 기본 길은 관리용 망 쪽이다. [docs:history/cluster_state_20261116.md:21]

## 노드가 스스로 알리는 주소

쿠버네티스는 노드마다 그 노드를 가리키는 내부 주소(InternalIP)를 하나 기록한다. 이 값은 노드마다 도는 에이전트인 kubelet이 정한다. 이 클러스터의 kubelet에는 어느 주소를 쓸지 지정하는 설정이 없고, 다섯 대 모두 내부 주소가 관리용 망(eth0) 쪽 주소로 잡혀 있다. [docs:history/cluster_state_20261116.md:9-15] [docs:history/cluster_state_20261116.md:26] 일부러 그렇게 한 것이 아니라 기본값이 그대로 남은 것이다. [docs:history/human_answers_20261116.md:15] 클러스터가 실제로 통신하는 길은 위에서 말한 대로 고정 주소 망이라, 지금 클러스터는 정상으로 돈다.

다만 이 때문에 생길 수 있는 일이 셋 있다. 노드 목록을 넓게 보는 명령이 보여 주는 노드 주소는 관리용 망 주소라, 그 화면만 보고 노드끼리 어느 길로 통신하는지 판단하면 틀린다. [docs:history/cluster_state_20261116.md:9-15] [docs:history/cluster_state_20261116.md:23-24] 노드의 내부 주소를 그대로 가져다 쓰는 기능은 관리용 망을 탄다. 모니터링이 각 노드의 kubelet에서 컨테이너 사용량을 긁어 올 때 찾아가는 주소가 이 내부 주소다. [code:apps/monitoring/prometheus/configmap.yaml:33-43] 그리고 관리용 망 주소는 다시 켤 때 바뀔 수 있어, 바뀌면 노드가 알리는 내부 주소도 따라 바뀐다. [docs:history/human_answers_20261116.md:7] [docs:history/human_answers_20261116.md:15] kubelet에 주소를 지정해 고정 주소 망으로 옮기는 일은 남은 일로 적어 두었다. [c:a40b111]

## 알려진 한계

- 프로비저너는 VM을 처음 만들 때만 돈다. Vagrantfile을 고쳐도 이미 있는 노드에는 따로 다시 돌려야 들어간다. [docs:history/build_log/01_cluster.md:73]
- 가상 머신이 모두 같은 서버 한 대 위에 있는 것은 여러 편에 걸리는 조건이라 → 「알려진 한계」에 모았다

## 용어 풀이

- VM(가상 머신): 실제 컴퓨터 안에서 소프트웨어로 흉내 낸 컴퓨터
- Vagrant: VM의 모양을 파일에 적어 두면 그대로 만들어 주는 도구
- 박스: Vagrant가 VM을 찍어 낼 때 쓰는 OS 이미지
- 프로비저너: VM을 처음 만들 때 그 안에서 자동으로 한 번 도는 설정 명령
- 랜카드: 컴퓨터를 망에 붙이는 장치. VM에서는 가상 장치다
- DHCP: 망에 붙은 장치에게 주소를 그때그때 빌려 주는 방식
- InternalIP: 쿠버네티스가 노드마다 기록하는 그 노드의 내부 주소
- MetalLB: 클라우드가 아닌 클러스터에서 바깥 요청을 받을 대표 주소를 나눠 주고 망에 알리는 도구
