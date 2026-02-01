#!/bin/bash
# Setup script for Lambda Labs instances
# Run this after cloning the repo

set -e

echo "=============================================="
echo "  ComfyUI Worker Setup"
echo "=============================================="

# Check if running on Lambda Labs (has NVIDIA GPU)
if command -v nvidia-smi &> /dev/null; then
    echo "[✓] NVIDIA GPU detected"
    nvidia-smi --query-gpu=name --format=csv,noheader
else
    echo "[!] No NVIDIA GPU detected (running locally?)"
fi

# Install Python dependencies
echo ""
echo "[*] Installing Python dependencies..."
pip install -r requirements.txt

# Create .env from example if it doesn't exist
if [ ! -f .env ]; then
    echo ""
    echo "[*] Creating .env file from template..."
    cp .env.example .env
    echo "[!] IMPORTANT: Edit .env with your actual credentials!"
    echo "    nano .env"
fi

echo ""
echo "=============================================="
echo "  Setup complete!"
echo "=============================================="
echo ""
echo "Next steps:"
echo ""
echo "  1. Edit .env with your credentials:"
echo "     nano .env"
echo ""
echo "  2. Make sure ComfyUI is running:"
echo "     cd /path/to/ComfyUI && python main.py"
echo ""
echo "  3. Start the worker:"
echo "     python worker.py"
echo ""
echo "=============================================="
