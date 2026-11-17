<!--
다루는 곳: apps/monitoring/
읽은 커밋: 736d833
-->
# 모니터링

`apps/monitoring/`의 손으로 쓴 매니페스트(차트 없음)를 ArgoCD Application `monitoring`이 자동 Sync한다. 이력과 설계 기록은 `docs/history/build_log/09_monitoring.md`. 크기 계산 근거와 읽기 계정 권한 전체는 `apps/monitoring/README.md`. [code:apps/monitoring/app.yaml:17-27] [docs:history/build_log/09_monitoring.md:29-34]

## 지금 구성

| 구성 | 이미지 | 종류, 배치 | 요청 / 상한 | 저장 |
| --- | --- | --- | --- | --- |
| Prometheus | `quay.io/prometheus/prometheus:v3.15.0` | StatefulSet 1, w4 | 100m, 384Mi / 500m, 768Mi | local-path 10Gi, 15일 또는 9GB |
| node-exporter | `quay.io/prometheus/node-exporter:v1.12.1` | DaemonSet, 모든 노드(hostNetwork 9100) | 20m, 32Mi / 100m, 64Mi | 없음 |
| kube-state-metrics | `registry.k8s.io/kube-state-metrics/kube-state-metrics:v2.19.1` | Deployment 1, w4 | 20m, 64Mi / 100m, 128Mi | 없음 |
| json-exporter | `quay.io/prometheuscommunity/json-exporter:v0.7.0` | Deployment 1, w4 | 10m, 16Mi / 100m, 64Mi | 없음 |
| Loki | `docker.io/grafana/loki:3.5.0` | StatefulSet 1, w4, 단일 바이너리 | 100m, 256Mi / 500m, 768Mi | local-path 10Gi, 7일 |
| Alloy | `docker.io/grafana/alloy:v1.8.0` | DaemonSet, 모든 노드 | 20m, 64Mi / 200m, 256Mi | 노드 `/var/lib/alloy-monitoring`(읽은 위치) |
| Grafana | `docker.io/grafana/grafana:13.2.3` | Deployment 1, w4 | 100m, 384Mi / 1, 1Gi | emptyDir |

근거: [code:apps/monitoring/prometheus/statefulset.yaml:32-37] [code:apps/monitoring/prometheus/statefulset.yaml:49-51] [code:apps/monitoring/prometheus/statefulset.yaml:61-69] [code:apps/monitoring/node-exporter/daemonset.yaml:16-42] [code:apps/monitoring/kube-state-metrics/deployment.yaml:25] [code:apps/monitoring/kube-state-metrics/deployment.yaml:42-44] [code:apps/monitoring/json-exporter/json-exporter.yaml:44] [code:apps/monitoring/json-exporter/json-exporter.yaml:51-53] [code:apps/monitoring/loki/loki.yaml:69-80] [code:apps/monitoring/loki/loki.yaml:90-98] [code:apps/monitoring/alloy/alloy.yaml:132] [code:apps/monitoring/alloy/alloy.yaml:148-150] [code:apps/monitoring/alloy/alloy.yaml:165-167] [code:apps/monitoring/grafana/deployment.yaml:26] [code:apps/monitoring/grafana/deployment.yaml:67-69] [code:apps/monitoring/grafana/deployment.yaml:83-85]

- 배치: w4 고정은 nodeSelector `node.ronanlab.dev/role: platform`. node-exporter(모든 taint 허용)와 Alloy(control-plane taint 허용)만 모든 노드 [code:apps/monitoring/kustomization.yaml:11] [code:apps/monitoring/node-exporter/daemonset.yaml:18-19] [code:apps/monitoring/alloy/alloy.yaml:126-129]
- Application: `monitoring`, `targetRevision: main`, 자동 Sync, prune과 selfHeal 끔, `CreateNamespace=false`. 실제 스위치는 클러스터의 `kubectl patch`이고 `app.yaml`은 기록 [code:apps/monitoring/app.yaml:1-29]
- Namespace와 Secret(`grafana-admin`, `grafana-petmint-mysql`, `grafana-runshoes-mysql`)은 저장소에 없다. 사람이 만든다 [code:apps/monitoring/kustomization.yaml:10]
- 알림: Alertmanager 없음 [code:apps/monitoring/README.md:3]
- 바깥 주소: `https://grafana.ronanlab.dev`, `https://prometheus.ronanlab.dev`. Cloudflare 터널, ingress-nginx, cert-manager(`letsencrypt-prod`), Access 「운영도구」 앱. 사설망에서는 MetalLB VIP `192.168.122.240`으로 Access 없이 닿는다 [code:apps/monitoring/ingress.yaml:1-7]
- Grafana는 자체 로그인과 Access 두 겹, 익명 접근 끔. Prometheus는 자체 로그인 없음, admin API 끔 [code:apps/monitoring/ingress.yaml:5-7] [code:apps/monitoring/grafana/deployment.yaml:41-42]

수집 대상(30초 간격, 타임아웃 10초) [code:apps/monitoring/prometheus/configmap.yaml:7-113]:

| job | 찾는 법 | 남기는 것 |
| --- | --- | --- |
| `prometheus` | `localhost:9090` | 전부 |
| `node-exporter` | EndpointSlice, 서비스 `node-exporter`(headless), `node` 라벨 붙임 | 전부. veth, cali 등 NIC와 Pod 마운트는 exporter에서 뺀다 |
| `kubelet-cadvisor` | node SD, `https://<노드>:10250/metrics/cadvisor`, 인증서 검증 안 함 | `container_` 7종만 |
| `kube-state-metrics` | `kube-state-metrics.monitoring.svc:8080` | 전부. `--resources` 12종 |
| `kubernetes-pods` | pod SD, `prometheus.io/scrape: "true"` 주석 | 전부. 지금 ingress-nginx 컨트롤러(10254)와 runshoes 앱(9000 `/actuator/prometheus`) 등 |
| `milvus` | `192.168.122.1:9091` | 모두 drop, `up`과 `scrape_*`만 |
| `nvidia-gpu` | `192.168.122.1:9835` | `nvidia_smi_` 7종 |
| `ollama` | json-exporter `/probe?module=ollama_ps&target=http://192.168.122.1:11434/api/ps` | `ollama_loaded_model_vram_bytes`, `ollama_loaded_model_size_bytes` |

ingress-nginx와 runshoes 주석의 근거: [code:platform/ingress-nginx/overlay/deployment-patch.yaml:17-19] [code:apps/runshoes/app/deployment.yaml:40-42]. petmint 앱은 `/metrics`가 없어 HTTP 지표는 ingress-nginx에서 얻는다 [code:apps/monitoring/README.md:16-21]. apiserver와 kubelet `/metrics`는 긁지 않는다 [code:apps/monitoring/README.md:80].

로그:

- Alloy: 자기 노드 파드(`spec.nodeName`)의 `/var/log/pods/*<uid>/<container>/*.log`를 읽어 `http://loki.monitoring.svc:3100/loki/api/v1/push`로 보낸다 [code:apps/monitoring/alloy/alloy.yaml:39-110]
- 라벨: `namespace`, `pod`, `container`, `node` 넷 [code:apps/monitoring/alloy/alloy.yaml:61-76]
- 버리는 것: jenkins 네임스페이스에서 `jenkins-0`이 아닌 파드(빌드 Pod), runshoes `chatbot` 컨테이너의 `.*질문: .*` 줄(대화 원문) [code:apps/monitoring/alloy/alloy.yaml:49-60] [code:apps/monitoring/alloy/alloy.yaml:96-102]
- Loki: `auth_enabled: false`, tsdb v13 파일시스템, `retention_period: 168h`, 수신 4MB/s(버스트 8MB), compactor가 지운다 [code:apps/monitoring/loki/loki.yaml:10-43]
- Loki에는 서버 로그만 넣는다. 대화 기록은 넣지 않는다 [code:CLAUDE.md:50]

Grafana:

- 데이터소스 넷: `Prometheus`(uid `prometheus`, 기본, `timeInterval: 30s`), `Loki`(uid `loki`), `petmint-turns`(uid `petmint-mysql`, `mysql-replica.petmint.svc:3306`), `runshoes`(uid `runshoes-mysql`, `runshoes-mysql-replica.runshoes.svc:3306`). MySQL 둘은 계정 `grafana_ro`, `maxOpenConns: 3`, UTC [code:apps/monitoring/grafana/datasource.yaml:10-58]
- MySQL 계정은 칸 단위 SELECT만. 질문, 답, 코멘트, 고객, 상담원 칸은 권한 없음. 최대 연결 5 [code:apps/monitoring/README.md:27-30] [code:apps/monitoring/grafana/datasource.yaml:43-44]
- 대시보드 둘: `petmint 운영`(uid `petmint-overview`, 4묶음 18패널, 기본 30일), `runshoes 운영`(uid `runshoes-overview`, 7묶음 36패널, 기본 7일). 둘 다 1분 새로고침 [code:apps/monitoring/grafana/dashboards/gen_petmint.py:210-212] [code:apps/monitoring/grafana/dashboards/gen_runshoes.py:401-404]
- 프로비저닝: `disableDeletion: true`, `allowUiUpdates: false`. UI에서 고친 것은 남지 않는다 [code:apps/monitoring/grafana/dashboard-provider.yaml:11-16]

## 설정 자리

| 파일:줄 | 값 | 뜻 |
| --- | --- | --- |
| `apps/monitoring/prometheus/configmap.yaml:8` | `scrape_interval: 30s` | 수집 간격. Grafana `timeInterval`과 같게 둔다 |
| `apps/monitoring/prometheus/statefulset.yaml:19` | `monitoring.ronanlab.dev/config-rev: "1"` | ConfigMap만 바꾸면 다시 읽지 않는다. 올려서 롤링한다 |
| `apps/monitoring/prometheus/statefulset.yaml:36-37` | `retention.time=15d`, `retention.size=9GB` | PVC 10Gi보다 먼저 지운다 |
| `apps/monitoring/prometheus/statefulset.yaml:38` | `--web.external-url=https://prometheus.ronanlab.dev` | UI 링크 기준 |
| `apps/monitoring/kube-state-metrics/deployment.yaml:30` | `--resources=` 12종 | `rbac.yaml`과 같이 바꾼다 |
| `apps/monitoring/node-exporter/daemonset.yaml:33-34` | 마운트, NIC 제외 정규식 | Pod마다 생기는 것을 뺀다 |
| `apps/monitoring/json-exporter/json-exporter.yaml:9-21` | 모듈 `ollama_ps` | `/api/ps`의 `size_vram`, `size`를 모델 라벨로 |
| `apps/monitoring/loki/loki.yaml:33-37` | `retention_period: 168h` 등 | 보존 7일, 수신 상한 |
| `apps/monitoring/alloy/alloy.yaml:47-60` | jenkins 규칙 | 컨트롤러 `jenkins-0`만 남긴다 |
| `apps/monitoring/alloy/alloy.yaml:96-102` | `stage.drop` | runshoes 챗봇 질문 원문 줄을 버린다 |
| `apps/monitoring/grafana/deployment.yaml:35-40` | `MYSQL_PETMINT_RO_PASSWORD`, `MYSQL_RUNSHOES_RO_PASSWORD` | `datasource.yaml`의 `$이름`과 같아야 한다. 어긋나면 비밀번호가 빈 값 |
| `apps/monitoring/grafana/deployment.yaml:51-52` | `GF_SERVER_ROOT_URL` | 로그인 리다이렉트, 공유 링크 |
| `apps/monitoring/kustomization.yaml:31-37` | `configMapGenerator` `grafana-dashboards` | `petmint.json`, `runshoes.json`. 이름 해시 끔 |
| `apps/monitoring/ingress.yaml:40-41` | `proxy-read-timeout`, `proxy-send-timeout` 3600 | Grafana Live WebSocket |

근거: [code:apps/monitoring/prometheus/configmap.yaml:8] [code:apps/monitoring/prometheus/statefulset.yaml:18-19] [code:apps/monitoring/prometheus/statefulset.yaml:36-38] [code:apps/monitoring/kube-state-metrics/deployment.yaml:29-30] [code:apps/monitoring/node-exporter/daemonset.yaml:32-34] [code:apps/monitoring/json-exporter/json-exporter.yaml:9-21] [code:apps/monitoring/loki/loki.yaml:33-37] [code:apps/monitoring/alloy/alloy.yaml:47-60] [code:apps/monitoring/alloy/alloy.yaml:96-102] [code:apps/monitoring/grafana/deployment.yaml:32-40] [code:apps/monitoring/grafana/deployment.yaml:50-52] [code:apps/monitoring/kustomization.yaml:31-37] [code:apps/monitoring/ingress.yaml:40-41]

## 바꾸거나 다시 만들기

매니페스트를 고쳐 커밋하면 관리자가 push하고, 자동 Sync가 3분 안에 넣는다. prune이 꺼져 있어 git에서 지운 리소스는 클러스터에 남는다 [code:apps/monitoring/app.yaml:5-7].

대시보드 고치기(JSON을 손으로 고치지 않는다) [code:apps/monitoring/grafana/dashboard-provider.yaml:1-2]:

```bash
cd apps/monitoring/grafana/dashboards
python3 gen_petmint.py petmint.json
python3 gen_runshoes.py runshoes.json
```

Prometheus 설정을 바꾸면 `statefulset.yaml`의 `config-rev`도 올린다 [code:apps/monitoring/prometheus/statefulset.yaml:18-19].

처음 한 번(사람이 m-k8s에서, 값은 화면과 기록에 남기지 않는다) [code:apps/monitoring/README.md:32-45]:

```bash
kubectl create namespace monitoring
kubectl -n monitoring create secret generic grafana-admin --from-literal=admin-user=admin --from-literal=admin-password=<무작위 값>
kubectl -n monitoring create secret generic grafana-petmint-mysql --from-literal=password=<petmint grafana_ro 비밀번호>
kubectl -n monitoring create secret generic grafana-runshoes-mysql --from-file=password=<비밀번호 파일>
# petmint, runshoes Primary에 grafana_ro 계정과 칸 단위 GRANT(README 「처음 한 번」, 앱 저장소 문서)
# GPU 수집기: 호스트에서 bash scripts/host-gpu-exporter.sh
```

`grafana-runshoes-mysql`이 없으면 Grafana Pod가 뜨지 않는다 [code:apps/monitoring/README.md:43]. 바깥 주소의 DNS와 Access는 Cloudflare 대시보드에서 사람이 한다. Prometheus는 Access를 먼저 건 뒤 DNS를 연다 [code:apps/monitoring/ingress.yaml:5].

## 확인

컨트롤 플레인 노드에서:

```bash
kubectl -n monitoring get pods -o wide        # alloy, node-exporter는 노드 다섯에, 나머지는 w4
kubectl -n monitoring get pvc                 # data-prometheus-0, data-loki-0 모두 Bound 10Gi
kubectl -n argocd get app monitoring          # Synced, Healthy
```

호스트(사설망)에서:

```bash
curl -s --resolve grafana.ronanlab.dev:443:192.168.122.240 https://grafana.ronanlab.dev/api/health
curl -s --resolve prometheus.ronanlab.dev:443:192.168.122.240 'https://prometheus.ronanlab.dev/api/v1/query?query=up' \
  | python3 -c 'import json,sys; [print(r["metric"]["job"], r["metric"].get("instance"), r["value"][1]) for r in json.load(sys.stdin)["data"]["result"]]'
```

기대: 모든 대상이 1. `kubelet-cadvisor`, `node-exporter`는 노드 수(5)만큼, `kube-state-metrics`, `prometheus`, `milvus`, `nvidia-gpu`, `ollama`는 1씩, `kubernetes-pods`는 주석 단 Pod 수만큼 [docs:history/build_log/09_monitoring.md:238-244] [code:apps/runshoes/app/deployment.yaml:40-42].

Loki에 대화 원문이 없는지는 Grafana Explore에서 `{namespace="runshoes", container="chatbot"} |= "질문: "`가 0건인지 본다 [code:apps/monitoring/alloy/alloy.yaml:96-102].

ArgoCD 상태 기록: [docs:history/cluster_state_20261116.md:59].

## 알려진 한계

- Alertmanager가 없다. 사람이 대시보드를 열어야 안다 [docs:history/build_log/09_monitoring.md:208]
- Prometheus와 Loki는 한 대씩이고 local-path PV가 w4에 묶여 있다. w4를 비우면 그동안 지표와 로그가 빈다 [code:apps/monitoring/prometheus/statefulset.yaml:2] [docs:history/build_log/09_monitoring.md:209]
- 사설망 VIP로는 Access 없이 Prometheus에 닿는다 [code:apps/monitoring/ingress.yaml:6]
- Milvus 9091은 `/debug/pprof`, `/log/level`도 인증 없이 사설망에 응답한다 [code:apps/monitoring/README.md:61]
- search-service, model-service 생존은 수집하지 않는다 [docs:history/build_log/09_monitoring.md:212]
- 대화 원문 거르기는 문자열 일치다. 로그 꼴이 바뀌면 들어간다 [docs:history/build_log/09_monitoring.md:110]
- MySQL 패널은 Replica에 기댄다. 새 칸은 GRANT를 손으로 더해야 한다 [docs:history/build_log/09_monitoring.md:70]
- petmint 거절률은 문구 판정이다 [docs:history/build_log/09_monitoring.md:213]
- GPU 수집기는 ArgoCD 밖이다 [docs:history/build_log/09_monitoring.md:124]
