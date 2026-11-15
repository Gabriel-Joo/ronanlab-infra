<!--
다루는 곳: scripts/host-gpu-exporter.sh
읽은 커밋: e8e24ea
-->
# GPU와 호스트 서비스

GPU는 호스트에만 있고 VM에 넘기지 않는다(패스스루 없음). 파드는 호스트 서비스를 libvirt `default` 망의 호스트 주소 `192.168.122.1`로 부른다. [docs:history/cluster_state_20261116.md:80] 이력과 구축 기록은 `docs/history/build_log/00_server.md`, `docs/history/build_log/kubernetes_install.md`.

## 지금 구성

- GPU: NVIDIA GeForce RTX 5070 Ti 한 장, 드라이버 595.99.02, 메모리 16303MiB [docs:history/cluster_state_20261116.md:76]
- 패스스루 안 함. 처음 하는 작업이라 위험이 크고, 호스트의 Ollama를 계속 써야 했다 [docs:history/build_log/kubernetes_install.md:117]
- 호스트 망: libvirt `default`(virbr0, `192.168.122.0/24`). 노드 eth1이 이 망에 고정 주소로 붙는다 [docs:history/cluster_state_20261116.md:22-28]

호스트 서비스(파드가 부르는 것) [docs:history/cluster_state_20261116.md:77-80]:

| 서비스 | 실행 | 여는 주소 | 부르는 곳 |
| --- | --- | --- | --- |
| Ollama(추론) | Docker `ollama` | `127.0.0.1`, `172.17.0.1`, `192.168.122.1`의 11434 | petmint 앱, runshoes 앱, runshoes 챗봇, runshoes 요약 CronJob |
| Milvus(벡터 DB) | Docker `milvus-standalone`, `milvus-etcd` | `127.0.0.1`, `192.168.122.1`의 19530, 9091 | petmint 앱(19530), Prometheus(9091) |
| search-service | systemd `petmint-search` | `192.168.122.1:8100` | petmint 앱 |
| model-service(KURE-v1, bge-reranker-v2-m3, GPU) | systemd `model-service` | `192.168.122.1:8200` | runshoes 챗봇 |
| nvidia-gpu-exporter | Docker `nvidia-gpu-exporter` | `192.168.122.1:9835` | Prometheus |

Milvus와 서비스 행의 근거는 [docs:history/build_log/00_server.md:99] [docs:history/build_log/00_server.md:142-143].

클러스터와 닿지 않는 호스트 서비스:

- Open WebUI: `127.0.0.1:3000`에만 연다 [docs:history/cluster_state_20261116.md:77]
- `cloudflared-ollama`: 학교 PC 전용 Ollama 터널. 설정은 호스트의 `~/.cloudflared/config.yml`(저장소 밖). Cloudflare Access Service Auth(서비스 토큰)로 막는다. 파드는 쓰지 않는다 [docs:history/build_log/03_cloudflare_tunnel.md:64-69]

Ollama 동작:

- 모델은 요청 때 VRAM에 올리고, 마지막 요청 뒤 `OLLAMA_KEEP_ALIVE` 기본값(5분)이 지나면 내린다 [docs:history/build_log/00_server.md:234]
- `OLLAMA_KEEP_ALIVE`는 바꾸지 않는다. 학교 PC 등과 GPU 메모리를 나눠 쓴다 [code:CLAUDE.md:34]
- 클러스터가 쓰는 모델: petmint `tri-7b`(기본)와 `kabyul-tri-7b-rag1-rebuild4-ckpt462`(업무특화) [code:apps/petmint/app/configmap.yaml:29-30], runshoes 챗봇과 리뷰 요약 `gemma4:e4b` [code:apps/monitoring/grafana/dashboards/gen_runshoes.py:288]

## 설정 자리

| 파일:줄 | 값 | 뜻 |
| --- | --- | --- |
| `apps/petmint/app/configmap.yaml:23` | `PETMINT_OLLAMA_URL` `http://192.168.122.1:11434` | petmint의 Ollama |
| `apps/petmint/app/configmap.yaml:24` | `PETMINT_MILVUS_URL` `http://192.168.122.1:19530` | petmint의 Milvus |
| `apps/petmint/app/configmap.yaml:26` | `PETMINT_SEARCH_URL` `http://192.168.122.1:8100` | petmint의 search-service |
| `apps/petmint/app/configmap.yaml:29-30` | `PETMINT_MODEL_BASE`, `PETMINT_MODEL_RAG` | Ollama 모델 이름. 호스트에 `ollama create`로 먼저 올려 둔다 |
| `apps/runshoes/app/deployment.yaml:98-99` | 앱 `OLLAMA_URL` | 리뷰 요약 |
| `apps/runshoes/app/deployment.yaml:144-145` | 챗봇 `OLLAMA_URL` | 챗봇 답 |
| `apps/runshoes/app/deployment.yaml:148-149` | 챗봇 `MODEL_SERVICE_URL` `http://192.168.122.1:8200` | 없으면 챗봇은 뜨지만 검색 색인을 만들지 않는다 |
| `apps/runshoes/app/cronjob.yaml:49-50` | 요약 배치 `OLLAMA_URL` | 하루 한 번 요약 |
| `apps/runshoes/app/cronjob.yaml:27` | `activeDeadlineSeconds: 7200` | Ollama가 매달려도 2시간에 끝낸다 |
| `scripts/host-gpu-exporter.sh:9` | `utkuozdemir/nvidia_gpu_exporter:1.3.1` | GPU 수집기 이미지 |
| `scripts/host-gpu-exporter.sh:11-13` | `--restart unless-stopped`, `--gpus all`, `NVIDIA_DRIVER_CAPABILITIES=utility`, `-p 192.168.122.1:9835:9835` | 사설망 주소에만 연다 |
| `apps/monitoring/prometheus/configmap.yaml:91-97` | 작업 `nvidia-gpu` | 수집기를 긁고 쓰는 지표 7종만 남긴다 |
| `apps/monitoring/prometheus/configmap.yaml:99-113` | 작업 `ollama` | json-exporter가 `/api/ps`를 지표로 바꾼다 |
| `apps/monitoring/prometheus/configmap.yaml:78-87` | 작업 `milvus` | 응답 여부(`up`)만 본다 |

근거: [code:apps/petmint/app/configmap.yaml:23-30] [code:apps/runshoes/app/deployment.yaml:98-99] [code:apps/runshoes/app/deployment.yaml:144-149] [code:apps/runshoes/app/cronjob.yaml:27] [code:apps/runshoes/app/cronjob.yaml:49-50] [code:scripts/host-gpu-exporter.sh:9-13] [code:apps/monitoring/prometheus/configmap.yaml:78-113]

## 바꾸거나 다시 만들기

GPU 수집기(호스트에서, docker 그룹이라 sudo 없이). 있으면 지우고 다시 만든다 [code:scripts/host-gpu-exporter.sh:2-7]:

```bash
bash scripts/host-gpu-exporter.sh
docker rm -f nvidia-gpu-exporter      # 되돌리기
```

호스트 주소나 포트를 바꾸면 고칠 곳:

- `apps/petmint/app/configmap.yaml` 세 줄. envFrom이라 Sync 뒤 `kubectl -n petmint rollout restart deploy/petmint-app`이 있어야 반영된다 [code:apps/petmint/app/configmap.yaml:28]
- `apps/runshoes/app/deployment.yaml`, `apps/runshoes/app/cronjob.yaml`의 `OLLAMA_URL`, `MODEL_SERVICE_URL`
- `apps/monitoring/prometheus/configmap.yaml`의 `milvus`, `nvidia-gpu`, `ollama` 대상, `apps/monitoring/json-exporter/json-exporter.yaml` 머리 주석
- 호스트 쪽 게시 주소(Docker `-p`, systemd 유닛)는 저장소 밖이다. sudo가 필요한 것은 사람이 한다

새 모델을 petmint에 쓰려면 호스트에서 먼저 `ollama create`로 올린 뒤 `PETMINT_MODEL_*`를 바꾼다 [code:apps/petmint/app/configmap.yaml:27]

## 확인

호스트에서:

```bash
nvidia-smi --query-gpu=name,driver_version,memory.total --format=csv,noheader   # NVIDIA GeForce RTX 5070 Ti, 595.99.02, 16303 MiB
docker ps --format '{{.Names}}\t{{.Ports}}'      # ollama 11434가 127.0.0.1, 172.17.0.1, 192.168.122.1 셋에만
systemctl is-active docker cloudflared-ollama model-service petmint-search   # 모두 active
curl -s http://192.168.122.1:9835/metrics | /usr/bin/grep -c '^nvidia_smi'   # 0보다 크면 수집기가 돈다
curl -s http://192.168.122.1:11434/api/ps        # 지금 VRAM에 올라간 모델
```

기대값의 근거 [docs:history/build_log/00_server.md:597] [docs:history/build_log/00_server.md:606] [docs:history/build_log/00_server.md:609].

Prometheus 수집 대상 `ollama`, `milvus`, `nvidia-gpu`가 모두 `up` 1이면 파드 쪽 망에서 호스트 서비스가 보인다(→ 「모니터링」의 확인). [code:apps/monitoring/prometheus/configmap.yaml:78-113]

## 알려진 한계

- GPU가 한 장이다. 바깥에서 `ollama.ronanlab.dev`로 긴 생성을 돌리면 petmint 서빙이 멈춘다. 이 호스트는 늘 Access 뒤에 둔다 [docs:history/build_log/03_cloudflare_tunnel.md:701]
- petmint 모드가 섞이면 두 모델을 번갈아 올려 답이 느려진다. runshoes 모델과도 서로 내렸다 올린다 [code:apps/monitoring/grafana/dashboards/gen_petmint.py:202-203] [code:apps/monitoring/grafana/dashboards/gen_runshoes.py:289-290]
- model-service는 임베딩 모델을 VRAM에 늘 올려 둔다 [docs:history/build_log/00_server.md:586]
- 호스트가 꺼지면 Ollama, Milvus, model-service, NFS와 VM 다섯 대가 함께 멈춘다 [docs:history/build_log/kubernetes_install.md:198]
- 호스트 서비스와 GPU 수집기는 ArgoCD 밖이다 [docs:history/build_log/09_monitoring.md:124]
- search-service, model-service의 생존은 수집하지 않는다 [docs:history/build_log/09_monitoring.md:212]
- Milvus 19530과 9091은 사설망에 인증 없이 열려 있다 [docs:history/build_log/09_monitoring.md:211]
- 호스트 cloudflared-ollama 터널은 프로세스 하나이고, Cloudflare Access 정책은 저장소에 없다 [docs:history/build_log/03_cloudflare_tunnel.md:699-700]
