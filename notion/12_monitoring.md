<!--
다루는 곳: apps/monitoring/
읽은 커밋: e8e24ea
-->
# 모니터링

모니터링은 세 가지로 나뉜다. 숫자로 재는 지표(CPU, 메모리, 요청 수, GPU 사용률 같은 시간에 따른 값)는 Prometheus가 모으고, 서버가 남기는 글 기록인 로그는 Alloy가 모아 Loki에 넣으며, 사람이 보는 화면인 대시보드는 Grafana가 그린다. 모두 `apps/monitoring/` 아래 손으로 쓴 매니페스트이고, ArgoCD가 이 폴더를 자동으로 클러스터에 맞춘다. [code:apps/monitoring/app.yaml:20-27] Helm 차트(kube-prometheus-stack)를 쓰지 않은 것은 설정을 클러스터 안이 아니라 저장소에 남기기 위해서다. 다른 플랫폼 구성은 이미 저장소에 설정을 두었는데 모니터링만 클러스터 안에 두면 거기만 구멍이 된다. 지표 출처가 몇 안 되어 Operator와 CRD가 덜어 주는 일보다 늘리는 구성이 더 많았다. [docs:history/build_log/09_monitoring.md:31-33]

모니터링 구성은 모두 platform 역할의 노드 w4 한 대에 모았다. 노드마다 떠야 하는 node-exporter(노드 지표)와 Alloy(로그 수집)만 모든 노드에 뜬다. [code:apps/monitoring/kustomization.yaml:11] 이렇게 모은 까닭은 노드가 죽었을 때 무엇이 멈추는지를 노드 이름으로 말할 수 있게 하려는 것이다. w4가 죽으면 모니터링만 멈추고, 상담과 배포는 계속 돈다. [docs:history/build_log/09_monitoring.md:57-60] 바깥에서는 Grafana와 Prometheus를 Cloudflare 터널과 Access 뒤의 주소로 연다. 알림(Alertmanager)은 아직 없어서, 무슨 일이 생겼는지는 사람이 대시보드를 열어야 안다. [code:apps/monitoring/README.md:3] [docs:history/build_log/09_monitoring.md:145]

자세한 것은 세 편에 나눠 두었다. → 「지표」는 Prometheus가 무엇을 어디서 긁는지와 보존을, → 「로그」는 어떤 로그를 넣고 무엇을 버리는지를, → 「대시보드」는 Grafana가 무엇을 읽어 어떤 화면을 그리는지를 다룬다. GPU와 호스트 서비스 자체는 → 「GPU와 호스트 서비스」에 있다.
