#!/bin/bash
# ─────────────────────────────────────────────────────
#  Free Fire Level Bot — Termux Setup Script
#  Run: bash SETUP_LEVEL_TERMUX.sh
# ─────────────────────────────────────────────────────

set -e

echo ""
echo "  ╔═══════════════════════════════════════════╗"
echo "  ║  Free Fire Level Bot — Termux Setup v1.0   ║"
echo "  ╚═══════════════════════════════════════════╝"
echo ""

# Check Termux
if ! command -v pkg &> /dev/null; then
    echo "  ⚠️  Not running in Termux. This script is designed for Termux."
    echo "  On other systems, install Python 3.8+ and run:"
    echo "    pip install httpx pycryptodome protobuf protobuf-decoder PyJWT"
    exit 1
fi

# Update packages
echo "  [1/4] Updating packages..."
pkg update -y > /dev/null 2>&1 || true

# Install Python
echo "  [2/4] Installing Python..."
pkg install -y python > /dev/null 2>&1 || true

# Install pip dependencies
echo "  [3/4] Installing Python dependencies..."
pip install httpx pycryptodome protobuf protobuf-decoder PyJWT 2>/dev/null || pip3 install httpx pycryptodome protobuf protobuf-decoder PyJWT

# Create data directory
echo "  [4/4] Setting up data directory..."
mkdir -p data

echo ""
echo "  ✅ Setup complete!"
echo ""
echo "  To start the bot, run:"
echo "     python level_menu.py"
echo ""
echo "  Or directly:"
echo "     python run_level.py --uid YOUR_UID --password YOUR_PASSWORD --team-code TEAM_CODE"
echo ""
