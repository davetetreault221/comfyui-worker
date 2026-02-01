# ComfyUI Worker

A RabbitMQ-based worker for processing ComfyUI image generation jobs. Designed to run on Lambda Labs GPU instances alongside ComfyUI.

## Architecture

```
┌─────────────┐     ┌─────────────┐     ┌─────────────────────────────┐
│   FastAPI   │────▶│  RabbitMQ   │◀────│  Lambda Labs Instance       │
│  (Railway)  │     │ (CloudAMQP) │     │  ┌─────────┐  ┌──────────┐  │
└─────────────┘     └─────────────┘     │  │ Worker  │─▶│ ComfyUI  │  │
                                        │  └─────────┘  └──────────┘  │
                                        └─────────────────────────────┘
```

## Quick Start (Local Testing)

### 1. Start RabbitMQ with Docker

```bash
docker run -d --name rabbitmq -p 5672:5672 -p 15672:15672 rabbitmq:management
```

Management UI: http://localhost:15672 (guest/guest)

### 2. Clone and Setup

```bash
git clone https://github.com/YOUR_USERNAME/comfyui-worker.git
cd comfyui-worker
pip install -r requirements.txt
cp .env.example .env
```

### 3. Start ComfyUI

```bash
cd /path/to/ComfyUI
python main.py
```

### 4. Start the Worker

```bash
cd comfyui-worker
python worker.py
```

### 5. Test with a Sample Job

```bash
python test_publish.py
```

## Lambda Labs Deployment

### 1. SSH into your instance

```bash
ssh ubuntu@<instance-ip>
```

### 2. Clone the repo

```bash
git clone https://github.com/YOUR_USERNAME/comfyui-worker.git
cd comfyui-worker
```

### 3. Run setup

```bash
chmod +x setup.sh
./setup.sh
```

### 4. Configure environment

```bash
nano .env
```

Set your production values:
- `RABBITMQ_URL` - Your CloudAMQP URL
- `SUPABASE_URL` - Your Supabase project URL
- `SUPABASE_SERVICE_KEY` - Your Supabase service role key

### 5. Start ComfyUI and Worker

```bash
# Terminal 1: ComfyUI
cd ~/ComfyUI
python main.py

# Terminal 2: Worker
cd ~/comfyui-worker
python worker.py
```

## Running as a Service (Production)

Create a systemd service for auto-restart:

```bash
sudo nano /etc/systemd/system/comfyui-worker.service
```

```ini
[Unit]
Description=ComfyUI Worker
After=network.target

[Service]
Type=simple
User=ubuntu
WorkingDirectory=/home/ubuntu/comfyui-worker
ExecStart=/usr/bin/python3 worker.py
Restart=always
RestartSec=5
EnvironmentFile=/home/ubuntu/comfyui-worker/.env

[Install]
WantedBy=multi-user.target
```

Enable and start:

```bash
sudo systemctl daemon-reload
sudo systemctl enable comfyui-worker
sudo systemctl start comfyui-worker

# Check status
sudo systemctl status comfyui-worker

# View logs
journalctl -u comfyui-worker -f
```

## Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `RABBITMQ_URL` | RabbitMQ connection URL | `amqp://guest:guest@localhost:5672/` |
| `COMFYUI_URL` | ComfyUI HTTP URL | `http://localhost:8188` |
| `QUEUE_NAME` | RabbitMQ queue name | `comfyui_jobs` |
| `SUPABASE_URL` | Supabase project URL | (optional) |
| `SUPABASE_SERVICE_KEY` | Supabase service role key | (optional) |

## Job Message Format

The worker expects jobs in this format:

```json
{
  "job_id": "uuid-string",
  "workflow": {
    "4": { "class_type": "CheckpointLoaderSimple", ... },
    "5": { "class_type": "EmptyLatentImage", ... },
    ...
  }
}
```

## Files

- `worker.py` - Main worker script
- `test_publish.py` - Test script to publish jobs
- `requirements.txt` - Python dependencies
- `.env.example` - Environment variable template
- `setup.sh` - Quick setup script

## Troubleshooting

### Worker can't connect to RabbitMQ

- Check `RABBITMQ_URL` is correct
- Ensure RabbitMQ is running: `docker ps`
- Check firewall allows port 5672

### Worker can't connect to ComfyUI

- Ensure ComfyUI is running on port 8188
- Check `COMFYUI_URL` is correct
- Try: `curl http://localhost:8188/system_stats`

### Jobs not being processed

- Check queue has messages: `python test_publish.py check`
- Check worker logs for errors
- Verify workflow JSON is valid
