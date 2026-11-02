# apps/monitoring

Prometheus · Grafana · node-exporter · kube-state-metrics (petmint-rag-chatbot `docs/15_monitoring.md`). Alertmanager는 없다 — 알림 설계 전.
차트 없이 손으로 쓴 매니페스트다(14번 1-9절 — 설정을 저장소에 남긴다). ArgoCD Application `monitoring`이 이 디렉터리를 본다.

상태: △ 작성만 했다(2026-10-18). 적용·Sync 전 — VM 메모리를 4096 → 8192로 올린 뒤에 한다.

## 처음 한 번 (사람이 한다)

```
kubectl create namespace monitoring
read -rsp 'grafana admin password: ' P; echo
kubectl -n monitoring create secret generic grafana-admin --from-literal=admin-user=admin --from-literal=admin-password="$P"; unset P
# Application: bootstrap/root-app.yaml 의 exclude 줄(monitoring)을 지우고 push → 루트가 app.yaml 로 만든다(Sync 는 수동)
```

그다음 ArgoCD에서 monitoring만 Sync한다. petmint Application은 따로다.

## 확인 (전부 ClusterIP — port-forward)

```
kubectl -n monitoring port-forward svc/prometheus 9090:9090   # Status → Targets
kubectl -n monitoring port-forward svc/grafana 3000:3000      # Connections → Data sources → Prometheus
```

## 크기 — 무엇을 근거로 정했나 (2026-10-18 실측)

클러스터: 노드 4대(각 3,912MiB), Pod 49개·컨테이너 51개, K8s v1.35.9. 노드별 실사용(`kubectl top nodes`) 1,846~2,124Mi,
available(`free -m`) 2,022~2,760MiB. limits 합: w1 1,152Mi · w2 2,176Mi · w3 3,412Mi(89%). 디스크 여유 45GB 이상(/ 62G 중 8.7~14G 사용).

**시계열 수 추정 ≈ 1만(설정은 1.5만 기준)**

| 출처 | 추정 | 줄인 방법 |
|---|---|---|
| node-exporter | 노드당 ~700 × 4 ≈ 2.8천 | veth·cni NIC와 Pod 마운트 제외 |
| cAdvisor | 7개 지표 × 컨테이너·Pod ~150 ≈ 1천 | 1절에 쓰는 7개만 keep |
| kube-state-metrics | Pod 49 × ~40 + 나머지 ≈ 2.5천 | --resources로 12종만 |
| Prometheus 자신·기타 | ≈ 1천 | |
| Milvus | up·scrape_* 5개 | 노출 지표 전부 drop |

apiserver·kubelet /metrics는 긁지 않는다(시계열이 가장 많고 1절에 안 쓴다).

**메모리·CPU**

| 구성 | requests | limits | 근거 |
|---|---|---|---|
| Prometheus | 100m / 384Mi | 500m / 768Mi | 시계열 1.5만 × 헤드 ~8KB ≈ 120Mi + 런타임 ~100Mi + 압축·쿼리 여유. limit은 request의 2배 |
| Grafana | 50m / 128Mi | 250m / 256Mi | 대시보드 몇 개·사용자 1~2명 기준 기동 상주 80~120Mi |
| node-exporter ×4 | 20m / 32Mi | 100m / 64Mi | 수집기 기본값에서 15~25Mi |
| kube-state-metrics | 20m / 64Mi | 100m / 128Mi | 객체 수백 개 규모 30~50Mi |
| **합** | **270m / 704Mi** | **1,370m / 1,408Mi** | 노드 하나에 몰려도 requests 704Mi |

CPU는 노드 실사용 2~3%(2코어)라 여유가 크다. limit 500m은 Prometheus 압축이 다른 Pod를 밀어내지 않게 하는 상한이다.

4096 그대로면: requests는 어느 노드든 들어간다. 다만 Prometheus가 w3에 뜨면 w3 limits가 3,412 + 768 + 64 = 4,244Mi로 노드 용량(3,912)을 넘는다.
그래서 8192로 올린 뒤 적용한다. 배치 제약은 넣지 않았다 — 8192에서는 필요 없고, 넣으면 그때 다시 걷어내야 한다.

**PVC 5Gi (보존 7일)**

- 시계열 1.5만 / 30초 = 초당 500 샘플 × 604,800초 = 약 3억 샘플 × ~1.5바이트 ≈ 0.45GB(블록)
- WAL·헤드 약 3시간치 ≈ 0.1GB, 압축 중 임시로 가장 큰 블록만큼 더
- 합 ~1GB → 시계열이 3~4배로 늘어도(petmint /metrics, Pod 증가) 들어가게 5Gi. `--storage.tsdb.retention.size=4GB`로 PVC보다 먼저 지운다
- local-path는 크기를 강제하지 않는다(hostPath 디렉터리) — 실제 상한은 노드 디스크(여유 45GB)와 retention.size다
