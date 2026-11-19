<!--
다루는 곳: docs/history/notion_hardware_20261116.md
읽은 커밋: 736d833
-->
# 01-02 OS와 드라이버

## 호스트 OS

서버의 OS는 Ubuntu 26.04.1 LTS다. USB에 설치 이미지를 담아 설치했고, 설치가 끝난 뒤로는 서버 안의 디스크로 부팅한다. [docs:history/notion_hardware_20261116.md:17] 지금 커널은 7.0.0-42-generic이고, 서버는 32코어와 61GiB 메모리를 갖고 있다. [docs:history/cluster_state_20261116.md:75] 호스트의 Python은 3.14.4다. [docs:history/notion_hardware_20261116.md:19]

호스트 OS를 「호스트」라고 부르는 것은 그 위에 다른 것이 얹히기 때문이다. 이 서버 위에는 쿠버네티스 노드가 되는 가상 머신 다섯 대가 돌고, 그 가상 머신들은 호스트와 다른 판인 Ubuntu 22.04.3 LTS를 쓴다. [docs:history/cluster_state_20261116.md:17] 호스트는 가상 머신을 띄우는 일, GPU를 쓰는 일, 그리고 클러스터 밖에 둔 몇 가지 서비스를 맡는다. 가상 머신 쪽 OS는 → 「가상 머신과 노드」에서 다룬다.

## 그래픽카드와 NVIDIA 드라이버

서버에는 NVIDIA GeForce RTX 5070 Ti 한 장이 꽂혀 있고, 그래픽 메모리(VRAM)는 16GB다. [docs:history/notion_hardware_20261116.md:16] 지금 드라이버는 595.99.02이고, 드라이버가 보고하는 메모리는 16303MiB다. [docs:history/cluster_state_20261116.md:76]

드라이버는 자동 설치로 깔리지 않았다. Ubuntu에는 장치를 보고 알맞은 드라이버를 골라 까는 자동 추천 설치(`ubuntu-drivers autoinstall`)가 있는데, 이 서버에서는 실패했다. 그래서 장치 목록에서 이 카드에 맞는 드라이버 판을 직접 확인하고, 그 판을 지정해 깔았다. [docs:history/notion_hardware_20261116.md:23]

드라이버를 깔고 나서도 바로 쓸 수는 없었다. 이 서버는 Secure Boot(부팅할 때 서명이 확인된 코드만 올리게 하는 펌웨어 기능)가 켜져 있어서, 서명되지 않은 NVIDIA 커널 모듈이 올라오지 못했다. 드라이버를 설치할 때 임시 암호를 정하고, 재부팅한 뒤 나오는 MOK(Machine Owner Key, 기계 주인이 직접 믿는다고 등록하는 서명 키) 등록 화면에서 그 암호로 키를 등록했다. [docs:history/notion_hardware_20261116.md:24] 이렇게 하면 Secure Boot는 켜 둔 채 이 드라이버만 믿게 할 수 있다. Secure Boot를 끄는 것보다 부팅 단계의 보호를 그대로 지킬 수 있는 길이다.

## CUDA와 Python 환경

GPU로 계산을 하려면 드라이버 위에 CUDA(NVIDIA GPU에서 일반 계산을 돌리게 하는 도구 모음)가 있어야 한다. CUDA Toolkit 13.0을 NVIDIA 저장소의 서명 키(cuda-keyring)를 등록한 뒤 그 저장소에서 깔았다. [docs:history/notion_hardware_20261116.md:25] 저장소를 등록해 두면 패키지 관리자로 판을 올리고 내리기 쉽다.

Python 쪽은 계정마다 따로 가상 환경(venv, 한 프로젝트가 쓰는 Python 패키지를 따로 담는 폴더)을 두고, 그 안에 CUDA 13 계열에 맞춘 PyTorch(cu130 빌드)를 깔아 GPU가 보이는지 확인했다. [docs:history/notion_hardware_20261116.md:26] 서버를 여럿이 쓸 것을 전제로 했기 때문에, 한 사람이 패키지를 바꿔도 다른 사람의 환경이 깨지지 않도록 계정마다 환경을 나눴다.

## Docker와 GPU

추론 서버 같은 것은 컨테이너로 띄우기로 했다. 그래서 Docker와 NVIDIA Container Toolkit(컨테이너 안에서 호스트의 GPU를 쓸 수 있게 이어 주는 도구)을 깔았다. [docs:history/notion_hardware_20261116.md:27] 계정을 docker 그룹에 넣어 sudo 없이 Docker를 부르게 했는데, 다시 로그인해도 그룹이 반영되지 않아 결국 서버를 재부팅해서 풀었다. [docs:history/notion_hardware_20261116.md:27]

지금 호스트의 Docker에는 추론 서버 Ollama와 채팅 화면 Open WebUI 말고도 벡터 데이터베이스 Milvus, GPU 지표를 내보내는 exporter, MySQL 셋이 돈다. [docs:history/cluster_state_20261116.md:77] 이것들이 클러스터와 어떻게 이어지는지는 → 「GPU와 호스트 서비스」에서 다룬다.

## 추론 서버로 Ollama를 고른 까닭

언어 모델을 GPU에서 돌려 다른 프로그램이 부를 수 있게 해 주는 추론 서버로 Ollama를 골랐다. Ollama를 Docker 컨테이너로 띄워 모델 추론 API로 쓰고, 사람이 직접 대화해 볼 화면으로 Open WebUI 컨테이너를 붙였다. 둘 다 재시작 정책을 걸어 서버가 켜지면 같이 뜬다. [docs:history/notion_hardware_20261116.md:31]

처음에 견준 것은 LM Studio였다. LM Studio는 서버 전체에서 한 인스턴스만 돌 수 있어서, 한 사람이 쓰고 있으면 다른 사람은 실행조차 할 수 없었다. 실제로 그렇게 막히는 일을 겪었다. Ollama는 뒤에서 도는 API 서버라 여러 사람과 여러 프로그램이 동시에 부를 수 있다. [docs:history/notion_hardware_20261116.md:32] 서버를 여럿이 함께 쓰는 것을 전제로 했으니 Ollama가 맞았다.

Ollama는 모델을 요청이 올 때만 GPU 메모리에 올리고, 마지막 요청 뒤 유지 시간(기본 5분)이 지나면 내린다. 쉬는 동안 GPU 메모리가 거의 비어 있는 것을 확인했다. [docs:history/notion_hardware_20261116.md:33] GPU 메모리를 한 프로그램이 계속 붙잡지 않으니 다른 일과 나눠 쓰기 좋다. 여럿이 같은 모델을 쓰는 경우를 생각해, 공유하는 베이스 모델은 한 곳에만 두고 계정마다 복사하지 않았다. [docs:history/notion_hardware_20261116.md:34]

## 학습이 차례를 지키게 한 것

GPU가 한 장뿐이라 무거운 학습 두 개가 동시에 돌면 GPU 메모리가 넘쳐 둘 다 죽는다. 그래서 학습 코드 안에서 파일 잠금(fcntl, 한 파일을 한 번에 한 프로세스만 붙잡게 하는 운영체제 기능)을 걸어, 먼저 잠금을 잡은 학습이 끝날 때까지 다음 학습이 기다리게 했다. [docs:history/notion_hardware_20261116.md:35]

명령 앞에 `flock`을 붙여 프로그램 전체를 잠그는 방법도 있지만 Jupyter에는 맞지 않았다. Jupyter는 노트북을 셀 단위로 나눠 실행하므로, 명령 하나를 감싸는 잠금으로는 학습하는 구간만 골라 잠글 수 없다. [docs:history/notion_hardware_20261116.md:35] 코드 안에서 잠그면 GPU를 실제로 쓰는 구간만 잠글 수 있다.

## 알려진 한계

- 학습의 차례 지키기는 학습 코드가 스스로 잠금을 거는 약속에 기댄다. 잠금을 걸지 않는 프로그램은 막지 못한다

### 조건

- 드라이버를 판을 지정해 깔았으므로, 판을 올릴 때도 사람이 판을 골라야 한다
- GPU가 한 장이라 모두가 같은 메모리를 나눠 쓰는 것은 여러 편에 걸리는 조건이라 → 「알려진 한계」에 모았다

## 용어 풀이

- 호스트 OS: 물리 서버에 바로 깔린 OS. 가상 머신과 컨테이너가 그 위에서 돈다
- Secure Boot: 서명이 확인된 코드만 부팅 과정에 올리게 하는 펌웨어 기능
- MOK: 기계 주인이 직접 믿는다고 등록하는 서명 키. Secure Boot를 켠 채 직접 고른 드라이버를 올리게 한다
- CUDA: NVIDIA GPU에서 일반 계산을 돌리게 하는 도구 모음
- venv: Python 패키지를 프로젝트나 사람마다 따로 담는 가상 환경
- NVIDIA Container Toolkit: 컨테이너 안에서 호스트의 GPU를 쓰게 이어 주는 도구
- 추론 서버: 학습된 모델을 띄워 두고 요청이 오면 답을 만들어 돌려주는 서버
- 파일 잠금: 한 파일을 한 번에 한 프로세스만 붙잡게 해 일의 차례를 지키는 방법
