#!/usr/bin/env bash
set -e

echo ""
echo " Rank & Rent Deployer"
echo " ----------------------"
echo ""

# Check Python
if ! command -v python3 &>/dev/null; then
    echo " ERROR: python3 not found. Install Python 3.11+ from https://python.org"
    exit 1
fi

# Install dependencies once
if [ ! -f ".deps_installed" ]; then
    echo " Installing dependencies..."
    pip3 install -r requirements.txt
    touch .deps_installed
fi

# Bootstrap .env
if [ ! -f ".env" ]; then
    cp .env.example .env
    echo ""
    echo " IMPORTANT: Open .env and add your API keys, then run ./start.sh again."
    echo ""
    exit 0
fi

echo " Starting server — open http://localhost:5000 in your browser."
echo ""
python3 server.py
