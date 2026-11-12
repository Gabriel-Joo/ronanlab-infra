# 09. 모니터링

Prometheus, Grafana, node-exporter, kube-state-metrics로 지표를 모으고 Loki(Alloy 수집)로 서버 로그를 모은 기록이다. 전부 w4 한 노드에 올렸고, 앱 코드를 고치지 않고 볼 것을 채우려고 지표 출처를 나눴다.

- 날짜: 2026-11-10 설치, 2026-11-12 코드와 맞춤
- 범위: 지금 구성, 왜 이렇게 했나, 설치 기록. 크기 근거 표와 읽기 계정 권한 전체는 `apps/monitoring/README.md`
- 코드: apps/monitoring/, platform/ingress-nginx/overlay/, scripts/host-gpu-exporter.sh, apps/cloudflared/configmap.yaml

## 1. 지금 구성

| 구성 | 하는 일 | 배치 · 저장 |
| --- | --- | --- |
| Prometheus v3.15.0 | 지표 수집, 30초 간격 | w4, local-path 10Gi, 보존 15일(또는 9GB) |
| Loki 3.5.0 | 서버 로그 | w4, local-path 10Gi, 보존 7일 |
| Alloy v1.8.0 | Pod 로그를 Loki로 보낸다 | DaemonSet, 노드 다섯 |
| node-exporter v1.12.1 | 노드 CPU, 메모리, 디스크 | DaemonSet, 노드 다섯 |
| kube-state-metrics v2.19.1 | Pod 상태, 재시작 | w4 |
| json-exporter v0.7.0 | Ollama `/api/ps`를 지표로 | w4 |
| Grafana 13.2.3 | 대시보드 「petmint 운영」(패널 18개) | w4, 저장 없음(설정과 대시보드는 저장소에서) |
| nvidia_gpu_exporter 1.3.1 | GPU 사용률, VRAM | 클러스터 밖, 물리 서버의 Docker 컨테이너(192.168.122.1:9835) |

- 배치: node-exporter와 Alloy만 모든 노드에, 나머지는 전부 w4(`node.ronanlab.dev/role=platform`)
- 접속: `https://grafana.ronanlab.dev`, `https://prometheus.ronanlab.dev`. Cloudflare 터널과 Access 뒤에 있고, 사설망에서는 MetalLB VIP 192.168.122.240으로 닿는다
- Sync: ArgoCD Application `monitoring`, 자동(prune과 selfHeal은 끔). `main`에 push하면 3분 안에 들어간다
- 알림: 없다(Alertmanager 없음)

## 2. 왜 이렇게 했나

### 2-1. 차트 대신 손으로 쓴 매니페스트

- **문제**: 처음 계획은 kube-prometheus-stack(Helm)이었다. `helm install`로 넣으면 설정이 클러스터 안에만 남아, Pod를 다시 만들면 무엇을 어떻게 했는지 모르게 된다. MetalLB, cert-manager, ingress, Jenkins 설정(JCasC)을 전부 저장소에 남겨 두었는데 모니터링만 클러스터 안에 두면 거기만 구멍이 된다
- **고른 것**: 차트 없이 쓴 매니페스트를 `apps/monitoring/`에 두고 ArgoCD가 본다. Prometheus는 Operator 없이 설정 파일 하나(`prometheus/configmap.yaml`)로 긁는다. Grafana 데이터소스와 대시보드도 저장소의 파일로 프로비저닝한다
- **버린 안**: kube-prometheus-stack. 지표 출처가 넷뿐이라 Operator와 CRD가 줄여 주는 일보다 늘리는 구성이 많았다
- **대가**: 버전을 올리는 일이 손일이다. 이미지 태그를 하나씩 바꾸고 호환을 직접 본다(kube-state-metrics v2.19는 클러스터 1.35에 맞춰 골랐다). 차트가 주는 기본 대시보드와 경보 규칙도 없다. Grafana는 저장 공간이 없어 UI에서 고친 대시보드는 Pod를 다시 만들면 사라진다. 대시보드는 `grafana/dashboards/gen_petmint.py`를 고쳐 JSON을 다시 만든다

### 2-2. 앱에 `/metrics`가 없어 출처를 나눴다

- **문제**: 펫퍼민트 앱에는 `/metrics`가 없다. 요청 수, 질문 수, 응답 시간을 볼 곳이 없었다
- **고른 것**: 앱 코드를 고치지 않고, 이미 있는 곳에서 하나씩 얻는다

| 보고 싶은 것 | 출처 |
| --- | --- |
| 파드 상태, 재시작 | kube-state-metrics |
| 요청 수, 에러율 | ingress-nginx 메트릭. 업스트림이 `--enable-metrics=false`로 꺼 둔 것을 켰다 |
| 모드별, 시간대별 질문, 규칙별 발동, 코드 답과 모델 답, 좋아요와 싫어요, 응답 시간 p50/p90, 거절률, 검색 지연, 턴이 쓴 모델 | petmint 턴 로그(DB). Grafana가 MySQL을 직접 읽는다(2-4절) |
| GPU 사용률, VRAM | 물리 서버의 nvidia-gpu-exporter(2-7절) |
| Ollama에 올라간 모델 | json-exporter가 Ollama `/api/ps`를 지표로 바꾼다 |
| 서버 로그 | Loki(7일) ← Alloy(노드마다) |

- **버린 안**: 앱에 `/metrics`를 붙이는 것(FastAPI 미들웨어로 경로별 히스토그램, WebSocket 연결 수). 앱 코드를 고치는 일이라 이번에 하지 않았다. 왜 앱 계측을 미뤘는지 그 밖의 까닭은 기록 없음. Ollama는 응답만 보는 blackbox-exporter 대신 json-exporter를 골랐다. 지금 올라간 모델까지 보이기 때문이다
- **대가**: HTTP 지표는 ingress를 거친 요청만 보인다. 턴 로그에 칸이 없는 것은 볼 수 없다. 거절률과 검색 지연은 처음에 빈 패널이었고, 앱이 `refused`와 `search_ms`를 적기 시작한 뒤에야 들어왔다(3-4절). Ollama 말고 search-service, model-service가 살아 있는지는 아직 보지 못한다

**ingress-nginx 메트릭을 켠 까닭과 대가**: HTTP 요청 수와 상태코드를 앱 대신 얻을 수 있는 곳이 ingress였다. 메트릭을 켜려면 컨트롤러를 다시 띄워야 했고, 1개일 때 재시작이 12초 동안 모든 주소를 끊은 적이 있어 먼저 2개로 늘렸다(3-2절). 대가는 짧은 끊김 한 번(1초)과, 업스트림 매니페스트의 인자 순서에 기대는 패치다. 순서가 바뀌면 `test` 연산이 apply를 멈춘다.

### 2-3. w4 한 노드에 모았다

- **문제**: 전에는 local-path PVC가 노드 여기저기에 생겨, 어느 워커를 내려도 무언가 일부가 멈췄다. 노드가 죽었을 때 무엇이 멈추는지 노드 이름으로 말할 수 없었다. 메모리도 문제였다. 노드가 4GB일 때 Prometheus가 w3에 뜨면 w3의 limits 합이 노드 용량을 넘었다(크기 계산은 README 「크기」)
- **고른 것**: 노드마다 역할을 고정했다. app은 w1과 w2, infra(Harbor, Jenkins, ArgoCD)는 w3, platform(모니터링)은 w4. 모니터링 매니페스트는 `node.ronanlab.dev/role=platform`을 nodeSelector로 본다. 지표와 로그를 모으는 node-exporter와 Alloy만 모든 노드에 뜬다
- **버린 안**: 배치 제약 없이 아무 노드에나 띄우는 것. 노드를 8GB로 올리면 메모리로는 들어가지만, 어느 노드가 죽으면 무엇이 멈추는지 다시 흐려진다
- **대가**: w4가 죽으면 그동안 모니터링과 로그가 멈추고, 그 사이 지표와 로그는 빈다. local-path PV는 처음 붙은 노드에 묶여 Prometheus와 Loki는 w4 밖으로 옮겨지지 않는다. 대신 w4가 죽어도 상담과 배포는 돈다

### 2-4. Grafana가 DB를 직접 읽는다: Replica, 컬럼 단위 권한

- **문제**: 질문과 답에 관한 지표(모드, 규칙, 응답 시간, 평가)는 펫퍼민트 턴 로그(DB)에만 있다. 그런데 턴 로그에는 질문과 답 본문, 상담원 코멘트도 함께 있다
- **고른 것**: Grafana MySQL 데이터소스 `petmint-turns`가 DB를 읽는다. 세 가지를 붙였다
  - Primary가 아니라 **Replica**(`mysql-replica.petmint.svc`, w2)를 읽는다. 대시보드 쿼리가 운영 쓰기에 부하를 주지 않는다
  - 읽기 계정 `grafana_ro`는 **컬럼 단위 SELECT**만 받는다. 분류, 시간, 상태 칸만 읽고 질문, 답, 코멘트, 고객, 상담원 칸은 권한이 없다
  - 최대 연결 5
- **버린 안**: 앱 `/metrics`(2-2절). 테이블 단위 권한이나 뷰를 따져 봤다는 기록은 기록 없음
- **대가**: 턴 로그에 칸이 생기면 권한을 손으로 더해야 한다(`refused`, `search_ms`가 그랬다, 3-4절). Replica가 멈추거나 복제가 늦으면 질문 패널도 멈추거나 늦는다

설치 때 준 권한과 막힌 것을 시험한 결과:

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

뒤에 `turns`에 `refused`, `search_ms` 두 칸을 더했다. 지금 권한 전체는 README.

### 2-5. Loki에 대화를 넣지 않는다

- **문제**: 대화 기록은 이미 DB에 있다. 로그에도 들어가면 같은 내용이 권한이 다른 곳에 하나 더 생긴다. 확인해 보니 runshoes 챗봇이 질문 원문을 로그로 남기고 있었다

```py
print(f"[{now()}] 질문: {text}")
```

- **고른 것**: Loki에는 서버 로그만 넣는다(사용자 결정). 수집기(Alloy)에서 그 줄을 버린다. Jenkins 빌드 Pod의 로그(빌드 출력)도 넣지 않는다. 라벨은 namespace, pod, container, node 넷만 둔다

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

- **버린 안**: runshoes 앱에서 그 `print`를 지우는 것. 수집기에서 거르는 쪽을 고른 까닭은 기록 없음
- **대가**: 문자열 일치로 거른다. 앱이 로그 꼴을 바꾸면(「질문:」을 다른 말로) 거르지 못하고 들어간다. 다른 앱이 새로 원문을 찍어도 Alloy 설정을 고치기 전까지 들어간다

### 2-6. 보존: Prometheus 15일 · 10Gi, Loki 7일

- **문제**: local-path는 PVC 크기를 강제하지 않는다(노드 디렉터리일 뿐이다). 디스크가 차기 전에 Prometheus가 스스로 지워야 한다
- **고른 것**: 처음 설계는 7일에 5Gi였다. 시계열 1.5만을 30초마다 7일 모으면 블록이 약 0.45GB, WAL과 압축 여유까지 약 1GB라 3~4배로 늘어도 들어가게 5Gi로 잡았다. 설치 때 사용자가 보존을 15일로 정해 PVC를 10Gi로 올렸고, `--storage.tsdb.retention.size=9GB`로 PVC보다 먼저 지우게 했다. Loki는 7일(사용자 결정), compactor가 지운다
- **버린 안**: 7일 · 5Gi(처음 설계). 15일로 늘린 까닭은 기록 없음(사용자 결정이라는 것만 있다). Loki 7일의 까닭도 기록 없음
- **대가**: w4 디스크를 Prometheus와 Loki가 20Gi까지 쓴다. 15일을 넘는 추세는 볼 수 없다. 시계열이 늘면 9GB에 먼저 걸려 15일보다 짧게 남을 수 있다

### 2-7. GPU exporter는 물리 서버의 컨테이너

- **문제**: GPU(RTX 5070 Ti)는 물리 서버에 있고, Ollama도 거기서 Docker로 돈다. 쿠버네티스 노드는 그 위의 VM이다
- **고른 것**: 물리 서버에서 `scripts/host-gpu-exporter.sh`로 nvidia_gpu_exporter 컨테이너를 띄운다(`--gpus all`, utility 기능만). 포트는 VM 사설망 주소(192.168.122.1:9835)에만 열고 바깥에는 열지 않는다. Prometheus가 그 주소를 긁는다. 바깥 이미지를 GPU 권한으로 물리 서버에 띄우는 일이라 사람이 돌린다
- **버린 안**: 클러스터 안에서 GPU를 보는 안(VM에 GPU를 넘기는 것 등)을 따졌다는 기록은 기록 없음
- **대가**: ArgoCD 밖이다. 컨테이너가 사라지면 사람이 스크립트를 다시 돌려야 한다(`--restart unless-stopped`라 사람이 멈추지 않은 한 Docker가 다시 띄운다). 사람이 띄우기 전까지 nvidia-gpu 대상은 0/1이었다

### 2-8. 바깥 주소는 Ingress로

- **문제**: 처음에는 전부 ClusterIP에 port-forward로 봤다. 대시보드는 패널마다 쿼리를 동시에 보내는데, port-forward가 그때 connection reset으로 끊겼다
- **고른 것**: `grafana.ronanlab.dev`, `prometheus.ronanlab.dev` Ingress(`apps/monitoring/ingress.yaml`). ArgoCD, Harbor, Jenkins와 같은 모양이다. 바깥은 Cloudflare 터널 → ingress-nginx, 인증은 Cloudflare Access 「운영도구」 앱, 인증서는 cert-manager(letsencrypt-prod, DNS-01). 사설망에서는 MetalLB VIP로 같은 Ingress에 닿는다
- **버린 안**: port-forward. 위처럼 끊긴다
- **대가**: Prometheus는 자체 로그인이 없다. 바깥에서는 Access가 유일한 문이라 Access를 건 뒤에 DNS를 연다. Access와 DNS는 사람이 Cloudflare 대시보드에서 한다. 사설망 VIP로는 Access 없이 닿는다(admin API는 켜지 않았다). Grafana는 자체 로그인과 Access 두 겹이다

### 2-9. 자동 Sync

- **문제**: 처음에는 수동 Sync였다. 그런데 petmint는 자동 Sync라 앱은 push만으로 들어가는데 대시보드만 사람이 Sync를 눌러야 했다
- **고른 것**: 자동 Sync(사용자 지시). 대시보드는 깨져도 서비스에 영향이 없고 되돌리기 쉽다. prune과 selfHeal은 petmint와 같이 끈다. 켜고 끄는 실제 스위치는 클러스터의 `kubectl patch`이고 `app.yaml`은 기록이다(루트 Application이 자식의 syncPolicy를 덮지 않는다)
- **버린 안**: 수동 Sync. 위의 어긋남 때문이다
- **대가**: push가 곧 배포다. prune이 꺼져 있어 git에서 지운 리소스는 클러스터에 남는다. kubectl로 바꾼 것은 되돌려지지 않는다

### 2-10. Alertmanager는 아직 없다

- **문제**: 무엇을 누구에게 알릴지 정하지 않았다
- **고른 것**: 이번 단계는 보는 것까지로 했다. 알림은 알림 설계 뒤에 붙인다
- **버린 안**: 기본 규칙으로 일단 알림을 켜는 것. 버린 까닭은 위 말고는 기록 없음
- **대가**: 문제가 생겨도 아무도 불리지 않는다. 사람이 대시보드를 열어야 안다

## 3. 진행 기록

### 3-1. 13-1단계: 설치

설치 때의 값이다. 노출과 Sync는 뒤에 바뀌었다(3-4절).

| 구성 | 값 |
| --- | --- |
| 배치 | 전부 w4(`node.ronanlab.dev/role=platform`). node-exporter와 Alloy만 DaemonSet |
| Prometheus | 보존 15일(또는 9GB), w4 local-path 10Gi |
| Loki | 단일 바이너리, 보존 7일(compactor), w4 local-path 10Gi |
| Grafana | 데이터소스 Prometheus, Loki, petmint-turns(MySQL). 대시보드는 저장소의 JSON을 프로비저닝 |
| 노출 | 전부 ClusterIP, port-forward |
| ArgoCD | 루트 Application의 `exclude: 'monitoring/app.yaml'`을 빼서 Application을 만들었다. Sync는 수동 |

### 3-2. 13-2단계: ingress-nginx 메트릭

메트릭을 켜려면 컨트롤러를 다시 띄워야 한다. 앞서 w1을 비우기 전 ingress-nginx(1개)를 `rollout restart`했을 때 12초 동안 다섯 주소가 모두 응답하지 않았다(원인 미확인). 그래서 **먼저 2개로 늘린 뒤** 인자를 바꿨다. 인자는 배열이라 JSON 6902 패치로 그 한 줄만 바꾸고, `test` 연산으로 업스트림 인자 순서가 바뀌면 apply가 멈추게 했다(`platform/ingress-nginx/overlay/kustomization.yaml`).

```yaml
- op: test
  path: /spec/template/spec/containers/0/args/8
  value: --enable-metrics=false
- op: replace
  path: /spec/template/spec/containers/0/args/8
  value: --enable-metrics=true
```

한 개씩 롤링하는 동안 1초 탐침에서 21:13:29 한 번(1초) 다섯 주소 모두 응답이 없었다. 12초보다 짧지만 0은 아니다. 두 Pod 모두 `nginx_ingress_controller_requests`를 낸다.

### 3-3. 최종 확인

```txt
수집 대상: kube-state-metrics 1/1 · kubelet-cadvisor 5/5 · node-exporter 5/5 · kubernetes-pods 5/5(ingress 포함) · ollama 1/1 · prometheus 1/1
          milvus 0/1(9091이 호스트 127.0.0.1에만) · nvidia-gpu 0/1(exporter 아직 안 띄움)
Loki: 12개 네임스페이스 로그, 챗봇 질문 줄 0건, Jenkins 빌드 Pod 0건
Grafana: 데이터소스 셋 OK, 모드별 질문 쿼리 → 사내규정 56 · 업무특화 89 · 일반 17
```

대시보드 「petmint 운영」(`apps/monitoring/grafana/dashboards/petmint.json`, `gen_petmint.py`로 만든다), 설치 때 구성:

| 줄 | 패널 |
| --- | --- |
| 상단 | 앱 Pod Ready, 재시작(24시간), 요청 수(상태코드별), 에러율 |
| 중간 | 모드별 질문 수(시간당), 시간대별 질문 수(KST) |
| 하단 | 거절률, 규칙별 발동 수, 코드 답과 모델 답, 좋아요와 싫어요, 응답 시간 p50/p90, 검색 지연 |
| 별도 | GPU 사용률, VRAM, Ollama에 올라간 모델, 턴이 쓴 모델, 서버 로그 |

거절률과 검색 지연은 턴 로그에 칸이 없어 "앱 계측 필요" 텍스트 패널이었다. 지금은 네 줄(서비스 상태와 접속량, 질문량, 답변 품질과 속도, AI 서버)에 패널 18개이고, 이름은 비개발자가 읽는 말로 바꿨다.

### 3-4. 그 뒤 바뀐 것 (2026-11-11)

- **바깥 주소**: port-forward가 대시보드 동시 요청에서 connection reset으로 끊겨 Ingress `grafana.ronanlab.dev`, `prometheus.ronanlab.dev`를 만들었다(2-8절). 터널 호스트는 `apps/cloudflared/configmap.yaml`
- **자동 Sync**: `kubectl patch`로 켰다(2-9절). 켤 때 밀려 있던 것은 대시보드 ConfigMap 하나였고 바로 반영됐다
- **Grafana 메모리**: 처음 값(requests 50m/128Mi, limits 250m/256Mi)으로는 기동만으로 약 240Mi를 써, Dashboards 화면(검색 인덱스)에서 OOMKilled가 났고 바깥에서 502/503으로 보였다. requests 100m/384Mi, limits 1/1Gi로 올리고 프로브 timeout을 3초로 늘렸다
- **Milvus**: 9091이 물리 서버 127.0.0.1에만 열려 있어 닿지 않았다. 호스트 compose에서 192.168.122.1에도 게시해 milvus 1/1(19530과 같은 방식, etcd 2379는 닫힌 채). 디버그 경로도 함께 열렸다(4절)
- **거절률, 검색 지연**: 앱이 턴마다 `refused`, `search_ms`(앱 마이그레이션 0009)를 적게 되어 패널을 연결하고 `grafana_ro`에 두 칸 권한을 더했다. 그 전 턴은 NULL이라 빈 칸이다. 같은 날 「답변 실패 · 중단 비율」 패널(turns.status error, cancelled)을 더했다
- **GPU**: 물리 서버에서 `scripts/host-gpu-exporter.sh`로 nvidia-gpu-exporter를 띄웠다(09:22, 192.168.122.1:9835). 2026-11-12 09:18 물리 서버 조회에서 Up 24 hours, Prometheus 대상 nvidia-gpu up 1

## 4. 남은 한계

- 알림(Alertmanager)이 없다. 무엇을 누구에게 알릴지 정하기 전이다(2-10절)
- Prometheus와 Loki는 한 대씩이고 PV가 w4에 묶여 있다. w4가 죽거나 정비로 비우면 그동안의 지표와 로그가 빈다
- Prometheus는 자체 로그인이 없다. 바깥에서는 Cloudflare Access가 유일한 문이라 Access를 건 뒤에 DNS를 연다(사람이 대시보드에서). 사설망 VIP로는 Access 없이 닿는다
- Milvus 9091은 `/debug/pprof`, `/log/level`도 인증 없이 사설망에 응답한다. 19530(벡터 조회와 쓰기)이 이미 같은 망에 인증 없이 열려 있어 새 위험은 작다고 봤다(사용자 동의). 좁히려면 물리 서버에서 지표 경로만 넘기는 프록시를 두거나 NetworkPolicy로 Prometheus만 나가게 한다
- search-service, model-service가 살아 있는지는 보지 못한다(blackbox-exporter 없음)
- 거절률은 문구 판정이다. 거절 문구 없이 얼버무린 답은 거절로 세지 않는다

## 5. 확인 방법

Grafana admin 비밀번호(m-k8s에서, 화면에만 띄우고 어디에도 적지 않는다):

```bash
kubectl -n monitoring get secret grafana-admin -o jsonpath='{.data.admin-password}' | base64 -d; echo
```

사설망(물리 서버)에서 DNS 없이 Grafana를 부른다:

```bash
curl -s --resolve grafana.ronanlab.dev:443:192.168.122.240 https://grafana.ronanlab.dev/api/health
```

수집 대상 전부를 물리 서버(사설망)에서:

```bash
curl -s --resolve prometheus.ronanlab.dev:443:192.168.122.240 'https://prometheus.ronanlab.dev/api/v1/query?query=up' \
  | python3 -c 'import json,sys; [print(r["metric"]["job"], r["metric"].get("instance"), r["value"][1]) for r in json.load(sys.stdin)["data"]["result"]]'
```

기대: 20개 모두 1.

| job | 개수 |
| --- | --- |
| kube-state-metrics | 1 |
| kubelet-cadvisor | 5 |
| node-exporter | 5 |
| kubernetes-pods | 5(ingress-nginx 2, cert-manager 3) |
| ollama, prometheus, milvus, nvidia-gpu | 1씩 |

```bash
curl -s http://192.168.122.1:9835/metrics | /usr/bin/grep -c '^nvidia_smi'   # GPU exporter, 0보다 크면 돈다(지난번 88)
```

m-k8s에서:

```bash
kubectl -n monitoring get pods -o wide        # 기대: alloy, node-exporter는 노드 다섯에, 나머지는 w4
kubectl -n monitoring get pvc                 # 기대: data-prometheus-0, data-loki-0 모두 Bound 10Gi
kubectl -n argocd get app monitoring          # 기대: Synced, Healthy
```
