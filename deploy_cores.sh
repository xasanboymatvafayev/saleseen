#!/bin/bash

# Cores.uz da Python botni joylash skripti

echo "🚀 Cores.uz da Python botni joylash boshlanmoqda..."

# 1. System update
echo "📦 System yangilanmoqda..."
sudo apt update && sudo apt upgrade -y

# 2. Python o'rnatish
echo "🐍 Python o'rnatilmoqda..."
sudo apt install python3 python3-pip python3-venv git -y

# 3. Virtual environment yaratish
echo "📁 Virtual environment yaratilmoqda..."
python3 -m venv bot_env
source bot_env/bin/activate

# 4. Project papkasiga o'tish
echo "📂 Project papkasiga o'tilmoqda..."
mkdir -p /root/bot
cd /root/bot

# 5. Fayllarni yuklash (git orqali)
echo "📥 Kodlar yuklanmoqda..."
# Git repositorydan yuklash
# git clone your_repository_url .

# 6. Kutubxonalarni o'rnatish
echo "📚 Kutubxonalar o'rnatilmoqda..."
pip install aiogram python-dotenv

# 7. Botni background rejimda ishga tushirish
echo "🤖 Bot ishga tushirilmoqda..."
nohup python bot.py > bot.log 2>&1 &

# 8. Process holatini tekshirish
echo "🔍 Process holati:"
ps aux | grep python

echo "✅ Bot muvaffaqiyatli joylandi!"
echo "📝 Loglar: tail -f /root/bot/bot.log"
