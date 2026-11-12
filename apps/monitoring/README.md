# apps/monitoring

Prometheus · Grafana · node-exporter · kube-state-metrics + Loki · Alloy · json-exporter (petmint-rag-chatbot `docs/15_monitoring.md`). Alertmanager는 없다 — 알림 설계 전.
차트 없이 손으로 쓴 매니페스트다(14번 1-9절 — 설정을 저장소에 남긴다). ArgoCD Application `monitoring`(자동 Sync, 2026-11-11~ — prune · selfHeal 끔)이 이 디렉터리를 본다. 대시보드는 `dashboards/gen_petmint.py`를 고쳐 push하면 반영된다.

상태: ✓ 설치(2026-11-10, 가용성 묶음 2). 전부 w4(`node.ronanlab.dev/role=platform`)에 — node-exporter · alloy 만 DaemonSet이라 모든 노드에.

| 구성 | 하는 일 | 저장 |
| --- | --- | --- |
| Prometheus | 지표 수집 · 저장 | w4 local-path 10Gi, 보존 15일(또는 9GB) |
| Loki | 서버 로그 | w4 local-path 10Gi, 보존 7일(compactor) |
| Alloy(DaemonSet) | `/var/log/pods` → Loki. **넣지 않는 것**: runshoes 챗봇의 질문 원문 줄, Jenkins 빌드 Pod | 노드 `/var/lib/alloy-monitoring`(읽은 위치) |
| json-exporter | Ollama `/api/ps` → `ollama_loaded_model_vram_bytes{model}` | — |
| Grafana | 대시보드 `petmint — 운영`(`grafana/dashboards/`) · 데이터소스 Prometheus · Loki · petmint-turns(MySQL) | emptyDir — 설정 · 대시보드는 저장소에서 |

**데이터 출처**(앱에 `/metrics`가 없어서):

| 대시보드 칸 | 출처 |
| --- | --- |
| Pod 상태 · 재시작 | kube-state-metrics |
| 요청 수 · 에러율 | ingress-nginx 메트릭(`platform/ingress-nginx/overlay` — 2026-11-10 켬, Pod 주석으로 긁는다) |
| 모드별 · 시간대별 질문, code_rule, 코드 답 vs 모델 답, 👍👎, 응답 시간 p50/p90, 턴이 쓴 모델 | petmint 턴 로그(DB) — **Replica**(`mysql-replica.petmint.svc`)를 읽는다 |
| GPU 사용률 · VRAM | 호스트 컨테이너 nvidia-gpu-exporter(`utkuozdemir/nvidia_gpu_exporter:1.3.1`, `192.168.122.1:9835`, `scripts/host-gpu-exporter.sh`) — 사람이 띄운다. 2026-11-11 09:22 띄움 |
| Ollama 모델 교체 | json-exporter(`/api/ps`) + 턴 로그의 `model` |
| 거절률 · 검색 지연 | petmint 턴 로그 `turns.refused` · `turns.search_ms`(2026-11-11, 앱 0009 — `ba7bd28`로 패널 연결). 그 전 턴은 NULL이라 빈 칸 |

**petmint DB 읽기 계정** `grafana_ro`@`%`: 컬럼 단위 SELECT만 —
`turns`(turn_id · session_id · code_rule · model · first_token_ms · latency_ms · status · created_at · clarified · context_kind · refused · search_ms — 마지막 둘은 2026-11-11, 앱 0009),
`sessions`(session_id · mode · started_at), `feedback`(turn_id · rating · created_at). 질문 · 답 · 코멘트 · 고객 · 상담원 컬럼은 권한이 없다
(2026-11-10 시험: `SELECT question` · `SELECT comment` → ERROR 1143). Primary에서 만들어 Replica로 복제됐다. 최대 연결 5.

## 처음 한 번 (사람이 한다 — 2026-11-10에 한 그대로)

```
kubectl create namespace monitoring
R(){ head -c 48 /dev/urandom | base64 | tr -dc A-Za-z0-9 | head -c 32; }
kubectl -n monitoring create secret generic grafana-admin --from-literal=admin-user=admin --from-literal=admin-password="$(R)"
kubectl -n monitoring create secret generic grafana-mysql --from-literal=password="$(R)"
# petmint Primary 에 읽기 계정 — 비밀번호는 표준 입력으로, 권한은 위 컬럼만(GRANT SELECT (컬럼, …) ON petmint.<테이블>)
# Application: bootstrap/root-app.yaml 의 exclude 줄을 지웠다(2026-11-10) → 루트가 app.yaml 로 만든다. Sync 는 처음 수동, 2026-11-11부터 자동
# GPU: 호스트에서 bash scripts/host-gpu-exporter.sh (docker 그룹, sudo 불필요)
```

## 확인 · 접속

`https://grafana.ronanlab.dev` · `https://prometheus.ronanlab.dev`(2026-11-11, `ingress.yaml`) — argocd · harbor · jenkins와 같은 모양:
터널(`apps/cloudflared`, 호스트 7개) → ingress-nginx, 인증서는 cert-manager(letsencrypt-prod). 바깥 인증은 Cloudflare Access 「운영도구」 앱(대시보드에서 사람이 건다).
**Prometheus는 자체 로그인이 없다** — 바깥에서는 Access가 유일한 문이라, Access를 건 뒤에 DNS(CNAME)를 연다. port-forward는 대시보드 동시 요청에서 connection reset으로 끊겨 쓰지 않는다.

```
kubectl -n monitoring get secret grafana-admin -o jsonpath='{.data.admin-password}' | base64 -d; echo   # Grafana admin 비밀번호
# 사설망(호스트)에서 DNS 없이: curl --resolve grafana.ronanlab.dev:443:192.168.122.240 https://grafana.ronanlab.dev/api/health
```

2026-11-10 확인: 수집 대상 kube-state-metrics 1/1 · kubelet-cadvisor 5/5 · node-exporter 5/5 · kubernetes-pods 5/5(ingress 포함) · ollama 1/1 · prometheus 1/1 up,
milvus 0/1(9091이 호스트 127.0.0.1에만 — 15번 4절 그대로) · nvidia-gpu 0/1(exporter 아직 안 띄움).
2026-11-11: milvus 1/1 — 호스트 compose(petmint-rag-chatbot `deploy/host/milvus`)에서 9091을 192.168.122.1에도 게시했다(19530과 같은 방식, etcd 2379는 닫힌 채).
9091에는 `/debug/pprof` · `/log/level`도 인증 없이 응답한다 — 19530이 이미 같은 망에 인증 없이 열려 있어 새 위험은 작다고 봤다(앱 리포 docs 15번 4절).
2026-11-11: nvidia-gpu 1/1 — 호스트에 exporter를 띄웠다(09:22). 2026-11-12 다시 보니 수집 대상 전부 up(milvus · nvidia-gpu 포함).
Loki에 12개 네임스페이스 로그가 들어오고 챗봇 질문 줄 · Jenkins 빌드 Pod 로그는 0건. Grafana 데이터소스 셋 OK, MySQL 패널 쿼리가 값을 돌려준다(모드별 사내규정 56 · 업무특화 89 · 일반 17).

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
| Grafana | 100m / 384Mi | 1 / 1Gi | **2026-11-11 고침**: 처음 값 50m/128Mi · 250m/256Mi는 Grafana 13에 모자랐다 — 기동만으로 ~240Mi, Dashboards 화면(검색 인덱스)에서 넘어 OOMKilled → 바깥에서 502/503. 패널 쿼리를 돌린 뒤 253Mi |
| kube-state-metrics | 20m / 64Mi | 100m / 128Mi | 객체 수백 개 규모 30~50Mi |
| Loki | 100m / 256Mi | 500m / 768Mi | 단일 바이너리, 로그 7일 |
| json-exporter | 10m / 16Mi | 100m / 64Mi | Ollama `/api/ps` 하나만 |
| **w4 합**(위 다섯, 모두 w4) | **330m / 1,104Mi** | **2,200m / 2,752Mi** | w4 8,192Mi에 들어간다 |
| node-exporter(DaemonSet, 노드마다) | 20m / 32Mi | 100m / 64Mi | 수집기 기본값에서 15~25Mi. 5대 |
| Alloy(DaemonSet, 노드마다) | 20m / 64Mi | 200m / 256Mi | 로그 수집. 5대 |

위 값은 2026-11-12 매니페스트 · 클러스터와 같다. 처음(2026-10-18) 표는 Prometheus · Grafana · node-exporter ×4 · kube-state-metrics만 있었고 Grafana가 50m/128Mi였다.

CPU는 노드 실사용 2~3%(2코어)라 여유가 크다. limit 500m은 Prometheus 압축이 다른 Pod를 밀어내지 않게 하는 상한이다.

4096 그대로면: requests는 어느 노드든 들어간다. 다만 Prometheus가 w3에 뜨면 w3 limits가 3,412 + 768 + 64 = 4,244Mi로 노드 용량(3,912)을 넘는다.
그래서 8192로 올린 뒤 적용한다. 배치 제약은 넣지 않았다 — 8192에서는 필요 없고, 넣으면 그때 다시 걷어내야 한다.

**PVC — 처음 설계 5Gi · 보존 7일, 지금 10Gi · 15일 · 9GB**

지금 값(2026-11-10 사용자, `prometheus/statefulset.yaml`): PVC 10Gi, `--storage.tsdb.retention.time=15d`, `--storage.tsdb.retention.size=9GB`. 아래는 처음(2026-10-18) 설계 계산이다(7일 · 5Gi 기준). 15일 보존에 맞춰 10Gi로 올렸다(`statefulset.yaml` 주석).

- 시계열 1.5만 / 30초 = 초당 500 샘플 × 604,800초 = 약 3억 샘플 × ~1.5바이트 ≈ 0.45GB(블록)
- WAL·헤드 약 3시간치 ≈ 0.1GB, 압축 중 임시로 가장 큰 블록만큼 더
- 합 ~1GB → 시계열이 3~4배로 늘어도(petmint /metrics, Pod 증가) 들어가게 5Gi. `--storage.tsdb.retention.size=4GB`로 PVC보다 먼저 지운다
- local-path는 크기를 강제하지 않는다(hostPath 디렉터리) — 실제 상한은 노드 디스크(여유 45GB)와 retention.size다
