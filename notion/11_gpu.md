<!--
다루는 곳: scripts/host-gpu-exporter.sh
읽은 커밋: 6290346
-->
# 11 GPU와 호스트 서비스

이 클러스터에서 GPU를 쓰는 일은 모두 클러스터 밖, 물리 서버(호스트)에서 일어난다. 쿠버네티스 노드는 호스트 위에 올린 가상 머신이고, 그 가상 머신에는 GPU가 없다. 답을 만드는 언어 모델, 검색에 쓰는 임베딩 모델, 벡터 DB는 호스트에서 돌고, 클러스터 안의 파드는 그것들을 네트워크 너머의 API로 부른다. 이 편은 호스트에 무엇이 떠 있고, 파드가 그것을 어떻게 부르며, GPU 한 장을 여럿이 나눠 쓰는 데서 무엇이 생기는지를 다룬다.

## GPU를 가상 머신에 넘기지 않은 까닭

GPU 패스스루(물리 GPU를 가상 머신 하나에 통째로 넘겨, 그 안에서 제 장치처럼 쓰게 하는 것)를 하면 쿠버네티스가 GPU를 직접 나눠 줄 수도 있었다. 그 길을 가지 않았다. 처음 해 보는 작업이라 위험이 컸고, 호스트에서는 이미 추론 서버를 계속 쓰고 있어서 GPU를 가상 머신에 넘기면 호스트 쪽이 GPU를 못 쓰게 될 수 있었다. [docs:history/build_log/kubernetes_install.md:117] 그래서 GPU는 호스트에 그대로 두고, 파드는 추론 서버의 API를 네트워크로 부르기만 하는 구조로 정했다. [docs:history/build_log/kubernetes_install.md:200]

이 구조의 대가는 파드가 GPU를 직접 쓰지 못한다는 것이다. 쿠버네티스는 GPU가 얼마나 남았는지 모르고, GPU를 쓰는 일을 노드 사이로 옮겨 줄 수도 없다. 그 대신 호스트에서 이미 돌던 모델과 도구를 손대지 않고 그대로 클러스터에서 쓸 수 있다.

## 호스트에 떠 있는 것

GPU는 NVIDIA GeForce RTX 5070 Ti 한 장이고 메모리는 16GB다. [docs:history/notion_hardware_20261116.md:16] 호스트에서 이 클러스터와 닿는 서비스는 다섯 갈래다. [docs:history/cluster_state_20261116.md:77-78]

추론 서버는 Ollama(언어 모델을 받아 두었다가 요청이 오면 GPU에 올려 답을 만드는 서버)이고, 호스트의 Docker 컨테이너로 돈다. 여럿이 함께 부를 수 있는 백그라운드 API 서버라서 골랐다. 앞서 쓰던 데스크톱 도구는 서버 전체에서 한 사람만 띄울 수 있어, 누가 쓰고 있으면 다른 사람은 실행조차 못 하는 일을 실제로 겪었다. [docs:history/notion_hardware_20261116.md:31-32] 같은 호스트에 채팅 화면(Open WebUI)도 붙어 있지만 호스트 자신에게만 열려 있어 클러스터와는 닿지 않는다. [docs:history/notion_hardware_20261116.md:51]

호스트의 벡터 DB는 Milvus이고 역시 Docker 컨테이너로 돈다. 펫퍼민트가 약관 조각을 뜻으로 찾을 때 쓴다. [docs:history/build_log/00_server.md:99] 펫퍼민트의 검색 서비스(search-service)는 호스트의 systemd 서비스로 돌며, 키워드 검색과 벡터 DB 검색을 묶어 조항을 찾아 준다. [docs:history/build_log/00_server.md:143] 임베딩과 리랭커를 맡는 model-service도 호스트의 systemd 서비스이고 GPU를 쓴다. [docs:history/build_log/00_server.md:142] 마지막으로 GPU 지표를 내보내는 수집기(nvidia-gpu-exporter)가 컨테이너로 떠 있다. [docs:history/cluster_state_20261116.md:77]

이 서비스들은 ArgoCD가 관리하지 않는다. 저장소에 매니페스트가 없고, 호스트에서 사람이 띄운다. 이 저장소가 직접 가진 것은 GPU 수집기를 띄우는 스크립트 하나다. [code:scripts/host-gpu-exporter.sh:1-7]

## 파드가 호스트를 부르는 길

파드 안에서 「자기 자신」을 뜻하는 주소는 파드 자신이라, 파드는 호스트를 가상 머신 사설망 쪽에서 본 호스트 주소로 부른다. 이 사설망은 가상 머신 설정에 고정 주소로 박혀 있어, 가상 머신을 다시 만들어도 주소가 바뀌지 않는다. [code:apps/petmint/app/configmap.yaml:20-22]

펫퍼민트는 추론 서버, 벡터 DB, 검색 서비스 셋을 부른다. 세 주소는 펫퍼민트 ConfigMap에 들어 있다. [code:apps/petmint/app/configmap.yaml:23-26] 상담에 쓰는 모델은 기본 모델과 약관으로 학습한 모델 둘이고, 둘 다 추론 서버에 미리 올려 둔 이름으로 부른다. [code:apps/petmint/app/configmap.yaml:27-30]

런슈즈는 앱 컨테이너와 챗봇 컨테이너가 모두 추론 서버를 부른다. 앱은 리뷰 요약에, 챗봇은 답을 쓰는 데 쓴다. [code:apps/runshoes/app/deployment.yaml:6] [code:apps/runshoes/app/deployment.yaml:98-99] [code:apps/runshoes/app/deployment.yaml:144-145] 챗봇은 model-service도 부른다. 이 주소가 없으면 챗봇은 뜨기는 하지만 리뷰 검색 색인을 만들지 못한다. [code:apps/runshoes/app/deployment.yaml:146-149] 하루 한 번 도는 리뷰 요약 배치도 추론 서버를 부르는데, 추론 서버가 매달려도 두 시간이면 끝나도록 상한을 걸어 두었다. [code:apps/runshoes/app/cronjob.yaml:27] [code:apps/runshoes/app/cronjob.yaml:49-50]

추론 서버는 모든 주소에 열려 있지 않다. 호스트 자신, Docker 다리, 가상 머신 사설망의 호스트 주소 세 곳에만 연다. [docs:history/notion_hardware_20261116.md:50] 파드가 들어오는 길은 이 중 사설망 주소 하나다.

클러스터 밖에도 추론 서버를 부르는 곳이 있다. 학교 PC는 환경이 달라 사설망에 닿지 못하므로, 호스트에서 도는 전용 Cloudflare 터널로 추론 서버를 부른다. [docs:history/build_log/03_cloudflare_tunnel.md:114] 이 터널은 사람이 아니라 프로그램이 부르는 길이라, Cloudflare Access의 서비스 토큰(사람의 로그인 대신 요청 머리에 붙이는 비밀 열쇠)이 있어야만 통과한다. [docs:history/build_log/03_cloudflare_tunnel.md:180] 클러스터의 파드는 이 터널을 쓰지 않는다. [docs:history/build_log/03_cloudflare_tunnel.md:68]

## GPU 한 장을 나눠 쓰기

추론 서버는 모델을 요청이 올 때만 GPU 메모리에 올리고, 마지막 요청 뒤 유지 시간(기본 5분)이 지나면 내린다. [docs:history/notion_hardware_20261116.md:33] 쉬는 동안에는 메모리를 비워 두니, GPU 한 장으로 여러 모델과 여러 클라이언트를 돌릴 수 있다. 대가로 모델이 내려간 뒤 오는 첫 질문은 모델을 다시 올리느라 몇 초 더 걸린다. [code:apps/monitoring/grafana/dashboards/gen_petmint.py:187-188]

이 유지 시간은 기본값 그대로 두고 바꾸지 않는다. 클러스터의 두 서비스만 GPU를 쓰는 것이 아니라, 학교 PC 같은 다른 클라이언트도 같은 GPU 메모리를 나눠 쓰기 때문이다. [code:CLAUDE.md:34] 한쪽 서비스의 첫 답을 빠르게 하려고 유지 시간을 늘리면, 그 모델이 메모리를 오래 붙잡아 다른 쪽이 모델을 올릴 자리가 줄어든다.

나눠 쓰는 쪽이 여럿이라 서로 밀어내는 일이 생긴다. 펫퍼민트는 모드에 따라 기본 모델과 학습한 모델을 번갈아 쓰므로, 모드가 섞여 들어오면 두 모델을 번갈아 올리느라 답이 느려질 수 있다. [code:apps/monitoring/grafana/dashboards/gen_petmint.py:202-203] 런슈즈 챗봇과 리뷰 요약은 또 다른 모델을 쓰고, 두 서비스가 모델을 서로 내렸다 올리면 그때 첫 답이 늦어진다. [code:apps/monitoring/grafana/dashboards/gen_runshoes.py:288-290] model-service의 임베딩 모델도 같은 GPU 메모리에 올라간다. [code:apps/monitoring/grafana/dashboards/gen_runshoes.py:285]

이 모습은 모니터링에서 그대로 보인다. 호스트의 GPU 수집기는 GPU 사용률, 메모리, 온도, 전력을 내보내고 [code:scripts/host-gpu-exporter.sh:4], 추론 서버에 지금 어떤 모델이 올라가 있는지는 클러스터 안의 변환기가 추론 서버에 물어 지표로 바꾼다. [code:apps/monitoring/json-exporter/json-exporter.yaml:1-3] 자세한 것은 → 「지표」와 → 「대시보드」에 있다.

GPU 수집기는 sudo 없이 Docker 그룹 권한으로 사람이 한 번 띄운다. 가상 머신 사설망 주소에만 포트를 열고 바깥이나 공유기 쪽으로는 열지 않으며, 추론 서버와 벡터 DB 컨테이너는 건드리지 않는다. [code:scripts/host-gpu-exporter.sh:2-5] 재시작 정책이 붙어 있어 사람이 멈추지 않는 한 Docker가 다시 띄운다. [code:scripts/host-gpu-exporter.sh:11]

## 알려진 한계

- GPU가 한 장이다. 바깥에서 터널로 긴 생성을 돌리면 펫퍼민트 서빙이 멈출 수 있다. 그래서 그 터널은 늘 Access 뒤에 둔다. [docs:history/build_log/03_cloudflare_tunnel.md:701]
- 서버 한 대가 전부다. 호스트가 꺼지면 추론 서버, 벡터 DB, model-service와 쿠버네티스 가상 머신이 함께 멈춘다. [docs:history/build_log/kubernetes_install.md:198]
- 호스트 서비스는 ArgoCD 밖이라 저장소로 상태를 되돌릴 수 없다. [docs:history/cluster_state_20261116.md:76-77] GPU 수집기는 컨테이너가 사라지면 사람이 스크립트를 다시 돌려 띄운다. [docs:history/build_log/09_monitoring.md:124] [code:scripts/host-gpu-exporter.sh:11] 추론 서버와 다른 호스트 서비스가 사라졌을 때 어떻게 다시 띄우는지는 이 저장소에 기록이 없다.
- 검색 서비스와 model-service가 살아 있는지는 모니터링이 보지 못한다. 추론 서버와 벡터 DB만 응답 여부를 본다. [docs:history/build_log/09_monitoring.md:212]
- 벡터 DB는 가상 머신 사설망에 인증 없이 열려 있다. 그 망에는 호스트와 가상 머신만 있다. [docs:history/build_log/09_monitoring.md:211] [code:apps/monitoring/ingress.yaml:6]
- 파드가 부르는 호스트 주소는 매니페스트에 글자로 박혀 있다. 사설망 대역이 바뀌면 펫퍼민트와 런슈즈 매니페스트를 함께 고쳐야 한다. [code:apps/petmint/app/configmap.yaml:23-26] [code:apps/runshoes/app/deployment.yaml:98-99]

## 용어 풀이

- GPU 패스스루: 물리 GPU를 가상 머신 하나에 통째로 넘겨, 그 가상 머신이 직접 쓰게 하는 것
- 추론 서버: 학습이 끝난 모델을 메모리에 올려 두고 질문을 받으면 답을 만들어 돌려주는 서버. 여기서는 Ollama
- 벡터 DB: 글을 숫자 묶음(벡터)으로 바꿔 저장하고, 뜻이 가까운 것을 찾아 주는 DB. 여기서는 Milvus
- 임베딩 모델: 글을 벡터로 바꾸는 모델. 리랭커는 찾은 후보를 질문과 얼마나 맞는지 다시 매겨 순서를 바꾸는 모델
- 유지 시간: 마지막 요청 뒤 모델을 GPU 메모리에 남겨 두는 시간
- 서비스 토큰: 사람이 로그인하는 대신 프로그램이 요청마다 붙여 신원을 밝히는 열쇠
