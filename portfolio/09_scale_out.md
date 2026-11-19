<!--
다루는 곳: cluster/label-nodes.sh, cluster/Vagrantfile, apps/petmint/app/deployment.yaml, apps/petmint/app/pdb.yaml, apps/runshoes/app/deployment.yaml, apps/runshoes/app/pdb.yaml, platform/harbor/pvc-w3.yaml, platform/harbor/values.yaml, platform/argocd/pin-infra.sh, platform/jenkins/values.yaml, apps/petmint/mysql/replica.yaml, docs/runbooks/mysql-replica.md
읽은 커밋: ddbaadf
-->
# 워커를 늘리고 옮기기

> 이 글은 워커 노드를 한 대 더하고, 노드마다 역할을 정해 이미지 저장소와 배포 도구, 데이터베이스 사본을 옮긴 일을 다룹니다.

**노드 하나가 죽으면 무엇이 멈추는지 말할 수 없던 클러스터를, 노드 이름으로 답할 수 있는 클러스터로 바꿨습니다. 옮기는 동안 끊긴 일도 있었고, 그중 한 번은 원인을 아직 모릅니다.**

## 상황

이 클러스터는 서버 한 대 위의 가상 머신(VM)으로 이루어져 있습니다. 클러스터 전체를 관리하는 컨트롤 플레인 m-k8s 한 대와, 실제로 앱이 도는 워커 노드들입니다. 처음에는 워커가 w1부터 w3까지 세 대여서 노드는 모두 넷이었습니다 [docs:history/build_log/08_scale_out.md:117] [docs:history/build_log/01_cluster.md:620].

문제는 데이터가 놓인 자리였습니다. 이 클러스터는 저장 공간으로 local-path를 씁니다. 노드의 디스크 한 칸을 떼어 파드(쿠버네티스에서 컨테이너가 도는 단위)에 붙여 주는 방식인데, 그 칸은 파드가 처음 뜬 노드에 만들어지고 그 노드에 묶입니다 [docs:history/build_log/08_scale_out.md:117] [code:platform/harbor/pvc-w3.yaml:4]. 노드에 역할이 없던 때라 상태를 가진 것들이 처음 뜬 자리에 제각각 남았습니다. 이미지 저장소 Harbor 하나만 해도 데이터베이스, 캐시, 이미지 보관 칸이 세 노드에 흩어졌고, 그 결과 어느 워커를 내려도 Harbor의 일부가 멈췄습니다. 런슈즈 앱은 파드가 하나뿐이라 그 노드가 내려가면 서비스가 끊겼습니다 [docs:history/build_log/08_scale_out.md:119-125].

워커를 늘리고 메모리를 키우려면 노드를 하나씩 꺼야 했습니다 [docs:history/build_log/01_cluster.md:620]. 그런데 어느 노드를 꺼도 무엇이 멈출지 미리 말할 수 없었습니다.

## 고른 것

목표를 한 문장으로 정했습니다. 노드가 죽었을 때 무엇이 멈추는지를 노드 이름으로 말할 수 있게 하는 것입니다 [docs:history/build_log/08_scale_out.md:129].

그 답이 노드 역할입니다. 워커마다 역할 라벨(노드에 붙이는 이름표)을 붙였습니다. w1과 w2는 앱과 데이터베이스를 맡는 app, w3은 이미지 저장소와 빌드 서버와 배포 도구를 맡는 infra, 새로 만든 w4는 모니터링을 맡는 platform입니다 [code:cluster/label-nodes.sh:6-8]. 각 구성 요소의 설정은 「이 이름표가 붙은 노드에만 뜬다」는 조건을 답니다 [code:apps/petmint/app/deployment.yaml:43-44] [code:platform/harbor/values.yaml:56] [code:platform/jenkins/values.yaml:21-22] [code:platform/argocd/pin-infra.sh:7]. 라벨은 노드를 다시 만들면 사라지므로 손으로 붙이지 않고, 몇 번을 돌려도 결과가 같은 스크립트로 남겼습니다 [code:cluster/label-nodes.sh:3] [code:cluster/label-nodes.sh:11-14].

일은 이 차례로 했습니다.

먼저 앱을 둘로 나눴습니다. 노드를 하나씩 내리는데 앱 파드가 하나뿐이면 그 노드를 내리는 순간 서비스가 끊기기 때문입니다 [docs:history/build_log/08_scale_out.md:143]. 두 앱 모두 파드를 둘로 두고, 두 파드가 같은 노드에 뜨지 못하게 하는 anti-affinity(서로 떨어져 뜨라는 조건)를 걸었습니다 [code:apps/runshoes/app/deployment.yaml:22] [code:apps/petmint/app/deployment.yaml:45-51]. 그리고 PDB(노드를 비울 때 최소 몇 개는 남겨 두라는 약속)로 둘이 한꺼번에 내려가지 않게 했습니다 [code:apps/petmint/app/pdb.yaml:1] [code:apps/petmint/app/pdb.yaml:11].

다음으로 w4를 만들어 붙이고, 기존 워커 셋은 하나씩 비우고 꺼서 메모리를 늘렸습니다. 한 노드씩 「새 파드 배치 막기, 앱 파드 먼저 내보내기, 나머지 내보내기, 끄기, 메모리 늘리기, 켜기, 배치 다시 열기」를 되풀이했습니다 [docs:history/build_log/08_scale_out.md:196-197] [code:cluster/Vagrantfile:5-9].

그다음 흩어진 것을 역할 자리로 모았습니다. Harbor는 데이터를 w3 한 곳으로 옮겼고, 배포 도구 ArgoCD와 빌드 서버 Jenkins도 w3에 고정했습니다 [docs:history/build_log/08_scale_out.md:403]. 데이터베이스는 쓰기를 받는 원본(Primary)을 w1에 두고, 그 내용을 따라 적는 사본(Replica)을 w2에 새로 만들었습니다 [docs:runbooks/mysql-replica.md:3]. 원본이 죽어도 사본이 저절로 원본이 되지는 않고, 사람이 절차서(런북)를 따라 올립니다 [docs:runbooks/mysql-replica.md:3] [docs:runbooks/mysql-replica.md:44-45].

## 까닭

Harbor를 옮긴 방식은 local-path의 성질에서 나왔습니다. local-path 저장 공간은 다른 노드로 옮길 수 없습니다. 게다가 원본은 지우지 않는다는 조건이 있었습니다. 그래서 w3에 새 이름의 저장 공간 다섯을 만들고, 노드 사이로 데이터를 복사한 뒤, Harbor가 새 쪽을 보게 바꿨습니다 [docs:history/build_log/08_scale_out.md:259]. 복사 뒤에는 파일 이름, 크기, 권한, 소유자 목록을 원본과 견줘 같은 것을 확인했고 [docs:history/build_log/08_scale_out.md:283], 옛 저장 공간 다섯은 지우지 않고 남겨 두었습니다 [code:platform/harbor/pvc-w3.yaml:1].

데이터베이스에 자동 전환을 넣지 않은 까닭은 자원입니다. 자동 전환을 해 주는 도구는 붙는 부품이 늘고 메모리를 더 먹는데, VM 몇 대에 Harbor와 Jenkins와 모니터링까지 이미 올라가 있었습니다. 사람이 알아채고 올려야 하는 대신 구성이 단순하고 무엇을 하는지가 다 보이는 쪽을 골랐습니다 [docs:history/build_log/08_scale_out.md:134-137]. 사본은 원본과 같은 노드에 뜨지 못하게 막았습니다. 같은 노드에 있으면 그 노드가 멈출 때 둘이 같이 멈춰 사본을 둔 뜻이 없기 때문입니다 [docs:history/build_log/08_scale_out.md:325] [code:apps/petmint/mysql/replica.yaml:7]. 사본을 실제로 원본으로 올리는 시험도 해 봤습니다. 기계가 하는 일은 약 2분이었고, 나머지는 사람이 장애를 알아채고 판단하는 시간입니다. 앱 트래픽까지 새 쪽으로 옮기는 진짜 전환은 운영 쓰기를 멈춰야 해서 하지 않았습니다 [docs:history/build_log/08_scale_out.md:363-371].

결과는 처음 정한 목표에 대한 답입니다. 이제 「노드 하나가 죽으면 무엇이 멈추나」에 노드 이름으로 답할 수 있습니다 [docs:history/build_log/08_scale_out.md:407]. w3이 죽으면 새 배포와 빌드가 멈추지만, 이미 떠 있는 앱 파드는 이미지를 노드에 갖고 있어 서비스는 돕니다. w4가 죽으면 모니터링이 멈춥니다. w1이 죽으면 사람이 사본을 올리기 전까지 데이터베이스 쓰기가 실패합니다. 앱 노드 하나가 빠져도 앱 자체는 남은 파드가 받습니다 [docs:history/build_log/08_scale_out.md:26-31]. 지금 클러스터는 컨트롤 플레인 하나와 워커 넷, 모두 다섯 대입니다 [docs:history/cluster_state_20261116.md:9-15].

## 치른 값

- 데이터베이스 원본이 죽으면 자동으로 넘어가지 않습니다. 사람이 알아채고 사본을 올리기 전까지 두 앱의 쓰기는 실패합니다 [docs:runbooks/mysql-replica.md:3] [docs:history/build_log/08_scale_out.md:28]. 자동 전환 도구는 부품과 메모리를 더 먹어 쓰지 않았습니다 [docs:history/build_log/08_scale_out.md:134-137].
- 역할 노드가 한 대씩인 것은 여러 결정에 걸려 → 「알려진 한계」에 모았습니다

## 조건

아래는 고른 것이 아니라 바탕이 그러해서 따라오는 것입니다.

- 앱 노드가 둘뿐이라 새 파드를 먼저 띄우는 보통의 교체 방식을 쓸 수 없게 됐습니다. 세 번째 파드가 갈 노드가 없기 때문입니다. 그래서 옛 파드 하나를 먼저 내리고 새 파드를 띄우며, 교체하는 동안 잠깐 파드가 하나뿐입니다 [code:apps/petmint/app/deployment.yaml:5-7].
- 노드 역할이 모두 같은 서버 위에 있는 것은 여러 결정에 걸려 → 「알려진 한계」에 모았습니다

## 막혔을 때

**끊긴 것까지 그대로 적습니다.** Harbor, ArgoCD, Jenkins를 옮기는 동안 앱 응답은 끊기지 않았습니다. 앱 파드가 이미지를 노드에 이미 갖고 있었기 때문입니다 [docs:history/build_log/08_scale_out.md:419]. 이를 확인하려고 정비 내내 호스트에서 1초마다 다섯 주소를 불러 실패를 셌습니다 [docs:history/build_log/08_scale_out.md:220].

하지만 w1을 정비할 때는 끊김이 두 번 있었습니다. 하나는 예정된 것입니다. 그때 w1에는 두 앱의 MySQL과 Harbor의 redis(캐시)가 묶여 있었습니다 [docs:history/build_log/08_scale_out.md:121]. 그래서 이 노드를 끄는 약 1분 40초 동안 MySQL과 redis가 멈췄습니다. 사람이 미리 받아들인 중단입니다 [docs:history/build_log/08_scale_out.md:228] [docs:history/human_answers_20261117.md:15]. 다른 하나는 예정에 없던 것입니다. w1을 비우기 전에 들어오는 문 역할을 하는 ingress-nginx(바깥 요청을 주소에 따라 각 서비스로 나눠 주는 프로그램)를 다른 노드로 옮기려고 다시 띄웠더니, 12초 동안 다섯 주소가 모두 응답하지 않았습니다 [docs:history/build_log/08_scale_out.md:249]. **이 12초 끊김의 원인은 확인하지 못했습니다** [docs:history/build_log/08_scale_out.md:251]. 그 뒤 ingress-nginx를 두 개로 늘리고 하나씩 교체했는데, 그때도 1초 한 번은 다섯 주소 모두 응답이 없었습니다. 12초보다 짧지만 0은 아닙니다 [docs:history/build_log/08_scale_out.md:392] [docs:history/build_log/08_scale_out.md:441].

정비 순서를 바꾼 일도 있습니다. 처음에는 노드를 통째로 비웠습니다. 그런데 앱 파드가 다른 노드로 옮겨 가면서 Harbor에서 이미지를 받아야 하는 바로 그때, 같은 비우기가 Harbor까지 멈추면 새 파드가 이미지를 받지 못해 뜨지 못할 수 있었습니다. 그래서 앱 파드만 먼저 옮기고 나머지를 비우는 두 단계로 바꿨습니다 [docs:history/build_log/08_scale_out.md:200-201].

꺼진 노드가 한동안 「준비됨」으로 보이는 것도 겪었습니다. w2를 끈 직후 노드가 준비됐는지 기다리는 명령이 바로 통과했습니다. 쿠버네티스는 노드가 보내던 신호가 끊긴 뒤에야 꺼진 것을 알기 때문에, 막 끈 노드에는 준비 상태가 아직 남아 있습니다. 이후로는 「준비 안 됨」을 거쳐 다시 「준비됨」이 된 것을 보고 나서 배치를 다시 열었습니다 [docs:history/build_log/08_scale_out.md:233-237].
