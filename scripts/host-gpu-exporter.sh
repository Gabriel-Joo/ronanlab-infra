#!/usr/bin/env bash
# GPU 호스트에 nvidia_gpu_exporter 를 띄운다(2026-11-10 가용성 묶음 2 — 모니터링). 호스트에서, sudo 없이(docker 그룹):
#   bash scripts/host-gpu-exporter.sh
# - GPU 사용률 · VRAM · 온도 · 전력(nvidia-smi 를 읽는다). Prometheus(apps/monitoring)가 192.168.122.1:9835 를 긁는다
# - 포트는 VM 사설망 주소에만 연다(바깥 · 공유기 쪽으로 열지 않는다). Ollama · Milvus 컨테이너는 건드리지 않는다
# - nvidia 런타임이 nvidia-smi · NVML 을 넣어 준다(--gpus all, utility 만). 여러 번 돌려도 같다 — 있으면 지우고 다시 만든다
# - 되돌리기: docker rm -f nvidia-gpu-exporter
set -euo pipefail
IMG=docker.io/utkuozdemir/nvidia_gpu_exporter:1.3.1
docker rm -f nvidia-gpu-exporter >/dev/null 2>&1 || true
docker run -d --name nvidia-gpu-exporter --restart unless-stopped \
  --gpus all -e NVIDIA_DRIVER_CAPABILITIES=utility \
  -p 192.168.122.1:9835:9835 "$IMG"
sleep 3
curl -fsS http://192.168.122.1:9835/metrics | grep -E '^nvidia_smi_(utilization_gpu_ratio|memory_used_bytes|memory_total_bytes)' | head -3
