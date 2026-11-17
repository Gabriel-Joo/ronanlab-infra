<!--
다루는 곳: cluster/Vagrantfile, platform/metallb/pool.yaml, apps/petmint/app/configmap.yaml, apps/monitoring/prometheus/configmap.yaml
읽은 커밋: 02c240c
-->
# 랜카드 둘: 관리망과 고정망

> 이 글은 노드마다 랜카드를 둘 붙이고, 클러스터의 통신을 주소가 바뀌지 않는 쪽 망으로만 보낸 결정을 다룹니다.

**VM을 만드는 도구가 붙여 주는 관리망은 주소가 다시 켤 때마다 바뀔 수 있어서, 노드끼리 말하는 길로 쓰지 않았습니다. 사설 고정 주소망을 따로 붙이고, 쿠버네티스의 지휘 창구, 파드 망, 대표 주소 알림, 호스트 GPU 서비스 호출을 모두 그쪽으로 보냈습니다.**

## 상황

노드는 서버 안의 가상 머신이고, 이 VM은 Vagrant가 vagrant-libvirt라는 연결 도구로 만듭니다 [code:cluster/Vagrantfile:12-21]. vagrant-libvirt는 VM을 만들 때 관리용 랜카드(eth0)를 기본으로 하나 붙입니다. 이 랜카드는 DHCP(망에 붙는 장치에게 주소를 그때그때 빌려 주는 방식)로 주소를 받고, 사람이 노드에 접속하는 명령(`vagrant ssh`)도 이 길로 들어옵니다. 문제는 이 주소가 재부팅마다 바뀔 수 있다는 점입니다 [docs:history/human_answers_20261116.md:7].

쿠버네티스의 노드들은 쉬지 않고 서로 말을 주고받고, 상대를 주소로 찾습니다. 워커는 control-plane의 API 서버(클러스터에 내리는 모든 명령을 받는 창구) 주소를 기억해 붙고, 노드 사이로 파드 통신을 나르는 Calico도 상대 노드의 주소로 길을 깝니다. 그 주소가 바뀌면 클러스터가 서로를 잃습니다 [docs:history/human_answers_20261116.md:9].

## 고른 것

노드마다 둘째 랜카드(eth1)를 붙여 사설 고정 주소망에 연결했습니다. 주소는 VM 정의 파일에 노드마다 적혀 있습니다 [code:cluster/Vagrantfile:3-10] [code:cluster/Vagrantfile:17]. 이 망은 호스트의 가상화 도구가 처음부터 만들어 두는 기본 가상 망을 그대로 쓴 것이라, 서버 안에만 있고 공유기는 이 망을 모릅니다. 주소를 정의 파일에 적는 것만으로 고정이 끝나 공유기에 따로 설정할 것도 없었습니다 [docs:history/build_log/01_cluster.md:142-144] [docs:history/cluster_state_20261116.md:28].

그리고 클러스터가 쓰는 통신을 모두 이 고정망으로 보냈습니다 [docs:history/human_answers_20261116.md:9]. control-plane을 세울 때 API 서버가 알릴 주소를 고정망 주소로 못 박았습니다. 지정하지 않으면 설치 도구가 DHCP로 받는 관리망 주소를 고를 위험이 있었습니다 [docs:history/build_log/01_cluster.md:529]. 파드 망을 맡은 Calico는 다른 노드의 파드로 가는 길을 모두 상대 노드의 고정망 주소를 거쳐 깔고 있고, 이것은 실제 클러스터에서 확인한 결과입니다 [docs:history/cluster_state_20261116.md:23-24]. 바깥 요청을 받을 대표 주소를 망에 알리는 MetalLB는 알릴 랜카드를 eth1 하나로 묶었습니다 [code:platform/metallb/pool.yaml:12-22]. 파드가 호스트의 추론 서버 Ollama나 벡터 검색 Milvus 같은 GPU 쪽 서비스를 부를 때도 고정망 쪽 호스트 주소를 씁니다 [code:apps/petmint/app/configmap.yaml:21-26] [docs:history/cluster_state_20261116.md:80].

## 까닭

관리망과 사설 고정망을 나누는 것은 Vagrant로 쿠버네티스 클러스터를 만들 때 흔히 쓰는 방식입니다. 이 클러스터를 세울 때 참고한 책 《컨테이너 인프라 환경 구축을 위한 쿠버네티스/도커》(길벗, 조훈)의 VM 정의 파일도 두 망을 이렇게 나눕니다 [docs:history/human_answers_20261116.md:11]. 관리망은 VM을 만들고 접속하는 도구의 몫으로 두고, 클러스터는 주소가 바뀌지 않는 망 위에 세운 것입니다.

MetalLB를 eth1 하나로 묶은 것도 같은 까닭입니다. MetalLB가 나눠 주는 대표 주소가 고정 주소 대역 안에 있으니, 그 대역이 붙은 랜카드로만 알려야 합니다 [docs:history/human_answers_20261116.md:13] [docs:history/cluster_state_20261116.md:32-33].

## 치른 값과 남은 한계

설계는 고정망으로 했지만, 한 군데는 기본값이 그대로 남았습니다. 쿠버네티스는 노드마다 그 노드를 가리키는 내부 주소(InternalIP)를 하나 기록하는데, 이 값은 노드마다 도는 에이전트 kubelet이 정합니다. 이 클러스터의 kubelet에는 어느 주소를 쓸지 정하는 설정(`--node-ip`)이 없어서, 다섯 대 모두 내부 주소가 관리망(eth0) 쪽으로 잡혀 있습니다 [docs:history/cluster_state_20261116.md:9-15] [docs:history/cluster_state_20261116.md:26]. 일부러 그렇게 한 것이 아니라 기본값이 남은 것입니다 [docs:history/human_answers_20261116.md:15]. 실제 통신은 위에서 말한 대로 고정망을 타기 때문에 클러스터는 정상으로 돕니다. 다만 이것을 고치지 않고 지금 상태 그대로 문서에 적었고, 그 때문에 따라오는 일을 한계로 남겼습니다.

- 노드 목록 화면에 보이는 노드 주소는 관리망 주소입니다. 그 화면만 보고 노드끼리 어느 길로 통신하는지 판단하면 틀립니다 [docs:history/cluster_state_20261116.md:9-15] [docs:history/cluster_state_20261116.md:23-24].
- 노드의 내부 주소를 그대로 가져다 쓰는 기능은 관리망을 탑니다. 예를 들어 모니터링이 노드마다 컨테이너 사용량을 긁어 올 때 찾아가는 주소가 이 내부 주소입니다 [code:apps/monitoring/prometheus/configmap.yaml:33-43].
- 관리망 주소는 재부팅 때 바뀔 수 있으므로, 바뀌면 노드의 내부 주소도 따라 바뀝니다 [docs:history/human_answers_20261116.md:7] [docs:history/human_answers_20261116.md:15].
- 바깥 인터넷으로 나가는 기본 길은 관리망 쪽입니다. 랜카드 둘이 하는 일이 완전히 갈라진 것은 아닙니다 [docs:history/cluster_state_20261116.md:21].
