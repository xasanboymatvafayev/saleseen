# 🌟 Stars Shop Telegram Bot

Telegram Stars va Premium sotib olish uchun to'liq funksional bot.

## 🚀 Xususiyatlar

### 📱 Foydalanuvchi uchun
- **Stars sotib olish** - Turli miqdorlarda Telegram Stars (50 dan 10,000 gacha)
- **Premium sotib olish** - 1, 3, 6, 12 oylik Telegram Premium
- **Hisobni to'ldirish** - Karta orqali to'lov va admin tasdiqlashi
- **Maʼlumotlar** - Sotib olingan Stars va Premium statistikasi
- **Majburiy obuna** - Kanallarga obuna tekshirish

### 👨‍💼 Admin paneli
- **Foydalanuvchilarga xabar yuborish** - Barcha foydalanuvchilarga broadcast
- **Foydalanuvchilarni boshqarish** - ID orqali to'liq nazorat
- **Majburiy obuna kanallari** - Kanallarni qo'shish/o'chirish
- **Promokodlar** - Bonus berish va kanalga bog'lash
- **Bot statistikasi** - To'liq statistika va daromad
- **Karta boshqaruvi** - To'lov kartalarini boshqarish
- **Narxlarni o'zgartirish** - Stars va Premium narxlari

## 📦 O'rnatish

1. **Klonlash**
```bash
git clone https://github.com/yourusername/stars-shop-bot.git
cd stars-shop-bot
```

2. **Virtual muhit yaratish**
```bash
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
```

3. **Kutubxonalarni o'rnatish**
```bash
pip install -r requirements.txt
```

4. **Konfiguratsiya**
`config.py` faylini oching va quyidagilarni o'zgartiring:
```python
BOT_TOKEN = "YOUR_BOT_TOKEN_HERE"  # @BotFather dan olingan token
ADMINS = [123456789]  # Admin user ID
REQUIRED_CHANNELS = [  # Majburiy obuna kanallari
    {"id": -1001234567890, "name": "Official Channel"}
]
```

5. **Botni ishga tushirish**
```bash
python bot.py
```

## 🎳 Ishlatish

### Foydalanuvchi uchun
1. Botga `/start` deb yozing
2. Majburiy kanallarga obuna bo'ling
3. Asosiy menyudan kerakli bo'limni tanlang
4. Stars yoki Premium sotib oling
5. Hisobni to'ldiring

### Admin uchun
1. `/panel` buyrug'i bilan admin paneliga o'ting
2. Kerakli funksiyani tanlang
3. Ko'rsatmalarga amal qiling

## 🗄️ Ma'lumotlar bazasi

Bot SQLite3 dan foydalanadi va quyidagi jadvallarni o'z ichiga oladi:
- `users` - Foydalanuvchilar ma'lumotlari
- `transactions` - Tranzaksiyalar tarixi
- `payment_requests` - To'lov so'rovlari
- `channels` - Majburiy obuna kanallari
- `promo_codes` - Promokodlar
- `cards` - To'lov kartalari
- `prices` - Narxlar

## 💰 To'lov tizimi

1. Foydalanuvchi hisobni to'ldirish uchun miqdorni kiritadi
2. Bot karta raqamini ko'rsatadi
3. Foydalanuvchi to'lov qiladi va chek rasmini yuboradi
4. Admin to'lovni tekshiradi va tasdiqlaydi/bekor qiladi
5. Tasdiqlangan pul foydalanuvchi hisobiga qo'shiladi

## 🔧 Sozlamalar

### Narxlarni o'zgartirish
Admin panel orqali:
1. `/panel` - Admin paneliga kirish
2. `💰 Narxlarni o'zgartirish` - Tanlash
3. Format: `turs|narx` (masalan: `stars|250`)

### Kanallarni qo'shish
```python
# config.py faylida
REQUIRED_CHANNELS = [
    {"id": -1001234567890, "name": "Official Channel"},
    {"id": -1001234567891, "name": "News Channel"}
]
```

## 🛠️ Texnik xususiyatlar

- **Framework**: Aiogram 3.4.1
- **Database**: SQLite3
- **Language**: Python 3.8+
- **State Management**: FSM (Finite State Machine)
- **Async**: Full async support

## 📞 Yordam

- **Admin**: @Salee_uz
- **Dasturchi**: @MamurZokirov

## 📄 Litsenziya

Bu loyiha MIT litsenziyasi ostida tarqatilgan.

## 🤝 Hissa qo'shish

1. Repozitoriyani fork qiling
2. O'zgartirishlar uchun branch yarating
3. O'zgarishlarni commit qiling
4. Pull request yarating

---

**Eslatma**: Botdan to'liq foydalanishdan oldin barcha konfiguratsiyalarni tekshiring va to'g'ri sozlang!
