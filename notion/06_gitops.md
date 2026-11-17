<!--
다루는 곳: bootstrap/, platform/argocd/, apps/*/app.yaml
읽은 커밋: e8e24ea
-->
# 06 GitOps

이 클러스터에 올라가는 앱은 사람이 명령으로 하나하나 넣지 않는다. 저장소의 기본 브랜치인 `main`에 적힌 내용을 ArgoCD(Git 저장소와 클러스터를 계속 견주어, 다른 곳이 있으면 저장소 쪽으로 맞춰 주는 도구)가 읽어 클러스터에 넣는다. 그래서 이 저장소에서는 `main`이 곧 운영이다. `main`에 무엇이 들어가면 그것이 클러스터에 들어간다는 뜻이고, 거꾸로 클러스터에 무엇이 있는지 알고 싶으면 `main`을 보면 된다. [code:bootstrap/root-app.yaml:20-24]

이렇게 한 까닭은 손으로 넣는 방식의 약점 때문이다. 명령으로 바로 넣으면 누가 무엇을 바꿨는지가 클러스터 어디에도 남지 않고, 잘못 넣었을 때 되돌릴 기준이 없으며, 누가 몰래 고쳐도 알아챌 길이 없다. Git을 기준으로 삼으면 바뀐 내용이 모두 커밋으로 남고, 되돌리기는 앞 커밋으로 돌아가는 일이 된다. [docs:history/build_log/04_argocd.md:118-130]

## 루트 하나가 나머지를 만든다

ArgoCD에서 「무엇을 어디서 읽어 어디에 넣을지」를 적은 단위를 Application이라고 한다. 이 클러스터에는 Application이 여섯 있다. 그중 사람이 손으로 넣는 것은 `bootstrap/root-app.yaml`에 적힌 루트 Application 하나뿐이다. [docs:history/cluster_state_20261116.md:52-61] [code:bootstrap/root-app.yaml:1-2]

루트는 `apps` 폴더 아래 각 앱 폴더의 `app.yaml`만 골라 읽는다. 그 파일 하나하나가 앱 Application이고, 루트는 그것을 클러스터에 만들어 준다. 이렇게 Application이 다른 Application을 만드는 꼴을 App of Apps라고 부른다. 새 앱을 올리려면 `apps` 아래에 폴더를 하나 만들고 `app.yaml`과 매니페스트(쿠버네티스에 넣을 설정 파일)를 넣은 뒤 `main`에 올리면 된다. 그러면 몇 분 안에 그 앱의 Application이 생긴다. [code:bootstrap/root-app.yaml:3-4] [code:bootstrap/root-app.yaml:25-28]

앱 Application은 runshoes, petmint, monitoring, harbor-backup, cloudflared 다섯이다. 모두 `main`을 보고, 저마다 `apps` 아래 자기 폴더를 읽어 자기 네임스페이스에 넣는다. 루트가 맡는 것은 Application 객체를 만드는 데까지이고, 앱 안의 리소스를 어떻게 넣을지는 각 `app.yaml`이 정한다. [code:apps/runshoes/app.yaml:20-27] [code:bootstrap/root-app.yaml:6]

## 자동으로 들어가는 앱과 손으로 누르는 앱

Sync는 저장소의 내용을 클러스터에 맞춰 넣는 일이다. 자동 Sync가 켜진 앱은 `main`에 커밋이 올라가면 사람이 아무것도 하지 않아도 몇 분 안에 클러스터에 들어간다. 지금 runshoes, petmint, monitoring, harbor-backup이 자동이고 cloudflared 하나만 수동이다. [docs:history/cluster_state_20261116.md:54-61] [code:bootstrap/root-app.yaml:3]

cloudflared만 수동으로 둔 데는 까닭이 있다. cloudflared는 바깥에서 클러스터로 들어오는 터널이고, 공개 주소 일곱이 모두 이 터널 하나를 지난다. 터널이 깨지면 서비스만 멈추는 것이 아니라, 고칠 때 쓰는 ArgoCD 화면과 상황을 볼 Grafana까지 함께 보이지 않게 된다. 그때 되돌릴 길은 컨트롤 플레인 노드에서 명령을 치는 것뿐이다. 그래서 커밋이 곧바로 반영되지 않게 하고, 사람이 Sync를 누른 뒤 새 파드로 갈아타는 과정을 지켜본다. [code:apps/cloudflared/app.yaml:4-8] 터널 자체는 → 「바깥 공개와 인증서」에서 다룬다.

자동인 앱도 두 가지는 꺼 두었다. 하나는 prune(저장소에서 지운 리소스를 클러스터에서도 지우는 기능)이고, 다른 하나는 selfHeal(누가 클러스터에서 손으로 바꾼 것을 저장소 쪽으로 되돌리는 기능)이다. prune을 꺼 두었으니 저장소에서 지운 것도 클러스터에는 남고, 지우는 일은 사람이 직접 한다. selfHeal을 끈 것은 장애를 고치는 동안 사람이 일부러 파드 수를 0으로 내려 두는 일이 있기 때문이다. 이것을 ArgoCD가 곧바로 되돌리면 복구를 할 수 없다. [code:apps/runshoes/app.yaml:8] [code:apps/runshoes/app.yaml:11]

Application에는 finalizer(지울 때 딸린 리소스까지 함께 지우게 하는 표시)를 달지 않았다. Application을 지워도 앱과 데이터베이스와 저장 공간은 클러스터에 남는다. 루트를 지워도 앱 Application은 남는다. [code:apps/petmint/app.yaml:8] [code:bootstrap/root-app.yaml:11-12]

## 자동 Sync의 실제 스위치는 클러스터에 있다

`app.yaml`에도 자동 Sync를 켤지 끌지가 적혀 있다. 그러나 이미 만들어진 Application에서 자동 Sync를 켜고 끄는 실제 스위치는 클러스터에서 그 Application을 직접 고치는 명령이다. 루트는 앱 Application의 Sync 설정을 덮어쓰지 않게 되어 있고, `app.yaml`의 그 값은 처음 만들 때 한 번 쓰인 뒤로는 기록 구실만 한다. [code:bootstrap/root-app.yaml:8-10] [code:bootstrap/root-app.yaml:33-43]

이렇게 한 것은 데이터베이스 구조를 바꾸는 배포 때문이다. 그런 배포는 백업을 뜨고, 확인하고, 새 이미지를 넣는 순서를 지켜야 해서 그동안 자동 Sync를 잠시 꺼 둔다. 그런데 루트가 앱의 Sync 설정까지 저장소대로 맞춘다면, 빌드 서버가 이미지 태그를 커밋하는 순간 루트가 다시 Sync하면서 꺼 둔 자동 Sync를 도로 켜 버린다. 그러면 순서를 지키던 배포 한가운데에 새 이미지가 끼어든다. [code:bootstrap/root-app.yaml:9-10] [code:apps/runshoes/app.yaml:9]

수동인 앱을 넣을 때도 화면의 버튼 대신 넣을 커밋을 집어 Sync를 시키는 명령을 쓸 수 있다. 어느 커밋이 들어갔는지가 명령에 그대로 남는다.

```
kubectl -n argocd patch app <앱> --type merge -p '{"operation":{"sync":{"revision":"<커밋>"}}}'
```

## ArgoCD 밖에 있는 것

모든 것이 ArgoCD를 거치지는 않는다. `platform` 폴더에 있는 인증서 관리, 클러스터 DNS, 들어오는 문, 로드밸런서, 이미지 저장소, 빌드 서버, ArgoCD 자신의 Ingress는 ArgoCD보다 먼저 깔린 기반이라 ArgoCD가 보지 않는다. 이쪽은 `main`에 올려도 클러스터가 바뀌지 않고, 사람이 Helm이나 kubectl로 넣는다. [code:bootstrap/root-app.yaml:13]

특히 ArgoCD로 들어오는 길(Ingress)을 ArgoCD가 관리하지 않게 한 것은 일부러다. 자기에게 오는 길을 스스로 관리하다가 그 설정이 깨지면, 고칠 화면에도 들어갈 수 없게 된다. [docs:history/build_log/04_argocd.md:172] ArgoCD 화면은 바깥에서 터널을 거쳐 들어오고, 인증서는 클러스터의 인증서 관리 도구가 받는다. 들어오는 문에서 ArgoCD 서버까지도 암호화된 연결을 쓴다. ArgoCD 서버가 자체 인증서로만 연결을 받기 때문이다. [code:platform/argocd/ingress.yaml:3-4]

ArgoCD 자체는 v2.13.2로 고정해, 공식 설치 매니페스트 하나를 그대로 넣어 설치했다. 그 매니페스트는 이 저장소에 없다. 판을 고정한 것은 설치할 때마다 판이 달라지지 않게 하려는 것이다. [code:platform/versions.yaml:27-30] [docs:history/build_log/04_argocd.md:156]

ArgoCD의 파드 일곱은 모두 infra 역할의 워커 w3에 모았다. 설치 매니페스트에는 이 배치가 없어서, 설치 뒤에 `platform/argocd/pin-infra.sh`가 역할 라벨로 자리를 고정한다. 설치 매니페스트를 다시 넣으면 이 고정이 사라지므로 스크립트를 다시 돌려야 한다. ArgoCD는 저장 공간을 쓰지 않아 옮길 때 데이터를 챙길 것이 없다. [code:platform/argocd/pin-infra.sh:2-5] [code:platform/argocd/pin-infra.sh:8-11] 역할 라벨은 → 「역할 라벨과 워커 증설」에서 다룬다.

## 알림

ArgoCD는 Sync가 시작되거나, 성공하거나, 실패하거나, 저장소와 클러스터가 어긋나거나, 앱이 건강하지 않을 때마다 호스트에서 도는 작업 관리 서비스(FOREMAN)로 알림을 보낸다. 배포가 끝나 앱이 건강해진 때도 한 번 알린다. 알림 대상은 루트가 만든 Application들이다. 알림 설정은 `platform/argocd/notifications-cm.yaml`에 있고, 알림을 보낼 때 쓰는 토큰은 저장소에 없이 클러스터의 시크릿에만 있다. [code:platform/argocd/notifications-cm.yaml:3] [code:platform/argocd/notifications-cm.yaml:23-26]

ArgoCD는 저장소를 정해진 간격으로 들여다보기도 하지만, GitHub가 push를 곧바로 알려 주는 웹훅도 받는다. 그래서 커밋이 반영되기까지의 시간은 보통 그 간격보다 짧다. [docs:history/build_log/04_argocd.md:45]

## 알려진 한계

- ArgoCD 설치 매니페스트가 저장소에 없다. 다시 넣으면 w3 고정이 사라져 `pin-infra.sh`를 다시 돌려야 하고, 알림 설정도 지워질 수 있어 그 파일도 다시 넣어야 한다 [code:platform/argocd/notifications-cm.yaml:5]
- ArgoCD가 w3 한 노드에만 있다. w3가 내려가면 새 배포가 멈춘다. 이미 떠 있는 앱은 그대로 돈다 [code:cluster/label-nodes.sh:7]
- prune을 꺼 두어서 저장소에서 지운 리소스는 클러스터에 남는다. 사람이 따로 지워야 한다 [code:bootstrap/root-app.yaml:11]
- `app.yaml`의 자동 Sync 값과 클러스터의 실제 값이 다를 수 있다. 실제 값은 클러스터에서 확인해야 한다
- 웹훅 시크릿과 알림 토큰은 저장소에 없어, 클러스터를 새로 세우면 사람이 다시 넣어야 한다 [docs:history/build_log/04_argocd.md:56-59]

## 용어 풀이

- GitOps: Git 저장소에 적힌 것을 운영의 기준으로 삼고, 도구가 클러스터를 그 기준에 맞추는 운영 방식
- Application: ArgoCD에서 어느 저장소의 어느 폴더를 어느 네임스페이스에 넣을지 적은 단위
- App of Apps: Application 하나가 다른 Application들을 만들어 내는 구성
- Sync: 저장소의 내용을 클러스터에 맞춰 넣는 일
- prune: 저장소에서 지운 리소스를 클러스터에서도 지우는 기능
- selfHeal: 클러스터에서 손으로 바꾼 것을 저장소 쪽으로 되돌리는 기능
- finalizer: 객체를 지울 때 딸린 리소스까지 정리하게 하는 표시
- 웹훅: 어떤 일이 생겼을 때 한 서비스가 다른 서비스에 바로 알려 주는 호출
