# 노션 문서 옮기기와 코드 맞춤 기록 (2026-11-12)

노션 「프로젝트 / 인프라」 아래 기술문서를 docs로 옮기고, 지금 코드 · 클러스터 · 호스트와 다른 곳을 고친 기록이다.

- 날짜: 2026-11-12(노션은 11-10까지, 서버 문서는 10-06까지 고친 것)
- 범위: 무엇을 어디로 옮겼나, 합친 것, 실제와 달라서 고친 것, 판단하지 못해 남긴 것. 문서 본문은 각 파일
- 코드: 근거는 2026-11-12 09:18 KST 클러스터 · 호스트 조회(읽기만)와 저장소 파일

## 1. 지금 구성

| 노션 | docs |
| --- | --- |
| 인프라/서버 구축 포트폴리오 문서 | [00_server.md](../00_server.md) |
| 쿠버네티스 설치(머리 쪽) | [kubernetes_install.md](../kubernetes_install.md) |
| 01. 클러스터 구축 | [01_cluster.md](../01_cluster.md)(있던 파일에 합침) |
| 02. 메트릭·스토리지·Ingress | [02_metrics_storage_ingress.md](../02_metrics_storage_ingress.md) |
| 03. Cloudflare Tunnel 연결 | [03_cloudflare_tunnel.md](../03_cloudflare_tunnel.md) |
| 04. ArgoCD | [04_argocd.md](../04_argocd.md) |
| 05. Harbor | [05_harbor.md](../05_harbor.md) |
| 06. Jenkins | [06_jenkins.md](../06_jenkins.md) |
| 07. 프로젝트 배포 | [07_project_deploy.md](../07_project_deploy.md) |
| 08. 구조 확장·이관 | [08_scale_out.md](../08_scale_out.md)(옛 `02_availability.md`, 합침) |
| 09. 모니터링 | [09_monitoring.md](../09_monitoring.md)(지금 구성은 `apps/monitoring/README.md`) |
| Cloudflare Tunnel 세팅, 같은 문서 (트러블슈팅 기록) | 지금도 사실인 것은 03에, 나머지는 [cloudflare_tunnel_vcluster.md](cloudflare_tunnel_vcluster.md) |

## 2. 왜 이렇게 했나

- 말투 · 꼴은 사용자가 정했다(2026-11-12): 한다체, 머리 세 줄(요약 · 날짜 · 범위 · 코드), 절 다섯(지금 구성 / 왜 이렇게 했나 / 진행 기록 / 남은 한계 / 확인 방법), em dash 없음
- 「4. 남은 한계」 번호는 모든 문서가 같다. `TODO.md`가 「각 문서 4절」을 가리킨다
- 그때의 명령 · 출력은 역사 기록이라 그대로 두고, 「지금」을 말하는 문장만 실제에 맞췄다

## 3. 진행 기록

### 3-1. 합친 것

- **01_cluster.md**: 있던 지금 구성 · 버전 · 프로비저너 · 워커 추가 · 메모리 절차는 그대로 두고, 노션의 KVM/libvirt 개념, 왜 VM 여러 대, 네트워크 대역 · Pod CIDR을 정한 까닭, 1~5단계 설치 명령 · 출력, Vagrantfile · setup-node.sh 처음 판 해설과 지금 판과 다른 곳, 버전 스큐, Calico 설명, 트러블슈팅(swap 재활성, kubeconfig, 메모리 4GB)을 더했다
- **08_scale_out.md**: 있던 배치 · 정비 절차 · 실행 기록은 그대로 두고, 노션의 사전 정리(무엇이 문제였나), 설계 결정(역할별 노드, 수동 승격), 12-1~12-8단계, 트러블슈팅 다섯(꺼진 직후의 Ready, 메모리 4GB, ingress-nginx 12초, existingClaim, binlog 위치)을 더했다
- **03_cloudflare_tunnel.md**: 옛 Cloudflare 두 쪽에서 도메인 구매, cloudflared 설치 · 로그인, ollama-tunnel · systemd, Access Service Token, `route dns` 함정, https · noTLSVerify · httpHostHeader, Host 헤더 403, 301, Secret 이야기를 합쳤다

### 3-2. 실제와 달라서 고친 것

| 문서 | 적혀 있던 것 | 실제(2026-11-12) | 근거 |
| --- | --- | --- | --- |
| 00 | NVIDIA 드라이버 595.91.07, `nvidia-driver-595` | 595.99.02, `nvidia-driver-595-open` | `nvidia-smi`, `dpkg -l` |
| 00 | `/opt/lora/<계정>` 있음 | 없음 | `ls /opt` |
| 00 | Ollama `-p 11434:11434`, `/opt/models:ro`, 모델 하나 | 127.0.0.1 · 172.17.0.1 · 192.168.122.1에만, `/opt/models` RW, 모델 20개 | `docker inspect ollama`, `ollama list` |
| 00 | Open WebUI `-p 3000:8080` | 127.0.0.1:3000만 | `docker inspect openwebui` |
| 00 | 호스트 Docker는 ollama · openwebui | milvus · etcd · nvidia-gpu-exporter · mysql 셋 더 | `docker ps` |
| 00 | systemd는 VNC · Jupyter | cloudflared-ollama · model-service · petmint-search · nfs-server 더 | `systemctl list-units` |
| 00 | VNC 설정 `~/.vnc/config` | `~/.config/tigervnc/config` | `ls`, `cat` |
| kubernetes_install · 03 · 07 · cloudflared README | 터널 호스트 다섯 | 일곱(grafana · prometheus, 2026-11-11) | `apps/cloudflared/configmap.yaml`, 클러스터 ConfigMap |
| kubernetes_install · 03 | runshoes-tunnel 프로세스만 멈춤 | systemd 유닛 · `~/.cloudflared-runshoes` 없음, 터널도 `cloudflared tunnel list`에 없음 | 호스트 조회 |
| 01 | eth0 = libvirt 기본망 | `vagrant-libvirt` 망(virbr1). `default`(virbr0)는 122.0/24 | `virsh net-dumpxml` |
| 01 · 04 | 루트 62GB(4대) | w3만 92GB, 나머지 62GB | 노드 `df -h /` |
| 02 | metrics-server latest | v0.9.0, `--kubelet-insecure-tls` | 클러스터 Deployment |
| 02 | 인증서 셋(ArgoCD · Harbor · Jenkins) | 다섯(grafana-tls · prometheus-tls 더함) | `kubectl get certificate -A` |
| 02 | ingress-nginx 1개 | 2개, 메트릭 켬 | `platform/ingress-nginx/overlay/` |
| 04 · 07 | petmint 수동 Sync | 자동(2026-11-11~) | `apps/petmint/app.yaml`, Application syncPolicy |
| 04 · 07 | Application 다섯 | 여섯(monitoring) | `kubectl get applications` |
| 04 | Ingress 차이 「두 가지」 | 세 가지 | `platform/argocd/ingress.yaml` |
| 04 · 06 | 공개 주소 curl이 200 · 403 | Access에 막혀 302, VIP로는 200 | curl |
| 05 | Harbor PVC가 w1 · w2 · w3에 흩어짐 | 쓰는 것은 `harbor-*-w3` 다섯(w3, Retain). 옛 다섯은 남아 있음 | PVC · PV 조회, `platform/harbor/pvc-w3.yaml` |
| 05 | values에 existingClaim · nodeSelector 없음 | 있다(다섯 · 여덟 곳) | `platform/harbor/values.yaml` |
| 06 | 초기 비밀번호 Secret `jenkins` | admin은 Secret `jenkins-admin`(existingSecret) | values · Secret 이름 |
| 06 | 저장소 트리(monitoring 자리만) | 지금 트리 | `ls` |
| 07 | 롤링 maxSurge 1 · maxUnavailable 0 | 0 · 1(2026-11-10) | `apps/*/app/deployment.yaml` |
| 07 | MySQL 하나씩 | Primary(w1) + Replica(w2), Secret `mysql-repl` | StatefulSet 조회 |
| 08 | 커밋 해시 일곱(`d5bf708` 등) | main에서 닿지 않음(메시지를 다시 쓰기 전 해시). main 해시 `2570d50` · `862182f` · `1643ddc` · `84e884b` · `7bff1b6` · `db091cb` · `bb8b759`로 바꿈 | `git merge-base --is-ancestor` |
| 08 · 09 | GPU exporter 안 띄움 | 2026-11-11부터 돈다, Prometheus nvidia-gpu up | `docker ps`, Prometheus `up` |
| 09 | Sync 수동, 노출 ClusterIP, Grafana 바깥 주소 없음 | 자동, grafana · prometheus.ronanlab.dev | `apps/monitoring/app.yaml` · `ingress.yaml` |
| 09 | 거절률 · 검색 지연 · Milvus 데이터 없음 | 2026-11-11에 연결됨 | Prometheus `up`, `gen_petmint.py` |
| runbooks/mysql-replica.md | petmint 수동 Sync | 자동 | `apps/petmint/app.yaml` |
| apps/runshoes/README.md | 2분 폴링, 새 Pod 먼저, Application은 kubectl apply | 웹훅 + 15분 폴링, 0/1 롤링, App of Apps | `platform/jenkins/values.yaml`, deployment, `bootstrap/root-app.yaml` |

## 4. 남은 한계

판단하지 못해 고치지 않은 것.

- 공유기 설정(192.168.0.17 · 포트포워딩 5001 → 22)은 볼 수 없어 노션 그대로다(00)
- CUDA 13.0의 설치 방법을 모른다. `/usr/local/cuda-13.0`은 있으나 dpkg · apt에 흔적이 없다(00)
- Ollama `/opt/models`가 RW로 붙은 것이 의도인지, 호스트 컨테이너 `mysql`(127.0.0.1:3306)의 용도, kopo02의 VNC · 포트 규칙이 지금도 쓰이는지 기록이 없다(00)
- MetalLB · cert-manager를 넣은 helm 저장소 · 명령이 저장소에도 백업에도 없다(02)
- `kubectl diff -k`를 칠 자리: m-k8s에는 이 저장소가 없다(02)
- `harborAdminPassword`가 저장소 values에는 없고 배포된 릴리스 값에만 있다. 다음 `helm upgrade` 때 넣는 법이 정해지지 않았다(05)
- 알림 설정(argocd-notifications-cm) · 웹훅 시크릿이 클러스터에만 있다(04)
- `platform/harbor/values.yaml` registry `size: 20Gi`: 실제 PVC는 existingClaim `harbor-registry-w3` 30Gi다. 설정 값이라 손대지 않았다(existingClaim이 있으면 차트가 이 값을 쓰지 않는 것으로 보이나 확인하지 않음)

### 4-1. 같은 날 뒤이어 고친 것(사용자 지시)

주석도 다음 사람이 믿고 판단하는 글이라 실제와 맞췄다. 바꾼 줄은 모두 주석 · README이고 설정 값은 그대로다(`git diff`에서 주석 아닌 줄 0).

| 파일 | 적혀 있던 것 | 실제(2026-11-12 다시 확인) |
| --- | --- | --- |
| `platform/harbor/pvc-w3.yaml` | reclaimPolicy Delete, PVC를 지우면 데이터도 지워진다 | PV 다섯 모두 Retain(StorageClass 기본만 Delete) |
| `platform/metallb/pool.yaml` | 노드 고정 IP .10–.13 | .10–.14(w4) |
| `apps/cloudflared/app.yaml` · `kustomization.yaml` | 공개 주소 다섯 | 일곱 |
| `apps/runshoes/app/deployment.yaml` | maxSurge 1 · maxUnavailable 0 | 0 · 1 |
| `apps/monitoring/prometheus/statefulset.yaml` | 보존 7일, PVC 5Gi | 15일(또는 9GB), 10Gi |
| `apps/harbor-backup/cronjob.yaml` · `README.md` | 레이어 PVC `harbor-registry` 20Gi | `harbor-registry-w3` 30Gi |
| `apps/monitoring/README.md` | 거절률 · 검색 지연 없음, GPU 띄우기 전, 자원 표에 Loki · json-exporter · Alloy 없음 · node-exporter ×4, PVC 5Gi · 7일 | 2026-11-11 연결(`ba7bd28`), GPU exporter 2026-11-11 09:22부터, 표를 지금 매니페스트로, 10Gi · 15일 · 9GB |
- Cloudflare Access 칸은 저장소 주석 · 펫퍼민트 docs 13을 옮긴 것이고 대시보드는 보지 않았다(03)

## 5. 확인 방법

```bash
cd ~/ronanlab-infra/docs
grep -cP '\x{2014}' 0*.md kubernetes_install.md history/*.md   # em dash, 모두 0
for f in 0*.md kubernetes_install.md; do grep -c '^## [1-5]\. ' $f; done   # 모두 5
```
