#!/usr/bin/env python3
"""
Test script to publish a job to RabbitMQ.
Use this to test the worker without modifying FastAPI.
"""

import pika
import json
import uuid
import os
from dotenv import load_dotenv

load_dotenv()

RABBITMQ_URL = os.getenv("RABBITMQ_URL", "amqp://guest:guest@localhost:5672/")
QUEUE_NAME = os.getenv("QUEUE_NAME", "comfyui_jobs")

# Simple test workflow - generates a basic image
# Modify ckpt_name to match a model you have installed
TEST_WORKFLOW = {
    "4": {
        "class_type": "CheckpointLoaderSimple",
        "inputs": {
            "ckpt_name": "cyberRealisticPony_15.safetensors"
        }
    },
    "5": {
        "class_type": "EmptyLatentImage",
        "inputs": {
            "batch_size": 1,
            "height": 512,
            "width": 512
        }
    },
    "6": {
        "class_type": "CLIPTextEncode",
        "inputs": {
            "clip": ["4", 1],
            "text": "a beautiful sunset over mountains, high quality"
        }
    },
    "7": {
        "class_type": "CLIPTextEncode",
        "inputs": {
            "clip": ["4", 1],
            "text": "bad quality, blurry"
        }
    },
    "3": {
        "class_type": "KSampler",
        "inputs": {
            "cfg": 7,
            "denoise": 1,
            "latent_image": ["5", 0],
            "model": ["4", 0],
            "negative": ["7", 0],
            "positive": ["6", 0],
            "sampler_name": "euler_ancestral",
            "scheduler": "normal",
            "seed": 12345,
            "steps": 20
        }
    },
    "8": {
        "class_type": "VAEDecode",
        "inputs": {
            "samples": ["3", 0],
            "vae": ["4", 2]
        }
    },
    "9": {
        "class_type": "SaveImage",
        "inputs": {
            "filename_prefix": "ComfyUI",
            "images": ["8", 0]
        }
    }
}


def publish_job(workflow, job_id=None):
    """Publish a job to the RabbitMQ queue."""
    job_id = job_id or str(uuid.uuid4())
    
    connection = pika.BlockingConnection(pika.URLParameters(RABBITMQ_URL))
    channel = connection.channel()
    channel.queue_declare(queue=QUEUE_NAME, durable=True)
    
    message = {
        "job_id": job_id,
        "workflow": workflow,
    }
    
    channel.basic_publish(
        exchange='',
        routing_key=QUEUE_NAME,
        body=json.dumps(message),
        properties=pika.BasicProperties(delivery_mode=2)  # Persistent
    )
    connection.close()
    
    print(f"[✓] Published job: {job_id}")
    print(f"    Queue: {QUEUE_NAME}")
    return job_id


def check_queue():
    """Check how many messages are in the queue."""
    connection = pika.BlockingConnection(pika.URLParameters(RABBITMQ_URL))
    channel = connection.channel()
    queue = channel.queue_declare(queue=QUEUE_NAME, durable=True, passive=True)
    count = queue.method.message_count
    connection.close()
    print(f"[*] Queue '{QUEUE_NAME}' has {count} message(s)")
    return count


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == "check":
        check_queue()
    else:
        print("\n" + "="*50)
        print("  Publishing test job to RabbitMQ")
        print("="*50)
        print(f"  RabbitMQ: {RABBITMQ_URL.split('@')[-1] if '@' in RABBITMQ_URL else RABBITMQ_URL}")
        print(f"  Queue:    {QUEUE_NAME}")
        print("="*50 + "\n")
        
        publish_job(TEST_WORKFLOW)
        print("\n[*] Job published! The worker should pick it up.\n")
