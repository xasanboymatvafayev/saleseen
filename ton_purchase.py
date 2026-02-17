from aiogram import types, F, Bot, Dispatcher
from aiogram.fsm.context import FSMContext
from aiogram.filters import StateFilter
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters.state import State, StatesGroup
import sqlite3
import os
import logging

# Get the absolute path to the database file
DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'stars_shop.db')
from datetime import datetime
from typing import Optional, Tuple, Dict, Union
from aiogram import F, Router
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import Command

# Import from utils
from utils import get_user, is_user_banned, get_price, get_ton_wallet, get_ton_setting, set_ton_setting, get_ton_sell_price, get_ton_buy_price, get_all_admins, is_admin

# Create a router
router = Router()
# Define states at module level
class TonPurchaseStates(StatesGroup):
    # For buying TON
    ton_amount = State()
    ton_recipient_username = State()
    ton_wallet_address = State()
    
    # For selling TON
    ton_sell_amount = State()
    ton_sell_wallet = State()
    ton_sell_screenshot = State()

def ensure_ton_purchases_columns():
    """Ensure the ton_purchases table has all required columns"""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        # Check existing columns
        cursor.execute("PRAGMA table_info(ton_purchases)")
        existing_columns = [column[1] for column in cursor.fetchall()]
        
        # Add missing columns
        missing_columns = {
            'wallet_address': 'TEXT',
            'completed_at': 'TIMESTAMP',
            'updated_at': 'TIMESTAMP DEFAULT CURRENT_TIMESTAMP',
            'admin_id': 'INTEGER',
            'pixy_status': 'TEXT',
            'pixy_message': 'TEXT'
        }
        
        for column, column_type in missing_columns.items():
            if column not in existing_columns:
                cursor.execute(f'ALTER TABLE ton_purchases ADD COLUMN {column} {column_type}')
                logging.info(f"Added column {column} to ton_purchases table")
        
        conn.commit()
        conn.close()
    except Exception as e:
        logging.error(f"Error ensuring ton_purchases columns: {e}")

def register_ton_handlers(dp: Dispatcher):
    """Register TON purchase and sell handlers"""
    dp.include_router(router)

# TON Purchase Handlers
@router.callback_query(F.data == "ton_purchase")
async def ton_purchase(callback: types.CallbackQuery, state: FSMContext, bot: Bot):
    """Handle TON purchase button click"""
    if is_user_banned(callback.from_user.id):
        await callback.answer("Siz banlangansiz", show_alert=True)
        return
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="1 TON", callback_data="ton_1")],
        [InlineKeyboardButton(text="5 TON", callback_data="ton_5")],
        [InlineKeyboardButton(text="10 TON", callback_data="ton_10")],
        [InlineKeyboardButton(text="20 TON", callback_data="ton_20")],
        [InlineKeyboardButton(text="50 TON", callback_data="ton_50")],
        [InlineKeyboardButton(text="100 TON", callback_data="ton_100")],
        [InlineKeyboardButton(text=" Boshqa miqdor", callback_data="ton_custom")]
    ])
    
    await callback.message.edit_text(
        " *Nechta TON sotib olmoqchisiz?*",
        parse_mode="Markdown",
        reply_markup=keyboard
    )

@router.callback_query(F.data.regexp(r'^ton_(1|5|10|20|50|100|custom)$'))
async def ton_amount_selected(callback: types.CallbackQuery, state: FSMContext, bot: Bot):
    """Handle TON amount selection"""
    if is_user_banned(callback.from_user.id):
        await callback.answer("Siz banlangansiz", show_alert=True)
        return
    
    amount = callback.data.split("_")[1]
    
    if amount == "custom":
        await callback.message.edit_text(
            " *Qancha TON sotib olmoqchisiz?*\n\n"
            "Iltimos, miqdorni kiriting (masalan: 2.5):",
            parse_mode="Markdown"
        )
        await state.set_state(TonPurchaseStates.ton_amount)
    else:
        price_per_ton = get_ton_buy_price()
        total_price = float(amount) * price_per_ton
        
        await state.update_data(
            purchase_type="ton",
            ton_amount=float(amount),
            total_price=total_price,
            recipient=callback.from_user.username
        )
        
        # Ask for wallet address directly
        await callback.message.edit_text(
            " *TON hamyoni manzilingizni yuboring:*\n\n"
            "Iltimos, quyidagi formatda yuboring:\n"
            "`UQCD39vs5...` (yoki boshqa to'g'ri formatdagi TON manzili)",
            parse_mode="Markdown"
        )
        await state.set_state(TonPurchaseStates.ton_wallet_address)

@router.message(TonPurchaseStates.ton_amount)
async def process_ton_amount_input(message: types.Message, state: FSMContext, bot: Bot):
    """Process custom TON amount input"""
    try:
        ton_amount = float(message.text.replace(",", "."))
        if ton_amount <= 0:
            raise ValueError("Noto'g'ri miqdor")
        await process_ton_amount(ton_amount, message, state, bot)
    except ValueError:
        await message.answer(" Iltimos, to'g'ri miqdorni kiriting (masalan: 2.5)")

async def process_ton_amount(amount, message_or_callback, state: FSMContext, bot: Bot):
    """Process TON amount (both from buttons and custom input)"""
    price_per_ton = get_ton_buy_price()
    total_price = float(amount) * price_per_ton
    
    # Get user info safely
    if hasattr(message_or_callback, 'from_user'):
        user = message_or_callback.from_user
    elif hasattr(message_or_callback, 'message') and hasattr(message_or_callback.message, 'from_user'):
        user = message_or_callback.message.from_user
    else:
        user = None
    
    if not user:
        await message_or_callback.answer("❌ Xatolik yuz berdi. Iltimos, qaytadan urinib ko'ring.")
        return
    
    await state.update_data(
        purchase_type="ton",
        ton_amount=float(amount),
        total_price=total_price,
        recipient=user.username
    )
    
    # Ask for wallet address directly
    text = (
        " *TON hamyoni manzilingizni yuboring:*\n\n"
        "Iltimos, quyidagi formatda yuboring:\n"
        "`UQCD39vs5...` (yoki boshqa to'g'ri formatdagi TON manzili)"
    )
    
    if hasattr(message_or_callback, 'edit_text'):
        try:
            await message_or_callback.edit_text(text, parse_mode="Markdown")
        except Exception as e:
            # If edit fails, send new message
            await message_or_callback.answer(text, parse_mode="Markdown")
    else:
        await message_or_callback.answer(text, parse_mode="Markdown")
    
    await state.set_state(TonPurchaseStates.ton_wallet_address)

@router.message(TonPurchaseStates.ton_wallet_address)
async def process_ton_wallet_address(message: types.Message, state: FSMContext, bot: Bot):
    """Process TON wallet address input"""
    wallet_address = message.text.strip()
    
    # Simple validation for TON wallet address
    if not wallet_address or len(wallet_address) < 10:  # Basic validation
        await message.answer(" Iltimos, to'g'ri TON hamyoni manzilini kiriting!")
        return
    
    # Save wallet address to state
    await state.update_data(wallet_address=wallet_address)
    
    # Process the purchase with recipient and wallet address
    await process_ton_recipient(message, state, bot)

async def process_ton_recipient(update, state: FSMContext, bot: Bot):
    """Process TON purchase with recipient and wallet address"""
    data = await state.get_data()
    user_id = update.from_user.id
    
    # Show processing message first
    processing_msg = (
        "🔄 *Buyurtma bajarilmoqda...*\n\n"
        f"💎 Miqdori: {data['ton_amount']} TON\n"
        f"👤 Qabul qiluvchi: {data['recipient']}\n"
        f"💰 Narxi: {data['total_price']:,} so'm\n\n"
        "⏳ Iltimos, biroz kutib turing..."
    )
    
    try:
        if hasattr(update, 'edit_text'):
            await update.edit_text(processing_msg, parse_mode="Markdown")
        else:
            await update.answer(processing_msg, parse_mode="Markdown")
    except:
        await bot.send_message(chat_id=user_id, text=processing_msg, parse_mode="Markdown")
    
    # Check if we have all required data
    if 'recipient' not in data or 'ton_amount' not in data or 'total_price' not in data:
        error_msg = " Xatolik yuz berdi. Kerakli ma'lumotlar topilmadi. Iltimos, qaytadan urinib ko'ring."
        try:
            if hasattr(update, 'edit_text'):
                await update.edit_text(error_msg)
            else:
                await update.answer(error_msg)
        except:
            try:
                await bot.send_message(chat_id=user_id, text=error_msg)
            except:
                pass
        await state.clear()
        return
    
    # Check balance
    try:
        user = get_user(user_id)
        if not user:
            await bot.send_message(chat_id=user_id, text="Foydalanuvchi topilmadi. Iltimos, qaytadan urinib ko'ring.")
            await state.clear()
            return
            
        user_balance = user[3]  # balance is the 4th column in the users table
        if user_balance < data['total_price']:
            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text=" Hisobni to'ldirish", callback_data="my_account")],
                [InlineKeyboardButton(text=" Qayta urinish", callback_data="ton_purchase")]
            ])
            
            error_msg = (
                " *Hisobingizda yetarli mablag' mavjud emas!*\n\n"
                f" Sizning balansingiz: {user_balance:,.0f} so'm\n"
                f" Kerakli summa: {data['total_price']:,.0f} so'm"
            )
            
            try:
                if hasattr(update, 'edit_text'):
                    try:
                        await update.edit_text(error_msg, reply_markup=keyboard)
                    except:
                        if hasattr(update, 'message'):
                            await update.message.answer(error_msg, reply_markup=keyboard)
                        else:
                            await bot.send_message(chat_id=user_id, text=error_msg, reply_markup=keyboard)
                else:
                    await update.answer(error_msg, reply_markup=keyboard)
            except Exception as e:
                logging.error(f"Error sending balance error message: {e}")
                try:
                    await bot.send_message(chat_id=user_id, text=error_msg, reply_markup=keyboard)
                except:
                    pass
            
            await state.clear()
            return
    except Exception as e:
        logging.error(f"Error checking balance: {e}")
        error_msg = " Xatolik yuz berdi. Iltimos, qaytadan urinib ko'ring."
        try:
            if hasattr(update, 'edit_text'):
                await update.edit_text(error_msg)
            else:
                await update.answer(error_msg)
        except:
            try:
                await bot.send_message(chat_id=user_id, text=error_msg)
            except:
                pass
        await state.clear()
        return
    
    # Ensure database schema is up to date
    ensure_ton_purchases_columns()
    
    # Try to send TON via PixyAPI to the user's wallet address FIRST
    pixy_success = False
    pixy_message = ""
    
    try:
        from pixy_manager import pixy_manager, handle_pixy_error
        
        # Get wallet address from state
        wallet_address = data.get('wallet_address')
        if not wallet_address:
            # If no wallet address, use recipient as fallback (for backward compatibility)
            wallet_address = data['recipient']
        
        # Use enhanced PixyAPI manager with retry logic
        api_response = await pixy_manager.safe_transfer_ton(
            to_address=wallet_address,
            amount=float(data['ton_amount']),
            comment=f"TON xarid - @{data['recipient']}",
            order_id=f"TON-PRE-CHECK"
        )
        
        success, message = await handle_pixy_error(api_response, "TON transfer")
        
        if success:
            pixy_success = True
            pixy_message = "PixyAPI orqali muvaffaqiyatli yuborildi"
            logging.info(f"PixyAPI TON transfer pre-check successful")
        else:
            # API failed - return error immediately without deducting balance
            error_msg = f"❌ *TON xaridi amalga oshmadi!*\n\n📝 *Xatolik:* {message}\n\n💰 *Pul qaytarildi*\n\n🔧 *Iltimos, admin bilan bog'laning*"
            try:
                if hasattr(update, 'edit_text'):
                    await update.edit_text(error_msg, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🏠 Bosh menyu", callback_data="main_menu")]]))
                else:
                    await update.answer(error_msg, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🏠 Bosh menyu", callback_data="main_menu")]]))
            except:
                await bot.send_message(chat_id=user_id, text=error_msg, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🏠 Bosh menyu", callback_data="main_menu")]]))
            await state.clear()
            return
            
    except Exception as e:
        pixy_message = f"PixyAPI xatosi: {str(e)}"
        logging.error(f"PixyAPI TON transfer pre-check error: {e}")
        # API failed - return error immediately without deducting balance
        error_msg = f"❌ *TON xaridi amalga oshmadi!*\n\n📝 *Xatolik:* {pixy_message}\n\n💰 *Pul qaytarildi*\n\n🔧 *Iltimos, admin bilan bog'laning*"
        try:
            if hasattr(update, 'edit_text'):
                await update.edit_text(error_msg, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🏠 Bosh menyu", callback_data="main_menu")]]))
            else:
                await update.answer(error_msg, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🏠 Bosh menyu", callback_data="main_menu")]]))
        except:
            await bot.send_message(chat_id=user_id, text=error_msg, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🏠 Bosh menyu", callback_data="main_menu")]]))
        await state.clear()
        return
    
    # API was successful - now deduct balance and create purchase record
    conn = None
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        # Start transaction
        cursor.execute('BEGIN TRANSACTION')
        
        # Verify balance again right before deducting
        cursor.execute('SELECT balance FROM users WHERE user_id = ?', (user_id,))
        current_balance = cursor.fetchone()[0]
        
        if current_balance < data['total_price']:
            raise ValueError("Insufficient balance")
        
        # Deduct balance (only after API success)
        cursor.execute('UPDATE users SET balance = balance - ? WHERE user_id = ?', 
                      (data['total_price'], user_id))
        
        # Create purchase record
        cursor.execute(
            '''INSERT INTO ton_purchases 
               (user_id, amount, price, recipient, status) 
               VALUES (?, ?, ?, ?, ?)''',
            (user_id, data['ton_amount'], data['total_price'], 
             data['recipient'], 'completed')
        )
        purchase_id = cursor.lastrowid
        
        if not purchase_id:
            raise ValueError("Failed to create purchase record")
        
        # Record transaction
        transaction_details = f"TON xarid: {data['ton_amount']} TON, Qabul qiluvchi: @{data['recipient']}, Manzil: {wallet_address} ({pixy_message})"
        cursor.execute('''INSERT INTO transactions 
            (user_id, type, amount, status, details, confirmed_at)
            VALUES (?, ?, ?, 'completed', ?, CURRENT_TIMESTAMP)
        ''', (user_id, 'ton_purchase', data['total_price'], transaction_details))
        
        # Update purchase record with PixyAPI details
        cursor.execute('''UPDATE ton_purchases 
            SET status = 'completed', completed_at = CURRENT_TIMESTAMP, admin_id = ?, 
                wallet_address = ?, pixy_status = ?, pixy_message = ?
            WHERE id = ?''', (user_id, wallet_address, "success", pixy_message, purchase_id))
        
        # Commit the transaction
        conn.commit()
        
        # Prepare success message (API was successful)
        success_message = (
            "✅ *TON muvaffaqiyatli sotib olindi va yuborildi!*\n\n"
            f"💎 Miqdor: {data['ton_amount']} TON\n"
            f"👥 Qabul qiluvchi: @{data['recipient']}\n"
            f"💼 TON manzili: `{wallet_address}`\n"
            f"💰 Narxi: {data['total_price']:,.0f} so'm\n\n"
            f"🚀 *{pixy_message}*\n"
            f"TON tez orada sizning hamyoningizga tushadi."
        )
        
        # Create keyboard for user response
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🏠 Bosh menyu", callback_data="main_menu")]
        ])
        
        # Notify user
        if hasattr(update, 'message'):
            target = update.message
        else:
            target = update
        
        try:
            if isinstance(update, types.CallbackQuery):
                try:
                    if target.photo:
                        await target.edit_caption(
                            caption=success_message,
                            reply_markup=keyboard
                        )
                    else:
                        await target.edit_text(
                            success_message,
                            reply_markup=keyboard
                        )
                except Exception as edit_err:
                    logging.error(f"Error editing message: {edit_err}")
                    await target.answer(
                        success_message,
                        reply_markup=keyboard
                    )
            else:
                await target.answer(
                    success_message,
                    reply_markup=keyboard
                )
        except Exception as msg_err:
            logging.error(f"Error sending success message: {msg_err}")
            try:
                await bot.send_message(
                    chat_id=user_id,
                    text=success_message,
                    reply_markup=keyboard
                )
            except Exception as final_err:
                logging.error(f"Final error sending success message: {final_err}")
        
        # Purchase is automatically approved, no need to notify admins
        logging.info(f"TON purchase {purchase_id} automatically completed for user {user_id}")
            
    except Exception as e:
        logging.error(f"TON purchase error: {e}")
        if conn:
            try:
                conn.rollback()
            except Exception as rollback_error:
                logging.error(f"Error during rollback: {rollback_error}")
        
        error_message = " Xatolik yuz berdi. Iltimos, qaytadan urinib ko'ring."
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text=" Qayta urinish", callback_data="ton_purchase")]
        ])
        
        try:
            if hasattr(update, 'edit_text'):
                try:
                    await update.edit_text(error_message, reply_markup=keyboard)
                except Exception as edit_error:
                    logging.error(f"Error editing message: {edit_error}")
                    # If we can't edit, send a new message
                    await update.answer(error_message, reply_markup=keyboard)
            else:
                await update.answer(error_message, reply_markup=keyboard)
        except Exception as msg_error:
            logging.error(f"Error sending error message: {msg_error}")
            # If all else fails, try to send a basic message
            try:
                await bot.send_message(chat_id=update.from_user.id, text=error_message, reply_markup=keyboard)
            except Exception as final_error:
                logging.error(f"Final error sending message: {final_error}")
    finally:
        if conn:
            try:
                conn.close()
            except Exception as close_error:
                logging.error(f"Error closing connection: {close_error}")
        await state.clear()

# TON Selling Handlers
@router.callback_query(F.data == "ton_sell")
async def ton_sell(callback: types.CallbackQuery, state: FSMContext, bot: Bot):
    """Handle TON sell button click"""
    if is_user_banned(callback.from_user.id):
        await callback.answer("Siz banlangansiz", show_alert=True)
        return
    
    await callback.message.edit_text(
        "💎 *TON Sotish*\n\n"
        "Qancha TON sotmoqchisiz? Raqamda yozing (masalan: 5 yoki 2.5)",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔙 Orqaga", callback_data="back_to_balance")]
        ])
    )
    await state.set_state(TonPurchaseStates.ton_sell_amount)

@router.message(TonPurchaseStates.ton_sell_amount)
async def process_ton_sell_amount(message: types.Message, state: FSMContext, bot: Bot):
    """Process TON sell amount input"""
    try:
        amount = float(message.text.replace(",", "."))
        if amount <= 0:
            raise ValueError("Noto'g'ri miqdor")
            
        # Use sell price for selling TON
        price_per_ton = get_ton_sell_price()
        total_amount = amount * price_per_ton
        
        # Save amount to state
        await state.update_data(
            sell_amount=amount,
            price_per_ton=price_per_ton,
            total_amount=total_amount
        )
        
        # Show confirmation with inline keyboard
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="✅ Ha, to'g'ri", callback_data="confirm_ton_sell")],
            [InlineKeyboardButton(text="❌ Bekor qilish", callback_data="cancel_ton_sell")]
        ])
        
        await message.answer(
            f"💎 *TON Sotish Tasdiqlash*\n\n"
            f"💰 Miqdor: *{amount:.2f} TON*\n"
            f"💵 1 TON narxi: *{price_per_ton:,.0f} so'm*\n"
            f"💸 Jami: *{total_amount:,.0f} so'm*\n\n"
            "Barcha ma'lumotlar to'g'rimi?",
            parse_mode="Markdown",
            reply_markup=keyboard
        )
        
    except ValueError:
        await message.answer("❌ Iltimos, to'g'ri miqdorni kiriting (masalan: 5 yoki 2.5)")

async def process_ton_sell(amount, message_or_callback, state: FSMContext, bot: Bot):
    """Process TON sell (both from buttons and custom input)"""
    user_id = message_or_callback.from_user.id
    # Use sell price for selling TON
    price_per_ton = get_ton_sell_price()
    total_amount = amount * price_per_ton
    
    await state.update_data(
        sell_amount=amount,
        sell_total=total_amount,
        sell_price_per_ton=price_per_ton
    )
    
    text = (
        f"*TON Sotish*\n\n"
        f"💎 Miqdor: *{amount:.2f} TON*\n"
        f"💵 1 TON narxi: *{price_per_ton:,.0f} so'm*\n"
        f"💰 Jami: *{total_amount:,.0f} so'm*\n\n"
        f"🔹 Quyidagi manzilga *{amount:.2f} TON* yuboring:\n"
        f"`{get_ton_wallet()}`\n\n"
        "🔹 Iltimos, faqat TON (The Open Network) tarmog'idan yuboring!\n"
        "📎 To'lov cheki rasmini yuboring:"
    )
    
    if hasattr(message_or_callback, 'edit_text'):
        await message_or_callback.edit_text(text, parse_mode="Markdown")
    else:
        await message_or_callback.answer(text, parse_mode="Markdown")
    
    await state.set_state(TonPurchaseStates.ton_sell_screenshot)

@router.message(TonPurchaseStates.ton_sell_screenshot)
async def process_ton_sell_screenshot(message: types.Message, state: FSMContext, bot: Bot):
    """Process TON sell screenshot"""
    # Check if user sent a photo
    if not message.photo:
        # Check if user wants to cancel
        if message.text and message.text.lower() in ['cancel', 'bekor qilish', 'ortga']:
            await state.clear()
            await message.answer("❌ TON sotish bekor qilindi.")
            return
            
        # Send instructions with cancel button
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="❌ Bekor qilish", callback_data="cancel_ton_sell")]
        ])
        await message.answer(
            "❌ Iltimos, to'lov chekining rasmini yuboring!\n\n"
            "✅ To'g'ri rasm yuborish uchun quyidagilarga e'tibor bering:\n"
            "1. Rasm aniq va o'qiladigan bo'lishi kerak\n"
            "2. To'lov ma'lumotlari (miqdor, manzil, vaqt) ko'rinib turishi kerak\n"
            "3. Rasm yuborish uchun 📎 tugmasini bosing",
            reply_markup=keyboard
        )
        return
    
    # Get photo with best quality
    photo_id = message.photo[-1].file_id
    data = await state.get_data()
    user_id = message.from_user.id
    
    # Show processing message
    processing_msg = await message.answer("⏳ To'lov tekshirilmoqda, iltimos kuting...")

    # Save the sell request to database
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    try:
        # Get current TON sell price
        price_per_ton = get_ton_sell_price()
        total_amount = float(data['sell_amount']) * price_per_ton
        
        cursor.execute('''
            INSERT INTO ton_sales 
            (user_id, amount, price_per_ton, total_amount, status, photo_id, created_at)
            VALUES (?, ?, ?, ?, 'pending', ?, CURRENT_TIMESTAMP)
        ''', (user_id, data['sell_amount'], price_per_ton, total_amount, photo_id))
        
        sale_id = cursor.lastrowid
        conn.commit()
        
        # Notify admins
        admins = get_all_admins()
        user = get_user(user_id)
        username = user[1] if user and len(user) > 1 else str(user_id)
        user_display = f"@{username}" if username and not username.startswith('@') else username or f"ID: {user_id}"
        
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="✅ Tasdiqlash", 
                    callback_data=f"confirm_ton_sale_{sale_id}"
                ),
                InlineKeyboardButton(
                    text="❌ Rad etish", 
                    callback_data=f"reject_ton_sale_{sale_id}"
                )
            ]
        ])
        
        message_text = (
            "🔄 *Yangi TON Sotish So'rovi*\n\n"
            f"🆔 ID: `{sale_id}`\n"
            f"👤 Foydalanuvchi: {user_display}\n"
            f"💎 Miqdor: {data['sell_amount']} TON\n"
            f"📅 Sana: {datetime.now().strftime('%d.%m.%Y %H:%M')}"
        )
        
        for admin_id in admins:
            try:
                await bot.send_photo(
                    chat_id=admin_id,
                    photo=photo_id,
                    caption=message_text,
                    parse_mode="Markdown",
                    reply_markup=keyboard
                )
            except Exception as e:
                logging.error(f"Failed to send notification to admin {admin_id}: {e}")
        
        await message.answer(
            "✅ *So'rovingiz qabul qilindi!*\n\n"
            "Adminlar tez orada ko'rib chiqishadi. "
            f"Sizning so'rovingiz ID: `{sale_id}`\n\n"
            "⏳ Tasdiqlangandan so'ng, mablag' hisobingizga tushiriladi.",
            parse_mode="Markdown"
        )
        
    except Exception as e:
        logging.error(f"Error processing TON sell: {e}")
        await message.answer("Xatolik yuz berdi. Iltimos, qaytadan urinib ko'ring.")
    finally:
        conn.close()
        await state.clear()
