<!--
다루는 곳: docs/history/notion_hardware_20261116.md
읽은 커밋: e8e24ea
-->
# 원격 접속

## 모니터 없이 관리하는 서버

서버에는 모니터도 키보드도 없다. 설치할 때만 둘을 꽂아 작업했고, 원격 데스크톱을 붙인 뒤로는 떼어 내고 헤드리스(화면과 입력 장치 없이 망으로만 다루는 방식)로 운영한다. 서버는 교실 PC에서 SSH와 원격 데스크톱으로만 관리한다. [docs:history/notion_hardware_20261116.md:18] 그러니 원격 접속이 막히면 서버를 다룰 길이 없다. 이 편은 사람이 서버에 닿는 길을 다룬다. 클러스터 위의 웹 서비스가 인터넷에 공개되는 길은 이것과 따로이며, → 「바깥 공개와 인증서」에서 다룬다.

## SSH

모든 접속의 바탕은 SSH다. 서버에 openssh-server를 깔고, 방화벽(ufw, Ubuntu에 딸린 간단한 방화벽 도구)에서 SSH만 열었다. [docs:history/notion_hardware_20261116.md:39] 바깥에서 서버로 들어오는 길도 공유기가 SSH로 넘겨 주는 길 하나뿐이다. [docs:history/notion_hardware_20261116.md:11] 왜 SSH 하나만 열었는지는 → 「사무실 망과 서버」에서 다룬다.

교실 PC에서는 처음에 PuTTY(Windows에서 많이 쓰는 SSH 접속 프로그램)로 접속했다. [docs:history/notion_hardware_20261116.md:40]

## 터널로 여는 서비스

서버 안에는 사람이 화면으로 쓰는 서비스가 몇 있다. Jupyter(브라우저에서 코드를 셀 단위로 실행하는 노트북 환경), 추론 서버 Ollama, 채팅 화면 Open WebUI, 그리고 원격 데스크톱 VNC다. 이것들은 바깥에 열지 않고, PuTTY의 터널 기능으로 SSH 연결 안을 지나 서버 안쪽 주소로 이어 쓴다. [docs:history/notion_hardware_20261116.md:40] 교실 PC의 브라우저나 VNC 뷰어는 자기 PC의 한 포트에 붙고, PuTTY가 그 연결을 SSH 안으로 실어 서버 안의 서비스에 넘긴다. 서비스 쪽에서 보면 연결이 서버 자신에게서 온 것처럼 보인다.

이 방식 덕분에 서비스들은 서버 바깥 주소에 귀를 열 필요가 없다. 지금 채팅 화면 Open WebUI는 서버 자신에게만 연결을 받는다. [docs:history/notion_hardware_20261116.md:51] 터널로만 쓰니 이것으로 충분하다. 추론 서버 Ollama는 서버 자신 말고도 클러스터가 부를 수 있는 주소 몇 곳에 더 열려 있는데, 그 까닭은 → 「GPU와 호스트 서비스」에서 다룬다. [docs:history/notion_hardware_20261116.md:50]

## 원격 데스크톱

화면이 필요한 일을 위해 원격 데스크톱을 붙였다. 서버에는 TigerVNC 서버를 두고, 교실 PC에서는 UltraVNC Viewer로 붙는다. 원격 데스크톱 안의 데스크톱 환경은 가벼운 Xfce다. [docs:history/notion_hardware_20261116.md:41]

VNC는 화면을 디스플레이 번호로 나눈다. 서버에는 Ubuntu 기본 데스크톱인 GNOME이 이미 앞 디스플레이 번호를 차지하고 있어서, VNC는 그 뒤 번호를 쓴다. [docs:history/notion_hardware_20261116.md:41] 지금 도는 VNC 서비스는 2번 디스플레이의 것이다. [docs:history/cluster_state_20261116.md:78]

원격 데스크톱 안에서 기본 터미널을 열면 cgroup(리눅스가 프로세스 묶음마다 자원을 나눠 관리하는 장치) 오류가 나며 뜨지 않았다. 서비스 파일에 `Delegate=yes`(서비스 안의 프로세스가 자기 cgroup을 직접 나눠 쓰도록 맡기는 설정)를 넣고, 기본 터미널을 xfce4-terminal로 바꿔 풀었다. [docs:history/notion_hardware_20261116.md:42]

## 재부팅해도 저절로 뜨게

헤드리스 서버에서는 재부팅 뒤 원격 데스크톱이 안 뜨면 화면으로 들어갈 길이 없다. 그래서 VNC와 Jupyter Lab을 systemd 서비스(리눅스가 부팅 때 띄우고 죽으면 다시 살리는 서비스 관리 장치)로 등록해, 서버를 다시 켜면 사람이 손대지 않아도 저절로 뜨게 했다. [docs:history/notion_hardware_20261116.md:43] 지금도 VNC 서비스와 Jupyter 서비스가 돌고 있다. [docs:history/cluster_state_20261116.md:78] Docker 컨테이너로 띄운 Ollama와 Open WebUI는 systemd 대신 Docker의 재시작 정책으로 같은 일을 한다. [docs:history/notion_hardware_20261116.md:31]

## 알려진 한계

- 모든 원격 접속이 SSH 하나에 기댄다. SSH 서비스나 방화벽 설정이 잘못되면 바깥에서는 서버에 닿을 길이 없고, 서버 앞에 가서 모니터와 키보드를 꽂아야 한다
- 터널은 접속하는 PC마다 PuTTY에 따로 설정해 두어야 한다. 이 설정은 저장소에 남지 않는다
- VNC 서비스 파일의 `Delegate=yes` 같은 호스트 설정은 저장소 밖에 있어, 서버를 새로 깔면 사람이 다시 넣어야 한다

## 용어 풀이

- 헤드리스: 모니터와 키보드 없이 망으로만 다루는 운영 방식
- PuTTY: Windows에서 많이 쓰는 SSH 접속 프로그램. 터널도 열 수 있다
- ufw: Ubuntu에 딸린 간단한 방화벽 도구
- VNC: 원격으로 화면을 보고 마우스와 키보드를 쓰는 원격 데스크톱 방식
- 디스플레이 번호: 한 서버에서 화면 여럿을 가르는 번호
- cgroup: 리눅스가 프로세스 묶음마다 CPU와 메모리 같은 자원을 나눠 관리하는 장치
- systemd 서비스: 부팅 때 띄우고 죽으면 다시 살리도록 리눅스에 등록한 프로그램
