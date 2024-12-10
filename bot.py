import asyncio
import aiohttp
import base64
import json
import requests
from typing import Tuple, List, Dict
import time as time_module
from datetime import datetime
from aiogram import Bot, Dispatcher, types
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, FSInputFile, ChatMemberOwner, ChatMemberAdministrator, ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove
from aiogram.filters import Command
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import Message
import sqlite3
import logging

# Basic Configuration
API_TOKEN = '8067666224:AAELEOrjl0lHDUsqP7NUFU8FTYuzRt972ik'
NFT_COLLECTION_ADDRESS = 'EQDmUOKwwa6KU0YFbA_CZTGccRdh5SWIQdBDKg741ecOqzR0'
GROUP_INVITE_LINK = "https://t.me/+X44w-gPPj3AzYWU0"
NFT_MARKETPLACE_LINK = "https://getgems.io/collection/EQDmUOKwwa6KU0YFbA_CZTGccRdh5SWIQdBDKg741ecOqzR0"
ADMIN_IDS = ["1499577590","5851290427"]
VERIFICATION_WALLET = "UQA53kg3IzUo2PTuaZxXB3qK7fICyc1u_Yu8d0JDYJRPVWpz"
TON_API_KEY = "6767227019a948426ee2ef5a310f490e43cc1ca23363b932303002e59988f833"
GROUP_ID = -1002476568928
BASE_URL = "https://toncenter.com/api/v3"
WELCOME_IMAGE_PATH = "boris.jpg"
TONAPI_KEY = "AHZNMH2YZTTI2NIAAAACRWPE4TMJORYEHELN4ADWSJYBYH475H4AN4FYZUNVNZV4JM74HJY"
SHIVA_TOKEN_ADDRESS = "EQAQAYqUr9IDiiMQKvXXHtLhT77WvbhH7VGhvPPJmBVF3O7y"

# Initialize bot and dispatcher
bot = Bot(token=API_TOKEN)
storage = MemoryStorage()
dp = Dispatcher(storage=storage)
logger = logging.getLogger(__name__)

class UserState(StatesGroup):
    selecting_language = State()
    waiting_for_wallet = State()
    waiting_for_transaction = State()

# Add translations dictionary
TRANSLATIONS = {
    'en': {
        'select_language': "🌐 Please select your language:",
        'username_required': (
            "❌ You need to set a username in Telegram before using this bot.\n\n"
            "To set a username:\n"
            "1. Go to Telegram Settings\n"
            "2. Tap on your profile\n"
            "3. Tap 'Username'\n"
            "4. Set a username\n\n"
            "Once you've set a username, come back and use /start again."
        ),
        'welcome_message': (
            "👋 This is Boris.\nWelcome {}@{}!\n\n"
            "I'm tonfans NFT checker bot. I'll help you verify your NFT "
            "ownership and get access to our exclusive group.\n\n"
            "Please send me your TON wallet address to begin verification."
        ),
        'invalid_wallet': "❌ Invalid wallet address format. Please send a valid TON wallet address.",
        'verification_instructions': (
            "To verify your wallet ownership, please:\n\n"
            "1. Send a small transaction (0.01 TON) to this address:\n"
            "`{}`\n\n"
            "2. Include this exact memo in your transaction message:\n"
            "`{}`\n\n"
            "3. Use /verify command after sending the transaction.\n\n"
            "I'll check for your transaction and verify your NFT ownership."
        ),
        'checking_transaction': "🔍 Checking your verification transaction...",
        'transaction_not_found': (
            "❌ Transaction not found. Please make sure you:\n\n"
            "1. Sent 0.01 TON to:\n"
            "`{0}`\n\n"
            "2. Included this memo:\n"
            "`{1}`\n\n"
            "Try again with /verify after sending the transaction."
        ),
        'transaction_verified': "✅ Transaction verified! Now checking NFT ownership...",
        'checking_royalties': "🔍 Checking NFT royalty status...",
        'royalty_status': (
            "📊 NFT Royalty Status:\n"
            "✅ NFTs with paid royalties: {}\n"
            "❌ NFTs without royalties: {}\n"
            "ℹ️ NFTs with no transfer info: {}\n\n"
            "Detailed NFT Status:\n"
        ),
        'nft_status_paid': "✅ Royalty paid",
        'nft_status_unpaid': "❌ Royalty not paid",
        'nft_status_unknown': "ℹ️ No transfer information",
        'success_message': "🎉 Congratulations! Your wallet is verified and your tonfans NFT ownership confirmed.",
        'royalty_warning': "\n⚠️ Some of your NFTs have unpaid royalties. Please consider paying them to support the project.",
        'join_group': "\nYou can now join our exclusive group:",
        'no_nft_found': (
            "✅ Wallet verified but no NFT found in your wallet.\n"
            "To join our group, you need to own at least one NFT from our collection.\n"
            "You can get one here:"
        ),
        'join_group_button': "Join Group",
        'buy_nft_button': "Buy NFT",
        'nft_marketplace_button': "NFT Marketplace",
        'token_balance': "Your $SHIVA balance: {:,.2f}",
        'no_token_balance': "You don't have any $SHIVA tokens in your wallet.",
        'start_verification': "Please start the verification process first using /start command.",
        'no_pending_verification': "No pending verification found. Please start over using /start command.",
        'admin_new_verification': (
            "🆕 *New Verification Attempt:*\n"
            "User: @{}\n"
            "ID: `{}`\n"
            "Wallet: `{}`\n"
            "Verification Memo: `{}`"
        ),
        'admin_verification_success': (
            "✅ NFT Verification Successful:\n"
            "User: @{}\n"
            "ID: {}\n"
            "Wallet: {}\n"
            "$SHIVA Balance: {:.2f}\n"
            "Royalty Status: {} paid, {} unpaid, {} unknown"
        ),
        'admin_no_nft': (
            "❌ *No NFT Found:*\n"
            "User: @{}\n"
            "ID: `{}`\n"
            "Wallet: `{}`"
        )
    },
    'ru': {
        'select_language': "🌐 Пожалуйста, выберите язык:",
        'username_required': (
            "❌ Прежде чем использовать этого бота, вам нужно установить имя пользователя в Telegram.\n\n"
            "Чтобы установить имя пользователя:\n"
            "1. Перейдите в настройки Telegram\n"
            "2. Нажмите на свой профиль\n"
            "3. Нажмите 'Имя пользователя'\n"
            "4. Установите имя пользовател\n\n"
            "После установки имени пользователя вернитесь и снова используйте команду /start."
        ),
        'welcome_message': (
            "👋 Это Борис.\nДобро ��ожаловать {}@{}!\n\n"
            "Я бот-проверщик NFT tonfans. Я помогу вам проверить владение NFT "
            "и получить доступ к нашей эксклюзивной группе.\n\n"
            "Пожалуйста, отправьте мне адрес вашего TON кошелька для начала проверки."
        ),
        'invalid_wallet': "❌ Неверный формат адреса кошелька. Пожалуйста, отправьте действительный адрес TON кошелька.",
        'verification_instructions': (
            "Для подтверждения владения кошельком, пожалуйста:\n\n"
            "1. Отправьте небольшую транзакцию (0.01 TON) на этот адрес:\n"
            "`{}`\n\n"
            "2. Включите это точное сообщение в вашу транзакцию:\n"
            "`{}`\n\n"
            "3. Используйте команду /verify после отправки транзакции.\n\n"
            "Я проверю вашу транзакцию и владение NFT."
        ),
        'checking_transaction': "🔍 Проверяю вашу транзакц��ю...",
        'transaction_not_found': (
            "❌ Транзакция не найдена. Пожалуйста, убедитесь, что вы:\n\n"
            "1. Отправили 0.01 TON на:\n"
            "`{0}`\n\n"
            "2. Включили это сообщение:\n"
            "`{1}`\n\n"
            "Попробуйте снова с командой /verify после отправки транзакции."
        ),
        'transaction_verified': "✅ Транзакция подтверждена! Теперь проверяю владение NFT...",
        'checking_royalties': "🔍 Проверяю стат���с роялти NFT...",
        'royalty_status': (
            "📊 Статус роялти NFT:\n"
            "✅ NFT с оплаченными роялти: {}\n"
            "❌ NFT без роялти: {}\n"
            "ℹ️ NFT без информации о переводе: {}\n\n"
            "Подробный статус NFT:\n"
        ),
        'nft_status_paid': "✅ Роялти ��плачено",
        'nft_status_unpaid': "❌ Роялти не оплачено",
        'nft_status_unknown': "ℹ️ Нет информации о переводе",
        'success_message': "🎉 Поздравляем! Ваш кошелек подтвержден и владение NFT tonfans подтверждено.",
        'royalty_warning': "\n⚠️ Некоторые из ваших NFT имеют неоплаченные роялти. Пожалуйста, рассмотрит�� возможность их оплаты для поддержки проекта.",
        'join_group': "\nТеперь вы можете присоединиться к нашей эксклюзивной группе:",
        'no_nft_found': (
            "✅ Кошелек подтвержден, но NFT не найден в вашем кошельке.\n"
            "Чтобы присоединиться к нашей группе, вам нужно владеть хотя бы одним NFT из нашей коллекции.\n"
            "Вы можете получить его здесь:"
        ),
        'join_group_button': "Присоединиться к группе",
        'buy_nft_button': "Купит���� NFT",
        'nft_marketplace_button': "NFT Маркетп��ес",
        'token_balance': "Ваш баланс $SHIVA: {:,.2f}",
        'no_token_balance': "У вас нет токенов $SHIVA в кошельке.",
        'start_verification': "Пожалуйста, сначала начните процесс верификации, используя команду /start.",
        'no_pending_verification': "Не найдено неотправленных запросов на верификацию. Пожалуйста, начните снова, используя команду /start.",
        'admin_new_verification': (
            "�� *Новый запрос на верификацию:*\n"
            "Пользователь: @{}\n"
            "ID: `{}`\n"
            "Кошелек: `{}`\n"
            "Memo: `{}`"
        ),
        'admin_verification_success': (
            "✅ *Верификация NFT успешно завершена:*\n"
            "Пользователь: @{}\n"
            "ID: `{}`\n"
            "Кошелек: `{}`\n"
            "$SHIVA Balance: {:.2f}\n"
            "Статус роялти: {} оплачено, {} не оплачено, {} неизвестно"
        ),
        'admin_no_nft': (
            "❌ *NFT не найден:*\n"
            "Пользователь: @{}\n"
            "ID: `{}`\n"
            "Кошелек: `{}`"
        )
    }
}

# Database setup

def setup_database():
    conn = sqlite3.connect('members.db')
    cursor = conn.cursor()
    
    # First, check if the language column exists
    cursor.execute("PRAGMA table_info(members)")
    columns = [column[1] for column in cursor.fetchall()]
    
    if 'language' not in columns:
        # Add language column if it doesn't exist
        cursor.execute('ALTER TABLE members ADD COLUMN language TEXT DEFAULT "en"')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS members (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            wallet_address TEXT,
            last_checked TIMESTAMP,
            has_nft BOOLEAN,
            verification_memo TEXT,
            language TEXT DEFAULT 'en'
        )
    ''')
    conn.commit()
    conn.close()

# Enhanced database operations
async def get_user_data(user_id: int):
    conn = sqlite3.connect('members.db')
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM members WHERE user_id = ?', (user_id,))
    result = cursor.fetchone()
    conn.close()
    if result and len(result) < 7:  # If language is not in the result
        return (*result, 'en')  # Add default language
    return result

async def get_user_by_wallet(wallet_address: str):
    conn = sqlite3.connect('members.db')
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM members WHERE wallet_address = ?', (wallet_address,))
    result = cursor.fetchone()
    conn.close()
    return result

async def save_user_data(user_id: int, username: str, wallet_address: str, has_nft: bool, verification_memo: str = None):
    conn = sqlite3.connect('members.db')
    cursor = conn.cursor()
    
    # First get the current language setting
    cursor.execute('SELECT language FROM members WHERE user_id = ?', (user_id,))
    result = cursor.fetchone()
    language = result[0] if result else 'en'
    
    cursor.execute('''
        INSERT OR REPLACE INTO members 
        (user_id, username, wallet_address, last_checked, has_nft, verification_memo, language)
        VALUES (?, ?, ?, CURRENT_TIMESTAMP, ?, ?, ?)
    ''', (user_id, username, wallet_address, has_nft, verification_memo, language))
    conn.commit()
    conn.close()

async def save_user_language(user_id: int, language: str):
    conn = sqlite3.connect('members.db')
    cursor = conn.cursor()
    cursor.execute('''
        UPDATE members 
        SET language = ?
        WHERE user_id = ?
    ''', (language, user_id))
    conn.commit()
    conn.close()

async def bulk_add_members(members_data: list):
    """
    Add multiple members to the database
    
    Parameters:
    members_data: list of tuples (user_id, username, wallet_address)
    """
    conn = sqlite3.connect('members.db')
    cursor = conn.cursor()
    try:
        for user_id, username, wallet_address in members_data:
            cursor.execute('''
                INSERT OR REPLACE INTO members 
                (user_id, username, wallet_address, last_checked, has_nft)
                VALUES (?, ?, ?, CURRENT_TIMESTAMP, ?)
            ''', (user_id, username, wallet_address, False))
        conn.commit()
        return True
    except Exception as e:
        logger.error(f"Error in bulk_add_members: {e}")
        return False
    finally:
        conn.close()

async def notify_admin(message: str):
    for admin_id in ADMIN_IDS:
        try:
            await bot.send_message(admin_id, message, parse_mode="Markdown")
        except Exception as e:
            logger.error(f"Failed to notify admin {admin_id}: {e}")

# Transaction verification function
async def check_nft_ownership(wallet_address: str) -> bool:
    url = f'https://tonapi.io/v2/accounts/{wallet_address}/nfts?collection={NFT_COLLECTION_ADDRESS}&limit=1000&offset=0&indirect_ownership=false'
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        nft_items = response.json().get('nft_items', [])
        return len(nft_items) > 0
    except Exception as e:
        logger.error(f"Error checking NFT ownership for {wallet_address}: {e}")
        return False

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

async def check_nft_royalties(wallet_address: str) -> Tuple[int, int, int, List[Dict]]:
    """
    Check royalty payment status for NFTs in a wallet.
    Returns: (paid_royalties, unpaid_royalties, no_transfer_info, nft_details)
    """
    nft_response = requests.get(
        f"{BASE_URL}/nft/items",
        params={
            "owner_address": wallet_address,
            "collection_address": NFT_COLLECTION_ADDRESS,
            "limit": 25,
            "offset": 0
        },
        headers={"accept": "application/json"}
    )
    
    nft_data = nft_response.json()
    nft_items = nft_data.get("nft_items", [])
    
    paid_royalties = 0
    unpaid_royalties = 0
    no_transfer_info = 0
    nft_details = []
    
    for nft in nft_items:
        nft_address = nft["address"]
        nft_index = nft.get("index", "Unknown")
        
        transfer_response = requests.get(
            f"{BASE_URL}/nft/transfers",
            params={
                "owner_address": wallet_address,
                "item_address": nft_address,
                "collection_address": NFT_COLLECTION_ADDRESS,
                "direction": "in",
                "limit": 25,
                "offset": 0,
                "sort": "desc"
            },
            headers={"accept": "application/json"}
        )
        
        transfer_data = transfer_response.json()
        transfers = transfer_data.get("nft_transfers", [])
        
        if transfers:
            latest_transfer = transfers[0]
            forward_amount = latest_transfer.get("forward_amount")
            
            nft_status = {
                "index": nft_index,
                "royalty_paid": forward_amount != "1",
                "transfer_info": True
            }
            
            if forward_amount == "1":
                unpaid_royalties += 1
            else:
                paid_royalties += 1
        else:
            nft_status = {
                "index": nft_index,
                "royalty_paid": None,
                "transfer_info": False
            }
            no_transfer_info += 1
            
        nft_details.append(nft_status)
    
    return paid_royalties, unpaid_royalties, no_transfer_info, nft_details

# Updated start command handler
@dp.message(Command('start'))
async def start_command(message: types.Message, state: FSMContext):
    # Create language selection keyboard
    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [
                KeyboardButton(text="🇬🇧 English"),
                KeyboardButton(text="🇷🇺 Русский")
            ]
        ],
        resize_keyboard=True,
        one_time_keyboard=True
    )
    
    # Force language selection first
    await message.answer(
        "🌐 Please select your language:\n🌐 Пожалуйста, выберите язык:", 
        reply_markup=keyboard
    )
    await state.set_state(UserState.selecting_language)

# Add language selection handler
@dp.message(UserState.selecting_language)
async def handle_language_selection(message: types.Message, state: FSMContext):
    # Explicitly set language based on selection
    language = 'ru' if '🇷🇺' in message.text else 'en'
    user_id = message.from_user.id
    
    # Save language preference
    await save_user_language(user_id, language)
    
    # Verify the language was saved
    user_data = await get_user_data(user_id)
    translations = TRANSLATIONS[language]
    
    # Log for debugging
    print(f"Selected language: {language}")
    print(f"User data after save: {user_data}")
    
    username = message.from_user.username
    existing_user = await get_user_data(user_id)
    
    await message.answer(
        translations['welcome_message'].format(
            'back ' if existing_user else '',
            username
        ),
        reply_markup=ReplyKeyboardRemove()
    )
    
    await state.set_state(UserState.waiting_for_wallet)

# Updated wallet submission handler
@dp.message(UserState.waiting_for_wallet)
async def handle_wallet_input(message: types.Message, state: FSMContext):
    user_id = message.from_user.id
    user_data = await get_user_data(user_id)
    language = user_data[6] if user_data else 'en'
    translations = TRANSLATIONS[language]
    
    wallet_address = message.text.strip()
    username = message.from_user.username
    
    # Basic wallet address validation
    if not wallet_address.startswith('EQ') and not wallet_address.startswith('UQ'):
        await message.answer(translations['invalid_wallet'])
        await notify_admin(f"❌ *Invalid Wallet Attempt:*\n"
                         f"User: @{username}\n"
                         f"ID: `{user_id}`\n"
                         f"Invalid Input: `{wallet_address}`")
        return
    
    # Check if wallet is already registered
    existing_wallet_user = await get_user_by_wallet(wallet_address)
    if existing_wallet_user and existing_wallet_user[0] != user_id:
        await message.answer(translations['wallet_already_registered'])
        await notify_admin(f"⚠️ *Duplicate Wallet Attempt:*\n"
                         f"User: @{username}\n"
                         f"ID: `{user_id}`\n"
                         f"Wallet: `{wallet_address}`\n"
                         f"Already registered to ID: `{existing_wallet_user[0]}`")
        return
    
    # Generate verification memo
    verification_memo = f"verify_{user_id}_{int(time_module.time())}"
    await save_user_data(user_id, username, wallet_address, False, verification_memo)
    
    verification_message = translations['verification_instructions'].format(
        VERIFICATION_WALLET,
        verification_memo
    )
    await message.answer(verification_message, parse_mode="Markdown")
    await state.set_state(UserState.waiting_for_transaction)
    
    # Notify admin about verification attempt
    admin_message = translations['admin_new_verification'].format(
        username,
        user_id,
        wallet_address,
        verification_memo
    )
    await notify_admin(admin_message)

@dp.message(Command('verify'))
async def verify_command(message: types.Message, state: FSMContext):
    user_id = message.from_user.id
    user_data = await get_user_data(user_id)
    
    if not user_data:
        await message.answer(TRANSLATIONS['en']['start_verification'])
        return
        
    language = user_data[6] if user_data else 'en'
    translations = TRANSLATIONS[language]
    
    username = message.from_user.username
    verification_memo = user_data[5]
    wallet_address = user_data[2]
    
    if not verification_memo or not wallet_address:
        await message.answer(translations['no_pending_verification'])
        return
    
    await message.answer(translations['checking_transaction'])
    
    transaction_verified = await check_transaction(VERIFICATION_WALLET, verification_memo)
    
    if not transaction_verified:
        await message.answer(
            translations['transaction_not_found'].format(
                VERIFICATION_WALLET,
                verification_memo
            ),
            parse_mode="Markdown"
        )
        return

    # Check NFT ownership
    has_nft = await check_nft_ownership(wallet_address)
    
    if has_nft:
        # Check token balance
        token_balance = await check_token_balance(wallet_address, SHIVA_TOKEN_ADDRESS)
        shiva_balance = token_balance / 1_000_000_000
        
        # Check NFT royalties
        paid, unpaid, no_info, nft_details = await check_nft_royalties(wallet_address)
        
        # Send verification status
        admin_message = translations['admin_verification_success'].format(
            username,
            user_id,
            wallet_address,
            shiva_balance,
            paid,
            unpaid,
            no_info
        )
        await message.answer(admin_message)
        
        # Send success message
        success_message = translations['success_message']
        if unpaid > 0:
            success_message += translations['royalty_warning']
        success_message += translations['join_group']
        
        # Create keyboard with group link
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text=translations['join_group_button'], url=GROUP_INVITE_LINK)]
        ])
        
        await message.answer(success_message, reply_markup=keyboard)
    else:
        # Send no NFT found message
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text=translations['buy_nft_button'], url=NFT_MARKETPLACE_LINK)]
        ])
        await message.answer(translations['no_nft_found'], reply_markup=keyboard)

# Add a new command to check royalties separately
@dp.message(Command('royalties'))
async def check_royalties_command(message: types.Message):
    user_id = message.from_user.id
    user_data = await get_user_data(user_id)
    
    if not user_data or not user_data[2]:  # Check if user has registered wallet
        await message.answer("❌ Please register your wallet first using /start command.")
        return
    
    wallet_address = user_data[2]
    await message.answer("���� Checking NFT royalty status...")
    
    paid, unpaid, no_info, nft_details = await check_nft_royalties(wallet_address)
    
    royalty_status = (
        "📊 NFT Royalty Status:\n"
        f"✅ NFTs with paid royalties: {paid}\n"
        f"❌ NFTs without royalties: {unpaid}\n"
        f"ℹ️ NFTs with no transfer info: {no_info}\n\n"
        "Detailed NFT Status:\n"
    )
    
    for nft in nft_details:
        if nft["transfer_info"]:
            status = translations['nft_status_paid'] if nft["royalty_paid"] else translations['nft_status_unpaid']
        else:
            status = translations['nft_status_unknown']
        royalty_status += f"NFT #{nft['index']}: {status}\n"
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="NFT Marketplace", url=NFT_MARKETPLACE_LINK)]
    ])
    
    await message.answer(royalty_status, reply_markup=keyboard)
    
@dp.message(Command('search'))
async def search_user(message: types.Message):
    if str(message.from_user.id) not in ADMIN_IDS:
        return
        
    args = message.text.split(maxsplit=1)
    if len(args) < 2:
        await message.answer("❌ Please provide a username to search. Format: /search username")
        return
    
    search_username = args[1].replace('@', '')
    
    conn = sqlite3.connect('members.db')
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM members WHERE username LIKE ?', (f"%{search_username}%",))
    results = cursor.fetchall()
    conn.close()
    
    if not results:
        await message.answer(f"❌ No users found matching username '{search_username}'")
        return
    
    for user in results:
        user_id, username, wallet_address, last_checked, has_nft, verification_memo = user
        if wallet_address:
            current_nft_status = await check_nft_ownership(wallet_address)
            last_checked_str = datetime.fromisoformat(last_checked).strftime("%Y-%m-%d %H:%M:%S") if last_checked else "Never"
            
            report = (
                f"📋 User Information:\n\n"
                f"👤 Username: @{username}\n"
                f"🆔 User ID: {user_id}\n"
                f"💼 Wallet: {wallet_address}\n"
                f"💎 Has NFT: {'Yes ✅' if current_nft_status else 'No ❌'}\n"
                f"🕒 Last Checked: {last_checked_str}\n"
                f"📊 Status Change: {'No' if current_nft_status == has_nft else 'Yes'}"
            )
            
            if current_nft_status != has_nft:
                await save_user_data(user_id, username, wallet_address, current_nft_status)
                report += "\n\n⚠⚠️ Database has been updated with new NFT status"
            
            await message.answer(report)

@dp.message(Command('to_kick'))
async def check_nft_holders(message: types.Message):
    if str(message.from_user.id) not in ADMIN_IDS:
        return
    
    await message.answer("🔍 Checking all wallets for users without NFTs... Please wait.")
    
    conn = sqlite3.connect('members.db')
    cursor = conn.cursor()
    cursor.execute('SELECT user_id, username, wallet_address FROM members WHERE wallet_address IS NOT NULL')
    members = cursor.fetchall()
    conn.close()
    
    no_nft_holders = []
    for user_id, username, wallet_address in members:
        has_nft = await check_nft_ownership(wallet_address)
        if not has_nft:
            no_nft_holders.append({
                'username': username or "Unknown",
                'wallet': wallet_address,
                'user_id': user_id
            })
            await save_user_data(user_id, username, wallet_address, False)
    
    if no_nft_holders:
        report = "🚫 Users to be kicked (no NFTs):\n\n"
        for user in no_nft_holders:
            report += f"• @{user['username']}\n"
            report += f"  Wallet: {user['wallet']}\n"
            report += f"  User ID: {user['user_id']}\n\n"
    else:
        report = "✅ All users currently hold NFTs!"
    
    await message.answer(report)

@dp.message(Command('mem'))
async def list_nft_holders(message: types.Message):
    if str(message.from_user.id) not in ADMIN_IDS:
        return
    
    await message.answer("📋 Fetching current NFT holders... Please wait.")
    
    conn = sqlite3.connect('members.db')
    cursor = conn.cursor()
    cursor.execute('SELECT user_id, username, wallet_address FROM members')
    members = cursor.fetchall()
    conn.close()
    
    nft_holders = []
    for user_id, username, wallet_address in members:
        has_nft = await check_nft_ownership(wallet_address)
        if has_nft:
            nft_holders.append({
                'username': username or "Unknown",
                'wallet': wallet_address,
                'user_id': user_id
            })
    
    if nft_holders:
        report = "💎 Current NFT Holders:\n\n"
        for user in nft_holders:
            report += f"• @{user['username']}\n"
            report += f"  Wallet: {user['wallet']}\n"
            report += f"  User ID: {user['user_id']}\n\n"
    else:
        report = "���� No NFT holders found in database!"
    
    await message.answer(report)

@dp.message(Command('add'))
async def add_members_command(message: types.Message):
    # Check if user is admin
    if str(message.from_user.id) not in ADMIN_IDS:
        return

    # Split the message into lines
    lines = message.text.split('\n')
    if len(lines) == 1:
        await message.answer(
            "❌ Please provide member data in the following format:\n\n"
            "/add\n"
            "Username: @username1\n"
            "Wallet: WALLET_ADDRESS1\n"
            "User ID: USER_ID1\n\n"
            "Username: @username2\n"
            "Wallet: WALLET_ADDRESS2\n"
            "User ID: USER_ID2"
        )
        return

    # Process the input
    members_to_add = []
    current_member = {}
    success_count = 0
    failed_members = []

    for line in lines[1:]:  # Skip the first line (/add command)
        line = line.strip()
        if not line:  # Skip empty lines
            continue

        if ':' in line:
            key, value = [x.strip() for x in line.split(':', 1)]
            
            if 'Username' in key:
                # If we have a complete member entry, add it to the list
                if current_member and len(current_member) == 3:
                    members_to_add.append(current_member)
                    current_member = {}
                value = value.replace('@', '')  # Remove @ from username
                current_member['username'] = value
            elif 'Wallet' in key:
                current_member['wallet'] = value
            elif 'User ID' in key:
                try:
                    current_member['user_id'] = int(value)
                except ValueError:
                    failed_members.append(f"Invalid User ID format: {value}")
                    current_member = {}
                    continue

    # Add the last member if complete
    if current_member and len(current_member) == 3:
        members_to_add.append(current_member)

    # Validate and add members
    formatted_members = []
    for member in members_to_add:
        # Basic wallet address validation
        if not (member['wallet'].startswith('EQ') or member['wallet'].startswith('UQ')):
            failed_members.append(f"Invalid wallet format for @{member['username']}")
            continue
        
        formatted_members.append((
            member['user_id'],
            member['username'],
            member['wallet']
        ))

    # Add valid members to database
    if formatted_members:
        if await bulk_add_members(formatted_members):
            success_count = len(formatted_members)
            
            # Check NFT status for added members
            for user_id, username, wallet in formatted_members:
                has_nft = await check_nft_ownership(wallet)
                await save_user_data(user_id, username, wallet, has_nft)

    # Prepare response message
    response = []
    if success_count > 0:
        response.append(f"✅ Successfully added {success_count} member{'s' if success_count > 1 else ''} to database.")
    if failed_members:
        response.append("\n❌ Failed entries:")
        response.extend(failed_members)
    if not response:
        response.append("❌ No valid members to add.")

    await message.answer('\n'.join(response))

    # Notify other admins
    if success_count > 0:
        admin_message = (
            f"👤 Admin @{message.from_user.username} added {success_count} new member{'s' if success_count > 1 else ''}\n"
            "Added members:"
        )
        for user_id, username, wallet in formatted_members:
            admin_message += f"\n• @{username} (ID: {user_id})"
        
        for admin_id in ADMIN_IDS:
            if str(admin_id) != str(message.from_user.id):  # Don't notify the admin who added
                try:
                    await bot.send_message(admin_id, admin_message)
                except Exception as e:
                    logger.error(f"Failed to notify admin {admin_id}: {e}")

@dp.message(Command("group_info"))
async def get_group_info(message: Message):
    try:
        # Get chat information
        chat = await bot.get_chat(GROUP_ID)
        members_count = await bot.get_chat_member_count(GROUP_ID)
        
        info_text = (
            f"📊 Group Information:\n"
            f"Name: {chat.title}\n"
            f"ID: {chat.id}\n"
            f"Type: {chat.type}\n"
            f"Members: {members_count}\n"
        )
        
        if chat.description:
            info_text += f"Description: {chat.description}\n"
            
        await message.reply(info_text)
    except Exception as e:
        await message.reply(f"Error getting group info: {str(e)}")

@dp.message(Command("members"))
async def get_members(message: Message):
    try:
        # Get chat information first
        chat_info = await bot.get_chat(GROUP_ID)
        
        # Get administrators (owner and admins)
        admins = await bot.get_chat_administrators(GROUP_ID)
        
        # Format member information
        members_info = ["👥 Group Members:\n"]
        
        # Add administrators first
        members_info.append("👑 Administrators:")
        for admin in admins:
            user = admin.user
            member_info = f"• {user.full_name} (ID: {user.id})"
            if user.username:
                member_info += f" @{user.username}"
            if isinstance(admin, ChatMemberOwner):
                member_info += " (Owner)"
            elif isinstance(admin, ChatMemberAdministrator):
                member_info += " (Admin)"
            members_info.append(member_info)
        
        # Get total member count
        member_count = await bot.get_chat_member_count(GROUP_ID)
        members_info.append(f"\n📊 Total members: {member_count}")
        
        # Note about regular members
        members_info.append("\nNote: Due to Telegram API limitations, only administrators can be listed individually.")
        
        # Send the formatted message
        await message.reply("\n".join(members_info))
        
    except Exception as e:
        await message.reply(f"Error getting members: {str(e)}")

@dp.message(Command("kick"))
async def kick_member(message: Message):
    try:
        # Extract user ID from command
        command_parts = message.text.split()
        if len(command_parts) != 2:
            await message.reply("Please provide a user ID: /kick user_id")
            return
        
        user_id = int(command_parts[1])
        
        # Check if sender has admin rights
        sender = await bot.get_chat_member(GROUP_ID, message.from_user.id)
        if sender.status not in ["creator", "administrator"]:
            await message.reply("You don't have permission to kick members.")
            return
        
        # Kick (ban) the user
        await bot.ban_chat_member(GROUP_ID, user_id)
        await message.reply(f"User {user_id} has been kicked from the group.")
    except Exception as e:
        await message.reply(f"Error kicking member: {str(e)}")

@dp.message(Command("sendMessage"))
async def send_group_message(message: Message):
    try:
        # Extract message content after the command
        content = message.text.replace("/sendMessage", "", 1).strip()
        if not content:
            await message.reply("Please provide a message to send: /sendMessage your text here")
            return
        
        # Check if there's any media attached
        if message.reply_to_message and message.reply_to_message.media_group_id:
            # Handle media group
            media_group = []
            if message.reply_to_message.photo:
                media_group.append(types.InputMediaPhoto(
                    media=message.reply_to_message.photo[-1].file_id,
                    caption=content if not media_group else None
                ))
            # Add more media types as needed
            
            await bot.send_media_group(GROUP_ID, media_group)
        elif message.reply_to_message and message.reply_to_message.photo:
            # Handle single photo
            await bot.send_photo(
                GROUP_ID,
                photo=message.reply_to_message.photo[-1].file_id,
                caption=content
            )
        else:
            # Send text only
            await bot.send_message(GROUP_ID, content)
            
        await message.reply("Message sent successfully!")
    except Exception as e:
        await message.reply(f"Error sending message: {str(e)}")

# Add the token balance check function
async def check_token_balance(user_address: str, jetton_master_address: str) -> int:
    API_BASE_URL = "https://tonapi.io/v2"
    
    async with aiohttp.ClientSession() as session:
        try:
            url = f"{API_BASE_URL}/accounts/{user_address}/jettons/{jetton_master_address}"
            params = {
                "currencies": "shiva"
            }
            headers = {
                "accept": "application/json",
                "Authorization": f"Bearer {TONAPI_KEY}"
            }
            
            async with session.get(url, params=params, headers=headers) as response:
                if response.status != 200:
                    logger.error(f"API request failed with status {response.status}")
                    return 0
                
                data = await response.json()
                balance = int(data.get("balance", "0"))
                logger.info(f"$SHIVA balance for user address {user_address}: {balance}")
                return balance
                
        except Exception as e:
            logger.error(f"Error checking token balance: {str(e)}")
            logger.error(f"Error type: {type(e)}")
            logger.error("Error traceback: ", exc_info=True)
            return 0

# Main function
async def main():
    print("Starting NFT Checker Bot...")
    setup_database()
    
    try:
        await dp.start_polling(bot)
    except Exception as e:
        logger.error(f"Error: {e}")
    finally:
        await bot.session.close()

if __name__ == '__main__':
    asyncio.run(main())

async def get_user_language(user_id: int) -> str:
    user_data = await get_user_data(user_id)
    return user_data[6] if user_data and len(user_data) > 6 else 'en'

# Add middleware to check for language selection
class LanguageMiddleware:
    async def __call__(self, handler, event, data):
        if isinstance(event, Message):
            user_id = event.from_user.id
            user_data = await get_user_data(user_id)
            
            # Allow only /start command and language selection if no language is set
            if (not user_data or 'language' not in user_data) and \
               event.text not in ['/start', '🇬🇧 English', '🇷🇺 Русский']:
                await event.answer(
                    "🌐 Please start the bot and select your language first:\n"
                    "🌐 Пожалуйста, запустите бота и выберите язык сначала:\n"
                    "/start"
                )
                return
        
        return await handler(event, data)

# Add the middleware to the dispatcher
dp.message.middleware(LanguageMiddleware())