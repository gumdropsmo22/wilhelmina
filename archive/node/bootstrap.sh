#!/usr/bin/env bash
# Archived bootstrap for the Node prototype. Not used by Python runtime.
# C1 moved this script under archive/node. Keep for forensic reference only.
# STUB: verify Node-only steps here if you plan to run the old prototype.

set -e
echo "Installing archived Node dependencies..."
npm install
cp .env.example .env
chmod +x bootstrap.sh
