<!--
다루는 곳: apps/monitoring/prometheus/, apps/monitoring/node-exporter/, apps/monitoring/kube-state-metrics/, apps/monitoring/json-exporter/
읽은 커밋: 736d833
-->
# 12-01 지표

지표는 시간에 따라 바뀌는 숫자다. 노드의 CPU 사용량, 파드가 다시 시작된 횟수, 초당 요청 수, GPU 메모리 사용량 같은 것이 모두 지표다. 이 클러스터에서는 Prometheus 한 대가 지표를 모으고 저장한다. Prometheus는 지표를 내보내는 곳(수집 대상)에 정해진 간격마다 찾아가 값을 긁어 오는 방식으로 일한다. 간격은 30초다. [code:apps/monitoring/prometheus/configmap.yaml:7-10] 앱이 Prometheus에 값을 밀어 넣는 것이 아니라 Prometheus가 가져가는 것이라, 수집 대상은 지표를 읽을 수 있는 주소만 열어 두면 된다.

## 무엇을 어디서 긁나

수집 대상은 설정 파일 하나(`prometheus/configmap.yaml`)에 모두 적혀 있다. Operator(설정을 쿠버네티스 객체로 받아 대신 관리해 주는 프로그램) 없이 이 파일 하나로 끝난다. [docs:history/build_log/09_monitoring.md:32] 대상은 성격에 따라 넷으로 묶인다.

첫째는 노드와 컨테이너다. node-exporter는 노드마다 하나씩 떠서 그 노드의 CPU, 메모리, 디스크, 네트워크를 내보낸다. 노드의 운영체제 정보를 읽기 전용으로 들여다보고, 컨트롤 플레인 노드(m-k8s)에도 뜨도록 모든 taint(노드가 파드를 가려 받는 표시)를 견디게 했다. [code:apps/monitoring/node-exporter/daemonset.yaml:1-2] [code:apps/monitoring/node-exporter/daemonset.yaml:16-19] Prometheus는 node-exporter의 헤드리스 서비스(주소 하나로 묶지 않고 파드 주소를 그대로 알려 주는 서비스)로 노드별 대상을 찾는다. [code:apps/monitoring/node-exporter/service.yaml:1] 컨테이너가 CPU와 메모리를 얼마나 쓰는지는 각 노드의 kubelet에 들어 있는 cAdvisor에서 읽는다. [code:apps/monitoring/prometheus/configmap.yaml:33-34]

둘째는 쿠버네티스 객체의 상태다. kube-state-metrics는 API 서버를 지켜보며 파드가 준비됐는지, 몇 번 다시 시작했는지, 요청량과 상한이 얼마인지 같은 상태를 지표로 바꾼다. [code:apps/monitoring/prometheus/configmap.yaml:53-56] 판은 클러스터의 쿠버네티스 판에 맞춰 골랐다. [code:apps/monitoring/kube-state-metrics/deployment.yaml:1]

셋째는 주석을 단 파드다. 파드에 「긁어 가라」는 주석과 포트, 경로를 달면 Prometheus가 스스로 찾아가 긁는다. [code:apps/monitoring/prometheus/configmap.yaml:58-59] 지금 이 길로 들어오는 것은 ingress-nginx 컨트롤러와 런슈즈 앱이다. 펫퍼민트 앱에는 지표를 내보내는 주소가 없어서, 들어오는 요청 수와 오류는 앞단의 ingress-nginx가 주소별로 센 값을 쓴다. [code:platform/ingress-nginx/overlay/deployment-patch.yaml:4-5] [code:platform/ingress-nginx/overlay/deployment-patch.yaml:17-19] 런슈즈 앱(Spring Boot)은 스스로 지표 주소를 열고 있어 API별 요청 수, 응답 시간, DB 연결, 자바 메모리를 직접 내보낸다. [code:apps/runshoes/app/deployment.yaml:40-42]

넷째는 클러스터 밖, 호스트의 서비스다. 호스트의 GPU 수집기가 GPU 사용률, 메모리, 온도, 전력을 내보내고, Prometheus는 그중 쓰는 일곱 가지만 남긴다. [code:apps/monitoring/prometheus/configmap.yaml:89-97] 추론 서버(Ollama)는 지표 주소가 없어서, 지금 메모리에 올라간 모델 목록을 돌려주는 API를 json-exporter가 대신 불러 지표로 바꾼다. 모델마다 한 줄씩, 그 모델이 GPU 메모리를 얼마나 차지하는지가 나온다. [code:apps/monitoring/json-exporter/json-exporter.yaml:1-3] [code:apps/monitoring/prometheus/configmap.yaml:99-113] 응답만 보는 도구 대신 이 변환기를 고른 것은 지금 올라간 모델까지 보이기 때문이다. [docs:history/build_log/09_monitoring.md:50] 이 대상이 응답하는지가 곧 추론 서버가 살아 있는지를 뜻한다. [code:apps/monitoring/prometheus/configmap.yaml:100] 호스트의 벡터 DB(Milvus)는 응답하는지만 본다. 내보내는 지표가 수천 개라 값은 모두 버리고 살아 있는지만 남긴다. [code:apps/monitoring/prometheus/configmap.yaml:78-87] 호스트 서비스에 관한 자세한 것은 → 「GPU와 호스트 서비스」에 있다.

## 시계열을 작게 유지한다

Prometheus에서 시계열(이름과 라벨이 같은 값의 줄기 하나)의 수는 곧 메모리와 디스크다. 그래서 큰 출처는 쓰는 것만 남겼다. [code:apps/monitoring/prometheus/configmap.yaml:1] node-exporter는 파드마다 생기는 마운트와 가상 네트워크 장치를 빼고 [code:apps/monitoring/node-exporter/daemonset.yaml:32-34], cAdvisor는 컨테이너마다 수십 개를 내는 지표 가운데 일곱 개만 남기며 [code:apps/monitoring/prometheus/configmap.yaml:47-51], kube-state-metrics는 기본값인 모든 객체 종류 대신 열두 종류만 본다. [code:apps/monitoring/kube-state-metrics/deployment.yaml:29-30] API 서버와 kubelet 자체의 지표는 시계열이 가장 많은데 대시보드에 쓰지 않아 긁지 않는다. 이렇게 줄여 시계열을 약 1만으로 어림했고, 설정은 1.5만을 기준으로 잡았다. [repo:apps/monitoring/README.md:70-80]

## 저장과 보존

Prometheus는 한 대이고, 지표를 w4의 로컬 디스크 볼륨(local-path, 노드의 디렉터리를 그대로 볼륨으로 쓰는 방식)에 10Gi로 저장한다. [code:apps/monitoring/prometheus/statefulset.yaml:61-69] 보존은 15일이고, 그보다 먼저 9GB에 닿으면 오래된 것부터 지운다. local-path는 볼륨 크기를 강제하지 않아서 디스크를 채우지 않게 하는 실제 상한은 이 9GB다. [code:apps/monitoring/prometheus/statefulset.yaml:36-37] [repo:apps/monitoring/README.md:109] 처음 설계는 7일에 5Gi였고, 15일 보존에 맞춰 10Gi로 올렸다. [repo:apps/monitoring/README.md:104]

local-path 볼륨은 처음 붙은 노드에 묶인다. Prometheus 파드는 그 노드로만 다시 뜨므로, w4를 비우면 Prometheus도 멈춘다. [code:apps/monitoring/prometheus/statefulset.yaml:2] 설정을 바꿨을 때도 주의가 필요하다. ConfigMap만 바뀌면 떠 있는 Prometheus는 설정을 다시 읽지 않으므로, 파드 주석의 판 숫자를 함께 올려 파드를 새로 띄운다. [code:apps/monitoring/prometheus/statefulset.yaml:18-19]

## 바깥에서 보기

Prometheus 화면은 Grafana와 같이 Cloudflare 터널과 ingress-nginx를 거쳐 바깥 주소로 연다. 처음에는 포트 포워딩으로 보았는데, 대시보드처럼 쿼리를 한꺼번에 보내면 연결이 끊겼다. [docs:history/build_log/09_monitoring.md:128] Prometheus에는 자체 로그인이 없어서 바깥에서는 Cloudflare Access가 유일한 문이다. 그래서 Access를 먼저 걸고 나서 DNS를 연다. 관리용 API는 켜지 않았다. [code:apps/monitoring/ingress.yaml:5-6]

## 알려진 한계

- 펫퍼민트의 HTTP 지표는 ingress-nginx를 거친 요청만 보인다. [docs:history/build_log/09_monitoring.md:51]
- Prometheus가 한 노드에 묶인 것, GPU 수집기가 ArgoCD 밖인 것, 사설망에서는 Access 없이 Prometheus에 닿는 것은 여러 편에 걸리는 한계라 → 「알려진 한계」에 모았다
- 15일을 넘는 추세는 볼 수 없고, 시계열이 늘면 9GB에 먼저 걸려 더 짧게 남는다. [docs:history/build_log/09_monitoring.md:117]

## 용어 풀이

- 지표: 시간에 따라 바뀌는 숫자 값. CPU 사용량, 요청 수 같은 것
- 시계열: 같은 이름과 라벨을 가진 지표 값이 시간 순서로 이어진 줄기 하나
- 수집 대상: Prometheus가 지표를 긁으러 찾아가는 주소
- exporter: 지표 주소가 없는 것을 대신 읽어 Prometheus가 긁을 수 있는 꼴로 내보내는 작은 프로그램
- cAdvisor: kubelet에 들어 있어 컨테이너별 자원 사용량을 재는 부분
- local-path: 노드의 디렉터리를 그대로 볼륨으로 쓰는 저장 방식. 크기 제한이 없고 노드에 묶인다
- DaemonSet: 노드마다 파드를 하나씩 띄우는 쿠버네티스 객체
