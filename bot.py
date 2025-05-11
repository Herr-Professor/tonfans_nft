import asyncio
import aiohttp
import base64
import requests
from typing import Tuple, List, Dict
import time as time_module
from datetime import datetime, timedelta, timezone
from aiogram import Bot, Dispatcher, types
from aiogram.types import (
    Message, 
    CallbackQuery,
    InlineKeyboardMarkup, 
    InlineKeyboardButton, 
    ReplyKeyboardMarkup, 
    KeyboardButton,
    ReplyKeyboardRemove,
    FSInputFile,
    WebAppInfo
)
from aiogram.filters import Command, ChatMemberUpdatedFilter, KICKED, LEFT 
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.memory import MemoryStorage
import aiosqlite
import logging
from ton_utils import (
    NFT_COLLECTION_ADDRESS,
    TON_API_KEY,
    TONAPI_KEY,
    SHIVA_TOKEN_ADDRESS,
    VERIFICATION_WALLET,
    GROUP_INVITE_LINK,
    NFT_MARKETPLACE_LINK,
    ADMIN_IDS,
    GROUP_ID,
    BASE_URL,
    WELCOME_IMAGE_PATH,
    SHIVA_DEX_LINK,
    PING_ADMIN_ID,
    escape_md,
    check_nft_ownership,
    check_token_balance,
    get_shiva_price,
    get_top_holders
)
from admin import AdminCommands, register_admin_handlers
from aiohttp import web
import pytz

# At the top of the file
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Initialize bot and dispatcher
bot = Bot(token="8067666224:AAELEOrjl0lHDUsqP7NUFU8FTYuzRt972ik")
storage = MemoryStorage()
dp = Dispatcher(storage=storage)
logger = logging.getLogger(__name__)

# Messages in English and Russian
MESSAGES = {
    'username_required': {
        'en': "❌ You need to set a Telegram username before using this bot.\n\nTo set a username:\n1. Go to Settings\n2. Tap on 'Username'\n3. Choose a username\n4. Return here and try again",
        'ru': "❌ Вам нужно установить имя пользователя Telegram перед использованием этого бота.\n\nКак установить имя пользователя:\n1. Перейдите в Настройки\n2. Нажмите 'Имя пользователя'\n3. Выберите имя пользователя\n4. Вернитесь сюда и попробуйте снова"
    },
    'welcome_message': {
        'en': "👋 This is Boris.\nWelcome {}!\n\nI'm tonfans NFT checker bot. I'll help you verify your NFT ownership and get access to our exclusive group.\n\nPlease send me your TON wallet address to begin verification.",
        'ru': "👋 Это Борис.\nДобро пожаловать, {}!\n\nЯ бот для проверки TONFANS NFT. Я помогу вам подтвердить владение NFT и получить доступ в наш эксклюзивный чат.\n\nПожалуйста, отправьте мне свой TON-кошелек для начала проверки."
    },
    'invalid_wallet': {
        'en': "❌ Invalid wallet address. Please send a valid TON wallet address.",
        'ru': "❌ Неверный адрес кошелька. Пожалуйста, отправьте действительный TON-кошелек."
    },
    'wallet_saved': {
        'en': "✅ Wallet address saved: `{}`\n\nChecking NFT ownership...",
        'ru': "✅ Адрес кошелька сохранён: `{}`\n\nПроверяю владение NFT..."
    },
    'verification_success': {
        'en': "🎉 Verification successful!\n\nYour wallet owns a TONFANS NFT. Welcome to the club! 🚀\n\nYou can now join our exclusive group.",
        'ru': "🎉 Верификация успешна!\n\nВаш кошелек владеет TONFANS NFT. Добро пожаловать в клуб! 🚀\n\nТеперь вы можете присоединиться к нашему эксклюзивному чату."
    },
    'verification_failed': {
        'en': "❌ Verification failed.\n\nNo TONFANS NFT found in this wallet. To get access:\n1. Buy a TONFANS NFT on GetGems\n2. Try verification again with /verify",
        'ru': "❌ Верификация не удалась.\n\nВ этом кошельке не найдено TONFANS NFT. Для получения доступа:\n1. Купите TONFANS NFT на GetGems\n2. Попробуйте снова пройти верификацию с помощью /verify"
    },
    'already_verified': {
        'en': "✅ You're already verified! Welcome back!",
        'ru': "✅ Вы уже прошли проверку! Добро пожаловать обратно!"
    },
    'start_verification': {
        'en': "Please start verification using the /start command.",
        'ru': "Пожалуйста, начните верификацию с помощью команды /start."
    },
    'no_pending_verification': {
        'en': "No pending verification requests found. Please start again with /start.",
        'ru': "Не найдено ожидающих запросов на верификацию. Пожалуйста, начните заново с /start."
    },
    'whale_checking_balance': {
        'en': "🐳 Checking your $SHIVA balance...",
        'ru': "🐳 Проверяю ваш баланс $SHIVA..."
    },
    'whale_verification_success': {
        'en': "🐳 Congratulations! You qualify as a whale!",
        'ru': "🐳 Поздравляем! Вы квалифицируетесь как кит!"
    },
    'whale_verification_failed': {
        'en': "❌ Sorry, you don't qualify as a whale yet.",
        'ru': "❌ Извините, вы пока не квалифицируетесь как кит."
    },
    'price': {
        'en': """💰 *SHIVA Token Price*\n\n*USD:* ${:.8f} ({})\n*TON:* {:.8f} TON ({})\n\nBuy on DeDust: {}""",
        'ru': """💰 *Цена токена SHIVA*\n\n*USD:* ${:.8f} ({})\n*TON:* {:.8f} TON ({})\n\nКупить на DeDust: {}"""
    },
    'buy_shiva': {
    'en': """💎 *How to Buy $SHIVA (New Gem)*\n\n1️⃣ Get TON coins from any exchange\n2️⃣ Transfer TON to your wallet\n3️⃣ Visit DeDust.io using the button below\n4️⃣ Connect your wallet\n5️⃣ Swap TON for SHIVA\n\n*Contract Address:*\n`{}`\n\n*Current Price:* ${:.8f}""", # Changed to {} here as we will escape the price string ourselves
    'ru': """💎 *Как купить $SHIVA (Новый гем)*\n\n1️⃣ Получите монеты TON на любой бирже\n2️⃣ Переведите TON на свой кошелек\n3️⃣ Перейдите на DeDust.io, нажав кнопку ниже\n4️⃣ Подключите свой кошелек\n5️⃣ Обменяйте TON на SHIVA\n\n*Адрес контракта:*\n`{}`\n\n*Текущая цена:* ${}""" # Changed to {} here
},
    'buy_nft': {
        'en': """🖼 *How to Buy TONFANS NFT*\n\n1️⃣ Get TON coins from any exchange\n2️⃣ Transfer TON to your wallet\n3️⃣ Visit GetGems using the link below\n4️⃣ Connect your wallet\n5️⃣ Choose your favorite NFT\n\n*Collection Address:*\n`{}`\n\nClick the button below to view the collection! 🎨""",
        'ru': """🖼 *Как купить TONFANS NFT*\n\n1️⃣ Получите монеты TON на любой бирже\n2️⃣ Переведите TON на свой кошелек\n3️⃣ Перейдите на GetGems по ссылке ниже\n4️⃣ Подключите свой кошелек\n5️⃣ Выберите свой любимый NFT\n\n*Адрес коллекции:*\n`{}`\n\nНажмите на кнопку ниже, чтобы посмотреть коллекцию! 🎨"""
    },
    'help_message': {
        'en': """🤖 *Available Commands*\n\n*Basic Commands:*\n/start - Start the bot and begin verification\n/help - Show this help message\n\n*Verification Commands:*\n/wallet - Submit your wallet address\n/verify - Verify your NFT ownership\n\n*Token Commands:*\n/whale - Check if you qualify as a whale\n/price - Check current SHIVA token price\n/top - View top SHIVA token holders\n\n*Purchase Information:*\n/buy - Learn how to buy SHIVA tokens\n/nft - Learn how to buy TONFANS NFTs\n\n*TON Connect:*\n/connect - Connect your wallet via TON Connect\n/wallet_info - View your connected wallet info\n/burn - Burn tokens from your wallet\n/disconnect - Disconnect your wallet\n\nNeed assistance? Start with /start to begin the verification process!""",
        'ru': """🤖 *Доступные команды*\n\n*Основные команды:*\n/start - Запустить бота и начать верификацию\n/help - Показать это сообщение\n\n*Команды верификации:*\n/wallet - Отправить адрес кошелька\n/verify - Проверить владение NFT\n\n*Токен-команды:*\n/whale - Проверить, являетесь ли вы китом\n/price - Узнать текущую цену SHIVA\n/top - Посмотреть топ холдеров SHIVA\n\n*Покупка:*\n/buy - Как купить SHIVA\n/nft - Как купить TONFANS NFT\n\n*TON Connect:*\n/connect - Подключить кошелек через TON Connect\n/wallet_info - Просмотреть информацию о подключенном кошельке\n/burn - Сжечь токены из вашего кошелька\n/disconnect - Отключить ваш кошелек\n\nНужна помощь? Начните с /start!"""
    },
    'please_wait': {
        'en': "Please wait...",
        'ru': "Пожалуйста, подождите..."
    },
    'error_fetching_data': {
        'en': "❌ Error fetching data. Please try again later.",
        'ru': "❌ Ошибка при получении данных. Пожалуйста, попробуйте позже."
    },
    'unable_to_fetch_price': {
        'en': "❌ Unable to fetch price data. Please try again later.",
        'ru': "❌ Не удалось получить данные о цене. Пожалуйста, попробуйте позже."
    },
    'unable_to_fetch_holders': {
        'en': "❌ Unable to fetch holders data. Please try again later.",
        'ru': "❌ Не удалось получить данные о держателях. Пожалуйста, попробуйте позже."
    },
    'resources_to_meet_requirements': {
        'en': "Resources to help you meet the requirements:",
        'ru': "Ресурсы для выполнения требований:"
    },
    'click_below_to_join': {
        'en': "Click below to join:",
        'ru': "Нажмите ниже, чтобы вступить:"
    },
    'join_group': {
        'en': "Join Group",
        'ru': "Вступить в группу"
    },
    'buy_nft_btn': {
        'en': "Buy NFT",
        'ru': "Купить NFT"
    },
    'buy_shiva_btn': {
        'en': "Buy SHIVA",
        'ru': "Купить SHIVA"
    },
    'trade_on_dedust': {
        'en': "🔄 Trade on DeDust",
        'ru': "🔄 Торговать на DeDust"
    },
    'view_on_getgems': {
        'en': "🖼 View on GetGems",
        'ru': "🖼 Смотреть на GetGems"
    },
    'fetching_top_holders': {
        'en': "🔍 Fetching top SHIVA holders...",
        'ru': "🔍 Получаю топ держателей SHIVA..."
    },
    'wallet_connected': {
        'en': "✅ Wallet connected: `{}`",
        'ru': "✅ Кошелек подключен: `{}`"
    },
    'wallet_disconnected': {
        'en': "Wallet disconnected.",
        'ru': "Кошелек отключен."
    },
    'connect_wallet': {
        'en': "Connect your wallet to use burn functionality.",
        'ru': "Подключите ваш кошелек, чтобы использовать функцию сжигания."
    },
    'burn_confirmation': {
        'en': "⚠️ You are about to burn {} tokens. This action is irreversible. Type /confirm_{} to proceed or /cancel to abort.",
        'ru': "⚠️ Вы собираетесь сжечь {} токенов. Это действие необратимо. Введите /confirm_{} для продолжения или /cancel для отмены."
    },
    'burn_success': {
        'en': "✅ Successfully burned {} tokens!\n\nTransaction hash: `{}`",
        'ru': "✅ Успешно сожжено {} токенов!\n\nХеш транзакции: `{}`"
    },
    'burn_cancelled': {
        'en': "Burn request cancelled.",
        'ru': "Запрос на сжигание отменен."
    }
}

class UserState(StatesGroup):
    choosing_language = State()
    waiting_for_wallet = State()
    waiting_for_transaction = State()

# Remove language-related fields from database
async def setup_database():
    async with aiosqlite.connect('members.db') as conn:
        cursor = await conn.cursor()
        # Keep existing members table creation
        await cursor.execute('''
            CREATE TABLE IF NOT EXISTS members (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                wallet_address TEXT UNIQUE,
                last_checked TIMESTAMP,
                has_nft BOOLEAN,
                verification_memo TEXT
            )
        ''')
        # --- ADD THIS NEW TABLE ---
        await cursor.execute('''
            CREATE TABLE IF NOT EXISTS monthly_message_stats (
                user_id INTEGER NOT NULL,
                year_month TEXT NOT NULL, -- Format: "YYYY-MM"
                username TEXT,            -- Store last known username for convenience
                message_count INTEGER DEFAULT 0,
                PRIMARY KEY (user_id, year_month)
            )
        ''')
        # Add new table for TON Connect wallet connections
        await cursor.execute('''
            CREATE TABLE IF NOT EXISTS user_wallets (
                telegram_id INTEGER PRIMARY KEY,
                wallet_addr TEXT NOT NULL, 
                connected_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_used TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        # --------------------------
        await conn.commit()

async def get_user_data(user_id: int):
    async with aiosqlite.connect('members.db') as conn:
        cursor = await conn.cursor()
        await cursor.execute('SELECT * FROM members WHERE user_id = ?', (user_id,))
        result = await cursor.fetchone()
        return result

async def get_user_by_wallet(wallet_address: str):
    async with aiosqlite.connect('members.db') as conn:
        cursor = await conn.cursor()
        await cursor.execute('SELECT * FROM members WHERE wallet_address = ?', (wallet_address,))
        result = await cursor.fetchone()
        return result

async def save_user_data(user_id: int, username: str, wallet_address: str, has_nft: bool, verification_memo: str = None):
    async with aiosqlite.connect('members.db') as conn:
        cursor = await conn.cursor()
        await cursor.execute('''
            INSERT OR REPLACE INTO members 
            (user_id, username, wallet_address, last_checked, has_nft, verification_memo)
            VALUES (?, ?, ?, CURRENT_TIMESTAMP, ?, ?)
        ''', (user_id, username, wallet_address, has_nft, verification_memo))
        await conn.commit()

async def check_transaction(address: str, memo: str) -> bool:
    API_BASE_URL = "https://toncenter.com/api/v2"
    
    async with aiohttp.ClientSession() as session:
        try:
            params = {
                "address": address,
                "limit": 1,
                "api_key": TON_API_KEY
            }
            async with session.get(f"{API_BASE_URL}/getTransactions", params=params) as response:
                if response.status != 200:
                    logger.error(f"API request failed with status {response.status}")
                    return False
                
                data = await response.json()
                if not data.get("ok", False):
                    logger.error(f"API request failed: {data.get('error', 'Unknown error')}")
                    return False
                
                transactions = data.get("result", [])
                if not transactions:
                    logger.info("No transactions found")
                    return False
                
                transaction = transactions[0]
                in_msg = transaction.get("in_msg", {})
                message = in_msg.get("message", "")
                
                if isinstance(message, str):
                    decoded_message = message
                else:
                    try:
                        decoded_message = base64.b64decode(message).decode('utf-8')
                    except:
                        decoded_message = str(message)
                
                return memo in decoded_message
                
        except Exception as e:
            logger.error(f"Error checking transaction: {str(e)}")
            return False

async def get_holder_name(holder_data: Dict) -> str:
    """Get holder name from database or owner data."""
    try:
        # Get owner data
        owner = holder_data.get("owner", {})
        owner_address = owner.get("address")
        
        # First check if we have a name in owner data
        if owner.get("name"):
            return owner["name"]
            
        # Then check our database for the address
        if owner_address:
            conn = aiosqlite.connect('members.db')
            cursor = conn.cursor()
            cursor.execute('SELECT username FROM members WHERE wallet_address = ?', (owner_address,))
            result = cursor.fetchone()
            conn.close()
            
            if result and result[0]:
                return f"@{result[0]}"
        
        return "Anonymous"
    except Exception as e:
        logger.error(f"Error getting holder name: {str(e)}")
        return "Anonymous"

async def notify_admins_wallet_registration(user_id: int, username: str, wallet_address: str):
    """Send detailed notification to admins about new wallet registration."""
    try:
        # Check NFT ownership
        has_nft = await check_nft_ownership(wallet_address)
        # Check SHIVA balance
        raw_balance, formatted_balance, price_data = await check_token_balance(wallet_address, SHIVA_TOKEN_ADDRESS)
        # Format notification message
        notification = (
            "🔔 *New Wallet Registration*\n\n"
            f"👤 User: @{escape_md(username)}\n"
            f"🆔 ID: `{escape_md(user_id)}`\n"
            f"👛 Wallet: `{escape_md(wallet_address)}`\n"
            f"🎨 NFT Status: {'✅ Has NFT' if has_nft else '❌ No NFT'}\n"
            f"💰 SHIVA Balance: {escape_md(f'{formatted_balance:,.2f}')}\n"
            f"⏰ Time: {escape_md(datetime.now().strftime('%Y-%m-%d %H:%M:%S UTC'))}"
        )
        # Send to all admins
        for admin_id in ADMIN_IDS:
            try:
                await bot.send_message(
                    chat_id=admin_id,
                    text=notification,
                    parse_mode="MarkdownV2"
                )
            except Exception as e:
                logger.error(f"Failed to notify admin {admin_id}: {str(e)}")
    except Exception as e:
        logger.error(f"Error in admin notification: {str(e)}", exc_info=True)
        
@dp.message(lambda message: message.chat.id == -1002201273698 and \
                            not message.from_user.is_bot and \
                            message.text and \
                            not message.text.startswith('/')
           )
async def handle_group_messages(message: Message):
    user_id = message.from_user.id
    username = message.from_user.username # Might be None
    # Use UTC for consistency
    current_time = datetime.now(timezone.utc)
    year_month = current_time.strftime('%Y-%m') # Format "YYYY-MM"

    logger.debug(f"Tracking message from user {user_id} (@{username}) for month {year_month}")

    try:
        async with aiosqlite.connect('members.db') as conn:
            cursor = await conn.cursor()
            # Use INSERT OR IGNORE + UPDATE or specific INSERT ON CONFLICT for atomicity
            # This tries to insert, if it fails (user_id, year_month exists), it updates.
            await cursor.execute('''
                INSERT INTO monthly_message_stats (user_id, year_month, username, message_count)
                VALUES (?, ?, ?, 1)
                ON CONFLICT(user_id, year_month) DO UPDATE SET
                    message_count = message_count + 1,
                    username = excluded.username -- Update username on conflict as well
            ''', (user_id, year_month, username))
            await conn.commit()
            logger.debug(f"Successfully updated/inserted message count for {user_id} in {year_month}")
    except Exception as e:
        logger.error(f"Failed to update message count for user {user_id} in month {year_month}: {e}", exc_info=True)
# --- END OF NEW MESSAGE HANDLER ---

# Helper to get language from FSM state
async def get_lang(state, user_id):
    data = await state.get_data()
    lang = data.get('language', 'en')
    return lang

@dp.message(Command('topchatters'))
async def top_chatters_command(message: Message):
    # Determine current month
    current_time = datetime.now(timezone.utc)
    year_month = current_time.strftime('%Y-%m') # Format like "2024-07"

    logger.info(f"User {message.from_user.id} requested top chatters for {year_month}")

    try:
        async with aiosqlite.connect('members.db') as conn:
            cursor = await conn.cursor()
            await cursor.execute('''
                SELECT user_id, username, message_count
                FROM monthly_message_stats
                WHERE year_month = ?
                ORDER BY message_count DESC
                LIMIT 10
            ''', (year_month,))
            top_users = await cursor.fetchall()

        if not top_users:
            # No special escaping needed for year_month in MarkdownV1
            reply_text = f"📊 No message data recorded yet for this month ({year_month})."
            await message.reply(reply_text) 
            return

        response_lines = [f"🏆 *Top 10 Chatters This Month ({year_month})*\n"]
        for i, (user_id, username, count) in enumerate(top_users, 1):
            
            display_name = f"`@{username}`" if username else f"`ID: {user_id}`"

            response_lines.append(f"{i}. {display_name}: {count} messages")

        reply_text = "\n".join(response_lines)
        # --- Change parse_mode to Markdown ---
        await message.reply(reply_text, parse_mode="Markdown")

    except Exception as e:
        logger.error(f"Error fetching top chatters: {e}", exc_info=True)
        error_msg = "❌ An error occurred while fetching the top chatters. Please try again later."
        await message.reply(error_msg)
# --- END OF NEW COMMAND HANDLER ---

@dp.message(Command('start'))
async def start_command(message: types.Message, state: FSMContext):
    user_id = message.from_user.id
    username = message.from_user.username
    # Always clear state
    await state.clear()
    # Language selection keyboard
    lang_kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="English", callback_data="lang_en"),
         InlineKeyboardButton(text="Русский", callback_data="lang_ru")]
    ])
    await message.answer("Please select your language / Пожалуйста, выберите язык:", reply_markup=lang_kb)
    await state.set_state(UserState.choosing_language)

@dp.callback_query(lambda c: c.data and c.data.startswith('lang_'))
async def process_language_selection(callback_query: CallbackQuery, state: FSMContext):
    lang = callback_query.data.split('_')[1]
    user_id = callback_query.from_user.id
    username = callback_query.from_user.username
    await state.update_data(language=lang)
    is_admin = str(user_id) in ADMIN_IDS
    lang = 'en' if is_admin else lang
    user_data = await get_user_data(user_id)

    # Also apply the same logic to the 'already_verified' message
    if user_data and user_data[4]:  # has_nft is True
        # Escape the whole message before sending
        already_verified_msg = escape_md(MESSAGES['already_verified'][lang])
        await callback_query.message.answer(already_verified_msg, parse_mode="MarkdownV2")
        
        # Add group invite link for already verified users
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text={
                'en': "Join Group",
                'ru': "Вступить в группу"
            }[lang], url=GROUP_INVITE_LINK)]
        ])
        await callback_query.message.answer(
            escape_md(MESSAGES['click_below_to_join'][lang]), 
            reply_markup=keyboard, 
            parse_mode="MarkdownV2"
        )
        return

    # Format the message with the raw first name
    raw_welcome_msg = MESSAGES['welcome_message'][lang].format(callback_query.from_user.first_name)
    # Escape the entire formatted message just before sending
    welcome_msg = escape_md(raw_welcome_msg)

    logger.info(f"Attempting to send welcome message (escaped): {welcome_msg}")
    try:
        await callback_query.message.answer_photo(
                FSInputFile(WELCOME_IMAGE_PATH),
            caption=welcome_msg,
            parse_mode="MarkdownV2"
            )
    except Exception as e:
        logger.error(f"Failed to send photo, trying text. Error: {e}")
        # Use the already escaped welcome_msg here
        await callback_query.message.answer(welcome_msg, parse_mode="MarkdownV2")
    await state.set_state(UserState.waiting_for_wallet)

@dp.message(Command("wallet"))
async def wallet_command(message: types.Message, state: FSMContext):
    args = message.text.split(maxsplit=1)
    lang = await get_lang(state, message.from_user.id)
    if len(args) < 2:
        await message.answer(escape_md({
            'en': "Please provide a wallet address: /wallet <address>",
            'ru': "Пожалуйста, укажите адрес кошелька: /wallet <address>"
        }[lang]), parse_mode="MarkdownV2")
        return
    wallet_address = args[1].strip()
    user_id = message.from_user.id
    username = message.from_user.username
    if not (wallet_address.startswith('EQ') or wallet_address.startswith('UQ')):
        await message.answer(escape_md(MESSAGES['invalid_wallet'][lang]), parse_mode="MarkdownV2")
        return
    await save_user_data(user_id, username, wallet_address, False)
    await message.answer(escape_md({
        'en': "✅ Wallet saved successfully!",
        'ru': "✅ Кошелек успешно сохранен!"
    }[lang]), parse_mode="MarkdownV2")
    await notify_admins_wallet_registration(user_id, username, wallet_address)

@dp.message(UserState.waiting_for_wallet)
async def handle_wallet_input(message: types.Message, state: FSMContext):
    lang = await get_lang(state, message.from_user.id)
    user_id = message.from_user.id
    username = message.from_user.username
    wallet_address = message.text.strip()
    if not (wallet_address.startswith('EQ') or wallet_address.startswith('UQ')):
        await message.answer(escape_md(MESSAGES['invalid_wallet'][lang]), parse_mode="MarkdownV2")
        return
    verification_memo = f"verify_{user_id}_{int(time_module.time())}"
    await state.update_data(wallet_address=wallet_address, verification_memo=verification_memo)
    verification_msg = {
        'en': f"""To verify your wallet ownership, please:\n\n1. Send a small transaction (0.01 TON) to this address:\n`{VERIFICATION_WALLET}`\n\n2. Include this exact memo in your transaction message:\n`{verification_memo}`\n\n3. Use /verify command after sending the transaction.\n\nI'll check for your transaction and verify your NFT ownership.""",
        'ru': f"""Для подтверждения владения кошельком, пожалуйста:\n\n1. Отправьте небольшую транзакцию (0.01 TON) на этот адрес:\n`{VERIFICATION_WALLET}`\n\n2. Укажите этот мемо в сообщении к транзакции:\n`{verification_memo}`\n\n3. Используйте команду /verify после отправки транзакции.\n\nЯ проверю вашу транзакцию и подтвержу владение NFT."""
    }[lang]
    await message.answer(verification_msg, parse_mode="Markdown")
    await state.set_state(UserState.waiting_for_transaction)

@dp.message(Command('verify'))
async def verify_command(message: types.Message, state: FSMContext):
    lang = await get_lang(state, message.from_user.id)
    user_id = message.from_user.id
    username = message.from_user.username
    state_data = await state.get_data()
    wallet_address = state_data.get('wallet_address')
    verification_memo = state_data.get('verification_memo')
    if not wallet_address or not verification_memo:
        await message.answer(escape_md({
            'en': "Please start the verification process with /start first.",
            'ru': "Пожалуйста, начните процесс верификации с /start."
        }[lang]), parse_mode="MarkdownV2")
        return
    await message.answer(escape_md({
        'en': "🔍 Checking your verification transaction...",
        'ru': "🔍 Проверяю вашу транзакцию..."
    }[lang]), parse_mode="MarkdownV2")
    transaction_verified = await check_transaction(VERIFICATION_WALLET, verification_memo)
    if not transaction_verified:
        failed_msg = {
            'en': f"""❌ Transaction not found. Please make sure you:\n\n1. Sent 0.01 TON to:\n`{VERIFICATION_WALLET}`\n\n2. Included this memo:\n`{verification_memo}`\n\nTry again with /verify after sending the transaction.""",
            'ru': f"""❌ Транзакция не найдена. Пожалуйста, убедитесь, что вы:\n\n1. Отправили 0.01 TON на:\n`{VERIFICATION_WALLET}`\n\n2. Указали этот мемо:\n`{verification_memo}`\n\nПопробуйте снова с /verify после отправки транзакции."""
        }[lang]
        await message.answer(escape_md(failed_msg), parse_mode="MarkdownV2")
        return
    await save_user_data(user_id, username, wallet_address, False)
    has_nft = await check_nft_ownership(wallet_address)
    _, shiva_balance, _ = await check_token_balance(wallet_address, SHIVA_TOKEN_ADDRESS)
    nft_requirement = has_nft
    shiva_requirement = shiva_balance >= 250_000
    if nft_requirement and shiva_requirement:
        await save_user_data(user_id, username, wallet_address, True)
        await message.answer(escape_md({
            'en': "🎉 Verification successful! You meet all requirements.\n\nYou can now join our exclusive group!",
            'ru': "🎉 Верификация успешна! Вы соответствуете всем требованиям.\n\nТеперь вы можете присоединиться к нашему эксклюзивному чату!"
        }[lang]), parse_mode="MarkdownV2")
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text={
                'en': "Join Group",
                'ru': "Вступить в группу"
            }[lang], url=GROUP_INVITE_LINK)]
        ])
        await message.answer(escape_md({
            'en': "Click below to join:",
            'ru': "Нажмите ниже, чтобы вступить:"
        }[lang]), reply_markup=keyboard, parse_mode="MarkdownV2")
    else:
        reasons = []
        if not nft_requirement:
            reasons.append({
                'en': "• You do not own a TONFANS NFT.",
                'ru': "• У вас нет TONFANS NFT."
            }[lang])
        if not shiva_requirement:
            reasons.append({
                'en': f"• You need at least 250,000 $SHIVA tokens. (Current: {shiva_balance:,.2f})",
                'ru': f"• Вам нужно минимум 250,000 $SHIVA токенов. (Сейчас: {shiva_balance:,.2f})"
            }[lang])
        reason_text = "\n".join(reasons)
        await message.answer(escape_md({
            'en': f"❌ You do not meet the requirements to join the group yet:\n\n{reason_text}\n\nPlease ensure you have at least 1 TONFANS NFT and 250,000 $SHIVA tokens, then try verification again.",
            'ru': f"❌ Вы пока не соответствуете требованиям для вступления в группу:\n\n{reason_text}\n\nПожалуйста, убедитесь, что у вас есть хотя бы 1 TONFANS NFT и 250,000 $SHIVA токенов, затем попробуйте снова."
        }[lang]), parse_mode="MarkdownV2")
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text={
                'en': "Buy NFT",
                'ru': "Купить NFT"
            }[lang], url=NFT_MARKETPLACE_LINK)],
            [InlineKeyboardButton(text={
                'en': "Buy SHIVA",
                'ru': "Купить SHIVA"
            }[lang], url=SHIVA_DEX_LINK)]
        ])
        await message.answer(escape_md({
            'en': "Resources to help you meet the requirements:",
            'ru': "Ресурсы для выполнения требований:"
        }[lang]), reply_markup=keyboard, parse_mode="MarkdownV2")
    await state.clear()

@dp.message(Command('whale'))
async def whale_command(message: Message, state: FSMContext):
    lang = await get_lang(state, message.from_user.id)
    user_id = message.from_user.id
    username = message.from_user.username
    user_data = await get_user_data(user_id)
    if not user_data or not user_data[2]:
        await message.reply(escape_md(MESSAGES['start_verification'][lang]), parse_mode="MarkdownV2")
        return
    wallet_address = user_data[2]
    await message.reply(escape_md(MESSAGES['whale_checking_balance'][lang]), parse_mode="MarkdownV2")
    raw_balance, formatted_balance, _ = await check_token_balance(wallet_address, SHIVA_TOKEN_ADDRESS)
    balance_message = escape_md({
        'en': f"Your $SHIVA balance: {formatted_balance:,.2f}",
        'ru': f"Ваш баланс $SHIVA: {formatted_balance:,.2f}"
    }[lang])
    await message.reply(balance_message, parse_mode="MarkdownV2")
    safe_username = escape_md(username)
    safe_wallet = escape_md(wallet_address)
    whale_notification = (
        f"Whale Status checked by @{safe_username} (ID: `{safe_wallet}`)\n"
        f"Balance: {escape_md(f'{formatted_balance:,.2f}')} $SHIVA\n"
        f"Wallet: `{safe_wallet}`"
    )
    for admin_id in ADMIN_IDS:
        try:
            await bot.send_message(
                chat_id=admin_id,
                text=whale_notification,
                parse_mode="MarkdownV2"
            )
        except Exception as e:
            logger.error(f"Failed to notify admin {admin_id}: {str(e)}")
    if formatted_balance >= 10_000_000:
        await message.reply(escape_md(MESSAGES['whale_verification_success'][lang]), parse_mode="MarkdownV2")
    else:
        shiva_needed = 10_000_000 - formatted_balance
        message_text = (
            f"{escape_md(MESSAGES['whale_verification_failed'][lang])}\n" +
            escape_md({
                'en': f"You need {shiva_needed:,.2f} more $SHIVA to qualify.",
                'ru': f"Вам нужно ещё {shiva_needed:,.2f} $SHIVA, чтобы квалифицироваться."
            }[lang])
        )
        await message.reply(message_text, parse_mode="MarkdownV2")

@dp.message(Command('price'))
async def price_command(message: Message, state: FSMContext): # <--- Added state
    """Show current SHIVA token price."""
    lang = await get_lang(state, message.from_user.id) # <--- Get language
    try:
        price_api_data = await get_shiva_price()
        if not price_api_data:
            await message.reply(escape_md(MESSAGES['unable_to_fetch_price'][lang]), parse_mode="MarkdownV2")
            return

        prices = price_api_data.get("prices", {})
        changes = price_api_data.get("diff_24h", {})

        usd_price = prices.get("USD", 0)
        ton_price = prices.get("TON", 0)
        usd_change = changes.get("USD", "+0%") 
        ton_change = changes.get("TON", "+0%")

        price_template = MESSAGES['price'][lang] 

        price_message_text = price_template.format(
            usd_price,
            usd_change, # Pass the string directly
            ton_price,
            ton_change, # Pass the string directly
            escape_md(SHIVA_DEX_LINK)
        )
        
        # Send the message using Markdown, as the template uses it
        await message.reply(price_message_text, parse_mode="Markdown", disable_web_page_preview=True) # Added preview disable

    except Exception as e:
        logger.error(f"Error in price command: {e}", exc_info=True) 
        # Use language for error message
        await message.reply(escape_md(MESSAGES['error_fetching_data'][lang]), parse_mode="MarkdownV2")

@dp.message(Command('top'))
async def top_command(message: Message, state: FSMContext):
    lang = await get_lang(state, message.from_user.id)
    try:
        await message.reply(escape_md(MESSAGES['fetching_top_holders'][lang]), parse_mode="MarkdownV2")
        holders = await get_top_holders()
        if not holders:
            await message.reply(escape_md(MESSAGES['unable_to_fetch_holders'][lang]), parse_mode="MarkdownV2")
            return
        response = {
            'en': "🏆 *Top SHIVA Holders*\n\n",
            'ru': "🏆 *Топ держателей SHIVA*\n\n"
        }[lang]
        for i, holder in enumerate(holders, 1):
            balance = int(holder.get("balance", "0")) / 1e9
            holder_name = await get_holder_name(holder)
            response += {
                'en': f"{i}. {holder_name}: {balance:,.2f} SHIVA\n",
                'ru': f"{i}. {holder_name}: {balance:,.2f} SHIVA\n"
            }[lang]
        response += {
            'en': f"\n💫 Total Holders: {len(holders):,}",
            'ru': f"\n💫 Всего держателей: {len(holders):,}"
        }[lang]
        await message.reply(escape_md(response), parse_mode="MarkdownV2")
    except Exception as e:
        logger.error(f"Error in top command: {e}")
        await message.reply(escape_md(MESSAGES['error_fetching_data'][lang]), parse_mode="MarkdownV2")

@dp.message(Command('buy_new_gem_shiva'))
async def buy_new_gem_shiva_command(message: Message, state: FSMContext):
    """Show information and link to buy SHIVA token."""
    lang = await get_lang(state, message.from_user.id)
    try:
        # Get current price to include in the message
        price_data = await get_shiva_price()
        # Default to 0 if price data is missing or invalid
        current_price = price_data.get("prices", {}).get("USD", 0)

        # Create the inline keyboard button with the new DEX link
        # Make sure NEW_SHIVA_DEX_LINK is defined somewhere accessible (see point 2 below)
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(
                text=MESSAGES['trade_on_dedust'][lang], # Text from MESSAGES
                url=SHIVA_DEX_LINK # Use the new link variable
            )]
        ])

        # Get the message template from MESSAGES (see point 3 below)
        buy_message_template = MESSAGES['buy_shiva'][lang]
        
        buy_message_text = buy_message_template.format(
            escape_md(SHIVA_TOKEN_ADDRESS),
            current_price
        )

        await message.reply(
            buy_message_text,
            reply_markup=keyboard,
            parse_mode="Markdown",
            disable_web_page_preview=True
        )
        logger.info(f"Sent buy_new_gem_shiva info to user {message.from_user.id}")

    except Exception as e:
        logger.error(f"Error in buy_new_gem_shiva command for user {message.from_user.id}: {e}", exc_info=True)
        await message.reply(escape_md(MESSAGES['error_fetching_data'][lang]), parse_mode="Markdown")

@dp.message(Command('nft'))
async def nft_command(message: Message, state: FSMContext):
    lang = await get_lang(state, message.from_user.id)
    try:
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(
                text=MESSAGES['view_on_getgems'][lang],
                url=NFT_MARKETPLACE_LINK
            )]
        ])
        await message.reply(
            escape_md(MESSAGES['buy_nft'][lang].format(NFT_COLLECTION_ADDRESS)),
            reply_markup=keyboard,
            parse_mode="MarkdownV2"
        )
    except Exception as e:
        logger.error(f"Error in nft command: {e}")
        await message.reply(escape_md(MESSAGES['error_fetching_data'][lang]), parse_mode="MarkdownV2")

@dp.message(Command('help'))
async def help_command(message: Message, state: FSMContext):
    lang = await get_lang(state, message.from_user.id)
    await message.reply(
        escape_md(MESSAGES['help_message'][lang]),
        parse_mode="MarkdownV2"
    )

# === TON Connect Wallet Integration Commands ===

TON_CONNECT_URL = "https://your-domain.com"  # Update with your actual domain

@dp.message(Command('connect'))
async def connect_command(message: Message, state: FSMContext):
    """Connect user wallet via TON Connect"""
    user_id = message.from_user.id
    username = message.from_user.username
    lang = await get_lang(state, message.from_user.id)
    
    # Check if already connected
    wallet = await get_user_wallet(user_id)
    if wallet:
        await message.reply(
            escape_md(f"Your wallet is already connected: `{wallet}`\nUse /disconnect if you want to connect a different wallet."),
            parse_mode="MarkdownV2"
        )
        return
        
    # Create web app URL for TON Connect
    connect_url = f"{TON_CONNECT_URL}/ton-connect?telegram_id={user_id}"
    
    # Send button that opens the web app
    await message.reply(
        escape_md("Click below to connect your TON wallet:"),
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="Connect Wallet", web_app=WebAppInfo(url=connect_url))]
        ]),
        parse_mode="MarkdownV2"
    )

@dp.message(Command('disconnect'))
async def disconnect_command(message: Message):
    """Disconnect user wallet"""
    user_id = message.from_user.id
    
    # Check if a wallet is connected
    wallet = await get_user_wallet(user_id)
    if not wallet:
        await message.reply(
            escape_md("You don't have a wallet connected. Use /connect to connect your wallet."),
            parse_mode="MarkdownV2"
        )
        return
    
    # Remove from database
    async with aiosqlite.connect('members.db') as conn:
        cursor = await conn.cursor()
        await cursor.execute('DELETE FROM user_wallets WHERE telegram_id = ?', (user_id,))
        await conn.commit()
    
    await message.reply(
        escape_md("Your wallet has been disconnected. Use /connect to connect a new wallet."),
        parse_mode="MarkdownV2"
    )

@dp.message(Command('wallet_info'))
async def wallet_info_command(message: Message):
    """Show user connected wallet info"""
    user_id = message.from_user.id
    
    # Get connected wallet
    wallet = await get_user_wallet(user_id)
    if not wallet:
        await message.reply(
            escape_md("You don't have a wallet connected. Use /connect to connect your wallet."),
            parse_mode="MarkdownV2"
        )
        return
    
    # Get balance info for the connected wallet if available
    raw_balance, formatted_balance, price_data = await check_token_balance(wallet, SHIVA_TOKEN_ADDRESS)
    
    # Format the response
    info_text = f"Connected Wallet: `{wallet}`\n\n"
    if formatted_balance > 0:
        info_text += f"SHIVA Balance: {formatted_balance:,.2f} tokens"
    else:
        info_text += "SHIVA Balance: 0 tokens"
    
    await message.reply(
        escape_md(info_text),
        parse_mode="MarkdownV2"
    )

@dp.message(Command('burn'))
async def burn_command(message: Message):
    """Initiate token burn process"""
    user_id = message.from_user.id
    
    # Check for connected wallet
    wallet = await get_user_wallet(user_id)
    if not wallet:
        await message.reply(
            escape_md("You need to connect your wallet first. Use /connect to connect your wallet."),
            parse_mode="MarkdownV2"
        )
        return
    
    # Parse the amount from arguments
    args = message.text.split()
    if len(args) != 2:
        await message.reply(
            escape_md("Usage: /burn <amount>\nExample: /burn 100"),
            parse_mode="MarkdownV2"
        )
        return
    
    try:
        amount = int(args[1])
        if amount <= 0:
            raise ValueError("Amount must be positive")
    except ValueError:
        await message.reply(
            escape_md("Invalid amount. Please provide a positive number."),
            parse_mode="MarkdownV2"
        )
        return
    
    # Check balance to make sure user has enough tokens
    _, balance, _ = await check_token_balance(wallet, SHIVA_TOKEN_ADDRESS)
    if balance < amount:
        await message.reply(
            escape_md(f"You don't have enough tokens. Your balance: {balance:,.2f}"),
            parse_mode="MarkdownV2"
        )
        return
    
    # Store the pending burn request
    pending_burns[user_id] = amount
    
    # Confirm with the user
    await message.reply(
        escape_md(f"⚠️ You are about to burn {amount} tokens permanently.\n\nThis action is irreversible.\n\nType /confirm_{amount} to proceed or /cancel to abort."),
        parse_mode="MarkdownV2"
    )

@dp.message(lambda message: message.text and message.text.startswith('/confirm_'))
async def confirm_burn_command(message: Message):
    """Confirm and execute token burn"""
    user_id = message.from_user.id
    
    # Extract amount from command
    try:
        amount = int(message.text.split('_')[1])
    except (IndexError, ValueError):
        await message.reply(
            escape_md("Invalid confirmation command. Please use the exact command provided."),
            parse_mode="MarkdownV2"
        )
        return
    
    # Check if there is a pending burn request
    if user_id not in pending_burns or pending_burns[user_id] != amount:
        await message.reply(
            escape_md("No matching burn request found. Please use /burn <amount> first."),
            parse_mode="MarkdownV2"
        )
        return
    
    # Get user wallet
    wallet = await get_user_wallet(user_id)
    if not wallet:
        await message.reply(
            escape_md("Your wallet connection has been lost. Please use /connect to reconnect."),
            parse_mode="MarkdownV2"
        )
        pending_burns.pop(user_id, None)
        return
    
    # Create web app URL for burn confirmation
    burn_url = f"{TON_CONNECT_URL}/ton-burn?telegram_id={user_id}&amount={amount}"
    
    # Send button that opens the burn confirmation web app
    await message.reply(
        escape_md(f"You're about to burn {amount} tokens. Please confirm the transaction in your wallet:"),
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text=f"Burn {amount} Tokens", web_app=WebAppInfo(url=burn_url))]
        ]),
        parse_mode="MarkdownV2"
    )
    
    # Note: The actual burn will be completed when the user signs the transaction
    # in the web app and the callback is received. We'll keep the pending burn
    # in memory until then.

@dp.message(Command('cancel'))
async def cancel_burn_command(message: Message):
    """Cancel pending burn request"""
    user_id = message.from_user.id
    
    if user_id in pending_burns:
        amount = pending_burns.pop(user_id)
        await message.reply(
            escape_md(f"Burn request for {amount} tokens has been cancelled."),
            parse_mode="MarkdownV2"
        )
    else:
        await message.reply(
            escape_md("No pending burn request to cancel."),
            parse_mode="MarkdownV2"
        )

# Endpoint to receive burn transaction results
async def handle_burn_result(request):
    """Web endpoint to receive burn transaction results"""
    data = await request.json()
    telegram_id = data.get('telegram_id')
    tx_hash = data.get('tx_hash')
    status = data.get('status')
    
    if telegram_id and tx_hash and status == 'success':
        # Get the amount from pending burns
        amount = pending_burns.pop(int(telegram_id), None)
        if amount:
            # Notify the user about successful burn
            await bot.send_message(
                chat_id=telegram_id,
                text=escape_md(f"✅ Successfully burned {amount} tokens!\n\nTransaction hash: `{tx_hash}`"),
                parse_mode="MarkdownV2"
            )
            
            # Notify admins
            for admin_id in ADMIN_IDS:
                try:
                    await bot.send_message(
                        chat_id=admin_id,
                        text=escape_md(f"🔥 User {telegram_id} burned {amount} tokens\nTransaction: `{tx_hash}`"),
                        parse_mode="MarkdownV2"
                    )
                except Exception as e:
                    logger.error(f"Failed to notify admin {admin_id}: {e}")
    
    return web.Response(text="OK")

async def health_check(request):
    return web.Response(text="OK")

async def start_http_server():
    app = web.Application()
    app.router.add_get('/health', health_check)
    # Add new endpoint for burn result
    app.router.add_post('/burn-result', handle_burn_result)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, '0.0.0.0', 8000)
    await site.start()
    logger.info("HTTP server started on port 8000")

async def send_active_ping(bot_instance: Bot):
    """Sends a ping message every 6 hours to keep the bot active."""
    while True:
        try:
            # Send ping to admin
            await bot_instance.send_message(PING_ADMIN_ID, "I am active")
            logger.info("Sent 'I am active' ping.")
            
            # Perform a health check on the database
            async with aiosqlite.connect('members.db') as conn:
                cursor = await conn.cursor()
                await cursor.execute('SELECT COUNT(*) FROM members')
                count = await cursor.fetchone()
                logger.info(f"Database health check: {count[0]} members in database")
            
            # Wait for 6 hours before next ping
            await asyncio.sleep(21600)
            
        except Exception as e:
            logger.error(f"Failed to send 'I am active' ping: {e}")
            # If there's an error, wait a shorter time before retrying
            await asyncio.sleep(5)

async def daily_membership_check(bot_instance: Bot):
    """Checks all users daily at 00:00 UTC and removes those who do not meet requirements."""
    while True:
        # Calculate seconds until next 00:00 UTC
        now = datetime.utcnow().replace(tzinfo=timezone.utc)
        # Ensure the next run is strictly in the future, even if run exactly at midnight
        if now.hour == 0 and now.minute == 0 and now.second < 30: # Add a small buffer
            next_run = now.replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=1)
        else:
            # Calculate next midnight normally
             target_time = datetime.combine(now.date(), datetime.min.time()).replace(tzinfo=timezone.utc) + timedelta(days=1)
             if target_time <= now: # Handle edge case if calculation results in past/present time
                 target_time += timedelta(days=1)
             next_run = target_time

        sleep_seconds = (next_run - now).total_seconds()
        logger.info(f"Daily membership check scheduled to run in {sleep_seconds:.2f} seconds.")
        await asyncio.sleep(sleep_seconds)
        logger.info("Starting daily membership check...")

        removed_users = []
        processed_users = 0
        start_time = datetime.now(timezone.utc)

        try:
            async with aiosqlite.connect('members.db') as conn:
                cursor = await conn.execute('SELECT user_id, username, wallet_address FROM members WHERE wallet_address IS NOT NULL AND wallet_address != ""')
                users = await cursor.fetchall()
            
            total_users_to_check = len(users)
            logger.info(f"Checking {total_users_to_check} users with wallets.")

            for user_id, username, wallet_address in users:
                # Add a try/except block for each user's check process
                try:
                    processed_users += 1
                    # Exclude core person and admins
                    if str(user_id) in ADMIN_IDS or str(user_id) == '718025267':
                        logger.debug(f"Skipping admin/core user: {user_id}")
                        continue # Skip to the next user
                    
                    logger.debug(f"Checking user: {user_id} (@{username or 'NoUsername'})")
                    
                    # Check requirements
                    has_nft = await check_nft_ownership(wallet_address)
                    # Add a small delay between the two API calls for the SAME user, just in case
                    await asyncio.sleep(0.5) 
                    _, shiva_balance, _ = await check_token_balance(wallet_address, SHIVA_TOKEN_ADDRESS)
                    
                    meets_requirements = has_nft and shiva_balance >= 250_000

                    if not meets_requirements:
                        logger.info(f"User {user_id} (@{username or 'NoUsername'}) does not meet requirements (NFT: {has_nft}, SHIVA: {shiva_balance:.2f}). Attempting removal.")
                        try:
                            # Update the database to mark user as not verified anymore
                            async with aiosqlite.connect('members.db') as update_conn:
                                await update_conn.execute('UPDATE members SET has_nft = ? WHERE user_id = ?', (False, user_id))
                                await update_conn.commit()
                                logger.info(f"Updated verification status for user {user_id} to False")
                            
                            # Send notification to the user
                            removal_reason = []
                            if not has_nft:
                                removal_reason.append("no longer own a TONFANS NFT")
                            if shiva_balance < 250_000:
                                removal_reason.append(f"SHIVA balance too low ({shiva_balance:,.2f}/250,000)")
                            
                            reason_text = " and ".join(removal_reason)
                            
                            notification_msg = f"""❗️ *Group Membership Notice*

You have been removed from the TONFANS group because you {reason_text}.

To rejoin the group, please:
1. Ensure you own at least 1 TONFANS NFT
2. Have at least 250,000 SHIVA tokens
3. Reverify using the bot with /start command

If you believe this is a mistake, please reverify your wallet again."""
                            
                            try:
                                await bot_instance.send_message(
                                    chat_id=user_id,
                                    text=notification_msg,
                                    parse_mode="Markdown"
                                )
                                logger.info(f"Sent removal notification to user {user_id}")
                            except Exception as notify_err:
                                logger.error(f"Failed to notify user {user_id} about removal: {notify_err}")
                            
                            # Ban and immediately unban to kick
                            await bot_instance.ban_chat_member(GROUP_ID, user_id)
                            # Add a small delay before unbanning if needed, but usually not necessary
                            # await asyncio.sleep(0.2) 
                            await bot_instance.unban_chat_member(GROUP_ID, user_id)  
                            removed_users.append(f"@{escape_md(username or 'NoUsername')} \\(ID: `{escape_md(user_id)}`\\)") # Escape for final message
                            logger.info(f"Successfully removed user {user_id}")
                        except Exception as remove_err:
                            # Log specific error for removal failure
                            logger.error(f"Failed to remove user {user_id} (@{username or 'NoUsername'}) from group {GROUP_ID}: {remove_err}")
                    else:
                         logger.debug(f"User {user_id} meets requirements.")

                except Exception as check_err:
                    # Log errors during the check process for a specific user
                    logger.error(f"Error checking requirements for user {user_id} (@{username or 'NoUsername'}): {check_err}")
                
                finally:
                    logger.debug(f"Sleeping for 1.5s after checking user {user_id}")
                    await asyncio.sleep(1.5) 

        except Exception as e:
            # Log errors related to the overall process (e.g., database connection)
            logger.error(f"Error during daily membership check main loop: {e}", exc_info=True)

        duration = (datetime.now(timezone.utc) - start_time).total_seconds()
        log_msg = f"Daily membership check finished. Processed: {processed_users}/{total_users_to_check}. Removed: {len(removed_users)}. Duration: {duration:.2f}s."
        logger.info(log_msg)

        if removed_users:
            admin_msg_text = (
                f"🚫 *Daily Membership Check Report*\n\n"
                f"The following users were removed for not meeting requirements \\(≥1 NFT and ≥250,000 \\$SHIVA\\):\n\n"
                + "\n".join(removed_users) +
                f"\n\n_Check completed in {duration:.1f} seconds\\._"
            )
        else:
            admin_msg_text = f"✅ Daily membership check complete\\. No users needed to be removed\\. \\({duration:.1f}s\\)"
        
        for admin_id in ADMIN_IDS:
            try:
                await bot_instance.send_message(admin_id, admin_msg_text, parse_mode="MarkdownV2")
            except Exception as e:
                logger.error(f"Failed to notify admin {admin_id}: {e}")

# TON Connect wallet functions
async def get_user_wallet(telegram_id: int) -> str:
    """Get connected wallet address for a telegram user."""
    async with aiosqlite.connect('members.db') as conn:
        cursor = await conn.cursor()
        await cursor.execute('SELECT wallet_addr FROM user_wallets WHERE telegram_id = ?', (telegram_id,))
        result = await cursor.fetchone()
        return result[0] if result else None

async def save_user_wallet(telegram_id: int, wallet_addr: str) -> bool:
    """Save or update user's connected wallet."""
    try:
        async with aiosqlite.connect('members.db') as conn:
            cursor = await conn.cursor()
            await cursor.execute('''
                INSERT OR REPLACE INTO user_wallets 
                (telegram_id, wallet_addr, connected_at, last_used)
                VALUES (?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            ''', (telegram_id, wallet_addr))
            await conn.commit()
            return True
    except Exception as e:
        logger.error(f"Error saving user wallet: {e}")
        return False

async def update_wallet_used(telegram_id: int) -> None:
    """Update the last_used timestamp for a wallet."""
    async with aiosqlite.connect('members.db') as conn:
        cursor = await conn.cursor()
        await cursor.execute('UPDATE user_wallets SET last_used = CURRENT_TIMESTAMP WHERE telegram_id = ?', (telegram_id,))
        await conn.commit()

# Store pending burn requests
pending_burns = {}  # telegram_id -> amount

async def main():
    print("Starting NFT Checker Bot...")
    await setup_database()
    
    # Create background tasks
    ping_task = asyncio.create_task(send_active_ping(bot))
    daily_check_task = asyncio.create_task(daily_membership_check(bot))
    
    try:
        # Start HTTP server for health checks
        await start_http_server()
        
        # Initialize admin commands
        admin_commands = AdminCommands(bot)
        register_admin_handlers(dp, admin_commands)
        
        # Start polling - This is the main event loop runner
        await dp.start_polling(bot)
        
    except Exception as e:
        # Log errors occurring in the main polling or startup process
        logger.error(f"Main loop error: {e}", exc_info=True)
    finally:
        # Cancel all background tasks on shutdown
        ping_task.cancel()
        daily_check_task.cancel()
        
        await asyncio.gather(
            ping_task, 
            daily_check_task,  
            return_exceptions=True # Important for robustness
        )
        
        await bot.session.close()
        logger.info("Bot session closed.")

if __name__ == '__main__':
    # Make sure logging is configured before running
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    logger = logging.getLogger(__name__) # Ensure logger is defined globally if needed here
    asyncio.run(main())
