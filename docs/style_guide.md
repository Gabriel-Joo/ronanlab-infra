# 문서 쓰는 법

ronanlab-infra 문서는 두 벌이다. `notion/`은 비개발자도 읽는 노션 기술문서 원고이고, `docs/NN_*.md`는 운영하는 사람이 보는 개발자 문서다. 두 벌은 같은 번호와 같은 편 나눔을 쓴다. 이 파일은 둘 다에 적용하는 규칙이다. FOREMAN 저장소의 원고 규칙을 본으로 삼고 이 저장소에 맞게 바꿨다.

모든 저장소에 같은 원고 기준은 FOREMAN `docs/manuscript_rules.md`(사람이 승인한 문서) 한 곳에 있고, 이 파일에는 이 저장소만 다른 것만 둔다(2026-11-17 문서 도구 합치기 4단계). 아래에서 「기준 문서」는 그 파일이다.

## 1. 차례 (고정)

원고의 첫 `# ` 줄은 「번호 제목」이다(예: `# 00 전체 그림`, `# 02-01 VM 다섯 대와 랜카드 둘`). 게시기가 이 줄을 노션 페이지 제목으로 쓴다(`.foreman/notion.toml`의 `title="h1"`). 번호는 아래 표의 번호 그대로다(2026-11-17 사용자). FOREMAN은 하위 편에 번호를 달지 않지만 여기서는 단다.

| 번호 | 원고 파일 | 제목(첫 `# ` 줄의 번호 뒤) | 다루는 곳 |
| --- | --- | --- | --- |
| 00 | `notion/00_overview.md` | 전체 그림 | `README.md` |
| 01 | `notion/01_server.md` | 서버와 호스트 OS | `docs/history/notion_hardware_20261116.md` |
| 01-01 | `notion/01_server/01_network.md` | 사무실 망과 서버 | 같음 |
| 01-02 | `notion/01_server/02_os_driver.md` | OS와 드라이버 | 같음 |
| 01-03 | `notion/01_server/03_remote.md` | 원격 접속 | 같음 |
| 02 | `notion/02_nodes.md` | 가상 머신과 노드 | `cluster/` |
| 02-01 | `notion/02_nodes/01_vms.md` | VM 다섯 대와 랜카드 둘 | `cluster/Vagrantfile` |
| 02-02 | `notion/02_nodes/02_setup.md` | 노드 설치 | `cluster/setup-node.sh` |
| 02-03 | `notion/02_nodes/03_roles.md` | 역할 라벨과 워커 증설 | `cluster/label-nodes.sh` |
| 03 | `notion/03_kubernetes.md` | 쿠버네티스 설치와 파드 망 | `platform/versions.yaml`, `platform/coredns/` |
| 04 | `notion/04_ingress.md` | 들어오는 문 | `platform/metallb/`, `platform/ingress-nginx/` |
| 05 | `notion/05_public.md` | 바깥 공개와 인증서 | `apps/cloudflared/`, `platform/cert-manager/` |
| 05-01 | `notion/05_public/01_path.md` | 공개 경로와 내부 경로 | `apps/cloudflared/` |
| 05-02 | `notion/05_public/02_tls.md` | TLS가 끝나는 곳 | `platform/cert-manager/` |
| 06 | `notion/06_gitops.md` | GitOps | `bootstrap/`, `platform/argocd/`, `apps/*/app.yaml` |
| 07 | `notion/07_registry.md` | 이미지 저장소 | `platform/harbor/`, `apps/harbor-backup/`, `scripts/host-nfs-harbor-backup-setup.sh` |
| 08 | `notion/08_build.md` | 빌드와 태그 고정 | `platform/jenkins/`, `scripts/make-deploy-keys.sh`, `apps/*/kustomization.yaml` |
| 09 | `notion/09_deploy.md` | 앱이 올라가는 길 | `apps/petmint/app/`, `apps/petmint/jobs/`, `apps/petmint/scripts/`, `apps/petmint/README.md`, `apps/runshoes/app/`, `apps/runshoes/scripts/`, `apps/runshoes/README.md`, `apps/runshoes/runbooks/` |
| 09-01 | `notion/09_deploy/01_manifests.md` | 매니페스트의 꼴 | `apps/petmint/app/`, `apps/runshoes/app/` |
| 09-02 | `notion/09_deploy/02_first_deploy.md` | 처음 배포와 시크릿 | `apps/petmint/scripts/`, `apps/runshoes/scripts/create-secrets.sh`, `apps/petmint/jobs/` |
| 09-03 | `notion/09_deploy/03_versions.md` | 버전이 바뀌는 길 | `apps/runshoes/runbooks/`, `apps/runshoes/scripts/check-image-migrations.sh` |
| 10 | `notion/10_database.md` | 데이터베이스 복제와 백업 | `apps/petmint/mysql/`, `apps/runshoes/mysql/`, `apps/petmint/backup/`, `scripts/mysql-replica-seed.sh`, `scripts/mysql-replica-check.sh` |
| 11 | `notion/11_gpu.md` | GPU와 호스트 서비스 | `scripts/host-gpu-exporter.sh` |
| 12 | `notion/12_monitoring.md` | 모니터링 | `apps/monitoring/` |
| 12-01 | `notion/12_monitoring/01_metrics.md` | 지표 | `apps/monitoring/prometheus/`, `apps/monitoring/node-exporter/`, `apps/monitoring/kube-state-metrics/`, `apps/monitoring/json-exporter/` |
| 12-02 | `notion/12_monitoring/02_logs.md` | 로그 | `apps/monitoring/loki/`, `apps/monitoring/alloy/` |
| 12-03 | `notion/12_monitoring/03_dashboards.md` | 대시보드 | `apps/monitoring/grafana/` |
| 13 | `notion/13_storage.md` | 공유 저장소 | `apps/petmint/data/nfs.yaml` |
| 14 | `notion/14_operations.md` | 운영 규칙과 문서 게시 | `CLAUDE.md`, `.foreman/notion.toml`, `.foreman/docs.toml`, `.gitignore`, `scripts/docs-check.py`, `scripts/docs_for_code.py`, `scripts/foreman_tool.py` |

개발자 문서는 같은 번호로 `docs/00_overview.md` ~ `docs/14_operations.md` 한 편씩이다(하위 편 없이 한 파일). 다루는 곳은 원고의 그 편과 하위 편을 합친 것이다.

하위 폴더가 있는 편은 위 파일(예: `notion/05_public.md`)이 그 편의 머리글이다. 머리글은 그 편 전체를 두세 문단으로 안내하고, 자세한 것은 하위 편에 둔다.

## 2. 머리 주석

모든 편(원고와 개발자 문서 모두)의 맨 첫 줄부터 이 주석을 둔다. 게시기가 노션 판에서 뗀다.

```
<!--
다루는 곳: cluster/Vagrantfile, cluster/label-nodes.sh
읽은 커밋: <읽은 커밋>
-->
# 02-01 VM 다섯 대와 랜카드 둘
```

다루는 곳은 그 편이 덮는 저장소 파일이다. 덮기 점검(문서 폴더 밖 파일이 모두 원고 어느 편에 드는지)만 이 칸을 읽고, 거꾸로 찾기는 이 칸을 읽지 않고 근거 표시만 읽는다(2026-11-17 FOREMAN 문서 도구 합치기). 여러 얘기가 섞인 파일을 덮는다고 그 파일이 바뀔 때마다 걸리지 않는다.

읽은 커밋은 편마다 적는다(2026-11-17부터. 그 전에는 모든 편이 같은 값이었다). 그 커밋 뒤에 생긴 파일은 근거로 걸 수 없다.

근거의 내용은 그대로이고 줄 번호만 밀렸을 때는 줄 번호만 고치고 읽은 커밋은 올리지 않는다. 읽은 커밋은 그 편을 실제로 열어 내용을 확인한 커밋에만 적는다(2026-11-17 사용자).

## 3. 근거 표시

사실을 말하는 문장 끝에 대괄호로 단다. 숫자나 인용이 있는 문장에는 반드시 단다. 종류는 셋이다.

- `[code:경로]` 또는 `[code:경로:줄]`, `[code:경로:줄-줄]`: 저장소 맨 위에서 본 파일이나 폴더(끝이 `/`)
- `[docs:경로]` 또는 줄 붙임: `docs/` 아래 경로. 예: `[docs:history/cluster_state_20261116.md:12-18]`
- `[c:커밋]`: 커밋

줄 번호는 읽은 커밋의 파일 기준이다. 줄 범위는 그 사실이 실제로 적힌 줄을 가리킨다. 기계 점검은 파일과 줄 범위만 보므로, 줄이 사실과 맞는지는 쓰는 사람이 직접 열어 확인한다.

근거로 쓸 수 있는 곳의 우선순위는 이렇다. 먼저 코드와 설정(`[code:]`), 다음 지금 상태 확인 기록(`docs/history/cluster_state_20261116.md`), 사람이 답한 까닭(`docs/history/human_answers_20261116.md`), 노션 하드웨어 사실(`docs/history/notion_hardware_20261116.md`), 마지막으로 옛 문서(`docs/history/build_log/`)다. 옛 문서는 구축할 때의 기록이라 지금과 다를 수 있다. 옛 문서에만 있는 값은 코드나 상태 기록과 맞춰 본 뒤에만 쓰고, 다르면 지금 상태를 따른다. 까닭(왜 이렇게 했나)은 옛 문서에서 가져와도 된다.

옛 기록(`docs/history/`)을 근거로 걸 때의 범위 규칙은 기준 문서 1절을 따른다. 이 저장소에서 그 사이에 바뀌기 쉬운 것은 노드 수, 호스트 수, 인증서 유무다. 예: 앱 주소만 있던 때 쓴 인증서 확인 까닭을 운영 도구 주소까지 넓혀 쓴 일, 학교 vcluster의 traefik에서 겪은 리다이렉트를 지금 ingress-nginx에 옮겨 쓴 일이 있었다.

다른 편을 가리킬 때는 `→ 「제목」`으로 쓴다. 제목은 위 차례의 제목 그대로이고 번호는 붙이지 않는다.

## 4. 원고(notion/) 쓰는 법

독자, 깊이, 말투, 문단과 목록, 어려운 말 풀기, 지금 상태만 쓰기, 왜를 쓰기, em dash와 가운뎃점은 기준 문서 1, 2, 4절을 따른다. 아래는 이 저장소만 다른 것이다.

- 한 편은 대략 2,000~5,000자, 머리글 편은 그보다 짧게 쓴다
- 감탄과 비유 남발을 쓰지 않는다(기준 문서에 올라가면 이 줄은 기준 문서를 따른다)
- 어려운 말을 푸는 예: 「Ingress(바깥 요청을 주소와 경로에 따라 알맞은 서비스로 나눠 주는 규칙)」
- 이력은 `docs/history/`의 몫이다
- 명령어와 설정 조각은 꼭 필요할 때만 짧은 코드 블록으로 넣는다. 원고는 절차서가 아니다

원고에 넣지 않는 것(점검 스크립트가 막는다): IP 주소, 도메인, 홈 경로, 토큰 꼴 문자열, 포트 번호. 숫자 대신 역할로 쓴다. 예: 「클러스터 내부 주소」, 「사설 고정 대역의 주소 하나」, 「호스트에서 도는 추론 서버」, 「HTTPS 기본 포트」. 노드 이름(m-k8s, w1 ~ w4), 네임스페이스, 파일 경로, 이미지 판은 써도 된다. 이미지 이름에 도메인이 붙어 있으면(사설 레지스트리 주소 등) 도메인을 빼고 「사설 이미지 저장소의 runshoes 이미지」처럼 쓴다. 노드 역할 라벨의 키도 도메인 꼴이라 「역할 라벨」로 쓴다.

편의 끝은 이 순서로 둔다(없으면 뺀다): 「알려진 한계」(목록), 「용어 풀이」(목록).

말투 견본:

> 노드마다 랜카드가 둘 붙어 있다. 하나는 VM을 만드는 도구가 스스로 붙이는 관리용 망이고, 다른 하나는 클러스터가 쓰려고 따로 붙인 고정 주소 망이다. 관리용 망은 주소를 그때그때 나눠 받기 때문에 VM을 다시 켜면 주소가 바뀔 수 있다. 쿠버네티스의 노드들은 서로 쉬지 않고 말을 주고받으니, 주소가 바뀌는 망 위에 클러스터를 세울 수는 없었다. [docs:history/human_answers_20261116.md:7-9]

## 5. 개발자 문서(docs/NN_*.md) 쓰는 법

운영하는 사람이 지금 구성을 확인하고, 바꾸고, 다시 만들 때 보는 문서다. 원고와 같은 머리 주석과 근거 표시를 단다.

- 절은 이 순서다: 「지금 구성」, 「설정 자리」(파일:줄과 그 값이 뜻하는 것), 「바꾸거나 다시 만들기」(명령), 「확인」(명령과 기대 결과), 「알려진 한계」
- 목록과 표, 한 줄에 사실 하나, 말투는 기준 문서 3절을 따른다
- 사설 IP, 포트, 명령, 경로를 숫자 그대로 쓴다. 비밀값(토큰, 암호)은 쓰지 않는다. 외부에서 들어오는 포트포워딩 번호와 공유기 주소도 쓰지 않는다
- 지금 상태만 쓴다. 이력은 `docs/history/`를 가리킨다

## 6. 포트폴리오(portfolio/) 쓰는 법

2026-11-17 사용자 지시 20. 읽는 사람은 채용 담당자와 면접관이다. 기술문서가 「어떻게 돌아가는가」를 말한다면, 포트폴리오는 「무엇을 만들었고, 왜 그렇게 했고, 막혔을 때 어떻게 풀었나」를 말한다. 저장소를 열지 않아도 글만으로 읽혀야 한다.

축은 결정 중심을 골랐다(축을 고르는 법과 결정 중심의 차례는 기준 문서 5절). 한 편이 갈림길 하나를 다루고, 편 순서는 바깥 요청이 서비스에 닿는 길을 따른다.

| 번호 | 파일 | 제목(첫 `# ` 줄) |
| --- | --- | --- |
| 00 | `portfolio/00_overview.md` | 한눈에 보는 홈랩 |
| 01 | `portfolio/01_kubeadm.md` | 손으로 세운 여러 노드 클러스터 |
| 02 | `portfolio/02_two_nics.md` | 랜카드 둘: 관리망과 고정망 |
| 03 | `portfolio/03_one_door.md` | 문은 하나만: MetalLB와 ingress-nginx |
| 04 | `portfolio/04_tunnel.md` | 포트포워딩 없이 공개하기 |
| 05 | `portfolio/05_tls.md` | TLS가 끝나는 곳과 noTLSVerify를 확인한 일 |
| 06 | `portfolio/06_gpu.md` | GPU는 호스트에, 파드는 불러 쓰기만 |
| 07 | `portfolio/07_delivery.md` | 사람 손을 타지 않는 배포 |
| 08 | `portfolio/08_monitoring.md` | 모니터링은 차트 대신 매니페스트로 |
| 09 | `portfolio/09_scale_out.md` | 워커를 늘리고 옮기기 |
| 10 | `portfolio/10_docs.md` | 문서를 기계로 검사하기 |
| 11 | `portfolio/11_limits.md` | 하지 않은 것과 한계 |

제목에는 번호를 붙이지 않는다. 게시기가 파일 이름의 번호를 앞에 붙인다.

- 머리 주석과 근거 표시는 기술문서와 같다. 읽은 커밋도 편마다 적는다
- 말투(경어체), 날짜를 쓰지 않기, 어려운 말 풀기, 하지 않은 것을 한 것처럼 쓰지 않기, 옛 기록 범위는 기준 문서 1, 2, 5절을 따른다. 이 저장소는 목록을 「치른 값」에도 쓴다
- 편의 차례: 첫머리 `> 이 글은 …을 다룹니다.` 한 줄, 굵은 한두 문장 요약, 그다음 「상황」, 「고른 것」, 「까닭」, 「치른 값」, 막힌 일이 있었으면 「막혔을 때」. 절 제목은 `##`로 편마다 맞게 바꿔도 된다
- 설정값을 늘어놓지 않는다. 코드 블록은 넣더라도 몇 줄로 줄인다
- 금지값: IP, 토큰, 홈 경로, 포트. 도메인은 ronanlab.dev만 쓸 수 있다
- 그림은 `![설명](img/NN_이름.png)`. 설명에 무엇을 가렸는지 적는다

## 7. 점검

```
python3 scripts/docs-check.py        # 틀린 것 0이어야 한다
python3 scripts/docs-check.py -v     # 근거 없는 숫자 줄도 본다
python3 scripts/docs_for_code.py <코드 파일 경로>               # 그 코드를 가리키는 문서와 줄
python3 scripts/docs_for_code.py --range main...HEAD --unfixed  # 이 브랜치가 바꾼 것으로 걸리는데 안 고친 문서
```

두 명령은 FOREMAN 문서 도구(`tools/docs.py`의 `check`, `refs`)를 부르는 껍데기다(2026-11-17 문서 도구 합치기). 규칙은 FOREMAN에 있고, 이 저장소만의 값은 `.foreman/docs.toml`에 있다. FOREMAN 폴더는 환경 변수 `FOREMAN_DIR`가 먼저이고, 없으면 `scripts/foreman_tool.py`의 기본 경로를 쓴다. 둘 다 못 찾으면 종료 코드 2로 멈춘다. 점검이나 거꾸로 찾기의 규칙을 고칠 일은 FOREMAN 관리자에게 부탁한다.

코드를 고치는 세션은 그 코드를 가리키는 문서도 같은 브랜치에서 고친다. 어느 문서가 걸리는지는 `python3 scripts/docs_for_code.py`로 본다. 고칠 수 없으면 무엇이 걸리는지 보고한다(2026-11-17 사용자). 디자이너와 조사 세션에는 적용하지 않는다.
