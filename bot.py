import asyncio
import aiohttp
import base64
import requests
from typing import Tuple, List, Dict
import time as time_module
from datetime import datetime
from aiogram import Bot, Dispatcher, types
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove
from aiogram.filters import Command
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import Message
import sqlite3
import logging

# At the top of the file
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Basic Configuration
API_TOKEN = '8067666224:AAELEOrjl0lHDUsqP7NUFU8FTYuzRt972ik'
NFT_COLLECTION_ADDRESS = 'EQDmUOKwwa6KU0YFbA_CZTGccRdh5SWIQdBDKg741ecOqzR0'
GROUP_INVITE_LINK = "https://t.me/+X44w-gPPj3AzYWU0"
NFT_MARKETPLACE_LINK = "https://getgems.io/collection/EQDmUOKwwa6KU0YFbA_CZTGccRdh5SWIQdBDKg741ecOqzR0"
SHIVA_DEX_LINK = "https://dedust.io/swap/EQDQoc5M3Bh8eWFephi9bClhevelbZZvW-vKTDbxB8pbwNDN"
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
        ),
        'whale_welcome': (
            "🐳 Welcome to the $SHIVA whales bot!\n"
            "To get access to the whale chat, you must have at least 10,000,000 $SHIVA.\n\n"
            "After verification, you will receive an invite to the closed chat.\n\n"
            f"CA: `{SHIVA_TOKEN_ADDRESS}`"
        ),
        'whale_verification_success': "🎉 Congratulations! Your wallet has been verified and you have enough $SHIVA tokens. Welcome to the Whale Club!",
        'whale_verification_failed': "❌ Sorry, you don't have enough $SHIVA tokens to join the Whale Club. You need at least 10,000,000 $SHIVA.",
        'whale_checking_balance': "🔍 Checking your $SHIVA balance...",
        'stats_title': "📊 *Community Statistics*",
        'stats_verified_users': "✅ Verified Users: {}",
        'stats_total_whales': "🐳 Total Whales: {}",
        'stats_total_shiva': "💰 Total $SHIVA: {:,.2f}",
        'stats_average_shiva': "📈 Average $SHIVA/member: {:,.2f}",
        'stats_nft_stats': "🖼 NFT Statistics:",
        'stats_paid_royalties': "  ✓ Paid Royalties: {}",
        'stats_unpaid_royalties': "  ✗ Unpaid Royalties: {}",
        'stats_unknown_royalties': "  • Unknown Status: {}",
        'stats_error': "❌ Error fetching statistics. Please try again later.",
        'stats_loading': "🔄 Calculating community statistics...",
        'price_title': "💎 *SHIVA Price Information*",
        'price_loading': "🔄 Fetching current SHIVA price...",
        'price_current': "💰 Current Price: {} TON",
        'price_error': "❌ Error fetching price data. Please try again later.",
        'top_title': "🏆 *Top SHIVA Holders*",
        'top_loading': "🔄 Calculating top holders...",
        'top_holder_format': "#{} 👤 `{}...{}` - {:,.2f} SHIVA",
        'top_error': "❌ Error fetching top holders. Please try again later.",
        'no_holders': "No SHIVA holders found in the database.",
        'buy_nft_title': "🖼 *Buy SHIVA NFT*",
        'buy_nft_description': "You can buy SHIVA NFT on GetGems marketplace. Click the button below to view the collection:",
        'buy_shiva_title': "💎 *Buy SHIVA Tokens*",
        'buy_shiva_description': "You can buy SHIVA tokens on DeDust.io. Click the button below to open the swap page:",
        'buy_shiva_button': "Buy SHIVA",
        'wallet_saved': "✅ Wallet saved successfully!",
        'wallet_invalid': "❌ Invalid wallet address. Please make sure it starts with 'EQ' or 'UQ'.",
        'admin_new_wallet': "💼 *New Wallet Added*\nUser: @{}\nID: `{}`\nWallet: `{}`",
        'admin_wallet_verified': "✅ *New Wallet Verified:*\nUser: @{}\nID: `{}`\nWallet: `{}`\nNFT Status: ✅ Has NFT\nSHIVA Balance: {:,.2f}",
        'admin_wallet_unverified': "❌ *Unverified Wallet:*\nUser: @{}\nID: `{}`\nWallet: `{}`\nNFT Status: ❌ No NFT\nSHIVA Balance: {:,.2f}",
        'checking_wallet': "🔍 Checking your wallet...",
        'help_title': "📚 *Available Commands*",
        'help_description': "Here are all the available commands:",
        'help_commands': """
🔷 *Basic Commands*
/start - Start the bot and select language
/wallet - Submit or update your wallet address
/verify - Start verification process for group access

🏦 *Token Commands*
/price - Show current SHIVA price
/buy - Get link to buy SHIVA tokens
/buy_nft - Get link to buy SHIVA NFT
/top - Show top 10 SHIVA holders

📊 *Statistics*
/stats - Show community statistics

❓ *Help*
/help - Show this help message
""",
    },
    'ru': {
        'select_language': "🌐 Пожалуйста, выберите язык:",
        'username_required': (
            "❌ Прежде чем использовать этого бота, вам нужно установить имя пользователя в Telegram.\n\n"
            "Чтобы установить имя пользователя:\n"
            "1. Перейдите в настройки Telegram\n"
            "2. Нажмите на свой профиль\n"
            "3. Нажмите 'Имя пользователя'\n"
            "4. Установите имя пользователя\n\n"
            "После установки имени пользователя вернитесь и снова используйте команду /start."
        ),
        'welcome_message': (
            "👋 Это Борис.\nДобро пожаловать {}@{}!\n\n"
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
        'checking_transaction': "🔍 Проверяю вашу транзакцию...",
        'transaction_not_found': (
            "❌ Транзакция не найдена. Пожалуйста, убедитесь, что вы:\n\n"
            "1. Отправили 0.01 TON на:\n"
            "`{0}`\n\n"
            "2. Включили это сообщение:\n"
            "`{1}`\n\n"
            "Попробуйте снова с командой /verify после отправки транзакции."
        ),
        'transaction_verified': "✅ Транзакция подтверждена! Теперь проверяю владение NFT...",
        'checking_royalties': "🔍 Проверяю статус роялти NFT...",
        'royalty_status': (
            "📊 Статус роялти NFT:\n"
            "✅ NFT с оплаченными роялти: {}\n"
            "❌ NFT без роялти: {}\n"
            "ℹ️ NFT без информации о переводе: {}\n\n"
            "Подробный статус NFT:\n"
        ),
        'nft_status_paid': "✅ Роялти оплачено",
        'nft_status_unpaid': "❌ Роялти не оплачено",
        'nft_status_unknown': "ℹ️ Нет информации о переводе",
        'success_message': "🎉 Поздравляем! Ваш кошелек подтвержден и владение NFT tonfans подтверждено.",
        'royalty_warning': "\n⚠️ Некоторые из ваших NFT имеют неоплаченные роялти. Пожалуйста, рассмотрите возможность их оплаты для поддержки проекта.",
        'join_group': "\nТеперь вы можете присоединиться к нашей эксклюзивной группе:",
        'no_nft_found': (
            "✅ Кошелек подтвержден, но NFT не найден в вашем кошельке.\n"
            "Чтобы присоединиться к нашей группе, вам нужно владеть хотя бы одним NFT из нашей коллекции.\n"
            "Вы можете получить его здесь:"
        ),
        'join_group_button': "Присоединиться к группе",
        'buy_nft_button': "Купить NFT",
        'nft_marketplace_button': "NFT Маркетплейс",
        'token_balance': "Ваш баланс $SHIVA: {:,.2f}",
        'no_token_balance': "У вас нет токенов $SHIVA в кошельке.",
        'start_verification': "Пожалуйста, сначала начните процесс верификации, используя команду /start.",
        'no_pending_verification': "Не найдено неотправленных запросов на верификацию. Пожалуйста, начните снова, используя команду /start.",
        'admin_new_verification': (
            "🆕 *Новый запрос на верификацию:*\n"
            "Пользователь: @{}\n"
            "ID: `{}`\n"
            "Кошелек: `{}`\n"
            "Memo: `{}`"
        ),
        'admin_verification_success': (
            "✅ Верификация NFT успешна:\n"
            "Пользователь: @{}\n"
            "ID: {}\n"
            "Кошелек: {}\n"
            "Баланс $SHIVA: {:.2f}\n"
            "Статус роялти: {} оплачено, {} не оплачено, {} неизвестно"
        ),
        'admin_no_nft': (
            "❌ *NFT не найден:*\n"
            "Пользователь: @{}\n"
            "ID: `{}`\n"
            "Кошелек: `{}`"
        ),
        'whale_welcome': (
            "🐳 Добро пожаловать в бот $SHIVA для китов!\n"
            "Для доступа в чат китов вам необходимо иметь минимум 10,000,000 $SHIVA.\n\n"
            "После верификации вы получите приглашение в закрытый чат.\n\n"
            f"CA: `{SHIVA_TOKEN_ADDRESS}`"
        ),
        'whale_verification_success': "🎉 Поздравляем! Ваш кошелек подтвержден и у вас достаточно токенов $SHIVA. Добро пожаловать в Клуб Китов!",
        'whale_verification_failed': "❌ Извините, у вас недостаточно токенов $SHIVA для вступления в Клуб Китов. Необходимо минимум 10,000,000 $SHIVA.",
        'whale_checking_balance': "🔍 Проверяю ваш баланс $SHIVA...",
        'stats_title': "📊 *Статистика сообщества*",
        'stats_verified_users': "✅ Проверенных пользователей: {}",
        'stats_total_whales': "🐳 Всего китов: {}",
        'stats_total_shiva': "💰 Всего $SHIVA: {:,.2f}",
        'stats_average_shiva': "📈 Среднее $SHIVA/участник: {:,.2f}",
        'stats_nft_stats': "🖼 Статистика NFT:",
        'stats_paid_royalties': "  ✓ Оплаченные роялти: {}",
        'stats_unpaid_royalties': "  ✗ Неоплаченные роялти: {}",
        'stats_unknown_royalties': "  • Неизвестный статус: {}",
        'stats_error': "❌ Ошибка при получении статистики. Пожалуйста, попробуйте позже.",
        'stats_loading': "🔄 Подсчитываю статистику сообщества...",
        'price_title': "💎 *Информация о цене SHIVA*",
        'price_loading': "🔄 Получаю текущую цену SHIVA...",
        'price_current': "💰 Текущая цена: {} TON",
        'price_error': "❌ Ошибка при получении данных о цене. Пожалуйста, попробуйте позже.",
        'top_title': "🏆 *Топ держателей SHIVA*",
        'top_loading': "🔄 Подсчитываю топ держателей...",
        'top_holder_format': "#{} 👤 `{}...{}` - {:,.2f} SHIVA",
        'top_error': "❌ Ошибка при получении топ держателей. Пожалуйста, попробуйте позже.",
        'no_holders': "Держатели SHIVA не найдены в базе данных.",
        'buy_nft_title': "🖼 *Купить SHIVA NFT*",
        'buy_nft_description': "Вы можете купить SHIVA NFT на маркетплейсе GetGems. Нажмите кнопку ниже, чтобы посмотреть коллекцию:",
        'buy_shiva_title': "💎 *Купить токены SHIVA*",
        'buy_shiva_description': "Вы можете купить токены SHIVA на DeDust.io. Нажмите кнопку ниже, чтобы открыть страницу обмена:",
        'buy_shiva_button': "Купить SHIVA",
        'wallet_saved': "✅ Кошелек успешно сохранен!",
        'wallet_invalid': "❌ Неверный адрес кошелька. Убедитесь, что он начинается с 'EQ' или 'UQ'.",
        'admin_new_wallet': "💼 *Добавлен новый кошелек*\nПользователь: @{}\nID: `{}`\nКошелек: `{}`",
        'admin_wallet_verified': "✅ *Новый верифицированный кошелек:*\nПользователь: @{}\nID: `{}`\nКошелек: `{}`\nСтатус NFT: ✅ Есть NFT\nБаланс SHIVA: {:,.2f}",
        'admin_wallet_unverified': "❌ *Неверифицированный кошелек:*\nПользователь: @{}\nID: `{}`\nКошелек: `{}`\nСтатус NFT: ❌ Нет NFT\nБаланс SHIVA: {:,.2f}",
        'checking_wallet': "🔍 Проверяю ваш кошелек...",
        'help_title': "📚 *Доступные команды*",
        'help_description': "Вот все доступные команды:",
        'help_commands': """
🔷 *Основные команды*
/start - Запустить бота и выбрать язык
/wallet - Отправить или обновить адрес кошелька
/verify - Начать процесс верификации для доступа к группе

🏦 *Команды токенов*
/price - Показать текущую цену SHIVA
/buy - Получить ссылку для покупки токенов SHIVA
/buy_nft - Получить ссылку для покупки NFT SHIVA
/top - Показать топ-10 держателей SHIVA

📊 *Статистика*
/stats - Показать статистику сообщества

❓ *Помощь*
/help - Показать это сообщение помощи
""",
    }
}

def setup_database():
    conn = sqlite3.connect('members.db')
    cursor = conn.cursor()
    
    # Create table with language column having a NOT NULL constraint
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS members (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            wallet_address TEXT,
            last_checked TIMESTAMP,
            has_nft BOOLEAN,
            verification_memo TEXT,
            language TEXT NOT NULL DEFAULT 'en'
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
    logger.info(f"Saving language {language} for user {user_id}")
    conn = sqlite3.connect('members.db')
    cursor = conn.cursor()
    cursor.execute('''
        UPDATE members 
        SET language = ?
        WHERE user_id = ?
    ''', (language, user_id))
    conn.commit()
    conn.close()
    logger.info(f"Language saved successfully for user {user_id}")

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
    API_BASE_URL = "https://toncenter.com/api/v3"
    
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

async def check_token_balance(user_address: str, jetton_master_address: str) -> Tuple[int, float]:
    """
    Check SHIVA token balance for a given wallet address.
    Returns both raw balance and formatted balance.
    """
    try:
        async with aiohttp.ClientSession() as session:
            url = f"https://tonapi.io/v2/accounts/{user_address}/jettons/{jetton_master_address}"
            params = {
                "currencies": "ton,usd"
            }
            headers = {
                "accept": "application/json",
                "Authorization": f"Bearer {TONAPI_KEY}"
            }
            
            async with session.get(url, params=params, headers=headers) as response:
                if response.status != 200:
                    logger.error(f"API request failed with status {response.status}")
                    return 0, 0.0
                
                data = await response.json()
                balance = data.get("balance", "0")
                
                try:
                    raw_balance = int(balance)
                    formatted_balance = raw_balance / 1e9  # Convert to actual SHIVA tokens
                    logger.info(f"$SHIVA balance for address {user_address}: {formatted_balance:,.2f}")
                    return raw_balance, formatted_balance
                except (ValueError, TypeError) as e:
                    logger.error(f"Error converting balance to integer: {str(e)}")
                    return 0, 0.0
                
    except Exception as e:
        logger.error(f"Error checking token balance: {str(e)}")
        logger.error(f"Error type: {type(e)}")
        logger.error("Error traceback: ", exc_info=True)
        return 0, 0.0

async def check_nft_royalties(wallet_address: str):
    """
    Check royalty payment status for NFTs in a wallet.
    Returns: (paid_royalties, unpaid_royalties, no_transfer_info, nft_details)
    """
    nft_details = []
    paid_royalties = 0
    unpaid_royalties = 0
    no_transfer_info = 0

    try:
        async with aiohttp.ClientSession() as session:
            url = f"https://tonapi.io/v2/accounts/{wallet_address}/nfts"
            headers = {
                "Authorization": f"Bearer {TONAPI_KEY}"
            }
            async with session.get(url, headers=headers) as response:
                if response.status != 200:
                    logger.error(f"API request failed with status {response.status}")
                    return 0, 0, 0, []

                data = await response.json()
                nfts = data.get("nfts", [])

                for nft in nfts:
                    if nft.get("collection", {}).get("address") != NFT_COLLECTION_ADDRESS:
                        continue

                    nft_status = {
                        "name": nft.get("metadata", {}).get("name", "Unknown NFT"),
                        "status": "unknown"
                    }

                    try:
                        # Check transfer history
                        transfer_url = f"https://tonapi.io/v2/nfts/{nft['address']}/transfers"
                        async with session.get(transfer_url, headers=headers) as transfer_response:
                            if transfer_response.status != 200:
                                no_transfer_info += 1
                                nft_status["status"] = "unknown"
                            else:
                                # Check if royalty was paid in the last transfer
                                transfer_data = await transfer_response.json()
                                transfers = transfer_data.get("transfers", [])

                                if not transfers:
                                    no_transfer_info += 1
                                    nft_status["status"] = "unknown"
                                else:
                                    last_transfer = transfers[0]
                                    if last_transfer.get("royalty_paid", False):
                                        paid_royalties += 1
                                        nft_status["status"] = "paid"
                                    else:
                                        unpaid_royalties += 1
                                        nft_status["status"] = "unpaid"

                    except Exception as e:
                        logger.error(f"Error checking transfer history: {str(e)}")
                        no_transfer_info += 1
                        nft_status["status"] = "unknown"

                    nft_details.append(nft_status)

    except Exception as e:
        logger.error(f"Error in check_nft_royalties: {str(e)}")
        return 0, 0, 0, []

    return paid_royalties, unpaid_royalties, no_transfer_info, nft_details

async def get_community_nft_stats():
    """Get NFT royalty statistics for all community members."""
    try:
        conn = sqlite3.connect('members.db')
        cursor = conn.cursor()
        cursor.execute('SELECT wallet_address FROM members WHERE wallet_address IS NOT NULL')
        wallets = [row[0] for row in cursor.fetchall()]
        conn.close()

        total_paid = 0
        total_unpaid = 0
        total_unknown = 0

        for wallet in wallets:
            paid, unpaid, unknown, _ = await check_nft_royalties(wallet)
            total_paid += paid
            total_unpaid += unpaid
            total_unknown += unknown

        return total_paid, total_unpaid, total_unknown
    except Exception as e:
        logger.error(f"Error getting community NFT stats: {e}")
        return 0, 0, 0

async def get_community_shiva_stats():
    """Get SHIVA token statistics for all community members."""
    try:
        conn = sqlite3.connect('members.db')
        cursor = conn.cursor()
        cursor.execute('SELECT wallet_address FROM members WHERE wallet_address IS NOT NULL')
        wallets = [row[0] for row in cursor.fetchall()]
        conn.close()

        total_shiva = 0
        whale_count = 0

        for wallet in wallets:
            raw_balance, formatted_balance = await check_token_balance(wallet, SHIVA_TOKEN_ADDRESS)
            total_shiva += formatted_balance
            if formatted_balance >= 10_000_000:
                whale_count += 1

        return total_shiva, whale_count, len(wallets)
    except Exception as e:
        logger.error(f"Error getting community SHIVA stats: {e}")
        return 0, 0, 0

async def get_shiva_price() -> float:
    """Get current SHIVA price in TON from DEX."""
    API_BASE_URL = "https://toncenter.com/api/v3"
    
    async with aiohttp.ClientSession() as session:
        try:
            # Get price from DEX pool
            headers = {"Authorization": f"Bearer {TON_API_KEY}"}
            async with session.get(
                f"{API_BASE_URL}/jetton/{SHIVA_TOKEN_ADDRESS}/price",
                headers=headers
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    return float(data['price'])
                else:
                    logger.error(f"Error fetching SHIVA price: {response.status}")
                    return None
        except Exception as e:
            logger.error(f"Error in get_shiva_price: {e}")
            return None

async def get_top_holders(limit: int = 10) -> List[Tuple[str, float]]:
    """Get top SHIVA token holders."""
    try:
        conn = sqlite3.connect('members.db')
        cursor = conn.cursor()
        cursor.execute('SELECT wallet_address FROM members WHERE wallet_address IS NOT NULL')
        wallets = [row[0] for row in cursor.fetchall()]
        conn.close()

        # Get balances for all wallets
        holders = []
        for wallet in wallets:
            raw_balance, formatted_balance = await check_token_balance(wallet, SHIVA_TOKEN_ADDRESS)
            if formatted_balance > 0:
                holders.append((wallet, formatted_balance))

        # Sort by balance and get top holders
        holders.sort(key=lambda x: x[1], reverse=True)
        return holders[:limit]
    except Exception as e:
        logger.error(f"Error getting top holders: {e}")
        return []

# Add middleware to check for language selection
class LanguageMiddleware:
    async def __call__(self, handler, event, data):
        if isinstance(event, Message):
            user_id = event.from_user.id
            
            # Skip middleware for these commands/messages
            allowed_messages = ['/start', '🇬🇧 English', '🇷🇺 Русский']
            if event.text in allowed_messages:
                return await handler(event, data)
            
            # Get current state
            state = data.get('state')
            if state and await state.get_state() == UserState.selecting_language:
                return await handler(event, data)
            
            # Check database for language
            conn = sqlite3.connect('members.db')
            cursor = conn.cursor()
            cursor.execute('SELECT language FROM members WHERE user_id = ?', (user_id,))
            result = cursor.fetchone()
            conn.close()
            
            if not result:
                await event.answer(
                    "🌐 Please start the bot and select your language first:\n"
                    "🌐 Пожалуйста, запустите бота и выберите язык сначала:\n"
                    "/start"
                )
                return
            
        return await handler(event, data)

# Add the middleware to the dispatcher
dp.message.middleware(LanguageMiddleware())

async def get_user_language(user_id: int) -> str:
    user_data = await get_user_data(user_id)
    return user_data[6] if user_data and len(user_data) > 6 else 'en'

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
    username = message.from_user.username
    
    # Save initial user data with language
    conn = sqlite3.connect('members.db')
    cursor = conn.cursor()
    cursor.execute('''
        INSERT OR REPLACE INTO members 
        (user_id, username, language)
        VALUES (?, ?, ?)
    ''', (user_id, username, language))
    conn.commit()
    conn.close()
    
    translations = TRANSLATIONS[language]
    
    # Remove keyboard and send welcome message
    await message.answer(
        translations['welcome_message'].format(
            'back ' if await get_user_data(user_id) else '',
            username
        ),
        reply_markup=ReplyKeyboardRemove()
    )
    
    # Store language in state for backup
    await state.update_data(language=language)
    await state.set_state(UserState.waiting_for_wallet)

# Updated wallet submission handler
@dp.message(UserState.waiting_for_wallet)
async def handle_wallet_input(message: types.Message, state: FSMContext):
    user_id = message.from_user.id
    username = message.from_user.username
    
    # Get user's language
    conn = sqlite3.connect('members.db')
    cursor = conn.cursor()
    cursor.execute('SELECT language FROM members WHERE user_id = ?', (user_id,))
    result = cursor.fetchone()
    conn.close()
    
    language = result[0] if result else 'en'
    translations = TRANSLATIONS[language]
    
    wallet_address = message.text.strip()
    
    # Basic wallet address validation
    if not wallet_address.startswith('EQ') and not wallet_address.startswith('UQ'):
        await message.answer(translations['invalid_wallet'])
        return
    
    # Generate verification memo
    verification_memo = f"verify_{user_id}_{int(time_module.time())}"
    
    # Save wallet address
    await save_user_data(user_id, username, wallet_address, False, verification_memo)
    
    # Notify admin about new verification attempt
    admin_message = translations['admin_new_verification'].format(
        username,
        user_id,
        wallet_address,
        verification_memo
    )
    await notify_admin(admin_message)
    
    # Send verification instructions
    await message.answer(
        translations['verification_instructions'].format(
            VERIFICATION_WALLET,
            verification_memo
        ),
        parse_mode="Markdown"
    )
    
    await state.set_state(UserState.waiting_for_transaction)

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

    await message.answer(translations['transaction_verified'])

    # Check NFT ownership
    has_nft = await check_nft_ownership(wallet_address)
    
    if has_nft:
        # Check token balance
        raw_balance, formatted_balance = await check_token_balance(wallet_address, SHIVA_TOKEN_ADDRESS)
        
        # Show SHIVA balance
        balance_message = f"Your $SHIVA balance: {formatted_balance:,.2f}"
        await message.answer(balance_message)
        
        # Check NFT royalties
        await message.answer(translations['checking_royalties'])
        paid, unpaid, no_info, nft_details = await check_nft_royalties(wallet_address)
        
        # Send verification status
        admin_message = translations['admin_verification_success'].format(
            username,
            user_id,
            wallet_address,
            formatted_balance,
            paid,
            unpaid,
            no_info
        )
        await notify_admin(admin_message)
        
        # Format royalty status message
        royalty_message = translations['royalty_status'].format(paid, unpaid, no_info)
        
        for nft in nft_details:
            status_key = f"nft_status_{nft['status']}"
            royalty_message += f"\n{nft['name']}: {translations[status_key]}"
        
        await message.answer(royalty_message)
        await message.answer(translations['success_message'])
        
        if unpaid > 0:
            await message.answer(translations['royalty_warning'])
        
        # Create keyboard with group invite
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text=translations['join_group_button'], url=GROUP_INVITE_LINK)]
        ])
        await message.answer(translations['join_group'], reply_markup=keyboard)
        
        # Save verified status
        await save_user_data(user_id, username, wallet_address, True)
    else:
        # Create keyboard for NFT marketplace
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text=translations['buy_nft_button'], url=NFT_MARKETPLACE_LINK)]
        ])
        await message.answer(translations['no_nft_found'], reply_markup=keyboard)
        
        # Notify admins
        admin_message = translations['admin_no_nft'].format(
            username,
            user_id,
            wallet_address
        )
        await notify_admin(admin_message)
        
        # Save unverified status
        await save_user_data(user_id, username, wallet_address, False)

@dp.message(Command("whale"))
async def whale_command(message: types.Message, state: FSMContext):
    user_id = message.from_user.id
    user_data = await get_user_data(user_id)
    user_language = await get_user_language(user_id)
    username = message.from_user.username
    
    if not user_data or not user_data[2]:  # Check if user exists and has wallet
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="Start Verification", callback_data="verify")]
        ])
        await message.reply(TRANSLATIONS[user_language]['start_verification'])
        return

    wallet_address = user_data[2]
    await message.reply(TRANSLATIONS[user_language]['whale_checking_balance'])
    
    # Check SHIVA token balance
    raw_balance, formatted_balance = await check_token_balance(wallet_address, SHIVA_TOKEN_ADDRESS)
    
    # Show current balance regardless of whale status
    balance_message = TRANSLATIONS[user_language]['token_balance'].format(formatted_balance)
    await message.reply(balance_message)
    
    if formatted_balance >= 10_000_000:  # 10M SHIVA threshold
        # Create invite link for whale group
        invite_link = "https://t.me/+X44w-gPPj3AzYWU0"  # Replace with actual whale group invite link
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="Join Whale Club 🐳", url=invite_link)]
        ])
        await message.reply(
            TRANSLATIONS[user_language]['whale_verification_success'],
            reply_markup=keyboard
        )
        
        # Notify admins about new whale
        admin_message = (
            "🐳 *New Whale Verified!*\n"
            f"User: @{username}\n"
            f"ID: `{user_id}`\n"
            f"Wallet: `{wallet_address}`\n"
            f"$SHIVA Balance: {formatted_balance:,.2f}"
        )
        await notify_admin(admin_message)
    else:
        # Calculate how many more SHIVA needed
        shiva_needed = 10_000_000 - formatted_balance
        message_text = (
            f"{TRANSLATIONS[user_language]['whale_verification_failed']}\n"
            f"You need {shiva_needed:,.2f} more $SHIVA to qualify."
        )
        await message.reply(message_text)
        
        # Notify admins about failed whale verification
        admin_message = (
            "❌ *Failed Whale Verification:*\n"
            f"User: @{username}\n"
            f"ID: `{user_id}`\n"
            f"Wallet: `{wallet_address}`\n"
            f"Current Balance: {formatted_balance:,.2f}\n"
            f"Needed: {shiva_needed:,.2f} more"
        )
        await notify_admin(admin_message)

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

@dp.message(Command("stats"))
async def stats_command(message: Message):
    user_language = await get_user_language(message.from_user.id)
    translations = TRANSLATIONS[user_language]
    
    # Show loading message
    loading_msg = await message.answer(translations['stats_loading'])
    
    try:
        # Get SHIVA statistics
        total_shiva, whale_count, total_users = await get_community_shiva_stats()
        average_shiva = total_shiva / total_users if total_users > 0 else 0
        
        # Get NFT royalty statistics
        paid_royalties, unpaid_royalties, unknown_royalties = await get_community_nft_stats()
        
        # Format the statistics message
        stats_message = (
            f"{translations['stats_title']}\n\n"
            f"{translations['stats_verified_users'].format(total_users)}\n"
            f"{translations['stats_total_whales'].format(whale_count)}\n"
            f"{translations['stats_total_shiva'].format(total_shiva)}\n"
            f"{translations['stats_average_shiva'].format(average_shiva)}\n\n"
            f"{translations['stats_nft_stats']}\n"
            f"{translations['stats_paid_royalties'].format(paid_royalties)}\n"
            f"{translations['stats_unpaid_royalties'].format(unpaid_royalties)}\n"
            f"{translations['stats_unknown_royalties'].format(unknown_royalties)}"
        )
        
        # Update the loading message with the stats
        await loading_msg.edit_text(stats_message, parse_mode="Markdown")
        
        # Log the statistics check
        logger.info(f"Statistics checked by user {message.from_user.username} (ID: {message.from_user.id})")
        
    except Exception as e:
        logger.error(f"Error in stats command: {e}")
        await loading_msg.edit_text(translations['stats_error'])

@dp.message(Command("price"))
async def price_command(message: Message):
    """Show current SHIVA price information."""
    user_language = await get_user_language(message.from_user.id)
    translations = TRANSLATIONS[user_language]
    
    # Show loading message
    loading_msg = await message.answer(translations['price_loading'])
    
    try:
        # Get current price
        price = await get_shiva_price()
        
        if price is not None:
            # Format the price message
            price_message = (
                f"{translations['price_title']}\n\n"
                f"{translations['price_current'].format(price)}"
            )
            
            # Update the loading message with the price info
            await loading_msg.edit_text(price_message, parse_mode="Markdown")
        else:
            await loading_msg.edit_text(translations['price_error'])
            
    except Exception as e:
        logger.error(f"Error in price command: {e}")
        await loading_msg.edit_text(translations['price_error'])

@dp.message(Command("top"))
async def top_command(message: Message):
    """Show top SHIVA token holders."""
    user_language = await get_user_language(message.from_user.id)
    translations = TRANSLATIONS[user_language]
    
    # Show loading message
    loading_msg = await message.answer(translations['top_loading'])
    
    try:
        # Get top holders
        top_holders = await get_top_holders(10)
        
        if top_holders:
            # Format the top holders message
            message_lines = [translations['top_title'], ""]
            
            for i, (wallet, balance) in enumerate(top_holders, 1):
                # Show first 6 and last 4 characters of wallet address
                shortened_wallet = f"{wallet[:6]}...{wallet[-4:]}"
                message_lines.append(
                    translations['top_holder_format'].format(
                        i, wallet[:6], wallet[-4:], balance
                    )
                )
            
            # Update the loading message with the top holders info
            await loading_msg.edit_text(
                "\n".join(message_lines),
                parse_mode="Markdown"
            )
        else:
            await loading_msg.edit_text(translations['no_holders'])
            
    except Exception as e:
        logger.error(f"Error in top command: {e}")
        await loading_msg.edit_text(translations['top_error'])

@dp.message(Command("buy"))
async def buy_command(message: Message):
    """Show information about buying SHIVA tokens."""
    user_language = await get_user_language(message.from_user.id)
    translations = TRANSLATIONS[user_language]
    
    # Create buy button
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=translations['buy_shiva_button'], url=SHIVA_DEX_LINK)]
    ])
    
    # Format message
    message_text = (
        f"{translations['buy_shiva_title']}\n\n"
        f"{translations['buy_shiva_description']}"
    )
    
    await message.answer(
        message_text,
        reply_markup=keyboard,
        parse_mode="Markdown"
    )

@dp.message(Command("buy_nft"))
async def buy_nft_command(message: Message):
    """Show information about buying SHIVA NFTs."""
    user_language = await get_user_language(message.from_user.id)
    translations = TRANSLATIONS[user_language]
    
    # Create buy button
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=translations['buy_nft_button'], url=NFT_MARKETPLACE_LINK)]
    ])
    
    # Format message
    message_text = (
        f"{translations['buy_nft_title']}\n\n"
        f"{translations['buy_nft_description']}"
    )
    
    await message.answer(
        message_text,
        reply_markup=keyboard,
        parse_mode="Markdown"
    )

@dp.message(Command("wallet"))
async def wallet_command(message: Message, state: FSMContext):
    """Direct wallet verification command."""
    command_parts = message.text.split()
    user_id = message.from_user.id
    username = message.from_user.username or "Unknown"
    
    # Get user's language
    user_language = await get_user_language(user_id)
    translations = TRANSLATIONS[user_language]
    
    # If no wallet provided in command, wait for next message
    if len(command_parts) == 1:
        await state.set_state(UserState.waiting_for_wallet)
        await message.reply(translations['enter_wallet'])
        return
    
    # Get wallet from command
    wallet_address = command_parts[1].strip()
    
    # Basic wallet validation
    if not wallet_address.startswith('EQ') and not wallet_address.startswith('UQ'):
        await message.reply(translations['wallet_invalid'])
        return
    
    try:
        # Check NFT ownership and balance
        has_nft = await check_nft_ownership(wallet_address)
        _, shiva_balance = await check_token_balance(wallet_address, SHIVA_TOKEN_ADDRESS)
        
        # Save to database
        await save_user_data(user_id, username, wallet_address, has_nft)
        
        # Notify user (simple message)
        await message.reply(translations['wallet_saved'])
        
        # Notify admin (detailed message)
        admin_message = translations['admin_wallet_verified' if has_nft else 'admin_wallet_unverified'].format(
            username,
            user_id,
            wallet_address,
            shiva_balance
        )
        await notify_admin(admin_message)
        
    except Exception as e:
        logger.error(f"Error in wallet command: {e}")
        await notify_admin(f"Error saving wallet for @{username} (ID: {user_id}): {str(e)}")

@dp.message(UserState.waiting_for_wallet)
async def handle_wallet_input(message: Message, state: FSMContext):
    """Handle wallet address input after /wallet command."""
    user_id = message.from_user.id
    username = message.from_user.username or "Unknown"
    wallet_address = message.text.strip()
    
    # Get user's language
    user_language = await get_user_language(user_id)
    translations = TRANSLATIONS[user_language]
    
    # Basic wallet validation
    if not wallet_address.startswith('EQ') and not wallet_address.startswith('UQ'):
        await message.reply(translations['wallet_invalid'])
        return
    
    try:
        # Check NFT ownership and balance
        has_nft = await check_nft_ownership(wallet_address)
        _, shiva_balance = await check_token_balance(wallet_address, SHIVA_TOKEN_ADDRESS)
        
        # Save to database
        await save_user_data(user_id, username, wallet_address, has_nft)
        
        # Clear the state
        await state.clear()
        
        # Notify user (simple message)
        await message.reply(translations['wallet_saved'])
        
        # Notify admin (detailed message)
        admin_message = translations['admin_wallet_verified' if has_nft else 'admin_wallet_unverified'].format(
            username,
            user_id,
            wallet_address,
            shiva_balance
        )
        await notify_admin(admin_message)
        
    except Exception as e:
        logger.error(f"Error processing wallet: {e}")
        await notify_admin(f"Error saving wallet for @{username} (ID: {user_id}): {str(e)}")

@dp.message(Command("help"))
async def help_command(message: Message):
    """Show list of available commands."""
    user_language = await get_user_language(message.from_user.id)
    translations = TRANSLATIONS[user_language]
    
    help_message = (
        f"{translations['help_title']}\n"
        f"{translations['help_description']}\n"
        f"{translations['help_commands']}"
    )
    
    await message.answer(help_message, parse_mode="Markdown")

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
