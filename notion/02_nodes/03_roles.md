<!--
다루는 곳: cluster/label-nodes.sh
읽은 커밋: 6290346
-->
# 02-03 역할 라벨과 워커 증설

## 노드마다 맡은 일

워커 네 대는 똑같이 생겼지만 맡은 일이 다르다. w1과 w2는 앱 노드로, 두 서비스의 앱과 데이터베이스가 여기에 뜬다. w3은 기반 노드로, 이미지 저장소와 빌드 서버, 배포 도구가 모여 있다. w4는 플랫폼 노드로, 지표와 로그를 모으는 모니터링이 산다. [code:cluster/label-nodes.sh:6-8] 컨트롤 플레인 m-k8s에는 역할 라벨이 없고 일반 파드도 올리지 않는다. [docs:history/cluster_state_20261116.md:11] [docs:history/build_log/08_scale_out.md:17]

이 배치는 역할 라벨(노드에 붙이는 이름표)로 정한다. `cluster/label-nodes.sh`가 네 워커에 차례로 app, app, infra, platform 이름표를 붙이고, 끝에 노드 목록을 이름표와 함께 보여 준다. [code:cluster/label-nodes.sh:10-15] 각 앱의 배포 정의는 이 이름표를 보고 "이 이름표가 붙은 노드에만 뜬다"는 조건(nodeSelector)을 단다. 앱과 데이터베이스 복제본은 app 노드를, 이미지 저장소와 빌드 서버는 infra 노드를, 모니터링 구성 요소는 platform 노드를 고른다. [code:apps/petmint/app/deployment.yaml:44] [code:platform/harbor/values.yaml:56] [code:platform/jenkins/values.yaml:22] [code:apps/monitoring/prometheus/statefulset.yaml:24]

들어오는 문, 바깥 터널, 클러스터 이름 풀이, 인증서 관리 같은 공용 구성 요소는 이름표 조건이 없어 아무 워커에나 뜬다. [docs:history/build_log/08_scale_out.md:33]

## 왜 역할을 나눴나

처음에는 노드에 역할이 없었다. 그러자 노드 디스크에 붙는 저장 공간이 처음 뜬 노드에 제각각 생겼고, 이미지 저장소 하나만 해도 조각이 세 노드에 흩어졌다. 그 결과 어느 워커를 내려도 이미지 저장소의 일부가 멈췄다. 그때 노드는 control-plane 하나와 워커 셋(w1 ~ w3)을 합해 넷이었는데, 노드 하나가 죽으면 무엇이 멈추는지 말할 수 없는 상태였다. [docs:history/build_log/08_scale_out.md:117-125] 지금은 w4가 붙어 control-plane 하나와 워커 넷, 모두 다섯 대다. [docs:history/cluster_state_20261116.md:9-15]

역할을 나눈 목표는 노드가 죽었을 때 멈추는 것을 노드 이름으로 말할 수 있게 하는 것이다. [docs:history/build_log/08_scale_out.md:129] 지금은 이렇게 답한다. w3이 죽으면 새 배포와 빌드가 멈추지만 서비스는 돈다. 이미 떠 있는 파드는 이미지를 노드에 갖고 있기 때문이다. w4가 죽으면 모니터링과 로그만 멈춘다. 앱 노드 하나가 죽으면 앱은 남은 노드의 파드가 받는다. 다만 w1이 죽으면 데이터베이스 원본이 멈추므로, 사람이 복제본을 원본으로 올리기 전까지 쓰기가 실패한다. [docs:history/build_log/08_scale_out.md:26-31] [docs:history/build_log/08_scale_out.md:407]

이름표는 노드를 새로 만들거나 클러스터에 다시 붙이면 사라진다. 그래서 손으로 붙이지 않고 스크립트로 남겼다. 스크립트는 이미 붙은 이름표를 덮어쓰는 방식이라 몇 번을 돌려도 결과가 같고, 컨트롤 플레인에서 다시 돌리면 된다. [code:cluster/label-nodes.sh:3-4] [code:cluster/label-nodes.sh:11-14]

## w4를 더한 까닭

워커는 처음에 세 대였고, 가장 늦게 w4 한 대를 더해 네 대가 됐다. [docs:history/build_log/01_cluster.md:142] [docs:history/cluster_state_20261116.md:15] 더한 까닭은 노드 하나를 정비하는 동안에도 서비스가 돌게 하려는 것이었다. [docs:history/build_log/01_cluster.md:620] w4는 처음부터 플랫폼 노드로 정하고 만들었고, 모니터링이 이 자리에 들어왔다. [code:cluster/Vagrantfile:8-9]

노드를 늘리기 전에 먼저 한 일이 있다. 노드를 하나씩 내려 메모리를 늘리고 정비하려면, 내리는 노드에 있던 앱이 끊기지 않아야 한다. 앱이 파드 하나뿐이면 그 노드를 내리는 순간 서비스가 멈추므로, 증설 전에 두 앱을 모두 파드 둘로 늘리고 서로 다른 노드에 뜨게 했다. [docs:history/build_log/08_scale_out.md:143]

## 워커를 더하는 순서

워커를 더하는 일은 앞의 두 편에서 다룬 파일을 차례로 쓰는 일이다. 먼저 호스트에 새 VM에 줄 메모리가 남아 있는지 본다. 같은 서버의 추론 서버와 메모리를 나눠 쓰기 때문이다. [docs:history/build_log/01_cluster.md:90] 다음으로 Vagrantfile의 노드 목록에 한 줄을 더하고(저장소와 호스트 작업 폴더 두 곳 모두), 호스트 작업 폴더에서 그 노드만 만든다. 만들면서 이름 풀이, 이미지 저장소 이름, 공유 폴더 도구가 프로비저너로 함께 들어간다. [docs:history/build_log/01_cluster.md:91-92] [code:cluster/Vagrantfile:25-44]

그다음 → 「노드 설치」의 스크립트를 새 노드에 돌려 기존 노드와 같은 판을 깐다. 클러스터에 붙일 때는 컨트롤 플레인에서 짧게 쓰고 버리는 참가 토큰을 새로 만들어 화면에 내지 않고 바로 새 노드로 넘긴다. 토큰은 클러스터에 들어올 수 있는 열쇠라서, 오래 살아 있거나 기록에 남으면 안 되기 때문이다. [docs:history/build_log/01_cluster.md:93-97] [docs:history/build_log/01_cluster.md:638] 마지막으로 `cluster/label-nodes.sh`에 새 노드의 줄을 더해 다시 돌린다. [docs:history/build_log/01_cluster.md:98]

붙은 뒤에는 노드가 준비 상태인지, 노드마다 하나씩 도는 Calico와 MetalLB 구성 요소가 그 노드에서도 도는지 본다. 그리고 그 노드에만 뜨도록 묶은 시험 파드로 이미지 저장소에서 이미지를 받고, 클러스터 이름 풀이와 공유 폴더 붙이기가 되는지 확인한다. 새 노드가 준비 상태라는 것만으로는 그 노드에서 앱이 실제로 뜰 수 있는지 알 수 없어서다. [docs:history/build_log/01_cluster.md:99]

## 알려진 한계

- infra와 platform은 노드가 한 대씩이다. w3이 죽으면 배포와 빌드가, w4가 죽으면 모니터링이 그 노드가 돌아올 때까지 멈춘다. 목표로 받아들인 한계다. [docs:history/build_log/08_scale_out.md:434]
- app 노드가 두 대뿐이다. 앱 노드 하나가 죽으면 각 앱이 파드 하나로 버틴다. [docs:history/build_log/08_scale_out.md:433]
- 이름표는 노드를 다시 만들면 사라지고, 스크립트를 다시 돌려야 돌아온다. 그 사이에는 이름표 조건이 걸린 파드가 그 노드에 뜨지 않는다. [code:cluster/label-nodes.sh:3]
- 컨트롤 플레인이 한 대다. m-k8s가 죽으면 이미 뜬 파드는 돌지만 새 배치와 복구, 사람의 명령이 멈춘다. [docs:history/build_log/01_cluster.md:700]
- 빌드 서버가 빌드할 때 띄우는 파드는 이름표 조건이 없어 아무 워커에나 뜬다. 앱 노드에 뜨면 앱과 메모리를 나눠 쓴다. [docs:history/build_log/08_scale_out.md:34] [docs:history/build_log/08_scale_out.md:440]

## 용어 풀이

- 라벨(이름표): 노드나 파드에 붙이는 이름과 값의 짝. 무엇을 어디에 둘지 고를 때 쓴다
- nodeSelector: "이 라벨이 붙은 노드에만 띄워라"라는 파드의 조건
- 컨트롤 플레인: 클러스터 전체를 관리하는 노드. 명령을 받고 파드를 어디에 둘지 정한다
- 워커: 실제로 앱 파드가 도는 노드
- 참가 토큰: 새 노드가 클러스터에 들어올 때 내미는 일회성 열쇠
- 복제본(Replica): 데이터베이스 원본의 내용을 그대로 따라 쓰는 사본
