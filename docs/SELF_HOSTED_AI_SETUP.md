# Self-Hosted AI Setup — Qwen 2.5 7B on GCP L4 GPU

## Overview

Production classification runs on a self-hosted model. No financial data leaves the client's infrastructure.

Priority chain: `LOCAL_LLM_URL (self-hosted) > Mistral API (dev only) > heuristic fallback`

## Hardware

| Option | GPU | VRAM | Monthly cost | Latency | Recommended |
|--------|-----|------|-------------|---------|-------------|
| GCP L4 | NVIDIA L4 | 24GB | ~$560 | ~2s | **Yes** |
| GCP T4 | NVIDIA T4 | 16GB | ~$300 | ~4s | Budget option |
| GCP A100 | NVIDIA A100 | 80GB | ~$2,400 | ~1s | Overkill |

## Deployment Steps

### 1. Create GPU VM on GCP

```bash
gcloud compute instances create arukai-llm \
  --zone=europe-west4-a \
  --machine-type=g2-standard-8 \
  --accelerator=type=nvidia-l4,count=1 \
  --boot-disk-size=100GB \
  --image-family=cos-stable \
  --image-project=cos-cloud \
  --maintenance-policy=TERMINATE
```

### 2. Install vLLM

```bash
# SSH into the VM
gcloud compute ssh arukai-llm --zone=europe-west4-a

# Install vLLM
pip install vllm

# Start serving Qwen 2.5 7B
vllm serve Qwen/Qwen2.5-7B-Instruct \
  --host 0.0.0.0 \
  --port 8080 \
  --max-model-len 4096 \
  --dtype float16
```

### 3. Or use Docker

```bash
docker run -d \
  --gpus all \
  --name arukai-llm \
  -p 8080:8080 \
  vllm/vllm-openai:latest \
  --model Qwen/Qwen2.5-7B-Instruct \
  --host 0.0.0.0 \
  --port 8080 \
  --max-model-len 4096
```

### 4. Verify

```bash
curl http://localhost:8080/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "Qwen/Qwen2.5-7B-Instruct",
    "messages": [{"role": "user", "content": "Hello"}],
    "max_tokens": 50
  }'
```

### 5. Connect to Capital Call backend

Set in Cloud Run (or .env):
```
LOCAL_LLM_URL=http://<gpu-vm-internal-ip>:8080/v1
LOCAL_LLM_MODEL=Qwen/Qwen2.5-7B-Instruct
```

The backend automatically uses the local model when `LOCAL_LLM_URL` is set. No code changes needed.

## Migration Path

| Phase | AI provider | Data leaves infra? |
|-------|------------|-------------------|
| Development | Mistral API (synthetic data only) | Yes (synthetic) |
| Staging | Self-hosted Qwen on GCP L4 | **No** |
| Production | Client-hosted Qwen on client GPU | **No** |

## Monitoring

```bash
# Check GPU utilization
nvidia-smi

# Check vLLM health
curl http://localhost:8080/health

# Check model info
curl http://localhost:8080/v1/models
```

## Cost

- L4 GPU VM (g2-standard-8): ~$0.78/hour = ~$560/month (24/7)
- Preemptible/spot: ~$0.23/hour = ~$168/month (with restart risk)
- Scale-to-zero: not possible with VMs (use GKE with GPU node pools for auto-scaling)

## Security

- GPU VM runs in the same VPC as Cloud Run (internal IP only)
- No public endpoint for the LLM
- Firewall rule: allow port 8080 only from Cloud Run service account
- Model weights are open-source (Apache 2.0 for Qwen) — no license risk
