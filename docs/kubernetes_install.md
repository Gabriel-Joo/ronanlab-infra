# 쿠버네티스 설치

GPU 서버 한 대([00_server.md](00_server.md)) 위에 KVM/libvirt + Vagrant로 VM 5대를 띄우고 kubeadm으로 쿠버네티스 클러스터를 직접 세웠다. 13단계 모두 끝났고, 지금 펫퍼민트 · 런슈즈와 Harbor · Jenkins · ArgoCD · 모니터링이 이 클러스터에서 돈다.
01~09 문서를 묶는 머리 문서다.

- 날짜: 2026-10-06 구축 시작, 2026-10-18 RUNSHOES 이주, 2026-11-10 증설(워커 4대 · 8GB) · 모니터링, 2026-11-12 코드 · 클러스터와 맞춤
- 범위: 목표 · 전체 구조 · 설계 원칙 · 13단계 순서와 진행 상황 · 터널 자산. 각 단계의 상세는 01~09(1-3절 표), 물리 서버는 [00_server.md](00_server.md)
- 코드: `cluster/`(Vagrantfile · setup-node.sh · label-nodes.sh), `platform/`(ArgoCD 밖), `apps/`(ArgoCD 앱), `bootstrap/root-app.yaml`

## 1. 지금 구성

### 1-1. 전체 인프라 구조 (2026-11-12)

```
[서버 PC, 상시가동]  kopo17-System-Product-Name, 32코어 · 61GB · RTX 5070 Ti (00_server.md)
  호스트 GPU: Ollama(도커 컨테이너, 11434) · model-service(systemd, KURE-v1 + bge-reranker, 8200)
  호스트 도커: Milvus(19530) · nvidia-gpu-exporter(9835)
  호스트 프로세스: search-service(systemd petmint-search, 8100, GPU 안 씀)
  NFS: 약관(읽기 전용) · 백업(쓰기), 192.168.122.0/24 에만
  호스트 systemd cloudflared-ollama: ollama-tunnel(학교 PC 전용)
  KVM/libvirt 위 Vagrant로 VM 생성 (5대, 합 36GB, ~/k8s-cluster)
    이름    사설 IP          역할 라벨  하는 일                         크기
    m-k8s   192.168.122.10  (없음)     컨트롤 플레인                   2 vCPU · 4GB
    w1-k8s  192.168.122.11  app        MySQL Primary + 앱              2 vCPU · 8GB
    w2-k8s  192.168.122.12  app        MySQL Replica + 앱              2 vCPU · 8GB
    w3-k8s  192.168.122.13  infra      Harbor · Jenkins · ArgoCD       2 vCPU · 8GB
    w4-k8s  192.168.122.14  platform   모니터링 · Loki                 2 vCPU · 8GB (2026-11-10 추가)
```

- VM 정의: `cluster/Vagrantfile`(m-k8s 4096MB, w1~w4 8192MB). 실제 `vagrant`가 도는 자리는 `~/k8s-cluster`(같은 내용의 사본)
- 역할 라벨: `node.ronanlab.dev/role`, `cluster/label-nodes.sh`가 붙인다(app = w1 · w2, infra = w3, platform = w4). 배치 고정이 이 라벨을 nodeSelector · nodeAffinity로 본다. infra · platform은 노드가 하나라 그 노드가 죽으면 배포 · 빌드 또는 모니터링만 멈춘다([08_scale_out.md](08_scale_out.md))
- 쿠버네티스 v1.35.9(kubeadm), containerd 2.2.1, Calico v3.28.0. 노드 5대 모두 Ready(2026-11-12)
- Pod는 GPU 호스트를 VM 사설망 주소 `192.168.122.1`로 부른다: Ollama `:11434`(`apps/petmint/app/configmap.yaml`, `apps/runshoes/app/deployment.yaml`), search-service `:8100`, Milvus `:19530`

### 1-2. 외부 노출 (Cloudflare Tunnel)

| 터널 | 도는 곳 | 호스트 | 가리키는 곳 |
| --- | --- | --- | --- |
| `ronanlab-tunnel` (02ad6a13-ce45-4262-a32a-40241bf034dc, 처음 이름 petmint-tunnel) | 클러스터 `cloudflared` Deployment 2개(`apps/cloudflared/`) | petmint · argocd · harbor · jenkins · runshoes · grafana · prometheus `.ronanlab.dev` (7개) | 모두 ingress-nginx ClusterIP `:443`(`https://`, `noTLSVerify: true`) |
| `ollama-tunnel` | 호스트 systemd `cloudflared-ollama` | `ollama.ronanlab.dev` | 호스트 `http://localhost:11434` |

호스트 목록은 `apps/cloudflared/configmap.yaml`. 호스트의 runshoes-tunnel(`cloudflared-runshoes` systemd, `~/.cloudflared-runshoes`)은 없다(2026-11-12 확인).

### 1-3. 단계와 문서 (13단계)

| 단계 | 내용 | CKA 연관 영역 | 문서 |
| --- | --- | --- | --- |
| 1 | KVM/libvirt 가상화 환경 구축 (qemu-system-x86, libvirt-daemon-system 등 설치 + 그룹 설정) | 클러스터 아키텍처 | [01_cluster.md](01_cluster.md) |
| 2 | Vagrant + vagrant-libvirt 플러그인 설치 | 클러스터 아키텍처 | [01_cluster.md](01_cluster.md) |
| 3 | Vagrantfile 작성 → VM 4대 생성(2026-11-10 워커 추가로 5대), 고정 IP 할당 | 클러스터 아키텍처 | [01_cluster.md](01_cluster.md) |
| 4 | 각 VM에 containerd, kubeadm/kubelet/kubectl 설치 (버전 고정) | 설치/구성 | [01_cluster.md](01_cluster.md) |
| 5 | kubeadm init(m-k8s) → kubeadm join(워커 3대, 지금 4대) → CNI(Calico) 설치 | 클러스터 설치 / 서비스·네트워킹 | [01_cluster.md](01_cluster.md) |
| 6 | metrics-server 설치 (지난번 vcluster에서 빠졌던 것, 이번엔 처음부터 포함) | 모니터링 전제조건 | [02_metrics_storage_ingress.md](02_metrics_storage_ingress.md) |
| 7 | local-path-provisioner (스토리지) | 스토리지 | [02_metrics_storage_ingress.md](02_metrics_storage_ingress.md) |
| 8 | Ingress Controller(nginx-ingress) | 서비스/네트워킹 | [02_metrics_storage_ingress.md](02_metrics_storage_ingress.md) |
| 9 | Cloudflare Tunnel 연결 (신규 `ronanlab-tunnel` 생성, 처음 이름은 petmint-tunnel. 기존 ollama-tunnel은 쓰지 않는다) | 외부 노출 | [03_cloudflare_tunnel.md](03_cloudflare_tunnel.md) |
| 10 | ArgoCD 설치 (GitOps 준비) + Jenkins 자체 구축(클러스터 내 Pod, GitHub webhook으로 트리거) + Harbor 자체 구축(클러스터 내 Pod, 이미지 레지스트리) | 없음 | [04_argocd.md](04_argocd.md) · [05_harbor.md](05_harbor.md) · [06_jenkins.md](06_jenkins.md) |
| 11 | 네임스페이스 생성(petmint, runshoes) 후 각 프로젝트 배포. petmint는 질문 · 답 · 참조조항을 앱이 MySQL 턴 로그로 남긴다(펫퍼민트 `docs/02_pipeline/12_data_storage.md`) | 워크로드/스케줄링 | [07_project_deploy.md](07_project_deploy.md) |
| 12 | 구조 확장 · 이관: 워커 4대 · 8GB(2026-11-10), Harbor · ArgoCD 이관, MySQL Replica, 노드별 배치 고정 | 클러스터 유지보수/스케줄링 | [08_scale_out.md](08_scale_out.md) |
| 13 | Prometheus · Grafana · node-exporter · kube-state-metrics(차트 없이 손으로 쓴 매니페스트) + Loki, w4(2026-11-10) | 모니터링 | [09_monitoring.md](09_monitoring.md) |

vcluster 시절 터널 기록은 [history/cloudflare_tunnel_vcluster.md](history/cloudflare_tunnel_vcluster.md).

이 문서에서 가리키는 앱 저장소 문서(펫퍼민트, 읽기만):

- `~/AI_programming/petmint-rag-chatbot/docs/02_pipeline/12_data_storage.md`: 상담 세션 · 턴 로그(MySQL)
- `~/AI_programming/petmint-rag-chatbot/docs/02_pipeline/13_access_and_tunnel.md`: 터널 구성 · Access 정책
- `~/AI_programming/petmint-rag-chatbot/docs/02_pipeline/14_deployment.md`: 무엇을 컨테이너로 만드는가 · 배포 흐름

## 2. 왜 이렇게 했나

### 2-1. 목표

서버 PC(GPU 보유 물리 머신) 위에 kubeadm으로 직접 K8s 클러스터를 구축한다. CKA 자격증은 아직 못 따지만, 이 프로젝트 자체가 CKA 수준 역량을 증명하는 자료가 되도록, 각 단계마다 「왜 이렇게 했는지」와 트러블슈팅을 기록해가며 진행한다.

### 2-2. 핵심 설계 원칙 (사전 확정된 것)

- **GPU는 호스트에 그대로 두고, K8s 파드는 Ollama API를 네트워크로 호출만 한다.** GPU 패스스루는 하지 않는다. 처음 해보는 작업이라 위험이 크고, 호스트에서 이미 Ollama를 계속 쓰고 있어서 넘기면 못 쓰게 될 수도 있다
- **CI/CD는 자체 구축한 Jenkins + Harbor로.** 학교 GitLab/Harbor를 다시 쓸 계획이었으나, 서버 PC에서 `std-gitlab.kopoctc.kr` / `std-harbor.kopoctc.kr`가 DNS부터 풀리지 않아 학교 내부망 전용 IP라고 확인됐다(학교 VPN 없이는 접근 불가). 그래서 GitHub(공인 네트워크)를 코드 저장소로 쓰고, Jenkins와 Harbor는 새 kubeadm 클러스터 안에 직접 Pod로 띄워 운영한다. 채용 공고 검색 결과 Jenkins가 여전히 DevOps/플랫폼 엔지니어 공고에 많이 언급되고 있어(GitHub Actions와 함께 나열되는 경우가 많음) 직접 구축하기로 했다
- **프로젝트별 네임스페이스 분리** (petmint, runshoes, 추후 추가되는 프로젝트도 같은 방식)
- **Cloudflare Tunnel은 클러스터 내부 Pod로 띄워, Ingress Controller만 바라보도록 설계** (포트포워딩 없이 아웃바운드 연결만)

### 2-3. 사전 검증 (웹 검색 기준)

- **kubeadm + Vagrant + libvirt**: 2026년 기준 최신 버전(K8s 1.36)까지도 여전히 표준적으로 쓰이는 방식이며, kubeadm 자체가 CKA 시험 범위에 명시적으로 포함된다(「CKA에서 kubeadm으로 클러스터를 부트스트랩하라고 요구받을 수 있다」)
- **cloudflared → Ingress 연결 패턴**: 2026년 가이드에서도 「하나의 터널을 Ingress Controller로 파이프하면, 새 앱을 노출할 때 Ingress 리소스만 추가하면 되고 터널 설정은 건드릴 필요 없다」는 이유로 이 패턴을 권장하고 있어, 우리 설계와 정확히 일치한다

### 2-4. RUNSHOES 터널에서 배운 것 (ronanlab-tunnel에 반영)

- `service`는 반드시 `https://...`로(http면 Ingress가 301 리다이렉트를 걸 수 있다), `noTLSVerify: true` 추가
- `route dns` 실행 뒤 **엉뚱한 터널로 CNAME이 연결될 수 있어** 반드시 Cloudflare 대시보드에서 Target을 확인한다
- nginx-ingress도 Host 헤더 기반 라우팅이면 `originRequest.httpHostHeader`가 필요할 수 있다
- k8s Secret은 base64일 뿐 암호화가 아니다. 「최소한의 노출 방지 장치」로만 이해하고 쓴다

### 2-5. IT 시스템엔지니어링 기초 수업에서 가져올 것

지난 학기에 들은 수업이다. 포트폴리오에는 이 수업 자체는 쓰지 않고 이 프로젝트에 녹여서 반영한다.

- **Day4-5 (K8s 기본 · 네트워킹)**: `kubectl apply -f`(선언형) 원칙, `kubectl diff`로 드리프트를 미리 확인하는 습관을 기본값으로. path vs host 분기 기준(「앱이 자기 경로를 아는가」)을 petmint API/UI Ingress 설계에 적용. 트러블슈팅은 검색 대신 `describe` Events를 먼저 보는 순서를 지킨다
- **Day6 (PV/PVC, StatefulSet, ConfigMap/Secret, requests/limits)**: **MySQL은 StatefulSet으로**(처음엔 Milvus도 올릴 계획이었으나 Milvus는 호스트 도커로 두었다, 펫퍼민트 `14_deployment.md` 「1-1. 무엇을 컨테이너로 만드는가」). Deployment + 공유 PVC는 여러 Pod가 한 디스크에 기록을 섞는 사고가 나므로 `volumeClaimTemplates`로 전용 PVC를 발급한다. PV/PVC는 `app.yaml` / `storage.yaml`로 나눠 `delete -f`가 실수로 데이터까지 지우지 않게 한다. Secret은 암호화가 아니라 표기법이므로 `.gitignore`로 관리한다(RUNSHOES와 같음). 각 파드(앱, MySQL)에 requests/limits를 명시하고 `kubectl top`으로 실측한 뒤 값을 정한다(QoS 등급 기록)
- **Day8 (Namespace, Quota, DaemonSet, Job/CronJob, Helm, GitOps 기초)**: Namespace 분리(petmint/runshoes)는 같은 이름 리소스가 칸마다 충돌 없이 공존함을 이미 확인했다. CronJob으로 FAQ 재생성 · Milvus 백업 · 로그 정리 자동화를 고려한다. Helm 차트는 `values` + `_helpers.tpl` + `required`로 환경별 값을 나누고 필수값이 빠지면 install 자체를 막게 한다. ArgoCD 전에 `diff → apply → drift 치유`를 손으로 연습해 두면 ArgoCD 이해에 도움이 된다
- **Day13-14 (관측가능성, 운영장애대응)**: kube-prometheus-stack 설치 경험(QoS 문제 해결 포함), Loki + Alloy 로그 수집, probe 3종(liveness/readiness/startup), OOMKilled 재현, 롤링 업데이트 장애대응을 이미 손으로 해보았으므로 그대로 09번(모니터링, [09_monitoring.md](09_monitoring.md))에서 재현한다

### 2-6. 대화 로그: 실제 사용자 질문 로그로 품질 관리 루프 만들기

앱이 질문 · 답 · 참조조항 · 상담원 평가를 MySQL 턴 로그(`turns` · `retrieved` · `feedback`)로 직접 남긴다(펫퍼민트 `~/AI_programming/petmint-rag-chatbot/docs/02_pipeline/12_data_storage.md`). 처음엔 Day4의 사이드카 패턴을 따라 같은 Pod의 로그 컨테이너가 Loki로 보내는 구조를 계획했다. 지금 턴 로그의 목표는 「그때 어떤 조건에서 무엇을 보고 어떻게 답했는가」를 나중에 그대로 재현하는 것이다(같은 문서 「0. 한 줄 요약」).

Loki에는 서버 로그만 넣고 대화 기록(질문 · 답 원문)은 넣지 않는다. Alloy가 런슈즈 챗봇의 질문 원문 줄을 버린다(`apps/monitoring/alloy/alloy.yaml`).

**활용 계획**:

- 어떤 질문에서 검색이 자주 실패하는지 분석 → FAQ 추가 생성이나 임베딩 튜닝 근거
- 실제 사용자 질문 로그를 펫퍼민트의 RAG 성능 정량 평가(Ragas)의 실측 평가셋으로 활용. 지금은 합성 FAQ로만 평가하는데, 진짜 질문이 쌓이면 더 현실적인 평가가 된다
- 상담원 평가(`feedback`)도 같은 턴에 쌓여 품질 관리 루프의 재료가 된다

## 3. 진행 기록

### 3-1. 진행 상황

(각 단계 완료 시 업데이트, 번호는 1-3절 13단계 표 기준)

- [x] KVM/libvirt 가상화 환경 구축
- [x] Vagrant + vagrant-libvirt 설치
- [x] Vagrantfile 작성 → VM 4대 생성 (2026-11-10 w4 추가로 5대)
- [x] containerd/kubeadm/kubelet/kubectl 설치
- [x] kubeadm init → join → CNI(Calico)
- [x] metrics-server
- [x] local-path-provisioner (스토리지)
- [x] Ingress Controller(nginx-ingress)
- [x] Cloudflare Tunnel 연결
- [x] ArgoCD 설치
- [x] Harbor 자체 구축
- [x] Jenkins 구축 + 파이프라인 (2026-10-15, GitHub 웹훅 2026-11-03)
- [x] 네임스페이스 생성 후 프로젝트 배포 (petmint 2026-10-16, runshoes 2026-10-18 이주)
- [x] 구조 확장 · 이관 (2026-11-10: 워커 4대 · 8GB, Harbor · ArgoCD w3, MySQL Replica w2, 배치 고정)
- [x] 모니터링 + Loki (2026-11-10, w4)

### 3-2. 기존 Cloudflare Tunnel 자산 파악 (RUNSHOES 프로젝트에서 이미 구축됨)

이 클러스터를 세우기 전 같은 GPU 서버에는 터널이 두 개 있었다. 지금 호스트에 남은 것은 ollama-tunnel 하나다(상세: [history/cloudflare_tunnel_vcluster.md](history/cloudflare_tunnel_vcluster.md), 노션 「Cloudflare Tunnel 세팅 (트러블슈팅 기록)」).

- **ollama-tunnel**: `ollama.ronanlab.dev` → GPU 호스트의 Ollama(`localhost:11434`). 호스트 systemd `cloudflared-ollama`가 띄운다. **학교 PC 전용**이다. 환경이 달라 학교 PC가 서버의 Ollama API를 이 터널로 부른다. 펫민트 · 런슈즈 Pod는 이 터널을 쓰지 않고 `http://192.168.122.1:11434`로 직접 부르므로 `CF_ACCESS_*` Secret도 없다(처음엔 펫민트도 이 터널을 다시 쓸 계획이었다). 2026-11-09: 적어도 11-02부터 토큰 없이 열려 있던 것을 확인했다. 바깥 IP 요청은 `/`에 대한 GET · HEAD뿐이었고 generate · pull · delete는 0건. 같은 날 Access Service Auth(토큰 `ollama-school-pc`)를 다시 걸었고, 토큰 없는 요청은 403이다
- **runshoes-tunnel**: 처음엔 `runshoes.ronanlab.dev` → 학교 vcluster(vc-kopo17)의 traefik Ingress를 가리켰다. 2026-10-18 RUNSHOES를 이 클러스터로 옮기면서 `runshoes.ronanlab.dev`는 `ronanlab-tunnel`의 다섯 번째 호스트가 됐다(펫퍼민트 `13_access_and_tunnel.md` 「1-3. Access 정책」 표). 호스트의 runshoes-tunnel 프로세스는 돌지 않고(2026-11-09 확인), 2026-11-12에는 systemd `cloudflared-runshoes`와 설정 폴더 `~/.cloudflared-runshoes`도 호스트에 없다

**새로 만든 것: `ronanlab-tunnel`**(처음 이름 petmint-tunnel, 02ad6a13…, 펫퍼민트 `13_access_and_tunnel.md` 「1-2. 터널 구성」): 클러스터 안 Pod로 돌며 nginx-ingress를 가리킨다. 처음에는 다섯 호스트(petmint, argocd, harbor, jenkins, runshoes)를 실었고, 지금은 일곱 호스트다(3-4절). RUNSHOES 때 겪은 시행착오를 참고했다(2-4절).

### 3-3. RUNSHOES 이주 (2026-10-18 끝남)

RUNSHOES를 학교 vcluster에서 이 클러스터로 옮겼다. 터널은 runshoes-tunnel의 대상을 바꾸는 대신 `ronanlab-tunnel`의 호스트로 옮겼다.

### 3-4. 이후 바뀐 것

- **2026-11-02**: search-service가 호스트 systemd 유닛 `petmint-search`(192.168.122.1:8100)로 돈다(펫퍼민트 `14_deployment.md` 「1-1. 무엇을 컨테이너로 만드는가」)
- **2026-11-11**: `ronanlab-tunnel`에 `grafana.ronanlab.dev` · `prometheus.ronanlab.dev`를 더해 일곱 호스트가 됐다(`apps/cloudflared/configmap.yaml`, Ingress는 `apps/monitoring/ingress.yaml`)
- **2026-11-11**: 검색 모델(KURE-v1 · bge-reranker-v2-m3)을 search-service에서 떼어 호스트 systemd `model-service`(192.168.122.1:8200)로 옮겼다. 런슈즈 챗봇도 같이 쓴다(펫퍼민트 `14_deployment.md` 「1-26. 검색 모델을 공용 model-service로」)

## 4. 남은 한계

- **서버 한 대가 전부다**: GPU 호스트가 꺼지면 VM 5대와 Ollama · Milvus · model-service · NFS가 같이 멈춘다. 노드 하나가 죽을 때의 시나리오는 [08_scale_out.md](08_scale_out.md) 「남은 한계」
- **infra(w3) · platform(w4)은 노드가 하나다**: w3가 죽으면 배포 · 빌드가, w4가 죽으면 모니터링이 멈춘다(`cluster/label-nodes.sh` 주석)
- **GPU 패스스루를 하지 않는다**: Pod는 GPU를 직접 쓰지 못하고 호스트 API(Ollama · model-service)를 네트워크로 부른다. 설계상 정한 것이다(2-2절)
- **대화 로그 활용 계획(2-6절)이 어디까지 됐는지**는 이 문서에서 확인하지 않았다. 펫퍼민트 저장소 문서에서 본다

## 5. 확인 방법

```bash
# VM 5대 (호스트, ~/k8s-cluster 에서)
cd ~/k8s-cluster && vagrant status                      # m-k8s · w1-k8s ~ w4-k8s 모두 running (libvirt)

# 노드 · 역할 라벨 (m-k8s 에서)
vagrant ssh m-k8s -c 'kubectl get nodes -L node.ronanlab.dev/role'
# 5대 Ready, v1.35.9. ROLE: w1 · w2 app, w3 infra, w4 platform, m-k8s 비어 있음

# ArgoCD 앱
vagrant ssh m-k8s -c 'kubectl -n argocd get applications'
# root · cloudflared · harbor-backup · monitoring · petmint · runshoes 모두 Synced · Healthy

# 터널 호스트
vagrant ssh m-k8s -c "kubectl -n cloudflared get cm cloudflared-config -o jsonpath='{.data.config\.yaml}'" | /usr/bin/grep -c 'hostname:'   # 7 (-o yaml 로 세면 last-applied 주석까지 8)
vagrant ssh m-k8s -c 'kubectl get ingress -A'           # argocd · harbor · jenkins · grafana · prometheus · petmint · runshoes

# 호스트 쪽
systemctl is-active cloudflared-ollama model-service petmint-search libvirtd   # 모두 active
systemctl list-unit-files 'cloudflared*'                # cloudflared-ollama 하나뿐
docker ps --format '{{.Names}}' | sort                  # ollama · openwebui · milvus-standalone 등
```
