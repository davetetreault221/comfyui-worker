#!/usr/bin/env python3
"""
ComfyUI Worker - Consumes jobs from RabbitMQ and processes them with ComfyUI.

This script runs on Lambda Labs instances alongside ComfyUI.
It connects to a RabbitMQ queue, pulls jobs, sends them to ComfyUI,
and uploads results to Supabase Storage.
"""

import pika
import json
import requests
import os
import time
from datetime import datetime
from supabase import create_client

# Configuration from environment variables
RABBITMQ_URL = os.getenv("RABBITMQ_URL", "amqp://guest:guest@localhost:5672/")
COMFYUI_URL = os.getenv("COMFYUI_URL", "http://localhost:8188")
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_SERVICE_KEY = os.getenv("SUPABASE_SERVICE_KEY")
QUEUE_NAME = os.getenv("QUEUE_NAME", "comfyui_jobs")

# Initialize Supabase client (optional - for production)
supabase = None
if SUPABASE_URL and SUPABASE_SERVICE_KEY:
    supabase = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)
    print("[✓] Supabase client initialized")
else:
    print("[!] Supabase not configured - results will only be logged")


def wait_for_comfyui(timeout=60):
    """Wait for ComfyUI to be ready."""
    print(f"[*] Waiting for ComfyUI at {COMFYUI_URL}...")
    for i in range(timeout):
        try:
            r = requests.get(f"{COMFYUI_URL}/system_stats", timeout=5)
            if r.status_code == 200:
                print(f"[✓] ComfyUI is ready")
                return True
        except requests.exceptions.RequestException:
            pass
        time.sleep(1)
    raise Exception(f"ComfyUI not ready after {timeout} seconds")


def wait_for_completion(prompt_id, timeout=300):
    """Poll ComfyUI until the image is ready."""
    for _ in range(timeout):
        try:
            r = requests.get(f"{COMFYUI_URL}/history/{prompt_id}")
            history = r.json()
            if prompt_id in history:
                return history[prompt_id].get("outputs", {})
        except requests.exceptions.RequestException as e:
            print(f"    [!] Error polling ComfyUI: {e}")
        time.sleep(1)
    raise Exception(f"Timeout waiting for ComfyUI after {timeout} seconds")


def upload_to_supabase(job_id, images):
    """Download images from ComfyUI and upload to Supabase Storage."""
    if not supabase:
        return None
    
    image_urls = []
    for i, img in enumerate(images):
        try:
            # Download image from ComfyUI
            img_response = requests.get(
                f"{COMFYUI_URL}/view",
                params={
                    "filename": img["filename"],
                    "subfolder": img.get("subfolder", ""),
                    "type": img.get("type", "output")
                }
            )
            
            if img_response.status_code != 200:
                print(f"    [!] Failed to download image: {img['filename']}")
                continue
            
            # Upload to Supabase Storage
            storage_path = f"{job_id}/{i}.png"
            supabase.storage.from_("generations").upload(
                storage_path,
                img_response.content,
                {"content-type": "image/png"}
            )
            
            # Get public URL
            url = supabase.storage.from_("generations").get_public_url(storage_path)
            image_urls.append(url)
            print(f"    [✓] Uploaded: {storage_path}")
            
        except Exception as e:
            print(f"    [!] Upload error: {e}")
    
    return image_urls


def update_job_status(job_id, status, image_urls=None, error=None):
    """Update job status in Supabase database."""
    if not supabase:
        return
    
    try:
        update_data = {"status": status}
        if image_urls:
            update_data["image_urls"] = image_urls
            update_data["completed_at"] = datetime.utcnow().isoformat()
        if error:
            update_data["error"] = str(error)
        
        supabase.table("tb_jobs").update(update_data).eq("id", job_id).execute()
    except Exception as e:
        print(f"    [!] Failed to update job status: {e}")


def process_job(ch, method, properties, body):
    """Process a single job from the queue."""
    message = json.loads(body)
    job_id = message.get("job_id", "unknown")
    workflow = message.get("workflow", {})
    
    print(f"\n{'='*60}")
    print(f"[*] Processing job: {job_id}")
    print(f"    Time: {datetime.now().isoformat()}")
    
    try:
        # Update status to processing
        update_job_status(job_id, "processing")
        
        # Submit to ComfyUI
        print(f"    Submitting to ComfyUI...")
        r = requests.post(
            f"{COMFYUI_URL}/prompt",
            json={"prompt": workflow},
            timeout=60
        )
        
        if r.status_code != 200:
            raise Exception(f"ComfyUI error: {r.status_code} - {r.text}")
        
        prompt_id = r.json()["prompt_id"]
        print(f"    ComfyUI prompt_id: {prompt_id}")
        
        # Wait for completion
        print(f"    Waiting for generation...")
        outputs = wait_for_completion(prompt_id)
        
        # Get images from SaveImage node (node 9)
        images = []
        if "9" in outputs and "images" in outputs["9"]:
            images = outputs["9"]["images"]
        
        if images:
            print(f"    Generated {len(images)} image(s)")
            
            # Upload to Supabase
            image_urls = upload_to_supabase(job_id, images)
            
            # Update job as complete
            update_job_status(job_id, "complete", image_urls=image_urls)
            
            print(f"[✓] Job {job_id} complete!")
            for img in images:
                print(f"    - {img['filename']}")
        else:
            print(f"[?] Job {job_id} complete but no images in output")
            update_job_status(job_id, "complete")
        
    except Exception as e:
        print(f"[✗] Job {job_id} failed: {e}")
        update_job_status(job_id, "failed", error=str(e))
    
    # Acknowledge message (remove from queue)
    ch.basic_ack(delivery_tag=method.delivery_tag)
    print(f"{'='*60}\n")


def main():
    """Main entry point."""
    print("\n" + "="*60)
    print("  ComfyUI Worker")
    print("="*60)
    print(f"  RabbitMQ:  {RABBITMQ_URL.split('@')[-1] if '@' in RABBITMQ_URL else RABBITMQ_URL}")
    print(f"  ComfyUI:   {COMFYUI_URL}")
    print(f"  Queue:     {QUEUE_NAME}")
    print(f"  Supabase:  {'Configured' if supabase else 'Not configured'}")
    print("="*60 + "\n")
    
    # Wait for ComfyUI to be ready
    wait_for_comfyui()
    
    # Connect to RabbitMQ
    print(f"[*] Connecting to RabbitMQ...")
    connection = pika.BlockingConnection(pika.URLParameters(RABBITMQ_URL))
    channel = connection.channel()
    
    # Declare queue (creates if doesn't exist)
    channel.queue_declare(queue=QUEUE_NAME, durable=True)
    
    # Fair dispatch - only give one message at a time
    channel.basic_qos(prefetch_count=1)
    
    # Start consuming
    channel.basic_consume(queue=QUEUE_NAME, on_message_callback=process_job)
    
    print(f"[✓] Connected to RabbitMQ")
    print(f"\n[*] Worker ready. Waiting for jobs... (Ctrl+C to exit)\n")
    
    try:
        channel.start_consuming()
    except KeyboardInterrupt:
        print("\n[*] Shutting down...")
        channel.stop_consuming()
        connection.close()
        print("[✓] Worker stopped")


if __name__ == "__main__":
    main()
