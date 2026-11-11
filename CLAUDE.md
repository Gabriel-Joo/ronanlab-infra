# ronanlab-infra — 세션 규칙

이 저장소에서 도는 Claude 세션(관리자 · 그 밖)이 읽는 규칙이다. 2026-11-11 처음 씀.
모르는 것은 「정해지지 않음」으로 둔다 — 지어내지 않는다.

## 1. 이 저장소가 무엇인가

- 홈랩 쿠버네티스(kubeadm 1.35.9, VM m-k8s · w1~w4)의 선언 저장소. 원격 `git@github.com:Gabriel-Joo/ronanlab-infra.git`
- **`main`이 곧 운영이다.** ArgoCD 루트 Application(`bootstrap/root-app.yaml`, App of Apps)이 `main`의 `apps/*/app.yaml`을 읽어 앱 Application을 만들고, 각 앱도 `targetRevision: main`을 본다
  - 자동 Sync인 앱은 push하면 3분 안에 클러스터에 들어간다. 2026-11-11 클러스터 기준 자동: runshoes · petmint · monitoring · harbor-backup, 수동: cloudflared
  - 자동 Sync 켜고 끄기의 실제 스위치는 클러스터의 `kubectl patch`이고 `app.yaml`은 기록이다(루트가 `spec.syncPolicy`를 덮지 않는다 — `bootstrap/root-app.yaml` 머리 주석)
  - 수동 Sync: `kubectl -n argocd patch app <앱> --type merge -p '{"operation":{"sync":{"revision":"<커밋>"}}}'`
- `platform/`(cert-manager · coredns · ingress-nginx · metallb · harbor · jenkins · argocd ingress)은 **ArgoCD 밖**이다 — push해도 바뀌지 않는다. helm · kubectl로 사람이(또는 지시받은 세션이) 손으로 넣는다
- `cluster/`는 VM 정의(Vagrantfile · setup-node.sh · label-nodes.sh). 실제로 `vagrant`를 돌리는 곳은 호스트 `~/k8s-cluster/`이고 `cluster/`는 그 사본이다(어느 쪽을 원본으로 둘지는 정해지지 않음)
- `main`에는 다른 쓰는 이가 있다: Jenkins(`Jenkins runshoes-app` · `Jenkins petmint-app`)가 이미지 태그를 커밋하고, 다른 세션도 문서를 커밋한다

## 2. 일하는 방식

- **worktree 없이 원본 폴더 `~/ronanlab-infra`의 `main`에서 일한다.** worktree나 다른 브랜치는 ArgoCD가 보지 않아 확인을 할 수 없다. FOREMAN 공통 규칙의 「worktree 세션은 push하지 않는다」는 여기 맞지 않는다
- 커밋 전 `git status` — 남이 고친 것(커밋 안 된 변경)은 건드리지 않고 **자기 파일만 `git add`**. push 전에 `git pull --rebase`(Jenkins 태그 커밋과 엇갈린다)
- **push**: 2026-11-10~11에는 이 저장소 세션이 사용자 지시로 직접 push했다. 관리자 체계에서 누가 push하는지는 **정해지지 않음** — 정해질 때까지 사용자 지시가 있을 때만 push한다
- 클러스터는 호스트에 kubectl이 없다 — `cd ~/k8s-cluster && vagrant ssh m-k8s -c '…'`로 m-k8s에서 kubectl을 친다
- 단계마다 확인한다. **확인에 실패하면 되돌리고 멈춰서 보고한다**
- 서비스가 끊기는 단계(재시작 · 노드 정비 등) 직전에는 사용자에게 알린다
- `apps/cloudflared/configmap.yaml`을 바꾸면 Sync만으로는 반영되지 않는다 — `rollout restart`까지(그 README)

## 3. 사람 승인이 필요한 것

되돌릴 수 없거나 운영이 끊기는 것은 하지 않고 사용자에게 묻는다:
- 운영 DB `DROP` · 데이터 지우기, PVC · PV · 네임스페이스 삭제, `vagrant destroy`
- 서버 · VM 재부팅 · 끄기(`vagrant halt`, `virsh` 메모리 바꾸기 포함)
- `sudo`가 필요한 호스트 명령 — 직접 치지 않고 사용자에게 한 줄로 알린다(예: `scripts/host-*.sh`)
- Cloudflare(터널 DNS · Access) 바꾸기 — 대시보드는 사람이 한다
- 지워도 되는 것은 시험용으로 자기가 만든 것뿐. 지우기 · 덮어쓰기 전에 대상을 먼저 본다

## 4. 비밀값

- `.env*` · kubeconfig · 토큰 · DB 암호를 화면 · 로그 · 커밋에 내지 않는다. 저장소에는 Secret이 없다 — 사람이 `kubectl create secret`으로 만든다(각 README 「처음 한 번」)
- 비밀값이 든 파일은 Edit · Write로 고치지 않는다. 값이 있는지는 개수로만 센다(`/usr/bin/grep -cF`)
- Loki에는 서버 로그만 넣는다 — 대화 기록(질문 · 답 원문)은 넣지 않는다(`apps/monitoring/alloy/alloy.yaml`이 버린다)

## 5. 문서 자리

- `docs/README.md` — 인프라 문서 원본(노션 「쿠버네티스 설치」와 다르면 이쪽이 맞다). `01_cluster.md` · `02_availability.md` · `TODO.md`(남은 일, 끝나면 줄을 지운다)
- `docs/runbooks/` — 절차(지금 `mysql-replica.md`). 앱 절차는 `apps/runshoes/runbooks/`
- 앱별 운영 문서는 `apps/<앱>/README.md`, 모니터링은 `apps/monitoring/README.md`
- 바꾼 것은 그 자리 문서에 날짜와 함께 적는다

## 6. FOREMAN 공통

- 항상 한국어로 답하고 쓴다
- 파일은 Edit · Write로 고친다 — `sed -i` · `perl -i` · heredoc 덧붙이기(`cat >> f <<EOF`) · `tee`로 저장소 파일을 고치지 않는다. 임시 파일은 세션 스크래치에
- 다른 저장소(foreman · runshoes · petmint-rag-chatbot)는 읽기만 한다. 그쪽 일은 그 프로젝트 관리자에게 부탁한다(아래)

## 7. 관리자(원본 폴더 세션) — FOREMAN 프로젝트별 관리자

- 이 저장소 관리자는 원본 폴더에서 도는 역할 manager 세션 하나다. 관리자와 다른 세션의 일 나누기(누가 매니페스트를 고치는지 · 합치기가 있는지)는 **정해지지 않음** — worktree가 없으므로 FOREMAN 다른 저장소의 「코더는 worktree, 관리자는 합치기」를 그대로 쓰지 않는다
- FOREMAN API는 이 프로젝트 토큰으로만 부른다:
  `T=$(sed -n 's/^FOREMAN_TOKEN_RONANLAB_INFRA=//p' ~/AI_programming/foreman/.env.project_tokens)` — 셸 변수로만 쓰고 값은 화면 · 로그 · 커밋에 내지 않는다. 이 토큰은 이 프로젝트 세션 · 방 API만 연다
- 다른 프로젝트에 부탁할 일: `POST http://127.0.0.1:8000/api/managers/<프로젝트>/ask {"text": "…"}`(헤더에 `$T`). 관리자가 없으면 사람에게 텔레그램으로 간다
- 교장이 넘긴 계획(입력 칸에 「[교장 계획 #N …]」)은 고칠 것이 없으면 적힌 명령(`/api/foreman/start` `{"dispatch_id": N, "use_saved": true}`)으로 띄운다. 틀렸으면 띄우지 말고 사람에게 묻는다
