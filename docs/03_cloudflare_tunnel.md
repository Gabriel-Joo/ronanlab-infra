# 03. Cloudflare Tunnel 연결

도메인 `ronanlab.dev`(Cloudflare)에 터널 두 개가 있다. 클러스터 공용 터널 `ronanlab-tunnel`은 클러스터 안 cloudflared Pod 2개가 공개 주소 7개를 ingress-nginx로 보내고, 호스트의 `ollama-tunnel`은 학교 PC가 서버의 Ollama를 부르는 데만 쓴다.

- 날짜: 2026-09-22 도메인 구매 · ollama-tunnel(RUNSHOES 시절), 2026-10-13 ronanlab-tunnel 생성(그때 이름 petmint-tunnel), 2026-10-18 `cloudflared` 네임스페이스로 이전 · runshoes 호스트 추가, 2026-11-02 ArgoCD Application으로, 2026-11-09 ollama Access 정책 다시 걸음, 2026-11-11 grafana · prometheus 추가, 2026-11-12 코드 · 클러스터와 맞춤
- 범위: 도메인, cloudflared 설치 · 로그인, 두 터널, Access Service Token(ollama), 터널 Pod 운영. 호스트별 Access 정책의 자세한 설계는 펫퍼민트 저장소 `~/AI_programming/petmint-rag-chatbot/docs/02_pipeline/13_access_and_tunnel.md`, 학교 vcluster 시절의 runshoes-tunnel · 앱 코드 · CI는 [history/cloudflare_tunnel_vcluster.md](history/cloudflare_tunnel_vcluster.md), ingress-nginx · MetalLB는 [02_metrics_storage_ingress.md](02_metrics_storage_ingress.md)
- 코드: apps/cloudflared/(app.yaml, kustomization.yaml, configmap.yaml, deployment.yaml, README.md), 호스트 `~/.cloudflared/config.yml`(ollama-tunnel, 저장소 밖)

## 1. 지금 구성

2026-11-12 기준. 운영 절차(처음 한 번, 바꿀 때, 확인)는 [apps/cloudflared/README.md](../apps/cloudflared/README.md)가 원본이고 여기서는 값만 적는다.

### 도메인 · 계정

| 항목 | 값 |
| --- | --- |
| 도메인 | `ronanlab.dev`(Cloudflare Registrar, $12.20/년). DNS Zone도 Cloudflare |
| 터널 관리 | locally-managed(설정 파일 방식). 호스트 `~/.cloudflared/`에 계정 인증서 `cert.pem`과 터널 자격증명 JSON 2개 |
| 호스트 cloudflared | `/usr/bin/cloudflared` 2026.9.1(실행 때 2026.10.7로 올리라는 경고가 나온다) |
| Access | Zero Trust 대시보드에서 사람이 건다. 저장소에는 없다 |

`cloudflared tunnel list`(2026-11-12 호스트에서):

```txt
ID                                   NAME            CREATED              CONNECTIONS
81af3e6c-7f36-4f88-a517-9774b60fa650 ollama-tunnel   2026-09-22T06:25:43Z 1xicn01, 2xicn06, 1xicn07
02ad6a13-ce45-4262-a32a-40241bf034dc ronanlab-tunnel 2026-10-13T08:42:52Z 2xicn01, 1xicn05, 4xicn06, 1xicn07
```

터널은 이 둘뿐이다. 학교 vcluster 시절의 `runshoes-tunnel`(`3f8ecf07-...`)은 목록에 없다(Cloudflare에서 지워졌다. 언제 지웠는지는 기록이 없다).

### ronanlab-tunnel (클러스터 공용)

| 항목 | 값 | 근거 |
| --- | --- | --- |
| 터널 | `ronanlab-tunnel`, ID `02ad6a13-ce45-4262-a32a-40241bf034dc`(만들 때 이름 `petmint-tunnel`) | `apps/cloudflared/configmap.yaml:11`, `cloudflared tunnel list` |
| ArgoCD Application | `cloudflared`, path `apps/cloudflared`, `targetRevision: main`, **수동 Sync**(automated 없음), prune 없음, finalizer 없음, `CreateNamespace=false` | `apps/cloudflared/app.yaml`, cluster_snapshot(`AUTO <none>`, Synced, Healthy) |
| 네임스페이스 | `cloudflared`(사람이 만든다) | `apps/cloudflared/kustomization.yaml:9` |
| Secret | `cloudflared-credentials`(키 `credentials.json`, 사람이 만든다. 저장소에 없다) | `apps/cloudflared/deployment.yaml:75-77` |
| Deployment | `cloudflared`, replicas 2, RollingUpdate maxSurge 1 · maxUnavailable 0, 이미지 `cloudflare/cloudflared:2026.10.0` | `apps/cloudflared/deployment.yaml:13-19,38`, cluster_snapshot |
| Pod 배치 | w1-k8s, w2-k8s 각 1개(topologySpreadConstraints `ScheduleAnyway`, 선호일 뿐) | cluster_snapshot |
| Probe | readiness `/ready`(5초), liveness `/ready`(10초, 처음 10초 대기), 포트 2000(metrics) | `apps/cloudflared/deployment.yaml:50-60` |
| 자원 | requests cpu 50m · memory 64Mi, limits memory 128Mi | `apps/cloudflared/deployment.yaml:68-73` |
| 원점 | 7개 전부 `https://ingress-nginx-controller.ingress-nginx.svc.cluster.local:443`, `noTLSVerify: true`. 마지막 규칙 `http_status:404` | `apps/cloudflared/configmap.yaml` |

공개 주소 7개(ConfigMap 순서):

| 호스트 | 더한 날 | Access(대시보드, 저장소 밖) |
| --- | --- | --- |
| petmint.ronanlab.dev | 2026-10-13 | 없음. 데모 공개를 위해 사용자가 지웠다, 앱 로그인(`PETMINT_AUTH=app`)이 받는다(펫퍼민트 docs 13 「Access 정책」) |
| argocd.ronanlab.dev | 2026-10 (10단계, [04_argocd.md](04_argocd.md)) | 운영자만(운영 도구 Application 하나) |
| harbor.ronanlab.dev | 2026-10 ([05_harbor.md](05_harbor.md)) | 운영자만 |
| jenkins.ronanlab.dev | 2026-10 ([06_jenkins.md](06_jenkins.md)) | 운영자만 |
| runshoes.ronanlab.dev | 2026-10-18 | 없음(공개 사이트) |
| grafana.ronanlab.dev | 2026-11-11 | 운영 도구 Application(`apps/cloudflared/configmap.yaml:35`) |
| prometheus.ronanlab.dev | 2026-11-11 | 운영 도구 Application |

Access 칸은 저장소 주석과 펫퍼민트 docs 13에 적힌 것을 옮겼다. 대시보드는 직접 보지 않았다.

### ollama-tunnel (호스트)

| 항목 | 값 |
| --- | --- |
| 터널 | `ollama-tunnel`, ID `81af3e6c-7f36-4f88-a517-9774b60fa650` |
| 실행 | 호스트 systemd `cloudflared-ollama.service`(enabled, active running). `/usr/bin/cloudflared tunnel --config /home/kopo17/.cloudflared/config.yml run ollama-tunnel` |
| 설정 | `~/.cloudflared/config.yml`: `ollama.ronanlab.dev` → `http://localhost:11434`, 나머지 `http_status:404` |
| 원점 | 호스트 Docker 컨테이너 `ollama`(11434) |
| 쓰는 곳 | **학교 PC 전용.** 펫퍼민트 · 런슈즈 Pod는 쓰지 않고 `http://192.168.122.1:11434`로 직접 부른다(`apps/petmint/app/configmap.yaml:23`, `apps/runshoes/app/deployment.yaml:92,135`) |
| Access | Access 앱 `ollama.ronanlab.dev`, 정책 Action **Service Auth** + Include Service Token **`ollama-school-pc`**(2026-11-09 다시 걸음). 토큰은 `runshoes-ollama-token`의 이름을 바꾼 것 |

저장소에는 이 터널을 쓰는 곳이 없어 안 쓰는 터널로 보이지만 끄면 안 된다. 호스트 systemd `cloudflared-runshoes`와 `~/.cloudflared-runshoes/`는 없다(host_snapshot).

## 2. 왜 이렇게 했나

### Cloudflare와 Cloudflare Tunnel

Cloudflare는 전 세계에 엣지 서버를 깔아 둔 회사다. `ronanlab.dev`로 들어온 요청은 내 서버로 바로 가지 않고 먼저 Cloudflare 엣지를 거친다. 그 사이에 DDoS 방어, 캐싱, HTTPS 인증서, DNS 관리를 Cloudflare가 한다. `ronanlab.dev`도 Cloudflare가 등록을 대행했고 DNS도 Cloudflare가 관리한다.

집 · 사내 서버를 외부에 공개하는 전통적인 방법은 **포트포워딩**이다. 공유기에 "80번 포트로 들어오면 서버로 보내라"고 설정하는 것. 그런데 문제가 많다.

| 문제 | 설명 |
| --- | --- |
| IP가 바뀜 | 가정용 회선은 고정 IP가 아니라 재접속 시 주소가 달라진다 |
| 보안 | 공유기에 구멍을 뚫는 것이라 그 포트로 누구나 접근을 시도할 수 있다 |
| 망 제약 | 학교 · 회사 망이면 애초에 포트포워딩 권한이 없다 |

**Cloudflare Tunnel은 방향을 뒤집는다.** 서버가 Cloudflare로 **아웃바운드 연결을 먼저 맺고**, 그 연결을 계속 유지한다. 외부 요청이 들어오면 Cloudflare가 그 연결을 통해 전달한다.

```txt
[외부 요청] → Cloudflare 엣지 → (이미 열린 연결) → cloudflared → 내부 서비스
```

인바운드 포트를 하나도 열지 않으므로 공유기 설정이 필요 없고, NAT가 자동으로 통과시킨다. 카카오톡이 공유기 설정 없이 메시지를 받는 것과 같은 원리다. 공인 IP가 바뀌어도 상관없고, 도메인 이름은 고정이라 안에서 서버가 어떻게 바뀌든 밖에서 보는 주소는 그대로다.

서버는 kopo17 · kopo02가 같이 쓰는 공유 서버다. cloudflared는 아웃바운드 연결만 만들고 공유기 설정 테이블에 아무것도 더하지 않는다. 본인 계정 안에서만 도는 프로세스라 다른 사용자의 서비스 · 네트워크에 영향이 없다.

### 기존 터널 자산 (RUNSHOES에서 구축)

이 클러스터를 세우기 전, 같은 GPU 서버에 이미 터널 두 개가 돌고 있었다(2026-10-13 당시 `cloudflared tunnel list`).

```txt
ID                                   NAME            CREATED              CONNECTIONS
81af3e6c-7f36-4f88-a517-9774b60fa650 ollama-tunnel   2026-09-22T06:25:43Z 2xicn06, 2xicn07
3f8ecf07-62fb-40a7-a9c4-07c1fb57fbe2 runshoes-tunnel 2026-09-22T06:59:52Z 2xicn05, 2xicn06
```

| 터널 | 용도 | 비고 |
| --- | --- | --- |
| ollama-tunnel | `ollama.ronanlab.dev` → 호스트의 Ollama(localhost:11434) | Access Service Auth + Service Token(`ollama-school-pc`, 2026-11-09 다시 걸음). 학교 PC 전용, 펫퍼민트 · 런슈즈 Pod는 쓰지 않는다 |
| runshoes-tunnel | `runshoes.ronanlab.dev` → 학교 vcluster의 traefik | 2026-10-18 RUNSHOES 이주 뒤 쓰지 않는다. `runshoes.ronanlab.dev`는 ronanlab-tunnel의 다섯 번째 호스트가 됐다. 호스트 프로세스도 돌지 않고(2026-11-09 확인), 2026-11-12 터널 목록에도 없다 |

**ollama-tunnel을 왜 만들었나 (처음 용도)**: RUNSHOES가 학교 vcluster에서 돌고 있었는데, 리뷰 요약 · 챗봇 기능이 서버의 Ollama를 호출해야 했다. 학교 망에서 이 서버로 직접 들어올 방법이 없어 터널로 고정 주소(`ollama.ronanlab.dev`)를 만들었다(자세한 것은 [history/cloudflare_tunnel_vcluster.md](history/cloudflare_tunnel_vcluster.md)).

**지금 용도, 학교 PC 전용**: RUNSHOES는 2026-10-18 이 클러스터로 옮겨졌고, 그 Pod는 Ollama를 `http://192.168.122.1:11434`로 직접 부른다. 지금 이 터널을 쓰는 것은 학교 PC뿐이다(환경이 달라 서버의 Ollama API를 이 터널로 부른다). 보호는 Access Service Auth(토큰 `ollama-school-pc`).

**기존 실행 방식 확인** (2026-10-13 당시):

```bash
ps aux | grep cloudflared | grep -v grep
```

```txt
/usr/bin/cloudflared tunnel --config /home/kopo17/.cloudflared-runshoes/config.yml run runshoes-tunnel
/usr/bin/cloudflared tunnel --config /home/kopo17/.cloudflared/config.yml run ollama-tunnel
```

**터널마다 config 파일과 프로세스를 따로 두는 방식**이다. 호스트에서 직접 실행했다. 지금은 아래쪽(ollama-tunnel) 하나만 돈다.

### 설계 결정: 호스트 프로세스 vs 클러스터 Pod

petmint-tunnel을 같은 방식(호스트 프로세스)으로 만들 수도 있었지만, **클러스터 안 Pod로 띄우기로 했다.**

|  | 호스트 프로세스 | 클러스터 Pod (채택) |
| --- | --- | --- |
| 작업량 | config 작성 + systemd 등록 | Secret + ConfigMap + Deployment |
| 장애 복구 | 프로세스가 죽으면 수동 재시작(systemd `Restart=on-failure`는 있다) | livenessProbe로 K8s가 자동 재시작 |
| 이중화 | 수동으로 프로세스를 여러 개 | `replicas: 2`로 선언 |
| 설정 관리 | 호스트 파일 시스템 | ConfigMap, 지금은 git(`apps/cloudflared/configmap.yaml`) |
| CKA 연관 | 없음 | Secret · Deployment · Probe를 직접 다룸 |

RUNSHOES는 호스트 방식, 펫퍼민트는 클러스터 방식으로 **발전한 흐름**이 되기도 한다. RUNSHOES도 2026-10-18 이 클러스터로 옮겨오면서 같은 터널의 호스트가 됐다.

### 설계 결정: 터널이 nginx-ingress를 바라본다

터널이 앱을 직접 가리키게 하면, 앱을 추가할 때마다 터널 설정을 고쳐야 한다. 대신 **Ingress Controller 하나만** 가리키면:

```txt
터널 → nginx-ingress ─┬→ petmint API
                      ├→ petmint UI
                      └→ (나중에 추가되는 앱)
```

새 앱은 **Ingress 리소스만 추가**하면 된다. 2026년 Cloudflare 가이드에서도 이 패턴을 권장한다. 다만 locally-managed 터널은 ConfigMap에 hostname을 하나씩 적어야 해서, 새 공개 주소를 더할 때는 ConfigMap 한 줄과 DNS CNAME도 같이 더한다(2026-10-18 runshoes, 2026-11-11 grafana · prometheus가 그렇게 들어왔다). 호스트 구분은 nginx가 Host 헤더로 한다.

### 원점 설정 세 가지: https, noTLSVerify, httpHostHeader

2026-09-22 runshoes-tunnel을 붙이며 403 → 301 → 200 순서로 하나씩 벗겨 낸 것이다(그때 원점은 학교 vcluster traefik). 지금 ConfigMap에도 그 교훈이 남아 있다.

1. **`service`를 `https://`로 쓴다.** `http://`로 쓰면 Ingress Controller(그때 traefik, 지금 ingress-nginx)가 HTTPS로 301 리다이렉트를 건다. 그 리다이렉트가 다시 터널로 돌아와 루프가 생길 수 있다
2. **`noTLSVerify: true`**: Ingress Controller의 내부 인증서(ingress-nginx 기본 인증서는 self-signed)는 검증이 실패한다. 클러스터 내부 통신이고 Cloudflare Tunnel 자체가 암호화된 통로라 검증을 끈다
3. **`originRequest.httpHostHeader`**: Ingress Controller는 Host 헤더로 라우팅한다. 공개 주소와 Ingress의 host가 다르면(그때 공개 `runshoes.ronanlab.dev`, Ingress `kopo17-runshoes.std.kopoctc.kr`) cloudflared가 원점에 보낼 Host를 이 옵션으로 바꿔 준다. **지금 클러스터는 Ingress host가 공개 주소와 같아서 이 옵션을 쓰지 않는다**(`apps/cloudflared/configmap.yaml`에 없다)

**Host 헤더는 클라이언트에서 바꾸면 안 된다.** 2026-09-22에 이렇게 시험했다:

```bash
curl -H "Host: kopo17-runshoes.std.kopoctc.kr" https://runshoes.ronanlab.dev/
```

Cloudflare 엣지 자체가 **403 Forbidden**(`server: cloudflare`, 우리 서버 응답이 아니다)을 돌려준다. 요청 도메인과 다른 Host 헤더를 실어 보내는 것은 **도메인 프런팅**으로 간주되어 차단된다. Host 헤더 조작은 클라이언트가 아니라 **cloudflared 설정 안에서**(`httpHostHeader`) 해야 한다.

**서비스 주소가 FQDN인 이유**: `ingress-nginx-controller.ingress-nginx.svc.cluster.local`은 K8s 내부 DNS 이름이다. cloudflared Pod(처음 petmint, 지금 cloudflared 네임스페이스)와 대상(ingress-nginx 네임스페이스)의 네임스페이스가 달라서 네임스페이스를 포함한 전체 이름이 필요하다.

### Access와 Service Token

Cloudflare Tunnel은 경로를 암호화해서 전달할 뿐 **"누가 접근 가능한지"를 제한하지 않는다.** 터널만 뚫으면 도메인 주소를 아는 누구나 부를 수 있다. 그래서 Access를 앞에 둔다.

- **Cloudflare Access**: 사람이 브라우저로 로그인(이메일 OTP, OAuth 등)하는 큰 틀의 기능
- **Service Token**: 그 Access 안에서 "사람이 아니라 앱이 자동으로 인증하는" 하위 방식. 요청마다 `CF-Access-Client-Id` · `CF-Access-Client-Secret` 헤더를 붙인다

택일 문제가 아니다. `ollama.ronanlab.dev`를 부르는 주체는 사람이 아니라 프로그램(처음 RUNSHOES 앱, 지금 학교 PC)이므로 Service Token을 쓴다. 정책 Action은 **Service Auth**여야 한다. Selector에 Service Token만 넣고 Action을 기본값 Allow로 두면 Cloudflare가 직접 경고한다:

> "For service tokens, use the Service Auth action, not Allow. Using Allow with only service token selectors requires users to authenticate via an identity provider too, which is likely a misconfiguration."

즉 Allow면 "사람 로그인도 추가로 요구하는" 정책이 되어 API 호출이 통과하지 못한다.

### k8s Secret은 암호화가 아니다

Secret 값은 **base64 인코딩일 뿐**이라 권한이 있으면 누구나 평문으로 되돌릴 수 있다. 그래도 쓰는 이유는 (1) git에 커밋되는 매니페스트에 실제 값이 박히는 것을 막고, (2) 일반 환경변수와 달리 `kubectl describe pod`에 값이 아니라 참조만 보이기 때문이다. "완전한 보안 금고"가 아니라 "최소한의 노출 방지 장치"로 이해하고 쓴다. 이 규모에서 Vault 같은 별도 시크릿 관리 도구는 오버스펙이라 들이지 않았다. 터널 자격증명 JSON은 저장소에 두지 않고 사람이 표준 입력으로 Secret을 만든다(README 「처음 한 번」).

### 이 Application은 자동 Sync를 켜지 않는다

ArgoCD · Jenkins · Harbor · Grafana UI가 전부 이 터널로 들어온다. 잘못된 커밋이 바로 반영되면 공개 주소 7개가 한꺼번에 안 보이고, 고칠 UI(ArgoCD)와 볼 UI(Grafana)도 같이 사라진다. 그래서 사람이 Sync를 누르고 롤링을 지켜본다(2026-11-11 다시 정함, 다른 Application은 자동). 터널 없이 쓰는 길은 m-k8s의 `kubectl`과, 호스트에서 MetalLB VIP로 부르는 것이다: `curl --resolve argocd.ronanlab.dev:443:192.168.122.240 https://argocd.ronanlab.dev/`([02_metrics_storage_ingress.md](02_metrics_storage_ingress.md)).

## 3. 진행 기록

### 2026-09-22 도메인 구매 (Cloudflare Registrar)

1. dash.cloudflare.com 가입(이미 있으면 로그인)
2. 왼쪽 메뉴 **Domain Registration** → 원하는 이름 검색
3. 사용 가능하면 **Purchase** → 등록자 정보(영문 주소) + 결제 정보(Billing address, 등록자 정보와 별개로 한 번 더) 입력 → **Register domain**
4. 구매하면 자동으로 Cloudflare DNS Zone으로 등록된다(별도 연결 작업 없음)

이름 고르기: `runshoes-ollama` 같은 프로젝트에 묶인 이름은 다른 프로젝트에 다시 쓰기 어렵고, `k8slab.dev` · `opslab.dev` 같은 인프라 이름은 마음에 들지 않았다. 영어 이름(Ronan)으로 `ronanlab`을 골랐다. `.com`은 이미 선점되어 `.dev`로 샀다($12.20/년, 개발자 도메인으로도 어울린다).

헷갈린 점: **Registrant information**(등록자 정보)과 **Billing address**(카드 청구지)가 별개의 폼이라 두 번 입력해야 한다. 주소는 영문으로 바꿔 넣는다(예: `<도로명 번지>, <동>-dong <호>-ho` 꼴).

### 2026-09-22 cloudflared 설치 · 로그인

GPU 서버(`kopo17-System-Product-Name`, 지금 이 호스트)에서 한다.

```bash
# 설치
curl -L https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64.deb -o cloudflared.deb
sudo dpkg -i cloudflared.deb

# 로그인 (브라우저 인증 URL이 뜨면 열어서 도메인 선택)
cloudflared tunnel login
```

로그인은 한 번만 하면 되고(계정 인증서 `~/.cloudflared/cert.pem`이 생긴다), 그 뒤 터널은 여러 개 만들 수 있다.

### 2026-09-22 ollama-tunnel

```bash
# 터널 생성
cloudflared tunnel create ollama-tunnel

# 서브도메인 연결
cloudflared tunnel route dns ollama-tunnel ollama.ronanlab.dev

# 설정 파일 작성 (~/.cloudflared/config.yml)
cat > ~/.cloudflared/config.yml << 'EOF'
tunnel: ollama-tunnel
credentials-file: /home/kopo17/.cloudflared/<터널ID>.json
ingress:
  - hostname: ollama.ronanlab.dev
    service: http://localhost:11434
  - service: http_status:404
EOF
```

`<터널ID>`는 `cloudflared tunnel create` 결과에 나온 값으로 바꾼다(또는 `ls ~/.cloudflared/`로 확인).

**테스트 실행**(systemd 등록 전 확인용):

```bash
cloudflared tunnel --config ~/.cloudflared/config.yml run ollama-tunnel
```

로그에 CONNECTIVITY PRE-CHECKS 4개 항목(DNS Resolution, UDP/TCP Connectivity, Cloudflare API)이 모두 PASS로 뜨면 정상이다.

**검증**(다른 터미널에서):

```bash
curl https://ollama.ronanlab.dev/api/tags
```

Ollama에 설치된 모델 목록(JSON)이 오면 성공이다. Ollama 컨테이너가 꺼져 있으면 502가 뜬다. `docker ps | grep ollama`로 확인하고 `docker start ollama`. 이 시점의 `ollama.ronanlab.dev`는 **누구나 접근할 수 있는 상태**였다(아래 Access에서 잠갔다).

**systemd 등록**(재부팅 대응). 터미널 창을 띄워 두는 방식은 재부팅 · 세션 종료 때 끊긴다. VNC · Jupyter와 같이 systemd 서비스로 등록한다.

```bash
sudo tee /etc/systemd/system/cloudflared-ollama.service << 'EOF'
[Unit]
Description=Cloudflare Tunnel for Ollama
After=network.target docker.service

[Service]
Type=simple
User=kopo17
ExecStart=/usr/bin/cloudflared tunnel --config /home/kopo17/.cloudflared/config.yml run ollama-tunnel
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable cloudflared-ollama.service
sudo systemctl start cloudflared-ollama.service
systemctl status cloudflared-ollama.service --no-pager
```

`active (running)`이면 끝이다. 그때는 `cloudflared-runshoes.service`도 같이 등록했다(지금은 없다, [history/cloudflare_tunnel_vcluster.md](history/cloudflare_tunnel_vcluster.md)).

### 2026-09-22 ollama 엔드포인트 잠그기: Access + Service Token

**Service Token 발급**

1. dash.cloudflare.com → 왼쪽 메뉴 **Zero Trust** → 처음이면 팀 이름 설정(예: `ronanlab`) 후 Free 플랜
2. Zero Trust 대시보드 왼쪽 **Access controls** → **Service credentials**
3. **Create a Service Token** → 이름 지정(그때 `runshoes-ollama-token`, 지금 이름 `ollama-school-pc`) → 생성
4. 생성 직후 한 번만 보이는 **Client ID** · **Client Secret**을 안전한 곳에 보관한다(다시 볼 수 없다)

**Access Application으로 도메인 보호**

1. **Access controls** → **Applications** → **Add an application**
2. 상단 탭 **Self-hosted and private** → 그 안의 하위 탭 **Service auth**(기본으로 선택된 Public DNS 탭은 사람이 로그인하는 방식이라 맞지 않는다)
3. **Destinations → Public hostnames**: Subdomain `ollama`, Domain `ronanlab.dev`
4. **Access policies → Add a policy**
   - Policy Name: `service-token-only`
   - **Include**: Selector **Service Token**, Value에 위 토큰
   - **Action**: 반드시 **Service Auth**(2절 「Access와 Service Token」)
5. Save policy → 애플리케이션 저장

**검증**

```bash
# 토큰 없이 호출 → 차단(로그인/거부 페이지)되어야 정상
curl https://ollama.ronanlab.dev/api/tags
```

그때 앱 쪽(RUNSHOES `server.cjs` · `chatbot_server.py`)에 헤더를 붙이고 k8s Secret으로 넣은 것은 [history/cloudflare_tunnel_vcluster.md](history/cloudflare_tunnel_vcluster.md).

#### 트러블슈팅: Access 메뉴를 못 찾았다

**증상**: Cloudflare 대시보드 왼쪽 메뉴에 "Access"가 없다. "Service Auth" 메뉴도 없다.

**원인**: Access는 **Zero Trust**라는 별도 대시보드(`one.dash.cloudflare.com`)로 들어가야 한다. Zero Trust 진입 화면의 "Manage account"(Billing, API tokens 등 계정 관리)를 잘못 눌러 헛돌기도 했다. 메뉴 이름도 가이드에서 본 "Service Auth"가 아니라 **"Service credentials"**로 바뀌어 있었다.

**해결**: Zero Trust → Access controls → Service credentials. 문서 · 가이드와 실제 UI 메뉴 이름이 다를 수 있다.

#### 트러블슈팅: Access Application 탭 · Action 기본값

**증상**: Application을 만들 때 기본 선택 탭이 **Public DNS**(사람이 로그인하는 웹앱용), 정책 Action 기본값이 **Allow**다.

**원인**: 그대로 두면 사람 로그인까지 요구하는 잘못된 설정이 된다.

**해결**: 상단 **Service auth** 탭으로 바꾸고, Action을 **Service Auth**로 명시한다. Allow로 두면 Cloudflare가 경고를 띄워 준다(2절). 그 경고가 없었다면 놓치기 쉬운 지점이었다.

### 9-1단계: 터널 생성 (2026-10-13)

```bash
cloudflared tunnel create petmint-tunnel
```

```txt
Created tunnel petmint-tunnel with id 02ad6a13-ce45-4262-a32a-40241bf034dc
```

자격증명이 `~/.cloudflared/02ad6a13-ce45-4262-a32a-40241bf034dc.json`에 생긴다. 이 파일에 터널의 비밀키가 들어 있어, 나중에 k8s Secret으로 넣는다. 이름은 2026-10-18 `ronanlab-tunnel`로 바꿨다(ID는 그대로).

### 9-2단계: DNS 연결

#### 트러블슈팅: 엉뚱한 터널로 CNAME이 연결됨

**증상**

```bash
cloudflared tunnel route dns petmint-tunnel petmint.ronanlab.dev
```

```txt
INF Added CNAME petmint.ronanlab.dev which will route to this tunnel
    tunnelID=81af3e6c-7f36-4f88-a517-9774b60fa650
```

**`81af3e6c...`는 ollama-tunnel의 ID다.** 방금 만든 petmint-tunnel(`02ad6a13...`)이 아니다.

**원인**: `cloudflared`는 `--config` 없이 실행하면 기본 설정 파일 `~/.cloudflared/config.yml`을 읽는다. 그 파일에 `tunnel: ollama-tunnel`이 적혀 있어서, 명령줄에 `petmint-tunnel`을 썼는데도 config의 터널을 대상으로 삼았다. 2026-09-22 runshoes-tunnel 때도 같은 일을 겪었다(그때는 터미널 입력이 꼬인 줄 알았다). 그때 `--overwrite-dns`를 붙여 여러 번, 새 터미널에서도 다시 해 봤지만 계속 ollama-tunnel ID로 나왔다. config 파일 탓이었으니 옵션으로는 풀리지 않았던 것이다.

**해결**: Cloudflare 대시보드에서 잘못 생긴 CNAME을 지우고, config를 무시하도록 `--config /dev/null`을 붙여 다시 한다.

```bash
cloudflared tunnel --config /dev/null route dns \
  02ad6a13-ce45-4262-a32a-40241bf034dc petmint.ronanlab.dev
```

```txt
INF Added CNAME petmint.ronanlab.dev which will route to this tunnel
    tunnelID=02ad6a13-ce45-4262-a32a-40241bf034dc
```

대시보드에서 직접 고치는 길도 있다: dash.cloudflare.com → 도메인 → **DNS** → **Records** → 그 레코드의 **Target**을 `<터널 UUID>.cfargotunnel.com`으로 바꾼다(2026-09-22 runshoes-tunnel은 이것으로 해결했다).

> 이번엔 로그에 터널 ID가 찍혀서 바로 알아챘지만, **확인하지 않으면 모르고 넘어갈 수 있는 종류의 오류**다. 터널이 여러 개인 환경에서는 `route dns` 실행 후 반드시 대시보드에서 Target을 확인한다. 호스트에는 지금도 `~/.cloudflared/config.yml`(ollama-tunnel)이 있으므로 이 함정은 그대로 살아 있다.

### 9-3단계: 네임스페이스와 Secret

자격증명 파일을 m-k8s로 옮긴다(호스트에는 kubectl이 없고 VM 안에서 작업한다).

```bash
cd ~/k8s-cluster
vagrant ssh m-k8s -c "mkdir -p ~/cf"
cat ~/.cloudflared/02ad6a13-ce45-4262-a32a-40241bf034dc.json \
  | vagrant ssh m-k8s -c "cat > ~/cf/credentials.json"
```

m-k8s 안에서:

```bash
kubectl create namespace petmint

kubectl -n petmint create secret generic cloudflared-credentials \
  --from-file=credentials.json=$HOME/cf/credentials.json
```

**네임스페이스를 프로젝트별로 나누는 이유**(수업 Day8에서 확인): 같은 이름의 리소스가 네임스페이스마다 충돌 없이 공존한다. 나중에 runshoes를 이 클러스터로 옮길 때도 같은 이름의 Service · Ingress를 쓸 수 있다.

Secret이 암호화가 아니라는 점은 2절. 자격증명 파일 자체는 `.gitignore`로 관리했다. 2026-10-18 이전 때부터는 디스크에 복사본을 남기지 않고 표준 입력으로 넣는다(아래 「이후」).

### 9-4단계: ConfigMap (터널 라우팅 규칙)

```bash
kubectl -n petmint create configmap cloudflared-config --from-literal=config.yaml='
tunnel: 02ad6a13-ce45-4262-a32a-40241bf034dc
credentials-file: /etc/cloudflared/creds/credentials.json
ingress:
  - hostname: petmint.ronanlab.dev
    service: https://ingress-nginx-controller.ingress-nginx.svc.cluster.local:443
    originRequest:
      noTLSVerify: true
  - service: http_status:404
'
```

| 항목 | 의미 |
| --- | --- |
| `tunnel` | 어느 터널인지(UUID) |
| `credentials-file` | Secret이 마운트될 경로 |
| `hostname` → `service` | 이 주소로 들어오면 여기로 보낸다 |
| `http_status:404` | 매칭되지 않는 요청은 404(필수, 마지막 규칙은 catch-all이어야 한다) |

`https://` · `noTLSVerify` · FQDN을 쓰는 이유는 2절 「원점 설정 세 가지」.

### 9-5단계: Deployment

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: cloudflared
  namespace: petmint
spec:
  replicas: 2
  selector:
    matchLabels:
      app: cloudflared
  template:
    metadata:
      labels:
        app: cloudflared
    spec:
      containers:
        - name: cloudflared
          image: cloudflare/cloudflared:2026.10.0
          args:
            - --no-autoupdate
            - --config
            - /etc/cloudflared/config/config.yaml
            - --metrics
            - 0.0.0.0:2000
            - tunnel
            - run
          livenessProbe:
            httpGet:
              path: /ready
              port: 2000
            initialDelaySeconds: 10
            periodSeconds: 10
          ports:
            - containerPort: 2000
              name: metrics
          volumeMounts:
            - name: config
              mountPath: /etc/cloudflared/config
              readOnly: true
            - name: creds
              mountPath: /etc/cloudflared/creds
              readOnly: true
          resources:
            requests:
              cpu: 50m
              memory: 64Mi
            limits:
              memory: 128Mi
      volumes:
        - name: creds
          secret:
            secretName: cloudflared-credentials
        - name: config
          configMap:
            name: cloudflared-config
```

| 설정 | 이유 |
| --- | --- |
| `replicas: 2` | 터널은 여러 연결을 동시에 유지할 수 있다. 하나가 죽어도 서비스가 끊기지 않는다 |
| `--no-autoupdate` | 컨테이너가 스스로 업데이트하면 예기치 않게 재시작한다. 버전은 이미지 태그로 고정하는 것이 K8s 방식 |
| `--metrics 0.0.0.0:2000` | 명시하지 않으면 랜덤 포트를 쓴다. livenessProbe가 볼 포트를 고정 |
| `livenessProbe` | 호스트 프로세스 방식에는 없는 이점, 죽으면 K8s가 자동 재시작 |
| `requests/limits` | 수업 Day6에서 배운 QoS. 나중에 `kubectl top`으로 실측해 조정 |
| 이미지 태그 고정 | `latest`를 쓰면 재배포 때마다 버전이 달라질 수 있다 |

지금 `apps/cloudflared/deployment.yaml`은 이것에 readinessProbe · maxSurge/maxUnavailable · topologySpreadConstraints를 더한 것이다(아래 「이후」).

#### 트러블슈팅: ImagePullBackOff (VM의 DNS 불량)

**증상**

```txt
cloudflared-54cf9fcd7c-4s927   0/1     ErrImagePull        0          2s
cloudflared-54cf9fcd7c-bz55r   0/1     ImagePullBackOff    0          2s
```

```bash
kubectl -n petmint describe pod -l app=cloudflared | grep "Failed to pull"
```

```txt
Failed to pull image "cloudflare/cloudflared:2026.10.0":
failed to resolve image: dial tcp: lookup registry-1.docker.io
on 127.0.0.53:53: server misbehaving
```

VM 안에서 진단:

```bash
ping -c 2 8.8.8.8        # 성공, 네트워크 자체는 정상
nslookup registry-1.docker.io
# ** server can't find registry-1.docker.io: SERVFAIL
resolvectl status | head -10
# DNS Servers: 4.2.2.1 4.2.2.2 208.67.220.220
```

**원인**: `generic/ubuntu2204` 박스의 기본 DNS 서버(`4.2.2.1` 등)가 응답하지 않는다. 네트워크는 되는데 이름 해석만 실패하는 상태. `DNSSEC=yes`도 SERVFAIL에 기여할 수 있다.

**해결**: 그때 노드 4대 전부에 적용했다.

```bash
for vm in m-k8s w1-k8s w2-k8s w3-k8s; do
  vagrant ssh $vm -c "sudo mkdir -p /etc/systemd/resolved.conf.d && \
    printf '[Resolve]\nDNS=8.8.8.8 1.1.1.1\nFallbackDNS=8.8.4.4\nDNSSEC=no\n' \
    | sudo tee /etc/systemd/resolved.conf.d/dns.conf > /dev/null && \
    sudo systemctl restart systemd-resolved"
done
```

> VM을 재부팅하면서 드러난 문제다. 같은 날 **swap 재활성화**([01_cluster.md](01_cluster.md) 「재부팅 뒤 swap이 다시 켜졌다」)도 함께 겪었다. 이 DNS 설정은 2026-11-10부터 Vagrantfile 프로비저너가 넣는다(`cluster/Vagrantfile:25-29`). 새 노드(w4)가 같은 문제로 패키지를 못 받은 뒤 옮겼다. 둘 다 "클러스터 자체는 멀쩡한데 VM 레벨 설정이 풀려서" 생긴 것이다.

#### 트러블슈팅: CrashLoopBackOff인데 에러가 없음

**증상**: DNS를 고친 뒤 이미지는 받았지만, Pod가 20초마다 재시작을 반복했다.

```txt
NAME                           READY   STATUS             RESTARTS       AGE
cloudflared-54cf9fcd7c-4s927   0/1     CrashLoopBackOff   9 (3m30s ago)  20m
```

**로그를 보니 오히려 정상이었다**:

```txt
INF Registered tunnel connection connIndex=0 ... location=icn05 protocol=quic
INF Registered tunnel connection connIndex=1 ... location=icn06 protocol=quic
INF |  SUMMARY: Environment is healthy. cloudflared will use 'quic' as primary protocol. |
INF precheck complete hard_fail=false suggested_protocol=quic
```

연결 4개가 전부 등록됐고 사전 점검도 모두 PASS. 그런데 거기서 로그가 끝난다.

```bash
kubectl -n petmint describe pod -l app=cloudflared | grep -A3 "Last State"
```

```txt
Last State:     Terminated
  Reason:       Completed
  Exit Code:    0
```

**Exit Code 0: 에러로 죽은 게 아니라 "할 일을 마쳤다"고 스스로 종료한 것이다.** Deployment는 컨테이너가 계속 돌기를 기대하므로, 정상 종료해도 재시작시킨다.

**원인**: args 순서.

```yaml
args:
  - tunnel
  - --config
  - /etc/cloudflared/config/config.yaml
  - --no-autoupdate      # ← run 앞에 끼어 있음
  - run
```

`cloudflared`에서 `--no-autoupdate`, `--config` 같은 플래그는 **전역 플래그**라 서브커맨드(`tunnel run`) 앞에 와야 한다. 위 순서로는 `tunnel`의 인자로 해석되어, 사전 점검만 하고 실제 실행으로 넘어가지 않는다.

**해결**: 전역 플래그를 앞으로, 서브커맨드를 뒤로.

```yaml
args:
  - --no-autoupdate
  - --config
  - /etc/cloudflared/config/config.yaml
  - --metrics
  - 0.0.0.0:2000
  - tunnel
  - run
```

> **에러 메시지 없이 죽는 경우**라 진단이 까다로웠다. "CrashLoopBackOff = 에러"라고 단정하지 않고 `Exit Code`와 `Reason`을 확인한 것이 실마리였다. 수업 Day4에서 배운 "트러블슈팅은 검색 대신 `describe` Events 먼저"가 그대로 적용된 사례다.

#### 최종 확인

```bash
kubectl apply -f ~/cloudflared-deploy.yaml
kubectl -n petmint get pods -w
```

```txt
cloudflared-68ff698fdb-q9hnn   1/1     Running             0               2s
cloudflared-68ff698fdb-ml6gn   1/1     Running             0               1s
cloudflared-54cf9fcd7c-bz55r   0/1     Terminating         9 (3m12s ago)   20m
cloudflared-54cf9fcd7c-4s927   0/1     Terminating         9 (3m33s ago)   20m
```

새 Pod가 Running이 된 뒤 옛 Pod가 종료되는 **롤링 업데이트**가 그대로 보인다. 서비스 중단 없이 교체된다.

```bash
kubectl -n petmint get pods
```

```txt
NAME                           READY   STATUS    RESTARTS   AGE
cloudflared-68ff698fdb-ml6gn   1/1     Running   0          36s
cloudflared-68ff698fdb-q9hnn   1/1     Running   0          38s
```

**RESTARTS 0**, 안정화 확인.

```bash
curl -I https://petmint.ronanlab.dev
```

```txt
HTTP/2 404
date: Tue, 13 Oct 2026 09:20:05 GMT
server: cloudflare
cf-ray: a49d4431b9d25282-NRT
```

**404가 정상이다.** 아직 Ingress 리소스를 만들지 않았으므로 nginx-ingress가 "매칭되는 규칙 없음"으로 응답한 것이다. 즉 요청이 끝까지 도달했다.

```txt
petmint.ronanlab.dev
  → Cloudflare 엣지 (cf-ray ...-NRT, 도쿄)
  → petmint-tunnel (클러스터 내 Pod 2개)
  → nginx-ingress
  → (11단계에서 배포한 petmint 앱, 07_project_deploy.md)
```

9단계 완료. 다음은 10단계(ArgoCD + Jenkins + Harbor, [04_argocd.md](04_argocd.md)).

> **주의(그때)**: 10단계는 이미지 pull과 압축 해제가 몰려 CPU · 디스크 IO 버스트가 생긴다. 같은 호스트에서 GPU 학습을 돌리는 중이라면 그 단계는 피하는 것이 안전하다. 또 VM당 디스크 20GB는 Harbor · Loki · Prometheus 단계에서 빠듯할 수 있어 다시 보기로 했는데, 확인해 보니 20GB는 무시됐고 루트는 62GB였다([04_argocd.md](04_argocd.md) 끝, [01_cluster.md](01_cluster.md) 「디스크 크기 정리」). 디스크 걱정은 없었다.

### 이후: 클러스터 공용 터널로 (2026-10-18 · 11-02)

위 9-3~9-5단계의 터널은 petmint 네임스페이스에 **손으로** 넣은 것이었다(m-k8s의 `~/cloudflared-deploy.yaml`과 `kubectl create configmap`). git에 없었고, 다섯 호스트(petmint · argocd · harbor · jenkins · runshoes)가 한 프로젝트 네임스페이스에 얹혀 있었다.

| 시점 | 바뀐 것 |
| --- | --- |
| 2026-10-18 | `cloudflared` 네임스페이스로 옮기고 매니페스트를 `ronanlab-infra`에 남겼다. 같은 터널에 새 커넥터를 먼저 붙여(2 → 4) 확인한 뒤 옛것을 지웠다. 공개 주소 1초마다 1,360회, 실패 0. 기록 · 되돌리기는 호스트 `~/k8s-cluster/backup/2026-10-18-cloudflared-platform/ROLLBACK.md`. 터널 이름도 `ronanlab-tunnel`로 바꿨다 |
| 2026-10-18 | `runshoes.ronanlab.dev`를 다섯 번째 호스트로 더했다(Access 없음, 공개 사이트). 그 전에는 호스트 systemd `cloudflared-runshoes`(runshoes-tunnel)가 학교 인그레스로 보냈다 |
| 2026-11-02 | `platform/cloudflared` → `apps/cloudflared`. 루트 Application(App of Apps, `bootstrap/root-app.yaml`)이 Application `cloudflared`를 만든다. 되돌리기는 호스트 `~/k8s-cluster/backup/2026-11-02-app-of-apps/ROLLBACK.md` |

```txt
apps/cloudflared/
  app.yaml             ArgoCD Application, 수동 Sync, prune 끔, finalizer 없음
  kustomization.yaml   namespace: cloudflared. Namespace · Secret은 여기 없다(사람이 만든다)
  configmap.yaml       터널 설정 config.yaml, 호스트가 모두 한 파일(지금 7개)
  deployment.yaml      커넥터 2개
  README.md            처음 한 번 · 바꿀 때 · 확인
```

손으로 넣던 Deployment에 세 가지를 더했다. 롤링 중 터널이 비지 않게.

| 설정 | 없으면 | 이유 |
| --- | --- | --- |
| `readinessProbe` `/ready` | Pod가 뜨자마자 Ready가 되어 옛 커넥터가 먼저 내려간다 | 엣지 연결이 하나라도 서야 200 |
| `maxSurge: 1`, `maxUnavailable: 0` | 새 커넥터가 연결되기 전에 둘 다 바뀔 수 있다 | 새 Pod가 Ready가 못 되면 옛 둘이 그대로 받는다 |
| `topologySpreadConstraints`(ScheduleAnyway) | 두 커넥터가 한 노드에 몰릴 수 있다 | 노드 하나가 죽어도 다른 커넥터가 받는다. 강제는 아니다, 워커가 빠져도 둘 다 뜨는 쪽이 낫다 |

**자격증명은 표준 입력으로 넣는다.** 디스크 · 화면에 평문을 남기지 않는다. 명령은 [apps/cloudflared/README.md](../apps/cloudflared/README.md) 「처음 한 번」. 2026-10-18에는 옛 `petmint/cloudflared-credentials`에서 같은 방법으로 복사했다.

**호스트를 더하거나 바꿀 때**는 [apps/cloudflared/README.md](../apps/cloudflared/README.md) 「바꿀 때」 순서대로 한다. 요점: ConfigMap 고쳐 push → 수동 Sync → `rollout restart`(cloudflared는 설정 파일을 기동 때만 읽는다) → 깨졌으면 git revert. 공개 주소의 CNAME은 Cloudflare 쪽에서 따로 붙인다(9-2단계의 `--config /dev/null`).

터널이 보는 곳은 지금도 ingress-nginx **ClusterIP**(Service DNS)다. ingress-nginx Service를 LoadBalancer(VIP `192.168.122.240`)로 바꿨지만([02_metrics_storage_ingress.md](02_metrics_storage_ingress.md)) 터널 설정은 그대로다.

### 2026-11-09 ollama-tunnel Access 다시 걸기

`ollama.ronanlab.dev`에 Access 정책이 빠져 토큰 없이 열려 있었다(Ollama 로그로 11-02부터 바깥 IP의 `GET /` · `HEAD /`가 들어왔다. 생성 · pull · delete는 바깥 IP 0건). 저장소에 쓰는 곳이 없어 터널을 잠시 껐다가 학교 PC 용도를 확인해 다시 켜고, Service Auth 정책(토큰 `ollama-school-pc`, `runshoes-ollama-token`의 이름을 바꾼 것)을 다시 걸었다. 토큰 없이 `/api/version` · `/api/tags` · `POST /api/generate` 모두 403. 자세한 것은 펫퍼민트 저장소 `docs/02_pipeline/13_access_and_tunnel.md` 「Access 정책」.

### 2026-11-11 grafana · prometheus 추가, 수동 Sync 다시 정함

모니터링(`apps/monitoring/ingress.yaml`)을 열며 `grafana.ronanlab.dev` · `prometheus.ronanlab.dev`를 ConfigMap에 더했다. Access 「운영도구」 앱(argocd · harbor · jenkins와 같은 앱)을 건 뒤 DNS를 연다(`apps/cloudflared/configmap.yaml:35`). 같은 날 사용자가 이 Application만 수동 Sync로 두기로 다시 정했다(`apps/cloudflared/app.yaml:4`). 모니터링은 [09_monitoring.md](09_monitoring.md).

## 4. 남은 한계

- **터널 하나에 공개 주소 7개.** 이 터널이 깨지면 서비스(petmint · runshoes)와 운영 도구(ArgoCD · Harbor · Jenkins · Grafana · Prometheus)가 한꺼번에 안 보인다. 되돌리기는 m-k8s의 kubectl과 MetalLB VIP로만 된다
- **Cloudflare 쪽(DNS CNAME · Access 정책 · Service Token)은 저장소에 없다.** 대시보드에서 사람이 한다. 2026-11-09처럼 정책이 빠져도 저장소로는 알 수 없다
- **ollama-tunnel은 호스트 프로세스 하나다.** 이중화 · probe가 없고 systemd `Restart=on-failure`뿐이다. 저장소에 쓰는 곳이 없어 안 쓰는 것으로 오해하기 쉽다(2026-11-09에 한 번 껐다)
- **GPU가 한 장이다.** 바깥에서 `ollama.ronanlab.dev`로 긴 생성을 돌리면 펫퍼민트 서빙이 멈춘다. 이 호스트는 늘 Access 뒤에 둔다
- **`route dns` 함정이 살아 있다.** 호스트 `~/.cloudflared/config.yml`이 ollama-tunnel을 가리키므로 `--config /dev/null` 없이 `route dns`를 치면 ollama-tunnel에 붙는다
- **k8s Secret은 암호화가 아니다.** base64일 뿐이다
- **ConfigMap은 기동 때만 읽는다.** Sync만 하고 `rollout restart`를 빠뜨리면 바뀐 설정이 안 들어간다
- 호스트 cloudflared 2026.9.1은 낡았다는 경고가 나온다(2026.10.7 권장). 클러스터 이미지 2026.10.0과도 다르다

## 5. 확인 방법

클러스터(호스트에서 `cd ~/k8s-cluster && vagrant ssh m-k8s -c '…'`):

```bash
kubectl -n argocd get app cloudflared -o jsonpath='{.spec.syncPolicy.automated}{" "}{.status.sync.status}{" "}{.status.health.status}{"\n"}'
# 기대: (비어 있음) Synced Healthy  → 수동 Sync

kubectl -n cloudflared get deploy cloudflared -o jsonpath='{.spec.replicas} {.spec.strategy.rollingUpdate.maxSurge} {.spec.strategy.rollingUpdate.maxUnavailable} {.spec.template.spec.containers[0].image}{"\n"}'
# 기대: 2 1 0 cloudflare/cloudflared:2026.10.0

kubectl -n cloudflared get pod -l app=cloudflared -o wide
# 기대: 1/1 Running 2개, 서로 다른 노드

kubectl -n cloudflared get cm cloudflared-config -o jsonpath='{.data.config\.yaml}' | grep hostname
# 기대: petmint · argocd · harbor · jenkins · runshoes · grafana · prometheus 7줄

kubectl -n cloudflared get secret cloudflared-credentials
# 기대: 있다(내용은 보지 않는다)

kubectl -n cloudflared logs -l app=cloudflared --since=10m | grep -E ' ERR '
# 기대: 없음
```

호스트:

```bash
cloudflared tunnel --config /dev/null list
# 기대: ollama-tunnel, ronanlab-tunnel 둘. ronanlab-tunnel 연결 8개(커넥터 2 × 4)

cloudflared tunnel --config /dev/null info 02ad6a13-ce45-4262-a32a-40241bf034dc
# 기대: 커넥터 2개

systemctl is-active cloudflared-ollama.service
# 기대: active

~/k8s-cluster/backup/2026-10-15-before-metallb/health.sh
# 기대: 커넥터마다 ha_connections=4, 공개 주소 302(Access 로그인)

curl -s -o /dev/null -w '%{http_code}\n' https://ollama.ronanlab.dev/api/tags
# 기대: 403(토큰 없음)
```
