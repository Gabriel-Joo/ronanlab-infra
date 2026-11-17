<!--
다루는 곳: docs/history/notion_hardware_20261116.md
읽은 커밋: 6290346
-->
# 서버와 호스트 OS

물리 서버 한 대와 그 호스트 OS, 사무실 망, 원격 접속을 다룬다. 이 편의 대상은 코드에 남지 않는다. 근거는 노션 하드웨어 기록에서 고른 사실과 호스트 상태 확인 기록이다. 클러스터가 호스트 서비스(Ollama, model-service, Milvus, search)를 부르는 구조는 → 「GPU와 호스트 서비스」의 몫이다.

## 지금 구성

### 망

- 사무실은 공유기 한 대로 인터넷에 닿고, 공유기 밑 스위치 2~3대에 서버 PC 10대가 나눠 꽂혀 있다 [docs:history/notion_hardware_20261116.md:9]
- 서버마다 고정 IP다. 공유기 포트포워딩이 특정 내부 IP를 가리키기 때문이다 [docs:history/notion_hardware_20261116.md:10]
- 바깥에서는 포트포워딩 하나로 이 서버의 SSH에만 들어온다. Jupyter, VNC, Ollama, Open WebUI는 SSH 터널로 연다 [docs:history/notion_hardware_20261116.md:11]
- 10대 중 이 프로젝트의 서버는 RTX 5070 Ti가 든 한 대다. 처음에는 두 계정이 포트 범위를 나눠 함께 쓰도록 설계했고, 지금은 혼자 쓴다 [docs:history/notion_hardware_20261116.md:12]
- 바깥 포트 번호와 공유기 주소는 문서에 적지 않는다

### 서버와 OS

- OS: Ubuntu 26.04.1 LTS, 커널 7.0.0-42-generic, 32코어, 메모리 61GiB [docs:history/cluster_state_20261116.md:75]
- USB로 설치했고 내장 디스크로 부팅한다 [docs:history/notion_hardware_20261116.md:17]
- 헤드리스다. 모니터와 키보드는 없고 SSH와 VNC로만 관리한다 [docs:history/notion_hardware_20261116.md:18]
- Python 3.14.4 [docs:history/notion_hardware_20261116.md:19]

### GPU와 드라이버

- GPU: NVIDIA GeForce RTX 5070 Ti, VRAM 16GB [docs:history/notion_hardware_20261116.md:16]
- 드라이버 595.99.02, `nvidia-smi` 메모리 16303MiB [docs:history/cluster_state_20261116.md:76]
- 드라이버는 `ubuntu-drivers autoinstall`이 실패해 판을 지정해 깔았다 [docs:history/notion_hardware_20261116.md:23]
- Secure Boot가 켜져 있다. NVIDIA 커널 모듈은 MOK로 등록한 키로 올라온다 [docs:history/notion_hardware_20261116.md:24]
- CUDA Toolkit 13.0, NVIDIA 저장소(cuda-keyring)에서 깔았다 [docs:history/notion_hardware_20261116.md:25]
- 계정마다 venv, PyTorch cu130 빌드 [docs:history/notion_hardware_20261116.md:26]
- Docker와 NVIDIA Container Toolkit [docs:history/notion_hardware_20261116.md:27]
- 노션 기록의 드라이버 판(595.91.07)은 옛 값이다. 지금 값은 위다 [docs:history/notion_hardware_20261116.md:49]

### 호스트 Docker 컨테이너

| 컨테이너 | 여는 주소 |
| --- | --- |
| ollama | 127.0.0.1, 172.17.0.1, 192.168.122.1의 11434 |
| openwebui | 127.0.0.1:3000 |
| milvus-standalone, milvus-etcd | → 「GPU와 호스트 서비스」 |
| nvidia-gpu-exporter | 192.168.122.1:9835 |
| mysql 셋 | 127.0.0.1에만 |

근거: [docs:history/cluster_state_20261116.md:77]

- ollama와 openwebui는 재시작 정책으로 서버가 켜지면 같이 뜬다 [docs:history/notion_hardware_20261116.md:31]
- Ollama는 요청 때만 모델을 GPU에 올리고 마지막 요청 뒤 유지 시간(기본 5분)이 지나면 내린다 [docs:history/notion_hardware_20261116.md:33]
- 공유 베이스 모델은 한 곳에만 둔다 [docs:history/notion_hardware_20261116.md:34]
- LM Studio를 쓰지 않는 까닭: 서버 전체에서 한 인스턴스만 돈다. Ollama는 여럿이 동시에 부를 수 있다 [docs:history/notion_hardware_20261116.md:32]
- GPU를 쓰는 학습은 코드 안의 파일 잠금(fcntl)으로 차례를 지킨다. Jupyter는 셀 단위 실행이라 `flock` 명령 감싸기가 맞지 않는다 [docs:history/notion_hardware_20261116.md:35]

### 원격 접속

- openssh-server, ufw에서 SSH를 열었다 [docs:history/notion_hardware_20261116.md:39]
- 교실 PC에서 PuTTY로 접속하고, PuTTY 터널로 Jupyter, Ollama, VNC, Open WebUI를 서버 안 주소로 이어 쓴다 [docs:history/notion_hardware_20261116.md:40]
- 원격 데스크톱: TigerVNC 서버, UltraVNC Viewer, Xfce. GNOME이 앞 디스플레이를 차지해 VNC는 뒤 번호를 쓴다 [docs:history/notion_hardware_20261116.md:41]
- VNC 서비스 파일에 `Delegate=yes`, 기본 터미널은 xfce4-terminal(cgroup 오류 때문) [docs:history/notion_hardware_20261116.md:42]
- VNC와 Jupyter Lab은 systemd 서비스로 부팅 때 뜬다 [docs:history/notion_hardware_20261116.md:43]

### 이 편과 닿는 호스트 서비스

실행 중: `tigervncserver@2`, `jupyter-kopo17`, `docker`, `libvirtd`, `cloudflared-ollama`, `model-service`, `petmint-search`, nfs-server 계열 [docs:history/cluster_state_20261116.md:78]

- VNC와 Jupyter 유닛: 이 편(원격 접속)
- `libvirtd`: 노드 VM. → 「가상 머신과 노드」
- `cloudflared-ollama`, `model-service`, `petmint-search`: → 「GPU와 호스트 서비스」
- nfs-server: → 「이미지 저장소」, → 「공유 저장소」

## 설정 자리

이 편의 설정은 모두 저장소 밖, 호스트에 있다. 저장소에 파일이 없다.

| 설정 | 자리 | 뜻 |
| --- | --- | --- |
| VNC | systemd 유닛 `tigervncserver@2` | 디스플레이 2, `Delegate=yes` [docs:history/notion_hardware_20261116.md:42] |
| Jupyter Lab | systemd 유닛 `jupyter-kopo17` | 부팅 때 뜬다 [docs:history/notion_hardware_20261116.md:43] |
| 방화벽 | ufw | SSH 허용 [docs:history/notion_hardware_20261116.md:39] |
| Ollama, Open WebUI | Docker 컨테이너 `ollama`, `openwebui` | 재시작 정책, 여는 주소는 위 표 [docs:history/cluster_state_20261116.md:77] |
| 공유기 포트포워딩 | 사무실 공유기 | 바깥에서 SSH로만. 번호는 적지 않는다 |

## 바꾸거나 다시 만들기

호스트 명령은 `sudo`가 필요하다. 세션은 직접 치지 않고 사용자에게 알린다. 재부팅은 클러스터 VM과 호스트 서비스가 모두 끊기므로 사람 승인이 필요하다. [code:CLAUDE.md:40-41]

- NVIDIA 드라이버: 자동 추천 설치가 실패하므로 장치 목록에서 판을 골라 지정해 깐다. Secure Boot가 켜져 있으므로 설치 때 MOK 암호를 정하고, 재부팅 뒤 MOK 등록 화면에서 키를 등록한다 [docs:history/notion_hardware_20261116.md:23-24]
- docker 그룹 추가가 다시 로그인해도 반영되지 않으면 재부팅으로 풀었다 [docs:history/notion_hardware_20261116.md:27]
- VNC 안 터미널이 cgroup 오류를 내면 서비스 파일의 `Delegate=yes`와 기본 터미널(xfce4-terminal)을 본다 [docs:history/notion_hardware_20261116.md:42]
- Ollama 유지 시간(`OLLAMA_KEEP_ALIVE`)은 바꾸지 않는다. GPU 메모리를 다른 PC와 나눠 쓴다 [code:CLAUDE.md:34]

## 확인

```
nvidia-smi                                   # RTX 5070 Ti, 드라이버 595.99.02, 16303MiB
mokutil --sb-state                           # SecureBoot enabled
docker ps --format '{{.Names}}\t{{.Ports}}'  # 위 컨테이너 표와 같은 이름, 같은 주소
systemctl is-active tigervncserver@2 jupyter-kopo17 docker libvirtd   # 모두 active
sudo ufw status                              # SSH 허용 (사용자가 친다)
```

기대 값의 근거: [docs:history/cluster_state_20261116.md:75-78]

## 알려진 한계

- 이 편의 설정(드라이버, VNC 유닛, ufw, 컨테이너 실행 옵션, 공유기)은 저장소에 없다. 서버를 새로 깔면 사람이 손으로 다시 넣어야 한다
- 바깥에서 서버로 가는 길이 공유기 포트포워딩과 SSH 하나에 기댄다. 막히면 서버 앞에서 모니터와 키보드를 꽂아야 한다
- 서버가 한 대라 이 서버가 멈추면 클러스터와 호스트 서비스가 모두 멈춘다
- 학습의 차례 지키기는 학습 코드의 파일 잠금 약속에 기댄다. 잠금을 걸지 않는 프로그램은 막지 못한다 [docs:history/notion_hardware_20261116.md:35]
- 하드웨어 이력과 노션 기록의 옛 값은 노션 하드웨어 기록의 「노션과 지금 상태가 다른 곳」에 있다 [docs:history/notion_hardware_20261116.md:45-53]
