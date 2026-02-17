import sqlite3
import logging
import os
from datetime import datetime
from aiogram import types, Bot, F, Dispatcher, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery, ReplyKeyboardMarkup, KeyboardButton
from aiogram.filters import Command, StateFilter
from config import ADMINS, REQUIRED_CHANNELS, OFFICIAL_CHANNEL, TRADE_GROUP, DATABASE_PATH
from utils import get_required_channels
from states import AdminState, TonSettingsState
from utils import get_price

# Use the same DATABASE_PATH from config
DB_PATH = DATABASE_PATH

# Create router
router = Router()

# Helper: Check Admin
def is_admin(user_id):
    try:
        # First check config ADMINS
        from config import ADMINS
        if user_id in ADMINS:
            return True
        
        # Then check database
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute('SELECT is_admin FROM users WHERE user_id = ?', (user_id,))
        row = cursor.fetchone()
        conn.close()
        return bool(row and row[0])
    except Exception as e:
        # Fallback to config check
        from config import ADMINS
        return user_id in ADMINS

# Admin menu keyboard
def get_admin_keyboard():
    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="📢 Xabar Yuborish")],
            [KeyboardButton(text="👤 Foydalanuvchilar"), KeyboardButton(text="📢 Kanallar")],
            [KeyboardButton(text="🎫 Promokodlar"), KeyboardButton(text="📊 Statistika")],
            [KeyboardButton(text="💳 Karta sozlamalari"), KeyboardButton(text="💰 Narxlar")],
            [KeyboardButton(text="⚙️ TON Sozlamalari"), KeyboardButton(text="💎 Referal bonus")],
            [KeyboardButton(text="👨‍💼 Adminlar"), KeyboardButton(text="🔙 Orqaga")],
        ],
        resize_keyboard=True
    )
    return keyboard

# Admin panel handler
async def admin_panel_handler(message: types.Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        await message.answer("❌ Siz admin emassiz!")
        return
    
    await state.clear()
    await message.answer(
        "👨‍💻 *Admin paneliga xush kelibsiz!*\n"
        "Barcha funksiyalar faollashtirildi. Kerakli bo'limni tanlang:",
        parse_mode="Markdown",
        reply_markup=get_admin_keyboard()
    )

# Statistics Handler (Improved)
async def show_statistics(message: types.Message):
    if not is_admin(message.from_user.id):
        await message.answer("❌ Siz admin emassiz!")
        return
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute('SELECT COUNT(*) FROM users')
    total_users = cursor.fetchone()[0]
    
    cursor.execute('SELECT COUNT(*) FROM users WHERE created_at >= date("now")')
    new_users_today = cursor.fetchone()[0]
    
    cursor.execute('SELECT SUM(amount) FROM transactions WHERE status = "completed"')
    total_revenue = cursor.fetchone()[0] or 0
    
    cursor.execute('SELECT SUM(amount) FROM transactions WHERE status = "completed" AND created_at >= date("now")')
    revenue_today = cursor.fetchone()[0] or 0
    
    cursor.execute('SELECT COUNT(*) FROM purchase_requests WHERE status = "pending"')
    pending_purchases = cursor.fetchone()[0]
    
    cursor.execute('SELECT COUNT(*) FROM payment_requests WHERE status = "pending"')
    pending_payments = cursor.fetchone()[0]
    
    conn.close()
    
    text = (
        "📊 *Bot Statistikasi*\n\n"
        f"👥 *Foydalanuvchilar:*\n"
        f"  • Umumiy: {total_users}\n"
        f"  • Bugun qo'shilgan: {new_users_today}\n\n"
        f"💰 *Moliyaviy:*\n"
        f"  • Umumiy daromad: {total_revenue:,.0f} so'm\n"
        f"  • Bugungi daromad: {revenue_today:,.0f} so'm\n\n"
        f"⏳ *Kutilayotgan so'rovlar:*\n"
        f"  • Xaridlar: {pending_purchases}\n"
        f"  • To'lovlar: {pending_payments}"
    )
    
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⏳ Kutilayotgan so'rovlar", callback_data="show_pending_requests")],
        [InlineKeyboardButton(text="🔙 Orqaga", callback_data="back_to_admin")]
    ])
    
    await message.answer(text, parse_mode="Markdown", reply_markup=kb)

# Card Settings Handlers (Missing implementation)
async def manage_cards_handler(message: types.Message):
    if not is_admin(message.from_user.id):
        await message.answer("❌ Siz admin emassiz!")
        return
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('SELECT card_number, card_holder, is_active FROM cards WHERE is_active = 1 LIMIT 1')
    card = cursor.fetchone()
    conn.close()
    
    text = "💳 *Karta Sozlamalari*\n\n"
    if card:
        text += f"💳 Joriy karta: `{card[0]}`\n👤 Egasi: {card[1]}"
    else:
        text += "❌ Faol karta o'rnatilmagan!"
        
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔢 Raqamni o'zgartirish", callback_data="admin_edit_card_number")],
        [InlineKeyboardButton(text="👤 Egani o'zgartirish", callback_data="admin_edit_card_holder")],
        [InlineKeyboardButton(text="🆕 Yangi karta qo'shish", callback_data="admin_add_card")],
        [InlineKeyboardButton(text="🔙 Orqaga", callback_data="back_to_admin")]
    ])
    await message.answer(text, parse_mode="Markdown", reply_markup=kb)

async def admin_edit_card_number_cb(callback: types.CallbackQuery, state: FSMContext):
    await callback.message.edit_text(
        "🔢 *Yangi karta raqamini kiriting:*",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🔙 Bekor qilish", callback_data="back_to_admin")]])
    )
    await state.set_state(AdminState.edit_card_number)
    await callback.answer()

async def process_edit_card_number(message: types.Message, state: FSMContext):
    if not is_admin(message.from_user.id): return
    number = message.text.strip()
    clean_number = number.replace(" ", "")
    if not clean_number.isdigit() or len(clean_number) < 16:
        await message.answer("❌ Karta raqami noto'g'ri! Kamida 16 ta raqam bo'lishi kerak.")
        return

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    # Update the active card's number
    cursor.execute('UPDATE cards SET card_number = ? WHERE is_active = 1', (number,))
    if cursor.rowcount == 0:
        # If no active card, insert one
        cursor.execute('INSERT INTO cards (card_number, card_holder, is_active) VALUES (?, ?, 1)', (number, "NOMALUM"))
    conn.commit()
    conn.close()
    
    await message.answer(f"✅ *Karta raqami muvaffaqiyatli o'zgartirildi!*\n\n💳 Yangi raqam: `{number}`", parse_mode="Markdown")
    await state.clear()

async def admin_edit_card_holder_cb(callback: types.CallbackQuery, state: FSMContext):
    await callback.message.edit_text(
        "👤 *Karta egasining ismini kiriting:*",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🔙 Bekor qilish", callback_data="back_to_admin")]])
    )
    await state.set_state(AdminState.edit_card_holder)
    await callback.answer()

async def process_edit_card_holder(message: types.Message, state: FSMContext):
    if not is_admin(message.from_user.id): return
    holder = message.text.strip().upper()
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    # Update the active card's holder
    cursor.execute('UPDATE cards SET card_holder = ? WHERE is_active = 1', (holder,))
    if cursor.rowcount == 0:
        # If no active card, insert one
        cursor.execute('INSERT INTO cards (card_number, card_holder, is_active) VALUES (?, ?, 1)', ("8600000000000000", holder))
    conn.commit()
    conn.close()
    
    await message.answer(f"✅ *Karta egasi muvaffaqiyatli o'zgartirildi!*\n\n👤 Yangi ega: {holder}", parse_mode="Markdown")
    await state.clear()

async def admin_add_card_cb(callback: types.CallbackQuery, state: FSMContext):
    await callback.message.edit_text(
        "💳 *Yangi karta ma'lumotlarini kiriting:*\n\nFormat: `KARTA_RAQAMI|KARTA_EGASI`",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🔙 Bekor qilish", callback_data="back_to_admin")]])
    )
    await state.set_state(AdminState.add_card)
    await callback.answer()

async def process_add_card(message: types.Message, state: FSMContext):
    if not is_admin(message.from_user.id): return
    try:
        if "|" not in message.text:
            await message.answer("❌ Noto'g'ri format!\n\nIltimos, karta raqami va egasini quyidagi formatda yuboring:\n`RAQAM|EGA` \n\nMisol: `8600123456789012|FALONCHI PISTONCHI`", parse_mode="Markdown")
            return
            
        parts = message.text.split("|")
        if len(parts) < 2:
            raise ValueError
            
        number = parts[0].strip()
        holder = parts[1].strip().upper()
        
        # Validate number (allow spaces)
        clean_number = number.replace(" ", "")
        if not clean_number.isdigit() or len(clean_number) < 16:
            await message.answer("❌ Karta raqami noto'g'ri! Kamida 16 ta raqam bo'lishi kerak.")
            return

        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute('UPDATE cards SET is_active = 0') # Deactivate old cards
        cursor.execute('INSERT INTO cards (card_number, card_holder, is_active) VALUES (?, ?, 1)', (number, holder))
        conn.commit()
        conn.close()
        
        await message.answer(f"✅ *Yangi karta muvaffaqiyatli o'rnatildi!*\n\n💳 Karta: `{number}`\n👤 Egasi: {holder}", parse_mode="Markdown")
        await state.clear()
    except Exception as e:
        await message.answer(f"❌ Xatolik yuz berdi: {str(e)}\n\nFormat: `RAQAM|EGA` ko'rinishida qayta yuboring.")


# User Management Handler
async def manage_users_handler(message: types.Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        await message.answer("❌ Siz admin emassiz!")
        return
    await state.clear()
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('SELECT user_id, balance, is_banned FROM users ORDER BY created_at DESC LIMIT 10')
    users = cursor.fetchall()
    
    cursor.execute('SELECT COUNT(*) FROM users')
    total_users = cursor.fetchone()[0]
    conn.close()
    
    text = f"👥 *Foydalanuvchilarni boshqarish*\n\nJami foydalanuvchilar: {total_users}\n\n*Oxirgi 10 foydalanuvchi:*\n"
    for u in users:
        text += f"{'🚫' if u[2] else '✅'} ID: `{u[0]}` | {u[1]:,.0f} so'm\n"
    
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔍 Foydalanuvchini qidirish", callback_data="admin_user_search")],
        [InlineKeyboardButton(text="🔙 Orqaga", callback_data="back_to_admin")]
    ])
    await message.answer(text, parse_mode="Markdown", reply_markup=kb)

async def admin_user_search_cb(callback: types.CallbackQuery, state: FSMContext):
    await callback.message.edit_text("🔍 *Foydalanuvchi ID sini kiriting:*", parse_mode="Markdown",
                                       reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🔙 Bekor qilish", callback_data="back_to_admin")]]))
    await state.set_state(AdminState.search_user)
    await callback.answer()

async def show_user_info(message: types.Message, user_id: int):
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute('SELECT user_id, balance, is_banned, username, full_name, ton_balance FROM users WHERE user_id = ?', (user_id,))
        user = cursor.fetchone()
        conn.close()
        
        if not user:
            await message.answer("❌ Foydalanuvchi topilmadi!")
            return
        
        username = f"@{user[3]}" if user[3] else "Noma'lum"
        name = user[4] or "Noma'lum"
        text = f"👤 *Foydalanuvchi:* {name} ({username})\n"
        text += f"🆔 ID: `{user[0]}`\n"
        text += f"💰 Balans: {user[1]:,.0f} so'm\n"
        text += f"💎 TON Balans: {user[5]:.2f} TON\n"
        text += f"📊 Holati: {'🚫 Banlangan' if user[2] else '✅ Faol'}"
        
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="➕ Pul qo'shish", callback_data=f"admin_add_{user[0]}"), InlineKeyboardButton(text="➖ Pul ayirish", callback_data=f"admin_remove_{user[0]}")],
            [InlineKeyboardButton(text="🚫 Banlash" if not user[2] else "✅ Bandan ochish", callback_data=f"admin_{'ban' if not user[2] else 'unban'}_{user[0]}")],
            [InlineKeyboardButton(text="🔙 Orqaga", callback_data="back_to_admin")]
        ])
        await message.answer(text, parse_mode="Markdown", reply_markup=kb)
    except Exception as e:
        print(f"Error in show_user_info: {e}")
        await message.answer("❌ Xatolik yuz berdi!")

async def process_user_search(message: types.Message, state: FSMContext = None):
    if not is_admin(message.from_user.id): return
    try:
        user_id = int(message.text.strip())
        await show_user_info(message, user_id)
    except Exception as e:
        print(f"Error in process_user_search: {e}")
        await message.answer("❌ Noto'g'ri ID!")
    finally:
        if state:
            await state.clear()

# Balance Management
async def admin_manage_balance_cb(callback: types.CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id): return
    data = callback.data.split("_")
    action = data[1] # add or remove
    user_id = int(data[2])
    
    await state.update_data(target_user_id=user_id, action=action)
    
    action_text = "qo'shish" if action == "add" else "ayirish"
    await callback.message.edit_text(
        f"💰 *Foydalanuvchi balansiga pul {action_text}:*\n\n"
        f"ID: `{user_id}`\n\n"
        f"Miqdorni kiriting (so'm):",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🔙 Bekor qilish", callback_data="back_to_admin")]])
    )
    await state.set_state(AdminState.manage_user_balance)
    await callback.answer()

async def process_manage_balance(message: types.Message, state: FSMContext):
    if not is_admin(message.from_user.id): return
    try:
        data = await state.get_data()
        user_id = data.get('target_user_id')
        action = data.get('action')
        amount = float(message.text.strip())
        
        if amount <= 0:
            await message.answer("❌ Miqdor musbat bo'lishi kerak!")
            return
        
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        if action == 'add':
            cursor.execute('UPDATE users SET balance = balance + ? WHERE user_id = ?', (amount, user_id))
        else:
            cursor.execute('UPDATE users SET balance = MAX(0, balance - ?) WHERE user_id = ?', (amount, user_id))
        
        conn.commit()
        
        cursor.execute('SELECT balance FROM users WHERE user_id = ?', (user_id,))
        new_balance = cursor.fetchone()[0]
        conn.close()
        
        await message.answer(f"✅ Balans yangilandi!\n\nID: `{user_id}`\nYangi balans: {new_balance:,.0f} so'm", parse_mode="Markdown")
        # Show updated user info
        await show_user_info(message, user_id)
    except ValueError:
        await message.answer("❌ Noto'g'ri miqdor!")
    except Exception as e:
        await message.answer(f"❌ Xatolik: {e}")
    finally:
        await state.clear()

# Channel Management Handlers
async def manage_channels_handler(message: types.Message):
    if not is_admin(message.from_user.id): return
    
    # Get active channels using the utility
    active_channels = await get_required_channels()
    
    # Get all DB channels for more details (IDs etc)
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('SELECT id, channel_id, channel_name FROM channels')
    db_channels = cursor.fetchall()
    conn.close()
    
    text = "📺 *Majburiy obuna kanallari:*\n\n"
    
    if not active_channels:
        text += "_Hozircha majburiy obuna kanallari yo'q._\n"
    else:
        for cid, name in active_channels:
            # Check if it's a config channel or DB channel
            is_main = any(str(cid) == str(c['id']) for c in REQUIRED_CHANNELS)
            type_label = "📌 (Asosiy)" if is_main else "➕ (Qo'shimcha)"
            # Escape special characters for Markdown and limit length
            name_safe = (name or "Noma'lum")[:30].replace("*", "\\*").replace("_", "\\_").replace("`", "\\`").replace("[", "\\[").replace("]", "\\]").replace(")", "\\)").replace("(", "\\(")
            cid_safe = str(cid or "Noma'lum")[:20].replace("*", "\\*").replace("_", "\\_").replace("`", "\\`").replace("[", "\\[").replace("]", "\\]").replace(")", "\\)").replace("(", "\\(")
            text += f"📺 {name_safe} ({cid_safe}) {type_label}\n"
            
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ Kanal qo'shish", callback_data="admin_channel_add")],
        [InlineKeyboardButton(text="🗑️ Kanal o'chirish", callback_data="admin_channel_remove")],
        [InlineKeyboardButton(text="🔙 Orqaga", callback_data="back_to_admin")]
    ])
    await message.answer(text, parse_mode="Markdown", reply_markup=kb)


async def admin_channel_add_cb(callback: types.CallbackQuery, state: FSMContext):
    await callback.message.edit_text(
        "📺 *Kanal qo'shish*\n\n"
        "Kanal username yoki ID sini kiriting:\n"
        "• Username (masalan: @suxa_cyber yoki suxa_cyber)\n"
        "• Numeric ID (masalan: -1001234567890)\n\n"
        "_@ belgisiz yoki bilan kiriting._",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🔙 Bekor qilish", callback_data="back_to_admin")]])
    )
    await state.set_state(AdminState.add_channel)
    await callback.answer()

async def admin_channel_remove_cb(callback: types.CallbackQuery, state: FSMContext):
    # Get active channels using utility
    active_channels = await get_required_channels()
    
    # Get DB channels specifically for IDs
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('SELECT id, channel_id, channel_name FROM channels')
    db_channels = cursor.fetchall()
    conn.close()
    
    text = "🗑️ *Kanal o'chirish*\n\n"
    text += "Quyidagilardan birini kiriting:\n"
    text += "• DB ID (masalan: 1)\n"
    text += "• Kanal nomi (masalan: STARS SHOP)\n"
    text += "• Kanal username (masalan: @suxa_cyber yoki suxa_cyber)\n\n"
    
    # Identify protected channel
    protected_id = REQUIRED_CHANNELS[0]['id'] if REQUIRED_CHANNELS else None
    
    # List Main channels (Config)
    text += "📌 *Asosiy kanallar:*\n"
    for c in REQUIRED_CHANNELS:
        is_deleted = not any(str(c['id']) == str(ac[0]) for ac in active_channels)
        if is_deleted: continue # Don't show already deleted config channels
        
        status = "🚫 (O'chirib bo'lmaydi)" if str(c['id']) == str(protected_id) else "🗑️ (O'chirish mumkin)"
        text += f"  • {c['name']} ({c['id']}) {status}\n"
    
    # List DB channels
    if db_channels:
        text += "\n➕ *Qo'shimcha kanallar:*\n"
        for c in db_channels:
            text += f"  • ID: {c[0]} | {c[2]} | {c[1]}\n"
    
    await callback.message.edit_text(
        text,
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🔙 Bekor qilish", callback_data="back_to_admin")]])
    )
    await state.set_state(AdminState.remove_channel)
    await callback.answer()

async def process_remove_channel(message: types.Message, state: FSMContext):
    if not is_admin(message.from_user.id): return
    
    input_text = message.text.strip()
    search_term = input_text.lower().lstrip('@')
    
    # 1. Check Protected Channel
    protected_id = REQUIRED_CHANNELS[0]['id'] if REQUIRED_CHANNELS else None
    if protected_id:
        p_id = protected_id.lower().lstrip('@')
        if search_term == p_id or input_text.lower() == protected_id.lower():
            await message.answer(f"❌ *{REQUIRED_CHANNELS[0]['name']}* botning asosiy kanali bo'lib, uni o'chirib bo'lmaydi!", parse_mode="Markdown")
            await state.clear()
            return

    # 2. Check other Config Channels
    for ch in REQUIRED_CHANNELS[1:]: # Skip the first one as it's protected
        ch_id = ch['id'].lower().lstrip('@')
        ch_name = ch['name'].lower()
        if search_term == ch_id or input_text.lower() == ch['id'].lower() or input_text.lower() == ch_name:
            # Mark as deleted in DB
            try:
                conn = sqlite3.connect(DB_PATH)
                cursor = conn.cursor()
                cursor.execute('INSERT OR IGNORE INTO deleted_main_channels (channel_id) VALUES (?)', (ch['id'],))
                conn.commit()
                conn.close()
                await message.answer(f"✅ Asosiy kanal muvaffaqiyatli o'chirildi: *{ch['name']}*", parse_mode="Markdown")
            except Exception as e:
                await message.answer(f"❌ Xatolik: {e}")
            await state.clear()
            return

    # 3. Check DB Channels
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    try:
        channel = None
        # Try as DB ID
        try:
            db_id = int(input_text)
            cursor.execute('SELECT id, channel_id, channel_name FROM channels WHERE id = ?', (db_id,))
            channel = cursor.fetchone()
        except ValueError: pass
        
        # Try by name
        if not channel:
            cursor.execute('SELECT id, channel_id, channel_name FROM channels WHERE channel_name LIKE ?', (f'%{input_text}%',))
            channel = cursor.fetchone()
        
        # Try by username
        if not channel:
            cursor.execute('SELECT id, channel_id, channel_name FROM channels WHERE channel_id = ? OR channel_id = ?', (input_text, f'@{search_term}'))
            channel = cursor.fetchone()
            
        if channel:
            cursor.execute('DELETE FROM channels WHERE id = ?', (channel[0],))
            conn.commit()
            await message.answer(f"✅ Qo'shimcha kanal o'chirildi: *{channel[2]}*", parse_mode="Markdown")
        else:
            await message.answer("❌ Kanal topilmadi!")
            
    except Exception as e:
        await message.answer(f"❌ Xatolik: {e}")
    finally:
        conn.close()
        await state.clear()

# Promo Handlers
async def manage_promo_handler(message: types.Message):
    if not is_admin(message.from_user.id):
        await message.answer("❌ Siz admin emassiz!")
        return
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('SELECT id, code, bonus_amount, usage_limit, used_count FROM promo_codes ORDER BY id DESC')
    promos = cursor.fetchall()
    conn.close()
    
    text = "🎫 *Promokodlar:*\n\n"
    if not promos:
        text += "_Hozircha promokodlar mavjud emas._\n"
    else:
        for p in promos:
            # p[0]=id, p[1]=code, p[2]=bonus_amount, p[3]=usage_limit, p[4]=used_count
            text += f"🎫 `{p[1]}` | {p[2]:,.0f} so'm | {p[4]}/{p[3]} ishlatilgan\n"
    
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🆕 Yaratish", callback_data="promo_new")],
        [InlineKeyboardButton(text="🔙 Orqaga", callback_data="back_to_admin")]
    ])
    await message.answer(text, parse_mode="Markdown", reply_markup=kb)

async def promo_new_cb(callback: types.CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ Siz admin emassiz!")
        return
    await callback.message.edit_text(
        "🎫 *Yangi promokod yaratish*\n\n"
        "Format: `KOD|SUMMA|LIMIT`\n\n"
        "Masalan: `PROMO2024|50000|100`\n\n"
        "*KOD* - promokod nomi (faqat harflar va raqamlar)\n"
        "*SUMMA* - bonus miqdori (so'm)\n"
        "*LIMIT* - ishlatish chegarasi (necha marta)",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🔙 Bekor qilish", callback_data="back_to_admin")]])
    )
    await state.set_state(AdminState.add_promo)
    await callback.answer()

async def process_add_promo(message: types.Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        await message.answer("❌ Siz admin emassiz!")
        await state.clear()
        return
    try:
        parts = message.text.split("|")
        if len(parts) != 3:
            await message.answer("❌ Xato format! `KOD|SUMMA|LIMIT` ko'rinishida yuboring.\nMasalan: `PROMO2024|50000|100`")
            await state.clear()
            return
        
        code = parts[0].strip().upper()
        bonus_amount = float(parts[1].strip())
        usage_limit = int(parts[2].strip())
        
        if bonus_amount <= 0 or usage_limit <= 0:
            await message.answer("❌ Summa va limit musbat son bo'lishi kerak!")
            await state.clear()
            return
        
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute('INSERT INTO promo_codes (code, bonus_amount, usage_limit) VALUES (?, ?, ?)', (code, bonus_amount, usage_limit))
        conn.commit()
        conn.close()
        await message.answer(
            f"✅ Promokod yaratildi!\n\n"
            f"🎫 Kod: `{code}`\n"
            f"💰 Bonus: {bonus_amount:,.0f} so'm\n"
            f"📊 Limit: {usage_limit} ta",
            parse_mode="Markdown"
        )
    except ValueError:
        await message.answer("❌ Xato format! Summa va limit raqam bo'lishi kerak.\nFormat: `KOD|SUMMA|LIMIT`")
    except sqlite3.IntegrityError:
        await message.answer("❌ Bu promokod allaqachon mavjud!")
    except Exception as e:
        await message.answer(f"❌ Xatolik: {str(e)}")
    finally:
        await state.clear()

# Broadcast Handlers
async def admin_broadcast_prompt(message: types.Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        await message.answer("❌ Siz admin emassiz!")
        return
    await message.answer("📢 *Barcha foydalanuvchilarga yuboriladigan xabarni kiriting:*", parse_mode="Markdown")
    await state.set_state(AdminState.broadcast_message)

async def process_broadcast(message: types.Message, state: FSMContext):
    text = message.text
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('SELECT user_id FROM users')
    users = cursor.fetchall()
    conn.close()
    s, e = 0, 0
    for u in users:
        try:
            await message.bot.send_message(u[0], text)
            s += 1
        except: e += 1
    await message.answer(f"✅ Xabar yuborish yakunlandi.\nBajarildi: {s}\nXato: {e}")
    await state.clear()

# Callback handlers for approvals
async def confirm_payment_handler(callback: types.CallbackQuery):
    p_id = int(callback.data.split("_")[2])
    if await confirm_payment(p_id, callback.bot):
        await callback.message.edit_caption(caption=callback.message.caption + "\n\n✅ TASDIQLANDI", reply_markup=None)
    await callback.answer()

async def cancel_payment_handler(callback: types.CallbackQuery):
    p_id = int(callback.data.split("_")[2])
    if await cancel_payment(p_id, callback.bot):
        await callback.message.edit_caption(caption=callback.message.caption + "\n\n❌ BEKOR QILINDI", reply_markup=None)
    await callback.answer()

async def confirm_purchase_handler(callback: types.CallbackQuery):
    p_id = int(callback.data.split("_")[2])
    if await confirm_purchase(p_id, callback.bot):
        await callback.message.edit_text(text=callback.message.text + "\n\n✅ TASDIQLANDI", reply_markup=None)
    await callback.answer()

async def cancel_purchase_handler(callback: types.CallbackQuery):
    p_id = int(callback.data.split("_")[2])
    if await cancel_purchase(p_id, callback.bot):
        await callback.message.edit_text(text=callback.message.text + "\n\n❌ BEKOR QILINDI", reply_markup=None)
    await callback.answer()

async def confirm_ton_purchase_cb(callback: types.CallbackQuery):
    w_id = int(callback.data.split("_")[3])
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('SELECT user_id, amount, status FROM ton_purchases WHERE id = ?', (w_id,))
    p = cursor.fetchone()
    if p and p[2] == 'pending':
        cursor.execute('UPDATE ton_purchases SET status = "completed" WHERE id = ?', (w_id,))
        conn.commit()
        await callback.bot.send_message(p[0], f"✅ TON yuborildi! Miqdor: {p[1]} TON")
        await callback.message.edit_text(text=callback.message.text + "\n\n✅ TASDIQLANDI", reply_markup=None)
    else:
        await callback.answer("⚠️ Ushbu so'rov allaqachon bajarilgan yoki bekor qilingan!", show_alert=True)
    conn.close()
    await callback.answer()

async def reject_ton_purchase_cb(callback: types.CallbackQuery):
    w_id = int(callback.data.split("_")[3])
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('SELECT user_id, amount, status FROM ton_purchases WHERE id = ?', (w_id,))
    p = cursor.fetchone()
    if p and p[2] == 'pending':
        cursor.execute('UPDATE users SET withdrawn_ton = withdrawn_ton - ? WHERE user_id = ?', (p[1], p[0]))
        cursor.execute('UPDATE ton_purchases SET status = "cancelled" WHERE id = ?', (w_id,))
        conn.commit()
        await callback.bot.send_message(p[0], "❌ TON yuborish rad etildi, mablag' qaytarildi.")
        await callback.message.edit_text(text=callback.message.text + "\n\n❌ RAD ETILDI", reply_markup=None)
    else:
        await callback.answer("⚠️ Ushbu so'rov allaqachon bajarilgan yoki bekor qilingan!", show_alert=True)
    conn.close()
    await callback.answer()

# Helper Logic
async def confirm_payment(p_id: int, bot: Bot):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('SELECT user_id, amount, status FROM payment_requests WHERE id = ?', (p_id,))
    p = cursor.fetchone()
    if p and p[2] == 'pending':
        cursor.execute('UPDATE payment_requests SET status = "confirmed" WHERE id = ?', (p_id,))
        cursor.execute('UPDATE users SET balance = balance + ? WHERE user_id = ?', (p[1], p[0]))
        conn.commit()
        await bot.send_message(p[0], f"✅ Tasdiqlandi! Hisobingizga +{p[1]:,.0f} so'm qo'shildi.")
        conn.close()
        return True
    conn.close()
    return False

async def cancel_payment(p_id: int, bot: Bot):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('SELECT status FROM payment_requests WHERE id = ?', (p_id,))
    p = cursor.fetchone()
    if p and p[0] == 'pending':
        cursor.execute('UPDATE payment_requests SET status = "cancelled" WHERE id = ?', (p_id,))
        conn.commit()
        conn.close()
        return True
    conn.close()
    return False

async def confirm_purchase(p_id: int, bot: Bot):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('SELECT user_id, product_type, status, details FROM purchase_requests WHERE id = ?', (p_id,))
    p = cursor.fetchone()
    if p and p[2] == 'pending':
        user_id, product_type, status, recipient_username = p
        
        # Update status
        cursor.execute('UPDATE purchase_requests SET status = "confirmed" WHERE id = ?', (p_id,))
        conn.commit()
        conn.close()
        
        # Handle different product types
        if product_type == 'premium_1month':
            # Get the price from the purchase request
            conn = sqlite3.connect(DB_PATH)
            cursor = conn.cursor()
            cursor.execute('SELECT price FROM purchase_requests WHERE id = ?', (p_id,))
            price_result = cursor.fetchone()
            premium_price = price_result[0] if price_result else 50000
            conn.close()
            
            # For 1-month premium, notify admin to manually provide premium
            await bot.send_message(
                user_id, 
                f"✅ *1 oylik Premium tasdiqlandi!*\n\n"
                f"👑 *Premium so'rovi tasdiqlandi!*\n"
                f"👤 *Qabul qiluvchi:* @{recipient_username}\n\n"
                f"📝 *Premium tez orada beriladi*\n"
                f"⏳ *Admin tomonidan qo'lda beriladi*",
                parse_mode="Markdown"
            )
            
            # Send completed notification to admins
            try:
                from bot import send_premium_completed_notification
                await send_premium_completed_notification(user_id, recipient_username, premium_price, str(p_id))
            except ImportError:
                # If import fails, send a simple notification
                for admin_id in get_all_admins():
                    try:
                        await bot.send_message(
                            admin_id,
                            f"✅ *1 oylik Premium tasdiqlandi!*\n\n"
                            f"👤 *Foydalanuvchi:* ID {user_id}\n"
                            f"🎯 *Qabul qiluvchi:* @{recipient_username}\n"
                            f"💰 *Narxi:* {premium_price:,} so'm\n"
                            f"🆔 *So'rov ID: #{p_id}\n\n"
                            f"⚠️ *Iltimos, Premiumni qo'lda bering!*",
                            parse_mode="Markdown"
                        )
                    except:
                        pass
            
            # Notify admins to manually provide premium
            for admin_id in get_all_admins():
                try:
                    await bot.send_message(
                        admin_id,
                        f"🔔 *1 oylik Premium tasdiqlandi!*\n\n"
                        f"👤 *Foydalanuvchi:* ID {user_id}\n"
                        f"🎯 *Qabul qiluvchi:* @{recipient_username}\n"
                        f"🆔 *So'rov ID: #{p_id}\n\n"
                        f"⚠️ *Iltimos, Premiumni qo'lda bering!*",
                        parse_mode="Markdown"
                    )
                except:
                    pass
        else:
            # For other purchases
            await bot.send_message(user_id, "✅ Xaridingiz tasdiqlandi va yetkazib berildi!")
        
        return True
    conn.close()
    return False

async def cancel_purchase(p_id: int, bot: Bot):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('SELECT user_id, price, status FROM purchase_requests WHERE id = ?', (p_id,))
    p = cursor.fetchone()
    if p and p[2] == 'pending':
        cursor.execute('UPDATE purchase_requests SET status = "cancelled" WHERE id = ?', (p_id,))
        cursor.execute('UPDATE users SET balance = balance + ? WHERE user_id = ?', (p[1], p[0]))
        conn.commit()
        await bot.send_message(p[0], "❌ Xaridingiz bekor qilindi, mablag' balansingizga qaytarildi.")
        conn.close()
        return True
    conn.close()
    return False

async def admin_ban_unban_cb(callback: types.CallbackQuery):
    if not is_admin(callback.from_user.id): return
    data = callback.data.split("_")
    action = data[1]
    user_id = int(data[2])
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute(f'UPDATE users SET is_banned = {"1" if action == "ban" else "0"} WHERE user_id = ?', (user_id,))
    conn.commit()
    conn.close()
    
    await callback.answer(f"✅ {'Banlandi' if action == 'ban' else 'Bandan ochildi'}")
    # Refresh the view
    await show_user_info(callback.message, user_id)

# Price Management Handler
async def change_price_handler(message: types.Message):
    if not is_admin(message.from_user.id):
        await message.answer("❌ Siz admin emassiz!")
        return
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Get all prices
    cursor.execute('SELECT item_type, price FROM prices')
    prices = cursor.fetchall()
    conn.close()
    
    text = "💰 *Narx sozlamalari:*\n\n"
    price_buttons = []
    
    # Stars price
    stars_price = next((p[1] for p in prices if p[0] == 'stars'), 200)
    text += f"⭐ Stars narxi: {stars_price:,.0f} so'm\n\n"
    price_buttons.append([InlineKeyboardButton(text=f"⭐ Stars narxini o'zgartirish", callback_data="set_stars_price")])
    
    # Stars sell price
    stars_sell_price = next((p[1] for p in prices if p[0] == 'stars_sell'), 900)
    text += f"💸 Stars sotish narxi: {stars_sell_price:,.0f} so'm\n\n"
    price_buttons.append([InlineKeyboardButton(text=f"💸 Stars sotish narxini o'zgartirish", callback_data="set_stars_sell_price")])
    
    # Premium prices
    text += "👑 Premium narxlari:\n"
    for period in ['1month', '3months', '6months', '12months']:
        key = f'premium_{period}'
        price = next((p[1] for p in prices if p[0] == key), 50000)
        period_name = period.replace('month', ' oy').replace('s', '')
        text += f"  • {period_name}: {price:,.0f} so'm\n"
        price_buttons.append([InlineKeyboardButton(text=f"👑 {period_name} narxini o'zgartirish", callback_data=f"set_premium_{period}")])
    
    price_buttons.append([InlineKeyboardButton(text="🔙 Orqaga", callback_data="back_to_admin")])
    
    kb = InlineKeyboardMarkup(inline_keyboard=price_buttons)
    await message.answer(text, parse_mode="Markdown", reply_markup=kb)

# Process Price Change
async def process_change_price(message: types.Message, state: FSMContext):
    if not is_admin(message.from_user.id): return
    try:
        data = await state.get_data()
        price_type = data.get('price_type')
        new_price = float(message.text.strip())
        
        if new_price <= 0:
            await message.answer("❌ Narx musbat son bo'lishi kerak!")
            return
        
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute('INSERT OR REPLACE INTO prices (item_type, price) VALUES (?, ?)', (price_type, new_price))
        conn.commit()
        conn.close()
        
        await message.answer(f"✅ Narx yangilandi: {price_type} = {new_price:,.0f} so'm")
    except ValueError:
        await message.answer("❌ Noto'g'ri format! Raqam kiriting.")
    except Exception as e:
        await message.answer(f"❌ Xatolik: {str(e)}")
    finally:
        await state.clear()

# Price Setting Callback Handler
async def handle_price_setting_cb(callback: types.CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id): 
        await callback.answer("❌ Siz admin emassiz!")
        return
    
    if callback.data == "back_to_prices":
        await callback.message.delete()
        await change_price_handler(types.Message(from_user=callback.from_user, chat=callback.message.chat, text="💰 Narxlar"))
        await callback.answer()
        return
    
    # Handle referral bonus callbacks separately
    if callback.data in ["set_ton_referral_bonus", "set_stars_referral_bonus", "set_uc_referral_bonus"]:
        await handle_referral_bonus_cb(callback, state)
        return
    
    # Determine price type from callback data
    if callback.data.startswith("set_stars_"):
        if callback.data == "set_stars_price":
            price_type = "stars"
            prompt = "⭐ *Stars narxini kiriting (so'm):*"
            current_price = get_price("stars")
        elif callback.data == "set_stars_sell_price":
            price_type = "stars_sell"
            prompt = "💸 *Stars sotish narxini kiriting (so'm):*"
            current_price = get_price("stars_sell")
        else:
            await callback.answer("❌ Noto'g'ri so'rov!")
            return
    elif callback.data.startswith("set_premium_"):
        period = callback.data.split("_")[2]
        price_type = f"premium_{period}"
        period_name = period.replace('month', ' oy').replace('s', '')
        prompt = f"👑 *{period_name} Premium narxini kiriting (so'm):*"
        current_price = get_price(price_type)
    else:
        await callback.answer("❌ Noto'g'ri so'rov!")
        return
    
    await state.update_data(price_type=price_type)
    await callback.message.edit_text(
        f"{prompt}\n\nJoriy narx: {current_price:,.2f}",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🔙 Bekor qilish", callback_data="back_to_prices")]])
    )
    await state.set_state(AdminState.change_price)
    await callback.answer()

# Referral Bonus Callback Handler
async def handle_referral_bonus_cb(callback: types.CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ Siz admin emassiz!")
        return
    
    if callback.data == "set_ton_referral_bonus":
        prompt = "💰 *TON referral bonus miqdorini kiriting:*"
        from referral import get_referral_bonus_by_type
        current_value = get_referral_bonus_by_type("ton")
        prompt += f"\n\nJoriy qiymat: {current_value} TON"
        await state.set_state(AdminState.change_referral_bonus)
        await state.update_data(bonus_type="ton")
        
    elif callback.data == "set_stars_referral_bonus":
        prompt = "⭐ *Stars referral bonus miqdorini kiriting:*"
        from referral import get_referral_bonus_by_type
        current_value = get_referral_bonus_by_type("stars")
        prompt += f"\n\nJoriy qiymat: {current_value} Stars"
        await state.set_state(AdminState.change_referral_bonus)
        await state.update_data(bonus_type="stars")
        
    elif callback.data == "set_uc_referral_bonus":
        prompt = "🎮 *UC referral bonus miqdorini kiriting:*"
        from referral import get_referral_bonus_by_type
        current_value = get_referral_bonus_by_type("uc")
        prompt += f"\n\nJoriy qiymat: {current_value} UC"
        await state.set_state(AdminState.change_referral_bonus)
        await state.update_data(bonus_type="uc")
    else:
        await callback.answer("❌ Noto'g'ri so'rov!")
        return
    
    await callback.message.edit_text(
        prompt,
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🔙 Bekor qilish", callback_data="back_to_admin")]])
    )
    await callback.answer()

# TON Settings Handler
async def admin_ton_settings_handler(message: types.Message):
    if not is_admin(message.from_user.id):
        await message.answer("❌ Siz admin emassiz!")
        return
    from utils import get_ton_wallet, get_ton_sell_price, get_ton_buy_price
    
    wallet = get_ton_wallet()
    sell_price = get_ton_sell_price()
    buy_price = get_ton_buy_price()  # Use correct function for buy price
    
    # Get current percentage from settings
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT setting_value FROM settings WHERE setting_key = 'ton_percentage'")
    percentage_result = cursor.fetchone()
    current_percentage = int(percentage_result[0]) if percentage_result else 10
    
    # Get market price from database
    cursor.execute("SELECT price FROM prices WHERE item_type = 'ton_market'")
    market_result = cursor.fetchone()
    market_price = float(market_result[0]) if market_result else (buy_price + sell_price) // 2
    conn.close()
    
    text = (
        "⚙️ *TON Sozlamalari*\n\n"
        f"💳 Hamyon manzili: `{wallet}`\n"
        f"📊 Bozor narxi: ~{market_price:,.0f} so'm\n"
        f"💰 Sotib olish narxi: {buy_price:,.0f} so'm\n"
        f"💰 Sotish narxi: {sell_price:,.0f} so'm\n"
        f"📈 Foiz: {current_percentage}%\n\n"
        "Kerakli sozlamani tanlang:"
    )
    
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💳 Hamyon manzilini o'zgartirish", callback_data="admin_change_ton_wallet")],
        [InlineKeyboardButton(text="📈 Foizni o'zgartirish", callback_data="admin_change_ton_percentage")],
        [InlineKeyboardButton(text="🔙 Orqaga", callback_data="back_to_admin")]
    ])
    
    await message.answer(text, parse_mode="Markdown", reply_markup=kb)

# TON Wallet Change Callback
async def admin_change_ton_wallet_cb(callback: types.CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id): 
        await callback.answer("❌ Siz admin emassiz!")
        return
    
    await callback.message.edit_text(
        "💳 *Yangi TON hamyon manzilini kiriting:*\n\n"
        "Format: `EQBBv8a1R3gXhXkJxJbDGYteZYZHhYJ4wjZQZJzXyFjWqj6X`",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🔙 Bekor qilish", callback_data="back_to_admin")]])
    )
    await state.set_state(TonSettingsState.waiting_for_ton_wallet)
    await callback.answer()

# Process TON Wallet Change
async def process_ton_wallet_change(message: types.Message, state: FSMContext):
    if not is_admin(message.from_user.id): return
    wallet_address = message.text.strip().split()[0]
    
    # Basic validation - very flexible for various TON address formats
    import re
    is_valid = False
    
    # Check if it looks like a standard TON address (Base64 or Hex)
    # Allows a wide range of characters and lengths common in TON addresses
    if re.match(r'^[A-Za-z0-9\-_:]{40,100}$', wallet_address):
        is_valid = True

    if not is_valid:
        await message.answer(
            "❌ Noto'g'ri TON manzil formati!\n\n"
            "Iltimos, to'g'ri manzil kiriting.\n"
            "Misol: `EQBBv8a1R3gXhXkJxJbDGYteZYZHhYJ4wjZQZJzXyFjWqj6X`",
            parse_mode="Markdown"
        )
        return
    
    from utils import set_ton_setting
    success = set_ton_setting('ton_wallet_address', wallet_address, message.from_user.id)
    
    if success:
        await message.answer(f"✅ TON hamyon manzili yangilandi:\n`{wallet_address}`", parse_mode="Markdown")
    else:
        await message.answer("❌ Xatolik yuz berdi!")
    
    await state.clear()

# TON Percentage Change Callback
async def admin_change_ton_percentage_cb(callback: types.CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id): 
        await callback.answer("❌ Siz admin emassiz!")
        return
    
    # Get current percentage
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT setting_value FROM settings WHERE setting_key = 'ton_percentage'")
    percentage_result = cursor.fetchone()
    current_percentage = int(percentage_result[0]) if percentage_result else 10
    conn.close()
    
    await callback.message.edit_text(
        f"📈 *TON foizini o'zgartirish*\n\n"
        f"Joriy foiz: {current_percentage}%\n\n"
        f"Yangi foizni kiriting (1-50):\n\n"
        f"📝 *Masallar:*\n"
        f"• 10%: Bozor 20,000 → Sotish 18,000, Sotib olish 22,000\n"
        f"• 20%: Bozor 20,000 → Sotish 16,000, Sotib olish 24,000\n"
        f"• 30%: Bozor 20,000 → Sotish 14,000, Sotib olish 26,000",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🔙 Bekor qilish", callback_data="back_to_admin")]])
    )
    await state.set_state(TonSettingsState.waiting_for_ton_percentage)
    await callback.answer()

# Process TON Percentage Change
async def process_ton_percentage_change(message: types.Message, state: FSMContext):
    if not is_admin(message.from_user.id): return
    try:
        new_percentage = int(message.text.strip())
        
        if new_percentage < 1 or new_percentage > 50:
            await message.answer("❌ Foiz 1 dan 50 gacha bo'lishi kerak!")
            return
        
        # Update percentage in settings
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        # Ensure settings table exists
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS settings (
                setting_key TEXT PRIMARY KEY,
                setting_value TEXT,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        cursor.execute('''
            INSERT OR REPLACE INTO settings (setting_key, setting_value, updated_at)
            VALUES ('ton_percentage', ?, datetime('now'))
        ''', (str(new_percentage),))
        
        conn.commit()
        conn.close()
        
        # Trigger immediate price update
        from ton_price_updater import TONPriceUpdater
        updater = TONPriceUpdater()
        await updater.update_prices()
        
        await message.answer(f"✅ TON foizi yangilandi: {new_percentage}%\n\n🔄 Narxlar avtomatik yangilandi!")
    except ValueError:
        await message.answer("❌ Iltimos, to'g'ri raqam kiriting!")
    except Exception as e:
        await message.answer(f"❌ Xatolik: {str(e)}")
    finally:
        await state.clear()

# Referral Bonus Management Handler
async def referral_bonus_handler(message: types.Message):
    if not is_admin(message.from_user.id):
        await message.answer("❌ Siz admin emassiz!")
        return
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Get current referral bonuses
    cursor.execute("SELECT setting_value FROM settings WHERE setting_key = 'referral_bonus_ton'")
    ton_result = cursor.fetchone()
    ton_bonus = float(ton_result[0]) if ton_result else 0.02
    
    cursor.execute("SELECT setting_value FROM settings WHERE setting_key = 'referral_bonus_stars'")
    stars_result = cursor.fetchone()
    stars_bonus = int(stars_result[0]) if stars_result else 2
    
    cursor.execute("SELECT setting_value FROM settings WHERE setting_key = 'referral_bonus_uc'")
    uc_result = cursor.fetchone()
    uc_bonus = int(uc_result[0]) if uc_result else 2
    
    conn.close()
    
    text = (
        f"💎 *Referal bonus sozlamalari*\n\n"
        f"💰 *TON bonus:* {ton_bonus} TON\n"
        f"⭐ *Stars bonus:* {stars_bonus} Stars\n"
        f"🛡 *UC bonus:* {uc_bonus} UC\n\n"
        f"📋 *O'zgartirish uchun tugmalardan foydalaning:*"
    )
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💰 TON bonus", callback_data="edit_referral_ton")],
        [InlineKeyboardButton(text="⭐ Stars bonus", callback_data="edit_referral_stars")],
        [InlineKeyboardButton(text="🛡 UC bonus", callback_data="edit_referral_uc")],
        [InlineKeyboardButton(text="🔙 Orqaga", callback_data="back_to_admin")]
    ])
    
    await message.answer(text, parse_mode="Markdown", reply_markup=keyboard)

# Admin Management Handler
async def manage_admins_handler(message: types.Message):
    if not is_admin(message.from_user.id):
        await message.answer("❌ Siz admin emassiz!")
        return
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Get all admins (both from DB and config)
    cursor.execute('SELECT user_id, username, full_name FROM users WHERE is_admin = 1')
    db_admins = cursor.fetchall()
    conn.close()
    
    from config import ADMINS
    text = "👨‍💼 *Adminlar ro'yxati:*\n\n"
    
    # Show config admins
    text += "📋 *Config admins:*\n"
    for admin_id in ADMINS:
        text += f"  • ID: `{admin_id}`\n"
    
    # Show DB admins
    if db_admins:
        text += "\n📋 *Database admins:*\n"
        for admin in db_admins:
            username = admin[1] if admin[1] else "Noma'lum"
            admin_name = admin[2] if admin[2] else "Noma'lum"
            # Escape special characters for Markdown and limit length
            username_safe = (username or "Noma'lum")[:30].replace("*", "\\*").replace("_", "\\_").replace("`", "\\`").replace("[", "\\[").replace("]", "\\]").replace(")", "\\)").replace("(", "\\(")
            admin_name_safe = (admin_name or "Noma'lum")[:30].replace("*", "\\*").replace("_", "\\_").replace("`", "\\`").replace("[", "\\[").replace("]", "\\]").replace(")", "\\)").replace("(", "\\(")
            text += f"  • ID: `{admin[0]}` | {username_safe} | {admin_name_safe}\n"
    else:
        text += "\n📋 *Database admins:* Yo'q\n"
    
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ Admin qo'shish", callback_data="admin_add_open")],
        [InlineKeyboardButton(text="➖ Admin o'chirish", callback_data="admin_remove_open")],
        [InlineKeyboardButton(text="🔙 Orqaga", callback_data="back_to_admin")]
    ])
    
    await message.answer(text, parse_mode="Markdown", reply_markup=kb)

# Add Admin Open Callback
async def admin_add_open_cb(callback: types.CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id): 
        await callback.answer("❌ Siz admin emassiz!")
        return
    
    await callback.message.edit_text(
        "➕ *Yangi admin qo'shish*\n\n"
        "👤 *Foydalanuvchi ID sini kiriting:*",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🔙 Bekor qilish", callback_data="back_to_admin")]])
    )
    await state.set_state(AdminState.add_admin)
    await callback.answer()

# Remove Admin Open Callback
async def admin_remove_open_cb(callback: types.CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id): 
        await callback.answer("❌ Siz admin emassiz!")
        return
    
    await callback.message.edit_text(
        "➖ *Admin o'chirish*\n\n"
        "👤 *Foydalanuvchi ID sini kiriting:*",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🔙 Bekor qilish", callback_data="back_to_admin")]])
    )
    await state.set_state(AdminState.remove_admin)
    await callback.answer()

# Process Add Admin
async def process_add_admin(message: types.Message, state: FSMContext):
    if not is_admin(message.from_user.id): return
    try:
        user_id = int(message.text.strip())
        
        from config import ADMINS
        if user_id in ADMINS:
            await message.answer("ℹ️ Bu foydalanuvchi allaqachon config orqali admin!")
            await state.clear()
            return
        
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        # Ensure user exists
        cursor.execute('SELECT 1 FROM users WHERE user_id = ?', (user_id,))
        if not cursor.fetchone():
            cursor.execute('INSERT INTO users (user_id, is_admin) VALUES (?, 1)', (user_id,))
        else:
            cursor.execute('UPDATE users SET is_admin = 1 WHERE user_id = ?', (user_id,))
        
        conn.commit()
        conn.close()
        
        await message.answer(f"✅ Foydalanuvchi admin qilindi!\n👤 ID: `{user_id}`", parse_mode="Markdown")
    except ValueError:
        await message.answer("❌ Noto'g'ri ID format!")
    except Exception as e:
        await message.answer(f"❌ Xatolik: {str(e)}")
    finally:
        await state.clear()

# Process Remove Admin
async def process_remove_admin(message: types.Message, state: FSMContext):
    if not is_admin(message.from_user.id): return
    try:
        user_id = int(message.text.strip())
        
        from config import ADMINS
        if user_id in ADMINS:
            await message.answer("⚠️ Bu foydalanuvchi config orqali admin, uni o'chirib bo'lmaydi!")
            await state.clear()
            return
        
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute('UPDATE users SET is_admin = 0 WHERE user_id = ?', (user_id,))
        conn.commit()
        conn.close()
        
        await message.answer(f"✅ Admin huquqi olib tashlandi!\n👤 ID: `{user_id}`", parse_mode="Markdown")
    except ValueError:
        await message.answer("❌ Noto'g'ri ID format!")
    except Exception as e:
        await message.answer(f"❌ Xatolik: {str(e)}")
    finally:
        await state.clear()

# Referral Bonus Handler
async def handle_referral_bonus_msg(message: types.Message):
    if not is_admin(message.from_user.id):
        await message.answer("❌ Siz admin emassiz!")
        return
    
    from referral import get_referral_bonus_by_type
    
    # Get current bonuses
    ton_bonus = get_referral_bonus_by_type("ton")
    stars_bonus = get_referral_bonus_by_type("stars")
    uc_bonus = get_referral_bonus_by_type("uc")
    
    text = (
        "💎 *Referal bonus sozlamalari*\n\n"
        f"💰 TON bonus: *{ton_bonus} TON*\n"
        f"⭐ Stars bonus: *{stars_bonus} Stars*\n"
        f"🎮 UC bonus: *{uc_bonus} UC*\n\n"
        "Har bir yangi referal uchun shu miqdorlar bonus beriladi."
    )
    
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💰 TON bonus", callback_data="set_ton_referral_bonus")],
        [InlineKeyboardButton(text="⭐ Stars bonus", callback_data="set_stars_referral_bonus")],
        [InlineKeyboardButton(text="🎮 UC bonus", callback_data="set_uc_referral_bonus")],
        [InlineKeyboardButton(text="🔙 Orqaga", callback_data="back_to_admin")]
    ])
    
    await message.answer(text, parse_mode="Markdown", reply_markup=kb)

# Process Referral Bonus
async def process_referral_bonus(message: types.Message, state: FSMContext):
    if not is_admin(message.from_user.id): 
        return
    
    data = await state.get_data()
    bonus_type = data.get('bonus_type', 'ton')
    
    try:
        bonus_value = message.text.strip()
        
        # Validate based on bonus type
        if bonus_type == "ton":
            bonus = float(bonus_value)
            if bonus <= 0:
                await message.answer("❌ Bonus musbat son bo'lishi kerak!")
                return
            setting_key = "referral_bonus_ton"
            unit = "TON"
        elif bonus_type == "stars":
            bonus = int(bonus_value)
            if bonus <= 0:
                await message.answer("❌ Bonus musbat son bo'lishi kerak!")
                return
            setting_key = "referral_bonus_stars"
            unit = "Stars"
        elif bonus_type == "uc":
            bonus = int(bonus_value)
            if bonus <= 0:
                await message.answer("❌ Bonus musbat son bo'lishi kerak!")
                return
            setting_key = "referral_bonus_uc"
            unit = "UC"
        else:
            await message.answer("❌ Noto'g'ri bonus turi!")
            return
        
        # Update referral bonus in settings table
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        # Ensure settings table exists
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS settings (
                setting_key TEXT PRIMARY KEY,
                setting_value TEXT,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        cursor.execute('''
            INSERT OR REPLACE INTO settings (setting_key, setting_value, updated_at)
            VALUES (?, ?, datetime('now'))
        ''', (setting_key, str(bonus)))
        
        conn.commit()
        conn.close()
        
        await message.answer(f"✅ {unit.title()} referral bonus yangilandi: {bonus} {unit}")
    except ValueError:
        await message.answer("❌ Noto'g'ri format! Raqam kiriting.")
    except Exception as e:
        await message.answer(f"❌ Xatolik: {str(e)}")
    finally:
        await state.clear()
        # After successful update, show updated referral bonus menu
        await handle_referral_bonus_msg(message)

# Back to Admin Callback
async def back_to_admin_cb(callback: types.CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id): 
        await callback.answer("❌ Siz admin emassiz!")
        return
    
    await state.clear()
    await callback.message.answer(
        "👨‍💻 *Admin paneliga xush kelibsiz!*\n"
        "Barcha funksiyalar faollashtirildi. Kerakli bo'limni tanlang:",
        parse_mode="Markdown",
        reply_markup=get_admin_keyboard()
    )
    try:
        await callback.message.delete()
    except:
        pass
    await callback.answer()

# Show Pending Payments
async def show_pending_payments(message: types.Message):
    if not is_admin(message.from_user.id): return
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Get pending payment requests
    cursor.execute('''
        SELECT pr.id, pr.user_id, pr.amount, pr.created_at, u.username, u.full_name
        FROM payment_requests pr
        LEFT JOIN users u ON pr.user_id = u.user_id
        WHERE pr.status = 'pending'
        ORDER BY pr.created_at DESC
        LIMIT 10
    ''')
    payments = cursor.fetchall()
    
    # Get pending purchase requests
    cursor.execute('''
        SELECT pr.id, pr.user_id, pr.product_type, pr.product_id, pr.price, pr.created_at, u.username, u.full_name
        FROM purchase_requests pr
        LEFT JOIN users u ON pr.user_id = u.user_id
        WHERE pr.status = 'pending'
        ORDER BY pr.created_at DESC
        LIMIT 10
    ''')
    purchases = cursor.fetchall()
    
    conn.close()
    
    text = "⏳ *Kutilayotgan so'rovlar*\n\n"
    
    if payments:
        text += "💰 *To'lov so'rovlari:*\n"
        for p in payments:
            username = f"@{p[4]}" if p[4] else f"ID: {p[1]}"
            text += f"  • ID: {p[0]} | {username} | {p[2]:,.0f} so'm\n"
        text += "\n"
    else:
        text += "💰 *To'lov so'rovlari:* Yo'q\n\n"
    
    if purchases:
        text += "📦 *Xarid so'rovlari:*\n"
        for p in purchases:
            username = f"@{p[6]}" if p[6] else f"ID: {p[1]}"
            product_info = f"{p[3]} {p[2]}"
            text += f"  • ID: {p[0]} | {username} | {product_info} | {p[4]:,.0f} so'm\n"
    else:
        text += "📦 *Xarid so'rovlari:* Yo'q\n"
    
    await message.answer(text, parse_mode="Markdown")

# Process Add Channel (complete implementation)
async def process_add_channel(message: types.Message, state: FSMContext):
    if not is_admin(message.from_user.id): return
    
    channel_input = message.text.strip()
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    try:
        # Normalize channel ID - keep @ for usernames, remove for numeric IDs if needed
        channel_id = channel_input
        
        # If it starts with @, keep it. Otherwise check if it's numeric
        if not channel_id.startswith('@'):
            # Try to see if it's a numeric ID (for supergroups)
            try:
                int(channel_id)  # If it's numeric, we might want to keep it as is
            except ValueError:
                # Not numeric, add @ for username
                channel_id = '@' + channel_id.lstrip('@')
        else:
            # Already has @, keep it
            pass
        
        # Check if channel already exists (check both with and without @)
        cursor.execute('SELECT id FROM channels WHERE channel_id = ? OR channel_id = ?', (channel_id, channel_id.lstrip('@')))
        if cursor.fetchone():
            conn.close()
            await message.answer("⚠️ Bu kanal allaqachon qo'shilgan!")
            await state.clear()
            return
        
        conn.close()
        
        # Save channel and ask for name
        await state.update_data(channel_id=channel_id)
        await message.answer(
            f"📺 *Kanal ID:* `{channel_id}`\n\n"
            f"📇 *Kanal nomini kiriting:*\n"
            f"_Masalan: STARS SHOP - Asosiy kanal_",
            parse_mode="Markdown"
        )
        await state.set_state(AdminState.add_channel_name)
        
    except Exception as e:
        conn.close()
        await message.answer(f"❌ Xatolik: {str(e)}")
        await state.clear()

# Process Add Channel Name
async def process_add_channel_name(message: types.Message, state: FSMContext):
    if not is_admin(message.from_user.id): return
    try:
        data = await state.get_data()
        channel_id = data.get('channel_id')
        channel_name = message.text.strip()
        
        if not channel_id:
            await message.answer("❌ Kanal ID topilmadi! Qaytadan boshlang.")
            await state.clear()
            return
        
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO channels (channel_id, channel_name)
            VALUES (?, ?)
        ''', (channel_id, channel_name))
        conn.commit()
        conn.close()
        
        await message.answer(
            f"✅ Kanal qo'shildi!\n\n"
            f"📺 Nomi: {channel_name}\n"
            f"🔗 ID: `{channel_id}`",
            parse_mode="Markdown"
        )
    except Exception as e:
        await message.answer(f"❌ Xatolik: {str(e)}")
    finally:
        await state.clear()

# Process Remove Channel (complete implementation)
async def process_remove_channel(message: types.Message, state: FSMContext):
    if not is_admin(message.from_user.id): return
    
    input_text = message.text.strip()
    
    # Check if user is trying to delete a config channel
    for ch in REQUIRED_CHANNELS:
        ch_id = ch['id'].lower()
        ch_name = ch['name'].lower()
        search_term = input_text.lower().lstrip('@')
        if search_term == ch_id.lstrip('@') or input_text.lower() == ch_id or input_text.lower() == ch_name:
            await message.answer(
                f"❌ *{ch['name']}* asosiy kanal bo'lib, uni bot orqali o'chirib bo'lmaydi.\n\n"
                "Uni o'chirish uchun `config.py` faylidan `REQUIRED_CHANNELS` ro'yxatini tahrirlash kerak.",
                parse_mode="Markdown"
            )
            await state.clear()
            return

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    try:
        # Try to find channel by:
        # 1. DB ID (if it's a number)
        # 2. Channel name
        # 3. Channel username/ID (with or without @)
        
        channel = None
        channel_id_to_delete = None
        
        # Try as DB ID first
        try:
            db_id = int(input_text)
            cursor.execute('SELECT id, channel_id, channel_name FROM channels WHERE id = ?', (db_id,))
            channel = cursor.fetchone()
            if channel:
                channel_id_to_delete = channel[0]
        except ValueError:
            pass  # Not a number, try other methods
        
        # Try by channel name
        if not channel:
            cursor.execute('SELECT id, channel_id, channel_name FROM channels WHERE channel_name LIKE ?', (f'%{input_text}%',))
            channel = cursor.fetchone()
            if channel:
                channel_id_to_delete = channel[0]
        
        # Try by channel_id/username (with or without @)
        if not channel:
            # Remove @ if present
            search_id = input_text.lstrip('@')
            cursor.execute('SELECT id, channel_id, channel_name FROM channels WHERE channel_id = ? OR channel_id = ?', (search_id, f'@{search_id}'))
            channel = cursor.fetchone()
            if channel:
                channel_id_to_delete = channel[0]
        
        if not channel:
            conn.close()
            await message.answer(
                "❌ Kanal topilmadi!\n\n"
                "Quyidagilardan birini kiriting:\n"
                "• DB ID (masalan: 1)\n"
                "• Kanal nomi (masalan: STARS SHOP)\n"
                "• Kanal username (masalan: @suxa_cyber)"
            )
            await state.clear()
            return
        
        # Delete channel
        cursor.execute('DELETE FROM channels WHERE id = ?', (channel_id_to_delete,))
        conn.commit()
        conn.close()
        
        await message.answer(
            f"✅ Kanal muvaffaqiyatli o'chirildi!\n\n"
            f"📺 Nomi: {channel[2]}\n"
            f"🔗 ID: {channel[1]}\n"
            f"🆔 DB ID: {channel[0]}"
        )
    except Exception as e:
        conn.close()
        await message.answer(f"❌ Xatolik: {str(e)}")
    finally:
        await state.clear()

async def show_pending_requests_cb(callback: types.CallbackQuery):
    if not is_admin(callback.from_user.id): return
    await show_pending_payments(callback.message)
    await callback.answer()

# Referral Bonus Callback Handlers
async def edit_referral_ton_cb(callback: types.CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id): 
        await callback.answer("❌ Siz admin emassiz!")
        return
    
    await callback.message.edit_text(
        "💰 *TON bonus o'zgartirish*\n\n"
        "📝 *Yangi miqdorni kiriting (TON):*\n"
        "_Masalan: 0.05_",
        parse_mode="Markdown"
    )
    await state.set_state(AdminState.waiting_for_ton_bonus)

async def edit_referral_stars_cb(callback: types.CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id): 
        await callback.answer("❌ Siz admin emassiz!")
        return
    
    await callback.message.edit_text(
        "⭐ *Stars bonus o'zgartirish*\n\n"
        "📝 *Yangi miqdorni kiriting (Stars):*\n"
        "_Masalan: 5_",
        parse_mode="Markdown"
    )
    await state.set_state(AdminState.waiting_for_stars_bonus)

async def edit_referral_uc_cb(callback: types.CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id): 
        await callback.answer("❌ Siz admin emassiz!")
        return
    
    await callback.message.edit_text(
        "🛡 *UC bonus o'zgartirish*\n\n"
        "📝 *Yangi miqdorni kiriting (UC):*\n"
        "_Masalan: 5_",
        parse_mode="Markdown"
    )
    await state.set_state(AdminState.waiting_for_uc_bonus)

# Message handlers for referral bonus changes
async def process_ton_bonus_change(message: types.Message, state: FSMContext):
    if not is_admin(message.from_user.id): return
    
    try:
        new_bonus = float(message.text.strip())
        if new_bonus < 0:
            await message.answer("❌ Bonus manfiy bo'lishi mumkin emas!")
            return
        
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute('''
            INSERT OR REPLACE INTO settings (setting_key, setting_value)
            VALUES ('referral_bonus_ton', ?)
        ''', (str(new_bonus),))
        conn.commit()
        conn.close()
        
        await message.answer(f"✅ TON bonus yangilandi: {new_bonus} TON")
        
        # Show updated referral bonus panel
        await referral_bonus_handler(message)
        
    except ValueError:
        await message.answer("❌ Iltimos, to'g'ri raqam kiriting!")
    except Exception as e:
        await message.answer(f"❌ Xatolik: {str(e)}")
    finally:
        await state.clear()

async def process_stars_bonus_change(message: types.Message, state: FSMContext):
    if not is_admin(message.from_user.id): return
    
    try:
        new_bonus = int(message.text.strip())
        if new_bonus < 0:
            await message.answer("❌ Bonus manfiy bo'lishi mumkin emas!")
            return
        
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute('''
            INSERT OR REPLACE INTO settings (setting_key, setting_value)
            VALUES ('referral_bonus_stars', ?)
        ''', (str(new_bonus),))
        conn.commit()
        conn.close()
        
        await message.answer(f"✅ Stars bonus yangilandi: {new_bonus} Stars")
        
        # Show updated referral bonus panel
        await referral_bonus_handler(message)
        
    except ValueError:
        await message.answer("❌ Iltimos, to'g'ri butun son kiriting!")
    except Exception as e:
        await message.answer(f"❌ Xatolik: {str(e)}")
    finally:
        await state.clear()

async def process_uc_bonus_change(message: types.Message, state: FSMContext):
    if not is_admin(message.from_user.id): return
    
    try:
        new_bonus = int(message.text.strip())
        if new_bonus < 0:
            await message.answer("❌ Bonus manfiy bo'lishi mumkin emas!")
            return
        
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute('''
            INSERT OR REPLACE INTO settings (setting_key, setting_value)
            VALUES ('referral_bonus_uc', ?)
        ''', (str(new_bonus),))
        conn.commit()
        conn.close()
        
        await message.answer(f"✅ UC bonus yangilandi: {new_bonus} UC")
        
        # Show updated referral bonus panel
        await referral_bonus_handler(message)
        
    except ValueError:
        await message.answer("❌ Iltimos, to'g'ri butun son kiriting!")
    except Exception as e:
        await message.answer(f"❌ Xatolik: {str(e)}")
    finally:
        await state.clear()

# Main Registration Function
def register_admin_handlers(dp: Dispatcher):
    # IMPORTANT: Use router and include it first to ensure admin handlers have priority
    # Register handlers on router first
    router.message.register(admin_panel_handler, Command("admin"))
    router.message.register(admin_panel_handler, Command("panel"))
    
    # Admin panel button handlers - Register on router
    router.message.register(admin_broadcast_prompt, F.text == "📢 Xabar Yuborish")
    router.message.register(admin_broadcast_prompt, F.text == "📢 Foydalanuvchilarga xabar yuborish")
    router.message.register(manage_users_handler, F.text == "👤 Foydalanuvchilar")
    router.message.register(manage_users_handler, F.text == "👥 Foydalanuvchilarni boshqarish")
    router.message.register(manage_channels_handler, F.text == "📢 Kanallar")
    router.message.register(manage_channels_handler, F.text == "📺 Majburiy obuna kanallar")
    router.message.register(manage_promo_handler, F.text == "🎫 Promokodlar")
    router.message.register(show_statistics, F.text == "📊 Statistika")
    router.message.register(show_statistics, F.text == "📊 Bot statistikasi")
    router.message.register(manage_cards_handler, F.text == "💳 Karta sozlamalari")
    router.message.register(manage_cards_handler, F.text == "💳 Karta qo'shish")
    router.message.register(change_price_handler, F.text == "💰 Narxlar")
    router.message.register(change_price_handler, F.text == "💰 Narxlarni o'zgartirish")
    router.message.register(admin_ton_settings_handler, F.text == "⚙️ wallet Sozlamalari")
    router.message.register(admin_ton_settings_handler, F.text == "⚙️ TON Sozlamalari")
    router.message.register(manage_admins_handler, F.text == "👨‍💼 Adminlar")
    router.message.register(handle_referral_bonus_msg, F.text == "💎 Referal bonus")
    router.message.register(handle_referral_bonus_msg, F.text == "💎 Referal bonus sozlamalari")
    router.message.register(admin_panel_handler, F.text == "🔙 Orqaga")
    
    # State Handlers - Register on router
    router.message.register(process_referral_bonus, AdminState.change_referral_bonus)
    router.message.register(process_change_price, AdminState.change_price)
    router.message.register(process_broadcast, AdminState.broadcast_message)
    router.message.register(process_add_card, AdminState.add_card)
    router.message.register(process_edit_card_number, AdminState.edit_card_number)
    router.message.register(process_edit_card_holder, AdminState.edit_card_holder)
    router.message.register(process_add_admin, AdminState.add_admin)
    router.message.register(process_remove_admin, AdminState.remove_admin)
    router.message.register(process_add_promo, AdminState.add_promo)
    router.message.register(process_ton_wallet_change, TonSettingsState.waiting_for_ton_wallet)
    router.message.register(process_ton_percentage_change, TonSettingsState.waiting_for_ton_percentage)
    router.message.register(process_ton_bonus_change, AdminState.waiting_for_ton_bonus)
    router.message.register(process_stars_bonus_change, AdminState.waiting_for_stars_bonus)
    router.message.register(process_uc_bonus_change, AdminState.waiting_for_uc_bonus)
    router.message.register(process_user_search, AdminState.search_user)
    router.message.register(process_add_channel_name, AdminState.add_channel_name)
    router.message.register(process_add_channel, AdminState.add_channel)
    router.message.register(process_remove_channel, AdminState.remove_channel)
    router.message.register(process_manage_balance, AdminState.manage_user_balance)
    
    # Callback Handlers - Register on router
    router.callback_query.register(edit_referral_ton_cb, F.data == "edit_referral_ton")
    router.callback_query.register(edit_referral_stars_cb, F.data == "edit_referral_stars")
    router.callback_query.register(edit_referral_uc_cb, F.data == "edit_referral_uc")
    router.callback_query.register(show_pending_requests_cb, F.data == "show_pending_requests")
    router.callback_query.register(back_to_admin_cb, F.data == "back_to_admin")
    router.callback_query.register(admin_add_card_cb, F.data == "admin_add_card")
    router.callback_query.register(admin_edit_card_number_cb, F.data == "admin_edit_card_number")
    router.callback_query.register(admin_edit_card_holder_cb, F.data == "admin_edit_card_holder")
    router.callback_query.register(handle_price_setting_cb, F.data == "back_to_prices")
    router.callback_query.register(admin_change_ton_wallet_cb, F.data == "admin_change_ton_wallet")
    router.callback_query.register(admin_change_ton_percentage_cb, F.data == "admin_change_ton_percentage")
    router.callback_query.register(admin_add_open_cb, F.data == "admin_add_open")
    router.callback_query.register(admin_remove_open_cb, F.data == "admin_remove_open")
    router.callback_query.register(promo_new_cb, F.data == "promo_new")
    router.callback_query.register(handle_price_setting_cb, F.data.startswith("set_stars_"))
    router.callback_query.register(handle_price_setting_cb, F.data.startswith("set_premium_"))
    router.callback_query.register(handle_price_setting_cb, F.data == "set_referral_bonus")
    router.callback_query.register(handle_referral_bonus_cb, F.data == "set_ton_referral_bonus")
    router.callback_query.register(handle_referral_bonus_cb, F.data == "set_stars_referral_bonus")
    router.callback_query.register(handle_referral_bonus_cb, F.data == "set_uc_referral_bonus")
    
    router.callback_query.register(admin_user_search_cb, F.data == "admin_user_search")
    router.callback_query.register(admin_manage_balance_cb, F.data.startswith("admin_add_"))
    router.callback_query.register(admin_manage_balance_cb, F.data.startswith("admin_remove_"))
    router.callback_query.register(admin_channel_add_cb, F.data == "admin_channel_add")
    router.callback_query.register(admin_channel_remove_cb, F.data == "admin_channel_remove")
    router.callback_query.register(admin_ban_unban_cb, F.data.startswith("admin_ban_"))
    router.callback_query.register(admin_ban_unban_cb, F.data.startswith("admin_unban_"))
    
    router.callback_query.register(confirm_payment_handler, F.data.startswith("confirm_payment_"))
    router.callback_query.register(cancel_payment_handler, F.data.startswith("cancel_payment_"))
    router.callback_query.register(confirm_purchase_handler, F.data.startswith("confirm_purchase_"))
    router.callback_query.register(cancel_purchase_handler, F.data.startswith("cancel_purchase_"))
    router.callback_query.register(confirm_ton_purchase_cb, F.data.startswith("confirm_ton_withdraw_"))
    router.callback_query.register(reject_ton_purchase_cb, F.data.startswith("reject_ton_withdraw_"))
    
    # Include router in dispatcher - this ensures admin handlers are checked first
    dp.include_router(router)
