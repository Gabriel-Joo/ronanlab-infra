# 인프라/서버 구축(하드웨어)

물리 GPU 서버 한 대(kopo17-System-Product-Name, RTX 5070 Ti 16GB)에 Ubuntu · NVIDIA 드라이버 · CUDA · 원격 접속(SSH · VNC · Jupyter) · Docker(Ollama · Open WebUI)를 올리고 헤드리스로 운영한다.
처음에는 두 계정(kopo17 · kopo02)이 베이스 모델과 GPU를 같이 쓰는 LoRA 실습 서버로 설계했고, 지금은 그 위에 쿠버네티스 VM · 앱용 호스트 서비스도 돈다.

- 날짜: 2026-09 구축(노션 마지막 수정 2026-10-06), 2026-11-12 호스트와 맞춤
- 범위: 물리 서버의 네트워크 · OS · 드라이버 · 원격 접속 · Docker · GPU 운영 규칙. 이 서버 위에 KVM/Vagrant로 올린 쿠버네티스 VM은 [kubernetes_install.md](kubernetes_install.md) · [01_cluster.md](01_cluster.md)
- 코드: 저장소 밖(호스트 설정). systemd 유닛 `/etc/systemd/system/tigervncserver@.service` · `/etc/systemd/system/jupyter-kopo17.service`, VNC 설정 `~/.config/tigervnc/`

## 1. 지금 구성

2026-11-12 호스트에서 읽기만 하는 명령으로 본 값이다(공유기 설정은 볼 수 없어 노션 값 그대로 둔다).

### 1-1. 서버 기본 환경

| 항목 | 값 |
| --- | --- |
| 호스트 이름 | kopo17-System-Product-Name (물리 서버) |
| OS | Ubuntu 26.04.1 LTS (resolute), 커널 7.0.0-42-generic |
| CPU · RAM | 32코어 · 61GB (2026-11-12 09:18 사용 35GB, available 25GB) |
| GPU | NVIDIA GeForce RTX 5070 Ti, 16GB VRAM (16303 MiB) |
| NVIDIA 드라이버 | 595.99.02 (패키지 `nvidia-driver-595-open` 595.99.02-0ubuntu0.26.04.1) |
| CUDA Toolkit | 13.0 (nvcc release 13.0, V13.0.48), `/usr/local/cuda` → `/usr/local/cuda-13.0` |
| Python | 3.14.4 |
| venv | `~/llm_env`, PyTorch 2.14.0+cu130, `torch.cuda.is_available()` True |
| Docker | 29.8.0 (`docker-ce`), NVIDIA Container Toolkit 1.20.0 |
| TigerVNC | 1.15.0 (`tigervnc-standalone-server`) |
| 계정 | kopo17(서버 관리자), kopo02(`/home/kopo02` 있음) |
| 가상화 | qemu-system-x86 10.2.1 · libvirt-daemon-system 12.0.0, Vagrant 2.4.9 + vagrant-libvirt 0.12.2 |

### 1-2. 네트워크 (공유기, 노션 값 그대로)

```
[인터넷] → [공유기 1대] → [스위치 2~3대로 분기] → [서버 PC 10대]
```

| 항목 | 값 |
| --- | --- |
| 서버 PC 내부 IP (고정) | `192.168.0.17` |
| 공유기 자체 IP | `192.168.23.18` |
| 공유기 관리자 페이지 (접속 주소) | `192.168.0.1` |

**공유기 포트포워딩 규칙**

| 외부 포트 (External) | 내부 IP | 내부 포트 (Internal) | 프로토콜 |
| --- | --- | --- | --- |
| 5001 | 192.168.0.17 | 22 (SSH 기본 포트) | TCP |

교실 PC에서 공유기의 외부 IP + 포트 5001로 접속하면 서버의 SSH(22번)로 연결된다. 개별 서비스(Jupyter, VNC 등)는 이 SSH 연결 안에서 PuTTY 터널로 더한 것이라, 공유기 포트포워딩과는 별개다(1-4절).

### 1-3. 디렉터리

`/opt/` (2026-11-12 `ls /opt`)

```
/opt/
  models/
    unsloth/DeepSeek-R1-Distill-Qwen-14B-GGUF/
      DeepSeek-R1-Distill-Qwen-14B-Q3_K_M.gguf   (공유 베이스 모델, 7,339,203,744 바이트)
  shared/
    gpu.lock                                     (GPU 사용 순서 관리용 락 파일, 권한 666)
  LM-Studio/  containerd/  innorix-ex/  vagrant/
```

`/opt/lora/`는 없다(3절 「이후 바뀐 것」).

계정별 개인 환경(`/home/kopo17/`):

```
~/llm_env/                    (Python venv)
~/AI_programming/
  configs/  data/  scripts/  notebooks/
  checkpoints/  lora_adapters/  logs/  vectorstore/  neo4j_data/
  petmint-rag-chatbot/  runshoes/  model-service/  foreman/   (프로젝트 저장소)
```

`/home/kopo02/`는 권한이 없어 안을 보지 않았다.

### 1-4. 원격 접속

| 용도 | 서버 쪽 | 자동 시작 | PuTTY Source Port → Destination |
| --- | --- | --- | --- |
| SSH | `ssh.service` (OpenSSH 10.2p1), 22 | 시스템 서비스 | 공유기 5001 → 22 |
| Jupyter Lab | `jupyter-kopo17.service`, 5002 | systemd | 5002 → `localhost:5002` |
| VNC | `tigervncserver@2.service`, 디스플레이 `:2` = 포트 5902 | systemd | 5034 → `localhost:5902` |
| Ollama API | 컨테이너 `ollama`, 11434 | `--restart unless-stopped` | 5012 → `localhost:11434` |
| Open WebUI | 컨테이너 `openwebui`, 127.0.0.1:3000 | `--restart unless-stopped` | 5014 → `localhost:3000` |

- VNC: `Xtigervnc :2 -localhost=0 ... -rfbport 5902`. 외부 접속 허용은 `~/.config/tigervnc/config`의 `localhost=0` 한 줄. xstartup은 `~/.config/tigervnc/xstartup`(Xfce, 3절 5-2)
- 기본 터미널: `x-terminal-emulator` = `/usr/bin/xfce4-terminal.wrapper`
- PuTTY 쪽 설정은 교실 PC에 있어 2026-11-12에 다시 보지 않았다

### 1-5. Docker 컨테이너

| 컨테이너 | 이미지 | 포트 | 비고 |
| --- | --- | --- | --- |
| `ollama` | `ollama/ollama:latest` | 127.0.0.1 · 172.17.0.1 · 192.168.122.1 의 11434 | `--gpus all`, `/opt/models` → `/opt/models` 바인드(지금 읽기 쓰기), 볼륨 `ollama_data` → `/root/.ollama`, `unless-stopped` |
| `openwebui` | `ghcr.io/open-webui/open-webui:main` | 127.0.0.1:3000 → 8080 | `OLLAMA_BASE_URL=http://host.docker.internal:11434`, `host.docker.internal:host-gateway`, 볼륨 `openwebui_data`, `unless-stopped` |
| `milvus-standalone` | `milvusdb/milvus:v3.0.2` | 127.0.0.1 · 192.168.122.1 의 9091 · 19530 | 펫퍼민트 벡터 DB |
| `milvus-etcd` | `quay.io/coreos/etcd:v3.5.33` | 내부만 | Milvus 메타데이터 |
| `nvidia-gpu-exporter` | `utkuozdemir/nvidia_gpu_exporter:1.3.1` | 192.168.122.1:9835 | 클러스터 Prometheus가 긁는다([09_monitoring.md](09_monitoring.md)) |
| `mysql` | `mysql:8.0.46` | 127.0.0.1:3306 | 용도 기록 없음(4절) |
| `runshoes-mysql-dev` | `mysql:8.0.46` | 127.0.0.1:3307 | 런슈즈 개발용(compose 위치 `~/AI_programming/runshoes/.worktrees/runshoes-3`, `docker-compose.yml`) |
| `foreman-mysql` | `mysql:8.0.46` | 127.0.0.1:3308 | FOREMAN DB(compose 위치 `~/AI_programming/foreman/deploy/mysql`) |

192.168.122.1은 libvirt 사설망에서 본 호스트 주소다. 쿠버네티스 Pod가 Ollama · Milvus를 이 주소로 부른다(`apps/petmint/app/configmap.yaml`, `apps/runshoes/app/deployment.yaml`).

Ollama 모델(`docker exec ollama ollama list`, 2026-11-12): 20개.

```
kabyul-tri-7b-rag1-rebuild5b-ckpt250:latest                   4.6 GB
kabyul-tri-7b-rag1-rebuild5-ckpt250:latest                    4.6 GB
kabyul-tri-7b-rag1-rebuild4-ckpt462:latest                    4.6 GB
hf.co/mykor/A.X-4.0-Light-gguf:Q4_K_M                         4.4 GB
hf.co/mradermacher/kanana-1.5-8b-instruct-2505-GGUF:Q4_K_M    4.9 GB
gemma4:12b                                                    8.0 GB
qwen3:14b                                                     9.3 GB
tri-7b:latest                                                 4.6 GB
kabyul-insurance-chatbot-q4:latest                            4.8 GB
bge-m3:latest                                                 1.2 GB
kabyul-exaone-restaurant-f16:latest                           2.6 GB
kabyul-exaone-restaurant-q4:latest                            812 MB
kabyul-exaone-nsmc-f16:latest                                 2.6 GB
kabyul-exaone-nsmc-q4:latest                                  812 MB
qwen2.5:7b                                                    4.7 GB
exaone3.5:7.8b                                                4.8 GB
llama3.1:8b                                                   4.9 GB
gemma4:e4b                                                    9.6 GB
qwen3:8b                                                      5.2 GB
deepseek-r1-14b:latest                                        7.3 GB
```

### 1-6. systemd 서비스

| 서비스 | 상태 | 하는 일 |
| --- | --- | --- |
| `tigervncserver@2.service` | enabled(indirect) · running | VNC `:2` |
| `jupyter-kopo17.service` | enabled · running | Jupyter Lab 5002 |
| `docker.service` · `containerd.service` | running | 컨테이너(1-5절) |
| `ssh.service` | running | SSH |
| `cloudflared-ollama.service` | enabled · running | `ollama-tunnel`, `ollama.ronanlab.dev` → `http://localhost:11434`(설정 `~/.cloudflared/config.yml`, User kopo17). 학교 PC 전용([kubernetes_install.md](kubernetes_install.md) 「기존 Cloudflare Tunnel 자산」) |
| `model-service.service` | enabled · running | KURE-v1 + bge-reranker-v2-m3, 192.168.122.1:8200, GPU 사용 |
| `petmint-search.service` | enabled · running | 펫퍼민트 search-service(BM25 + Milvus), 192.168.122.1:8100 |
| `nfs-server.service` | active(exited) | NFS(1-7절) |
| `libvirtd.service` · `libvirt-guests.service` | running | 쿠버네티스 VM 5대([01_cluster.md](01_cluster.md)) |

model-service · petmint-search의 자세한 것은 펫퍼민트 저장소 `~/AI_programming/petmint-rag-chatbot/docs/02_pipeline/14_deployment.md` 「1-1. 무엇을 컨테이너로 만드는가」 · 「1-26. 검색 모델을 공용 model-service로」.

### 1-7. NFS

`/etc/exports`는 주석만 있고, 실제 내보내기는 `/etc/exports.d/`(`petmint.exports` · `petmint-backup.exports` · `harbor-backup.exports`)에 있다. 모두 `192.168.122.0/24`(VM 사설망)에만 연다.

| 경로 | 권한 | 쓰는 곳 |
| --- | --- | --- |
| `/srv/nfs/petmint/chunks` · `graph` · `fixtures` | ro | 펫퍼민트 약관 볼륨(PV `petmint-chunks` · `petmint-graph` · `petmint-fixtures`) |
| `/srv/nfs/backup/petmint` | rw | 펫퍼민트 MySQL 백업(PV `petmint-backup`) |
| `/srv/nfs/backup/harbor` | rw | Harbor DB 백업(PV `harbor-backup`) |

### 1-8. 이 서버 위에 올린 것

KVM/libvirt + Vagrant로 쿠버네티스 VM 5대(합 36GB)를 올렸다. 구성과 까닭은 [kubernetes_install.md](kubernetes_install.md), VM · 버전 · 네트워크는 [01_cluster.md](01_cluster.md).

## 2. 왜 이렇게 했나

### 2-1. 스위치로 나누고 서버마다 고정 IP

공유기 1대의 LAN 포트만으로는 서버 PC 10대를 전부 연결할 수 없어, 스위치 2~3대를 공유기 밑에 연결하고 각 서버 PC를 스위치에 나눠 연결했다.
이 구성에서는 서버마다 **고정 IP**가 꼭 있어야 했다. DHCP로 두면 PC가 재부팅될 때마다 IP가 바뀔 수 있는데, 포트포워딩 규칙(외부 포트 → 내부 IP:내부 포트)은 특정 IP를 고정으로 가리키므로 IP가 바뀌면 포트포워딩 규칙 전체가 깨진다. 그래서 각 서버 PC에 고정 IP를 주어, 포트포워딩 규칙이 항상 같은 PC를 가리키도록 했다.

이 10대 중 내가 실제로 관리 · 사용한 것은 1대(물리 서버, RTX 5070 Ti)다. 원래는 2인(kopo17 = 나, kopo02)이 함께 쓰는 구조로 설계해, 공유 자원(베이스 모델, GPU)과 개인 자원(LoRA 결과물, venv)을 나누는 운영 체계까지 설계했다. 실제로는 결국 혼자 쓰게 됐고, 아래 설계는 당시 기준으로 둔다.

### 2-2. 공유 GPU 서버 LoRA 실습 환경 (당시 설계)

- **목적**: 베이스 모델 하나를 공유하고, 각자 LoRA 어댑터를 학습 · 교체해가며 실습
- **포트 규칙**: kopo17 = `5001~5500`, kopo02 = `5501~5999` (합의된 범위 안에서 각자 사용)
- **핵심 설계 원칙**: 무거운 자원(베이스 모델, GPU)은 공유, 개인 결과물(LoRA 어댑터, venv)은 분리. GUI 앱 중 「동시 실행이 막히는」 것(LM Studio)은 빼고, API 서버 기반(Ollama)으로 바꿔 다중 사용자 문제를 풀었다

당시 아키텍처(2026-09, 드라이버는 그때 값):

```
[교육 PC] --SSH+포트포워딩--> [서버: kopo17-System-Product-Name]
    GPU: RTX 5070 Ti (16GB VRAM), Driver 595.91.07
    CUDA Toolkit 13.0
    (계정별) Python venv + PyTorch  → LoRA 학습용
    (계정별) Jupyter Lab           → 실습/실험용
    (계정별) VNC(Xfce) 데스크톱     → GUI 필요 작업용
    Docker
      - Ollama 컨테이너   (모델 추론 서버, API)
      - Open WebUI 컨테이너 (채팅 GUI, 다중 사용자)
```

### 2-3. 공유 디렉터리 설계 이유

모델 파일은 계정마다 복사하지 않고 `/opt/models/`에 1개만 둔다(용량 절약). LoRA 어댑터는 계정별 폴더로 완전히 나눠 서로의 실험 결과를 덮어쓰지 않게 했다(당시 `/opt/lora/<계정>/`, 지금은 없다).

### 2-4. 헤드리스 운영

설치 직후에는 모니터 · 키보드를 서버에 직결해 작업했으나, VNC(TigerVNC)를 연결한 뒤로는 모니터 · 키보드를 완전히 빼고 헤드리스로 운영한다. 교실 PC에서 SSH + VNC로만 접속해서 관리한다.

### 2-5. 왜 LM Studio 대신 Ollama + Open WebUI인가

|  | LM Studio | Ollama + Open WebUI |
| --- | --- | --- |
| 실행 방식 | GUI 앱, 단일 인스턴스만 실행 가능(계정/세션 달라도 서버 전체 1개 제한) | 백그라운드 API 서버 |
| 동시 사용 | 한 명 실행 중이면 다른 사람 실행 자체가 막힘 | 여러 명 동시 접속 가능 |
| Linux GUI | 지원 | Ollama 자체엔 없음, Open WebUI로 대체 |

**실제 재현된 문제**: kopo02가 LM Studio를 실행 중인 상태에서 kopo17이 실행하려 하자 `LM Studio and LM Studio currently cannot run at the same time` 에러가 났다. GUI 창 유무와 무관하게 LM Studio 내부 추론 엔진 자체가 시스템 전체에서 하나만 실행되도록 잠겨 있어, 헤드리스(CLI) API 서버로 띄워도 똑같이 막힌다. 우리가 만든 GPU 락(2-6절)은 우리 학습 스크립트에만 적용할 수 있어, 상용 프로그램 내부 잠금은 우회할 수 없었다.

### 2-6. GPU 동시 사용 제약과 운영 규칙

물리적 한계: VRAM 16GB, 모델 약 7.3GB. 추론은 여유가 있으나 LoRA 학습(파인튜닝)은 동시에 돌리면 OOM 가능성이 높다. 컨테이너 · venv를 아무리 나눠도 GPU 자체가 하나라 무거운 연산 두 개를 동시에 돌리면 물리적으로 부딪힌다.

운영 규칙: 데이터 준비 · 코드 작성 · 디버깅은 동시에 각자 진행할 수 있고(GPU 미사용), 실제 학습 실행(GPU 점유 구간)만 순서를 조율한다. 터미널 명령 앞에 붙이는 `flock` 방식은 Jupyter의 「셀 단위 Run」 작업 방식과 맞지 않아, 파이썬 코드 안에서 `fcntl.flock`으로 자동 순서 관리하는 방식을 썼다.

```py
import fcntl

lock_file = open('/opt/shared/gpu.lock', 'w')
fcntl.flock(lock_file, fcntl.LOCK_EX)
print("GPU 락 획득, 학습 시작")

model.train()

fcntl.flock(lock_file, fcntl.LOCK_UN)
lock_file.close()
print("GPU 락 해제")
```

동작: kopo17이 셀을 Run하면 즉시 락을 잡고 시작한다. 거의 동시에 kopo02가 같은 방식의 셀을 Run하면 멈춘 것처럼 보이지만 정상이다. kopo17 것이 끝나 `LOCK_UN` 되는 순간 자동으로 이어서 실행된다. 자리가 멀어 실시간 조율이 어려운 상황에서, 동시에 GPU에 올라가 터지는 것을 코드 수준에서 자동으로 막았다.

### 2-7. 컨테이너를 상시 실행해도 VRAM은 낭비되지 않는다

`--restart unless-stopped`로 항상 떠 있지만, GPU(VRAM)는 요청이 들어올 때만 모델을 올리고 마지막 요청 뒤 약 5분(`OLLAMA_KEEP_ALIVE` 기본값)이 지나면 자동으로 내린다. 당시 `nvidia-smi`로 유휴 시 Memory-Usage가 거의 0에 가까운 것을 확인했다(지금은 model-service가 VRAM을 상시 쓴다, 4절).

## 3. 진행 기록

### 3-1. 서버 설치: USB 설치 → 헤드리스 전환

처음에는 Ubuntu 설치 이미지를 USB로 구워 서버 PC에 직접 설치했다(설치가 끝난 뒤에는 USB 없이 내장 디스크로 정상 부팅). 설치 직후에는 모니터 · 키보드를 직결해 작업했고, VNC를 연결한 뒤 헤드리스로 바꿨다(2-4절).

### 3-2. 0단계: 서버 최초 SSH · 네트워크 설정 (1회만)

#### 0-1. 서버 PC(Ubuntu): SSH 서버 설치 및 방화벽 설정

```bash
sudo apt update && sudo apt upgrade -y

sudo apt install -y openssh-server
sudo systemctl enable --now ssh
sudo ufw allow 22/tcp
sudo ufw reload
```

#### 0-2. 네트워크 & 포트포워딩 (공유기 설정)

값은 1-2절 표.

#### 0-3. 교실 PC(Client)에서 PuTTY로 최초 접속

PuTTY 설정: Host Name(공유기 외부 IP), Port 5001, Connection type SSH. 최초 1회 `PuTTY Security Alert` 팝업 → Accept → 계정 로그인.

#### 0-4. NVIDIA 드라이버 설치

```bash
ubuntu-drivers devices
sudo apt install -y nvidia-driver-595
```

`sudo ubuntu-drivers autoinstall`(자동 추천)은 실패해서, 목록을 직접 확인하고 특정 버전을 지정해 설치했다. 당시 드라이버 595.91.07. 지금 설치된 패키지는 `nvidia-driver-595-open`이다(3절 「이후 바뀐 것」).

확인: `nvidia-smi`

#### 트러블슈팅: MOK(Secure Boot) 등록 화면

**증상**: 드라이버 설치 · 재부팅 때 파란 콘솔 화면(MOK Management)이 뜬다.

**원인**: Secure Boot가 켜진 시스템에서는 NVIDIA 커널 모듈이 서명되지 않아, 이 등록 절차 없이는 드라이버가 로드되지 않는다.

**해결**:

1. 설치 중 임시 암호 설정
2. 재부팅 후 MOK Management 화면에서 "Enroll MOK" → 암호 입력 → "Continue"
3. 재부팅 완료 후 정상 로드

### 3-3. 2단계: 서버 기본 환경 (CUDA · Python)

#### CUDA Toolkit 13.0 설치

```bash
wget https://developer.download.nvidia.com/compute/cuda/repos/ubuntu2604/x86_64/cuda-keyring_1.1-1_all.deb
sudo dpkg -i cuda-keyring_1.1-1_all.deb
sudo apt update
sudo apt install cuda-toolkit-13-0 -y
```

#### Python 3.14 설치

```bash
sudo apt update
sudo apt install python3 python3-venv python3-pip -y
python3 --version
```

#### CUDA 환경변수 (`~/.bashrc`, 계정별)

```bash
export PATH=/usr/local/cuda/bin:$PATH
export LD_LIBRARY_PATH=/usr/local/cuda/lib64:$LD_LIBRARY_PATH
```

확인: `nvcc --version`, `nvidia-smi`. 2026-11-12에도 kopo17의 `~/.bashrc` 118~119줄에 같은 두 줄이 있다.

### 3-4. 3단계: 공유 디렉터리 구조 (`/opt/`)

당시 만든 구조:

```
/opt/
  models/
    unsloth/DeepSeek-R1-Distill-Qwen-14B-GGUF/
      DeepSeek-R1-Distill-Qwen-14B-Q3_K_M.gguf   (공유 베이스 모델, 약 7.3GB)
  lora/                                (계정별 LoRA 결과물, 분리 저장)
    kopo17/adapters,checkpoints,logs
    kopo02/adapters,checkpoints,logs
  shared/
    gpu.lock                           (GPU 사용 순서 관리용 락 파일)
```

```bash
sudo mkdir -p /opt/models
sudo mkdir -p /opt/lora/kopo17/{adapters,checkpoints,logs}
sudo mkdir -p /opt/lora/kopo02/{adapters,checkpoints,logs}
sudo mkdir -p /opt/shared
sudo chmod -R 775 /opt/models /opt/lora /opt/shared
sudo touch /opt/shared/gpu.lock
sudo chmod 666 /opt/shared/gpu.lock
```

### 3-5. 4단계: 계정별 개인 환경 (`/home/{kopo17,kopo02}/`)

```
~/llm_env/                    (Python venv, 계정별 독립 환경)
~/AI_programming/
  configs/base_config.yaml
  data/
  scripts/
  notebooks/
```

```bash
mkdir -p ~/AI_programming/{configs,data,scripts,notebooks}
python3 -m venv ~/llm_env
source ~/llm_env/bin/activate
pip install --upgrade pip
pip install torch --index-url https://download.pytorch.org/whl/cu130
pip install transformers peft bitsandbytes accelerate jupyterlab
```

GPU 인식 확인:

```bash
python3 -c "import torch; print(torch.__version__); print(torch.cuda.is_available()); print(torch.cuda.get_device_name(0))"
```

→ `2.14.0+cu130 / True / NVIDIA GeForce RTX 5070 Ti`

### 3-6. 5단계: 원격 접속 세팅

#### 5-1. SSH + 포트포워딩 (PuTTY)

| 용도 | Source Port | Destination |
| --- | --- | --- |
| Jupyter Lab | 5002 | `localhost:5002` |
| Ollama API | 5012 | `localhost:11434` |
| VNC | 5034 | `localhost:5902` |
| Open WebUI | 5014 | `localhost:3000` |

#### 5-2. VNC 원격 데스크톱 (TigerVNC + UltraVNC Viewer)

```bash
sudo apt install tigervnc-standalone-server tigervnc-common -y
tigervncpasswd
```

xstartup(`~/.config/tigervnc/xstartup`):

```bash
#!/bin/sh
unset SESSION_MANAGER DBUS_SESSION_BUS_ADDRESS WAYLAND_DISPLAY
export XDG_SESSION_TYPE=x11 GDK_BACKEND=x11 QT_QPA_PLATFORM=xcb
export LIBGL_ALWAYS_SOFTWARE=1 GALLIUM_DRIVER=llvmpipe
dbus-launch --exit-with-session startxfce4
```

(지금 파일은 같은 내용을 `unset` · `export` 한 줄에 하나씩 쓴 꼴이다.)

외부 접속 허용(노션 기록): `echo "localhost=0" > ~/.vnc/config`. 지금은 `~/.vnc/`가 없고 같은 한 줄이 `~/.config/tigervnc/config`에 있다.

디스플레이 배정: 서버 GNOME(Wayland)이 `:0`, `:1`을 차지해 충돌 → kopo17 = `:2`(포트 5902), kopo02 = `:3`(포트 5903)

```bash
tigervncserver :2 -geometry 1920x1080 -depth 24
```

기본 터미널 변경(Ptyxis 오류 회피): `sudo update-alternatives --config x-terminal-emulator` → `xfce4-terminal.wrapper` 선택

#### 5-3. Jupyter Lab

```bash
source ~/llm_env/bin/activate
jupyter lab password
nohup jupyter lab --no-browser --port=5002 > ~/jupyter.log 2>&1 &
```

### 3-7. 6단계: Docker + GPU 컨테이너 환경

#### 6-1. Docker 설치

```bash
curl -fsSL https://get.docker.com | sudo sh
sudo usermod -aG docker kopo17
sudo usermod -aG docker kopo02
```

#### 트러블슈팅: Docker 그룹이 반영되지 않음

**증상**: 그룹 추가 뒤 재로그인해도 `docker` 명령이 권한 오류를 낸다.

**원인**: 그룹 변경이 지금 세션에 바로 반영되지 않는 경우가 있었다.

**해결**: 서버 재부팅으로 해결했다. 그 전까지는 `sg docker -c "docker ..."` 또는 `sudo docker ...`로 우회했다.

#### 6-2. NVIDIA Container Toolkit

```bash
curl -fsSL https://nvidia.github.io/libnvidia-container/gpgkey | sudo gpg --dearmor -o /usr/share/keyrings/nvidia-container-toolkit-keyring.gpg
curl -s -L https://nvidia.github.io/libnvidia-container/stable/deb/nvidia-container-toolkit.list | sed 's#deb https://#deb [signed-by=/usr/share/keyrings/nvidia-container-toolkit-keyring.gpg] https://#g' | sudo tee /etc/apt/sources.list.d/nvidia-container-toolkit.list
sudo apt update && sudo apt install -y nvidia-container-toolkit
sudo nvidia-ctk runtime configure --runtime=docker
sudo systemctl restart docker
```

확인: `docker run --rm --gpus all nvidia/cuda:13.0.0-base-ubuntu24.04 nvidia-smi`

#### 6-3. Ollama 컨테이너

```bash
docker run -d --gpus all -v /opt/models:/opt/models:ro -v ollama_data:/root/.ollama -p 11434:11434 --name ollama --restart unless-stopped ollama/ollama
```

기존 GGUF 모델 등록(Modelfile):

```bash
cat > ~/Modelfile << 'EOF'
FROM /opt/models/unsloth/DeepSeek-R1-Distill-Qwen-14B-GGUF/DeepSeek-R1-Distill-Qwen-14B-Q3_K_M.gguf
EOF
docker cp ~/Modelfile ollama:/tmp/Modelfile
docker exec ollama ollama create deepseek-r1-14b -f /tmp/Modelfile
```

테스트: `docker exec ollama ollama run deepseek-r1-14b "hello"` → GPU 로그 `library=CUDA`, 약 88 tokens/sec 확인.

지금 컨테이너의 포트 · 마운트는 이 명령과 다르다(3-10절).

#### 6-4. Open WebUI 컨테이너

```bash
docker run -d -p 3000:8080 --add-host=host.docker.internal:host-gateway -e OLLAMA_BASE_URL=http://host.docker.internal:11434 -v openwebui_data:/app/backend/data --name openwebui --restart unless-stopped ghcr.io/open-webui/open-webui:main
```

최초 접속자가 관리자 계정을 만들고, 이후 각자 별도 계정으로 로그인한다(대화 기록은 개인별 분리, 모델 · GPU는 공유).

### 3-8. 9단계: systemd 자동 시작 (재부팅 시 VNC · Jupyter 자동 실행)

| 서비스 | 자동 시작 | 방식 |
| --- | --- | --- |
| VNC | 적용됨 | systemd 서비스 |
| Docker | 기본 자동 | 시스템 서비스 |
| Ollama 컨테이너 | 적용됨 | --restart unless-stopped |
| Open WebUI 컨테이너 | 적용됨 | --restart unless-stopped |
| Jupyter Lab | 적용됨 | systemd 서비스 |

#### VNC 자동 시작 (tigervncserver@.service)

```bash
sudo tee /etc/systemd/system/tigervncserver@.service << 'EOF'
[Unit]
Description=Remote desktop service (VNC) for kopo17
After=syslog.target network.target

[Service]
Type=forking
User=kopo17
Group=kopo17
WorkingDirectory=/home/kopo17
Delegate=yes
PIDFile=/home/kopo17/.config/tigervnc/%H:%i.pid
ExecStartPre=-/usr/bin/tigervncserver -kill :%i > /dev/null 2>&1
ExecStart=/usr/bin/tigervncserver -depth 24 -geometry 1920x1080 :%i
ExecStop=/usr/bin/tigervncserver -kill :%i

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable tigervncserver@2.service
sudo systemctl start tigervncserver@2.service
```

2026-11-12 `systemctl cat tigervncserver@.service` 내용이 위와 같다.

#### 트러블슈팅: VNC 화면 안 터미널의 cgroup 오류

**증상**: VNC 화면 안에서 터미널(Ptyxis)을 실행하면 systemd cgroup 오류가 난다.

**원인**: 서비스로 띄운 VNC 세션이 systemd cgroup을 위임받지 못했다.

**해결**: 유닛에 `Delegate=yes`를 넣었다. 기본 터미널도 xfce4-terminal로 바꿨다(5-2).

#### Jupyter Lab 자동 시작 (jupyter-kopo17.service)

```bash
sudo tee /etc/systemd/system/jupyter-kopo17.service << 'EOF'
[Unit]
Description=Jupyter Lab for kopo17
After=network.target

[Service]
Type=simple
User=kopo17
WorkingDirectory=/home/kopo17
ExecStart=/home/kopo17/llm_env/bin/jupyter lab --no-browser --port=5002
Restart=on-failure

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable jupyter-kopo17.service
sudo systemctl start jupyter-kopo17.service
```

2026-11-12 `systemctl cat jupyter-kopo17.service` 내용이 위와 같다.

상태 확인 · 재시작: `systemctl status tigervncserver@2.service --no-pager`, `systemctl status jupyter-kopo17.service --no-pager`, `sudo systemctl restart <서비스명>`

### 3-9. 당시 완료 항목 체크리스트 (노션 기록)

- [x] NVIDIA 드라이버 595.91.07
- [x] CUDA Toolkit 13.0 + 환경변수
- [x] Python 3.14.4
- [x] `/opt/models/` 공유 베이스 모델 (DeepSeek-R1-Distill-Qwen-14B-Q3_K_M.gguf)
- [x] `/opt/lora/`, `/opt/shared/gpu.lock` 공유 디렉터리 구조
- [x] venv(`llm_env`) + PyTorch 2.14.0+cu130 (GPU 인식 확인)
- [x] Jupyter Lab (비밀번호 로그인, 포트포워딩)
- [x] `~/AI_programming/` 프로젝트 폴더 구조
- [x] TigerVNC + systemd 자동 시작, UltraVNC Viewer 접속 확인
- [x] Docker + NVIDIA Container Toolkit
- [x] Ollama 컨테이너 + 모델 등록, GPU 추론 확인 (88 tokens/sec)
- [x] Open WebUI 컨테이너, 다중 사용자 채팅 GUI 확인

이 인프라 위에서 처음 돌린 프로젝트: 펫보험 RAG 챗봇(Ollama로 Tri-7B 서빙, 00~06번 파이프라인. 펫퍼민트 저장소 `~/AI_programming/petmint-rag-chatbot/docs/02_pipeline/`).

### 3-10. 이후 바뀐 것 (2026-11-12 호스트를 보고 적음)

언제 바뀌었는지 기록이 없는 것은 「확인 날짜」만 적는다.

- **NVIDIA 드라이버**: 595.91.07 → 595.99.02. 패키지 이름은 `nvidia-driver-595-open`(노션 명령은 `nvidia-driver-595`)
- **`/opt/lora/` 없음**: `/opt`에는 `models` · `shared` 말고 `LM-Studio` · `containerd` · `innorix-ex` · `vagrant`가 있다. kopo17의 LoRA 관련 폴더는 `~/AI_programming/lora_adapters` · `checkpoints`에 있다
- **Ollama 포트**: `-p 11434:11434`(모든 주소) → 127.0.0.1 · 172.17.0.1(도커 브리지) · 192.168.122.1(VM 사설망) 세 주소에만 연다. 192.168.122.1은 쿠버네티스 Pod가 부르는 길이다
- **Ollama 모델 마운트**: 노션 명령은 `/opt/models:/opt/models:ro`인데 지금 컨테이너는 읽기 쓰기(`RW: true`)로 붙어 있다
- **Ollama 모델**: `deepseek-r1-14b` 하나에서 20개로(1-5절)
- **Open WebUI 포트**: `-p 3000:8080` → `127.0.0.1:3000`만
- **호스트 Docker 컨테이너 추가**: `milvus-standalone` · `milvus-etcd` · `nvidia-gpu-exporter` · `mysql` · `runshoes-mysql-dev` · `foreman-mysql`
- **systemd 추가**: `cloudflared-ollama`(학교 PC용 Ollama 터널), `model-service`(2026-11-11, GPU) · `petmint-search`(2026-11-02 유닛), `nfs-server`
- **가상화**: KVM/libvirt + Vagrant로 쿠버네티스 VM 5대([kubernetes_install.md](kubernetes_install.md))
- **VNC 설정 파일 자리**: `~/.vnc/config` → `~/.config/tigervnc/config`

## 4. 남은 한계

- **공유기 설정은 확인 못 함**: 고정 IP 192.168.0.17, 공유기 IP 192.168.23.18, 관리 페이지 192.168.0.1, 포트포워딩 5001 → 22는 2026-11-12에 볼 수 없어 노션 값 그대로다
- **CUDA를 어떻게 설치했는지 확인 못 함**: `/usr/local/cuda-13.0`과 nvcc 13.0이 있지만 `dpkg`에 cuda 패키지가 없고 `/etc/apt/sources.list.d/`에 CUDA 저장소 목록도 없다. 노션의 `cuda-keyring` + `apt install cuda-toolkit-13-0` 명령은 기록으로만 둔다
- **GPU는 하나다**: 지금은 Ollama(모델을 쓸 때만) 말고도 `model-service`가 KURE-v1 · bge-reranker를 상시 VRAM에 올린다. LoRA 학습을 돌리면 이 둘과 VRAM을 나눠 쓴다. `gpu.lock`은 우리 학습 코드만 지킨다
- **호스트 메모리**: 61GB 중 VM 5대가 36GB를 쓴다. 2026-11-12 09:18 available 25GB
- **서버 한 대가 전부다**: 호스트가 꺼지면 Ollama · Milvus · model-service · NFS와 쿠버네티스 VM 전체가 같이 멈춘다
- **Ollama 모델 마운트가 읽기 쓰기**: 노션 설계(`:ro`)와 다르다. 의도한 것인지 기록이 없다
- **컨테이너 `mysql`(127.0.0.1:3306)의 용도**: 이름 · 이미지만 보고 무엇에 쓰는지 정하지 않았다
- **2인 설계는 당시 기준**: kopo02 계정은 남아 있지만 지금은 혼자 쓴다. kopo02의 VNC `:3` · 포트 범위 5501~5999 규칙이 지금도 쓰이는지 확인하지 않았다

## 5. 확인 방법

```bash
# 하드웨어 · 드라이버 · CUDA
nvidia-smi --query-gpu=name,driver_version,memory.total --format=csv,noheader   # NVIDIA GeForce RTX 5070 Ti, 595.99.02, 16303 MiB
nvcc --version | tail -2                                                        # release 13.0, V13.0.48
python3 --version                                                               # Python 3.14.4
~/llm_env/bin/python -c "import torch;print(torch.__version__, torch.cuda.is_available())"   # 2.14.0+cu130 True
nproc; free -g                                                                  # 32, Mem total 61

# 원격 접속 · 자동 시작
systemctl status tigervncserver@2.service --no-pager      # active (running)
systemctl status jupyter-kopo17.service --no-pager        # active (running)
systemctl is-active ssh docker cloudflared-ollama model-service petmint-search   # 모두 active

# 컨테이너
docker ps --format '{{.Names}}\t{{.Ports}}'               # ollama 11434(127.0.0.1 · 172.17.0.1 · 192.168.122.1), openwebui 127.0.0.1:3000 등 8개
docker logs ollama --tail 30
docker logs openwebui --tail 30
docker exec ollama ollama list                            # 20개, deepseek-r1-14b 포함
docker exec ollama ollama run deepseek-r1-14b "테스트 질문"

# 공유 디렉터리 · NFS
ls /opt /opt/shared                                       # models · shared(gpu.lock) 등, lora 없음
cat /etc/exports.d/*.exports                              # 192.168.122.0/24 에만 5개
```

자주 쓰는 명령(노션 부록):

```bash
nvidia-smi
source ~/llm_env/bin/activate
nohup jupyter lab --no-browser --port=5002 > ~/jupyter.log 2>&1 &
systemctl status tigervncserver@2.service --no-pager
sudo systemctl restart tigervncserver@2.service
docker ps
docker logs ollama --tail 30
docker logs openwebui --tail 30
docker exec ollama ollama list
docker exec ollama ollama run deepseek-r1-14b "테스트 질문"
```
