#!/bin/bash
# ==============================================================================
# Script Pembaruan Otomatis Bot Rekap Nilai CBT SMP Hang Tuah 5
# ==============================================================================

set -e

GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo -e "${BLUE}=====================================================${NC}"
echo -e "${BLUE}   🔄 MEMPERBARUI BOT REKAP NILAI DARI GITHUB        ${NC}"
echo -e "${BLUE}=====================================================${NC}"

APP_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$APP_DIR"

echo -e "${YELLOW}📥 Menarik pembaruan kode terbaru (git pull)...${NC}"
git pull origin main

if [ "$EUID" -eq 0 ]; then
    echo -e "${YELLOW}⚙️  Merestart layanan bot di background (root system)...${NC}"
    systemctl restart telegram-rekap-bot.service
    echo -e "\n${GREEN}=====================================================${NC}"
    echo -e "${GREEN}   ✅ BOT BERHASIL DIPERBARUI KE VERSI TERBARU!      ${NC}"
    echo -e "${GREEN}=====================================================${NC}"
    systemctl status telegram-rekap-bot.service --no-pager
else
    echo -e "${YELLOW}⚙️  Merestart layanan bot di background (user mode)...${NC}"
    systemctl --user restart telegram-rekap-bot.service
    echo -e "\n${GREEN}=====================================================${NC}"
    echo -e "${GREEN}   ✅ BOT BERHASIL DIPERBARUI KE VERSI TERBARU!      ${NC}"
    echo -e "${GREEN}=====================================================${NC}"
    systemctl --user status telegram-rekap-bot.service --no-pager
fi
