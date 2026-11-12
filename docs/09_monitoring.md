# 09. 모니터링

Prometheus · Grafana · node-exporter · kube-state-metrics를 설치하고 Loki(Alloy 수집)로 서버 로그를 모은 기록이다. 2026-11-10 전부 w4에 올렸고, 2026-11-11 자동 Sync · 바깥 주소(grafana.ronanlab.dev · prometheus.ronanlab.dev) · Milvus · GPU 지표가 더해졌다.

- 날짜: 2026-11-10 설치, 2026-11-11 바깥 주소 · 자동 Sync · Milvus · GPU · 거절률 · 검색 지연, 2026-11-12 코드 · 클러스터와 맞춤
- 범위: 왜 이렇게 했나와 설치 기록. 지금 구성 · 접속 · 크기 근거는 `apps/monitoring/README.md`(같은 사실을 두 곳에 적지 않는다). 노드 배치(w4 platform)는 [08_scale_out.md](08_scale_out.md)
- 코드: apps/monitoring/(app.yaml · ingress.yaml · prometheus/ · grafana/ · loki/ · alloy/ · node-exporter/ · kube-state-metrics/ · json-exporter/), platform/ingress-nginx/overlay/, scripts/host-gpu-exporter.sh, apps/cloudflared/configmap.yaml
- 앱 쪽 문서: `~/AI_programming/petmint-rag-chatbot/docs/02_pipeline/15_monitoring.md`

## 1. 지금 구성

`apps/monitoring/README.md`가 원본이다. 구성 요소 · 보존 · 데이터 출처 · DB 읽기 계정 · 「처음 한 번」 · 「확인 · 접속」 · 크기 근거가 거기 있다.

요약(2026-11-12 클러스터 · 매니페스트와 같다):
- ArgoCD Application `monitoring`, 자동 Sync(2026-11-11~, prune · selfHeal 끔). 전부 w4(`node.ronanlab.dev/role=platform`), node-exporter · Alloy만 DaemonSet
- 이미지: Prometheus v3.15.0 · Grafana 13.2.3 · Loki 3.5.0 · Alloy v1.8.0 · node-exporter v1.12.1 · kube-state-metrics v2.19.1 · json-exporter v0.7.0. 호스트 컨테이너 nvidia_gpu_exporter 1.3.1
- 접속: `https://grafana.ronanlab.dev` · `https://prometheus.ronanlab.dev`(`apps/monitoring/ingress.yaml`, 터널 호스트는 `apps/cloudflared/configmap.yaml`)

## 2. 왜 이렇게 했나

### 2-1. 사전 정리: 무엇을 어디서 얻나

처음 계획은 kube-prometheus-stack(Helm)이었으나 **차트 없이 손으로 쓴 매니페스트**로 바꿨다. Jenkins·MetalLB·cert-manager처럼 설정을 전부 저장소에 남기기 위해서다. 그런데 펫퍼민트 앱에는 `/metrics`가 없다. 앱 코드를 고치지 않고 볼 것을 채우려고 출처를 나눴다.

| 보고 싶은 것 | 출처 |
| --- | --- |
| 파드 상태 · 재시작 | kube-state-metrics |
| 요청 수 · 에러율 | ingress-nginx 메트릭. 업스트림이 `--enable-metrics=false`로 꺼 둔 것을 켰다 |
| 모드별 · 시간대별 질문, 규칙별 발동(code_rule), 코드 답 vs 모델 답, 좋아요 · 싫어요(rating), 응답 시간 p50/p90, 턴이 쓴 모델 | petmint 턴 로그(DB). Grafana가 MySQL을 직접 읽는다 |
| GPU 사용률 · VRAM | 호스트 컨테이너 nvidia-gpu-exporter |
| Ollama 모델 교체 | json-exporter가 Ollama `/api/ps`를 지표로 바꾼다 |
| 서버 로그 | Loki(7일) ← Alloy(노드마다) |

### 2-2. 설계 결정: DB를 읽되 대화는 읽지 못하게

턴 로그에는 질문과 답 본문이 있다. Grafana에 주는 계정은 **컬럼 단위 권한**만 받는다. 2026-11-10에 준 권한:

```sql
GRANT SELECT (turn_id, session_id, code_rule, model, first_token_ms, latency_ms, status, created_at, clarified, context_kind)
  ON petmint.turns TO 'grafana_ro'@'%';
GRANT SELECT (session_id, mode, started_at) ON petmint.sessions TO 'grafana_ro'@'%';
GRANT SELECT (turn_id, rating, created_at) ON petmint.feedback TO 'grafana_ro'@'%';
```

```txt
ERROR 1143 (42000): SELECT command denied to user 'grafana_ro'@'127.0.0.1' for column 'question' in table 'turns'
ERROR 1143 (42000): SELECT command denied to user 'grafana_ro'@'127.0.0.1' for column 'comment' in table 'feedback'
```

2026-11-11 `turns`에 `refused` · `search_ms`(앱 0009)가 더해졌다(3-4절, 지금 권한 목록은 README).

그리고 Primary가 아니라 **Replica**([08_scale_out.md](08_scale_out.md))를 읽는다. 대시보드 쿼리가 운영 쓰기에 부하를 주지 않는다.

### 2-3. 설계 결정: 로그에 대화를 넣지 않는다

대화 기록은 DB에 있다. Loki에는 서버 로그만 넣는다. 확인해 보니 runshoes 챗봇이 질문 원문을 로그로 남기고 있었다.

```py
print(f"[{now()}] 질문: {text}")
```

수집기(Alloy)에서 그 줄을 버린다(`apps/monitoring/alloy/alloy.yaml`). Jenkins 빌드 Pod의 로그(빌드 출력)도 넣지 않는다.

```txt
loki.process "pods" {
  stage.cri {}
  stage.match {
    selector = "{namespace=\"runshoes\", container=\"chatbot\"}"
    stage.drop { expression = ".*질문: .*" }
  }
  forward_to = [loki.write.default.receiver]
}
```

## 3. 진행 기록

### 3-1. 13-1단계: 설치 (2026-11-10)

그때의 값이다. 노출과 Sync는 2026-11-11에 바뀌었다(3-4절).

| 구성 | 값 |
| --- | --- |
| 배치 | 전부 w4(`node.ronanlab.dev/role=platform`). node-exporter · Alloy만 DaemonSet |
| Prometheus | 보존 15일(또는 9GB), w4 local-path 10Gi |
| Loki | 단일 바이너리, 보존 7일(compactor), w4 local-path 10Gi |
| Grafana | 데이터소스 Prometheus · Loki · petmint-turns(MySQL), 대시보드는 저장소의 JSON을 프로비저닝 |
| 노출 | 그때는 전부 ClusterIP, port-forward(2026-11-11 Ingress로 바꿈) |
| ArgoCD | 루트 Application의 `exclude: 'monitoring/app.yaml'`을 빼서 Application을 만들고, 그때 Sync는 수동(2026-11-11 자동) |

### 3-2. 13-2단계: ingress-nginx 메트릭 (2026-11-10)

메트릭을 켜려면 컨트롤러를 다시 띄워야 한다. 1개일 때 재시작이 12초 끊김을 낸 적이 있어([08_scale_out.md](08_scale_out.md) 「트러블슈팅: ingress-nginx 재시작 때 12초」), **먼저 2개로 늘린 뒤** 인자를 바꿨다. 인자는 배열이라 JSON 6902 패치로 그 한 줄만 바꾸고, `test` 연산으로 업스트림 인자 순서가 바뀌면 apply가 멈추게 했다(`platform/ingress-nginx/overlay/kustomization.yaml`).

```yaml
- op: test
  path: /spec/template/spec/containers/0/args/8
  value: --enable-metrics=false
- op: replace
  path: /spec/template/spec/containers/0/args/8
  value: --enable-metrics=true
```

1초 탐침에서 한 번(1초) 다섯 주소 모두 응답이 없었다. 12초보다 짧지만 0은 아니다.

### 3-3. 최종 확인 (2026-11-10)

```txt
수집 대상: kube-state-metrics 1/1 · kubelet-cadvisor 5/5 · node-exporter 5/5 · kubernetes-pods 5/5(ingress 포함) · ollama 1/1 · prometheus 1/1
          milvus 0/1(9091이 호스트 127.0.0.1에만) · nvidia-gpu 0/1(exporter 아직 안 띄움)
Loki: 12개 네임스페이스 로그, 챗봇 질문 줄 0건, Jenkins 빌드 Pod 0건
Grafana: 데이터소스 셋 OK, 모드별 질문 쿼리 → 사내규정 56 · 업무특화 89 · 일반 17
```

대시보드 「petmint 운영」(`apps/monitoring/grafana/dashboards/petmint.json`, `gen_petmint.py`로 만든다):

| 줄 | 패널 |
| --- | --- |
| 상단 | 앱 Pod Ready · 재시작(24시간) · 요청 수(상태코드별) · 에러율 |
| 중간 | 모드별 질문 수(시간당) · 시간대별 질문 수(KST) |
| 하단 | 거절률 · 규칙별 발동 수 · 코드 답 vs 모델 답 · 좋아요 · 싫어요 · 응답 시간 p50/p90 · 검색 지연 |
| 별도 | GPU 사용률 · VRAM · Ollama에 올라간 모델 · 턴이 쓴 모델 · 서버 로그 |

이때 거절률 · 검색 지연은 턴 로그에 칸이 없어 "앱 계측 필요" 텍스트 패널이었다.

### 3-4. 그 뒤 바뀐 것 (2026-11-11)

- **바깥 주소**: port-forward는 대시보드 동시 요청에서 connection reset으로 끊겨, Ingress `grafana.ronanlab.dev` · `prometheus.ronanlab.dev`를 만들었다(`apps/monitoring/ingress.yaml`, 인증서 cert-manager letsencrypt-prod, 터널 호스트 `apps/cloudflared/configmap.yaml`). argocd · harbor · jenkins와 같은 모양이다. Cloudflare Access · DNS는 사람이 대시보드에서 한다
- **자동 Sync**: petmint가 자동인데 대시보드만 수동인 것은 맞지 않고, 대시보드는 깨져도 서비스에 영향이 없어 자동으로 바꿨다(`apps/monitoring/app.yaml` 머리 주석, prune · selfHeal 끔)
- **Grafana 메모리**: 처음 값(50m/128Mi · 250m/256Mi)으로 Dashboards 화면에서 OOMKilled → 바깥에서 502/503. requests 100m/384Mi · limits 1/1Gi로 올렸다(README 「크기」)
- **Milvus**: 호스트 compose에서 9091을 192.168.122.1에도 게시해 milvus 1/1(디버그 경로도 함께 열림, 4절)
- **거절률 · 검색 지연**: 턴 로그에 `refused` · `search_ms`(앱 0009)가 생겨 패널을 연결하고 `grafana_ro`에 두 컬럼 권한을 더했다
- **GPU**: 호스트에서 `scripts/host-gpu-exporter.sh`로 nvidia-gpu-exporter를 띄웠다(192.168.122.1:9835). 2026-11-12 09:18 호스트 조회에서 Up 24 hours, Prometheus 대상 nvidia-gpu up 1

## 4. 남은 한계

- 알림(Alertmanager)이 없다. 알림 설계 전이다
- Prometheus · Loki는 한 대씩이다. w4가 죽으면 그동안의 지표 · 로그가 빈다([08_scale_out.md](08_scale_out.md) 「남은 한계」)
- Prometheus는 자체 로그인이 없다. 바깥에서는 Cloudflare Access가 유일한 문이라 Access를 건 뒤에 DNS를 연다(사람이 대시보드에서). 사설망 VIP로는 Access 없이 닿는다
- Milvus 9091은 `/debug/pprof` · `/log/level`도 인증 없이 사설망에 응답한다. 19530이 이미 같은 망에 인증 없이 열려 있어 새 위험은 작다고 봤다(앱 리포 `docs/02_pipeline/15_monitoring.md` 4절)

## 5. 확인 방법

접속 · Grafana 비밀번호 · 사설망에서 DNS 없이 부르는 법은 `apps/monitoring/README.md` 「확인 · 접속」.

수집 대상 전부를 호스트(사설망)에서:

```bash
curl -s --resolve prometheus.ronanlab.dev:443:192.168.122.240 'https://prometheus.ronanlab.dev/api/v1/query?query=up' \
  | python3 -c 'import json,sys; [print(r["metric"]["job"], r["metric"].get("instance"), r["value"][1]) for r in json.load(sys.stdin)["data"]["result"]]'
```

기대(2026-11-12 확인): 20개 모두 1. kube-state-metrics 1 · kubelet-cadvisor 5 · node-exporter 5 · kubernetes-pods 5(ingress-nginx 2 · cert-manager 3) · ollama 1 · prometheus 1 · milvus 1 · nvidia-gpu 1.

```bash
curl -s http://192.168.122.1:9835/metrics | /usr/bin/grep -c '^nvidia_smi'   # GPU exporter, 0 보다 크면 돈다(2026-11-12: 88)
```

m-k8s에서:

```bash
kubectl -n monitoring get pods -o wide        # 기대: alloy · node-exporter 는 노드 다섯에, 나머지는 w4
kubectl -n argocd get app monitoring          # 기대: Synced · Healthy
```
