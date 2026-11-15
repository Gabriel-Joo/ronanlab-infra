# 노션 하드웨어 기록에서 고른 사실 (2026-11-16)

하드웨어 편(서버, OS, 드라이버, 원격 접속, 사무실 망)은 코드에 남지 않는다. 그 편의 근거로 노션 「인프라/서버 구축(하드웨어)」 페이지(2026-11-11 판)에서 사실만 골라 옮겼다. 글은 옮기지 않았고 메모의 말투도 따르지 않았다. 바깥에서 들어오는 포트포워딩 번호와 공유기 주소는 옮기지 않았다.

노션 기록과 2026-11-16 호스트 상태가 다른 곳은 맨 아래에 따로 적었다. 새 문서는 지금 상태를 따른다.

## 사무실 망

- 인터넷에서 공유기 한 대로 들어오고, 공유기 밑에 스위치 2~3대를 달아 서버 PC 10대를 나눠 꽂았다. 공유기 LAN 포트만으로는 10대를 다 꽂을 수 없었다
- 서버마다 고정 IP를 줬다. 포트포워딩 규칙이 특정 내부 IP를 가리키므로, DHCP로 IP가 바뀌면 규칙이 깨지기 때문이다
- 바깥에서는 공유기의 포트포워딩 하나로 서버의 SSH에만 들어온다. 다른 서비스(Jupyter, VNC, Ollama, Open WebUI)는 그 SSH 연결 안의 터널로 연다
- 10대 가운데 이 프로젝트가 쓰는 것은 RTX 5070 Ti가 든 물리 서버 한 대다. 처음에는 두 계정(kopo17, kopo02)이 함께 쓰도록 설계했고, 계정마다 쓸 포트 범위를 나눴다. 결국 혼자 쓰게 됐다

## 서버와 OS

- GPU: NVIDIA GeForce RTX 5070 Ti, 16GB VRAM
- OS: Ubuntu 26.04.1 LTS. USB로 설치했고, 설치 뒤에는 내장 디스크로 부팅한다
- 처음에는 모니터와 키보드를 꽂아 작업했고, VNC를 붙인 뒤로는 둘 다 떼고 헤드리스로 운영한다. 교실 PC에서 SSH와 VNC로만 관리한다
- Python 3.14.4

## 드라이버와 GPU 환경

- 자동 추천 설치(`ubuntu-drivers autoinstall`)가 실패해서, 장치 목록을 보고 판을 지정해 NVIDIA 드라이버를 깔았다
- Secure Boot가 켜져 있어 서명되지 않은 NVIDIA 커널 모듈이 올라오지 않았다. 설치 때 임시 암호를 정하고, 재부팅 뒤 MOK 등록 화면에서 키를 등록해 해결했다
- CUDA Toolkit 13.0을 NVIDIA 저장소 키(cuda-keyring)로 깔았다
- 계정마다 venv를 두고 PyTorch(cu130 빌드)를 깔아 GPU 인식을 확인했다
- Docker와 NVIDIA Container Toolkit을 깔아 컨테이너가 GPU를 쓰게 했다. docker 그룹에 넣은 것이 다시 로그인해도 반영되지 않아 서버를 재부팅해 해결했다

## 추론 서버와 GPU 공유

- Ollama를 Docker 컨테이너로 띄워 모델 추론 API로 쓰고, Open WebUI 컨테이너를 채팅 화면으로 붙였다. 둘 다 재시작 정책으로 서버가 켜지면 같이 뜬다
- LM Studio를 쓰지 않은 까닭: 서버 전체에서 한 인스턴스만 돌 수 있어, 한 사람이 쓰고 있으면 다른 사람은 실행조차 할 수 없었다. 실제로 막히는 것을 겪었다. Ollama는 백그라운드 API 서버라 여럿이 함께 부를 수 있다
- 모델을 요청할 때만 GPU 메모리에 올리고, 마지막 요청 뒤 유지 시간(기본 5분)이 지나면 내린다. 쉬는 동안 GPU 메모리가 거의 0인 것을 확인했다
- 공유 베이스 모델은 한 곳에만 두고 계정마다 복사하지 않는다
- GPU가 한 장이라 무거운 학습 두 개가 동시에 돌면 메모리가 넘친다. 학습 코드 안에서 파일 잠금(fcntl)으로 차례를 지키게 했다. 셀 단위로 실행하는 Jupyter에는 명령 앞에 붙이는 flock이 맞지 않았다

## 원격 접속

- openssh-server를 깔고 방화벽(ufw)에서 SSH를 열었다
- 교실 PC에서는 PuTTY로 처음 접속했고, PuTTY 터널로 Jupyter, Ollama, VNC, Open WebUI를 서버 안 주소로 이어 쓴다
- 원격 데스크톱은 TigerVNC 서버와 UltraVNC Viewer다. 데스크톱은 Xfce다. 서버의 GNOME이 앞 디스플레이 번호를 차지하고 있어 VNC는 그 뒤 번호를 쓴다
- VNC 안에서 기본 터미널이 cgroup 오류를 내서, 서비스 파일에 `Delegate=yes`를 넣고 기본 터미널을 xfce4-terminal로 바꿨다
- VNC와 Jupyter Lab은 systemd 서비스로 등록해 재부팅하면 저절로 뜬다

## 노션과 지금 상태가 다른 곳

| 항목 | 노션 | 2026-11-16 지금 |
| --- | --- | --- |
| NVIDIA 드라이버 | 595.91.07 | 595.99.02 |
| Ollama가 여는 주소 | 모든 주소에 연다 | 호스트 자신, Docker 다리, libvirt 기본망의 호스트 주소 세 곳에만 연다 |
| Open WebUI가 여는 주소 | 모든 주소에 연다 | 호스트 자신에만 연다 |
| 호스트 컨테이너 | Ollama, Open WebUI 둘 | 그 밖에 Milvus, GPU exporter, MySQL 셋이 더 있다 |
| 호스트 서비스 | VNC, Jupyter | 그 밖에 cloudflared-ollama, model-service, petmint-search, NFS 서버가 더 있다 |

지금 값의 근거는 [cluster_state_20261116.md](cluster_state_20261116.md) 「호스트」다.
