import asyncio
import aiohttp
import base64
import requests
from typing import Tuple, List, Dict
import time as time_module
from datetime import datetime
from aiogram import Bot, Dispatcher, types
from aiogram.types import (
    Message, 
    CallbackQuery,
    InlineKeyboardMarkup, 
    InlineKeyboardButton, 
    ReplyKeyboardMarkup, 
    KeyboardButton,
    ReplyKeyboardRemove,
    FSInputFile
)
from aiogram.filters import Command
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.memory import MemoryStorage
import sqlite3
import logging
from admin import AdminCommands, register_admin_handlers

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
ADMIN_IDS = ["1499577590","5851290427"]
VERIFICATION_WALLET = "UQA53kg3IzUo2PTuaZxXB3qK7fICyc1u_Yu8d0JDYJRPVWpz"
TON_API_KEY = "6767227019a948426ee2ef5a310f490e43cc1ca23363b932303002e59988f833"
GROUP_ID = -1002476568928
BASE_URL = "https://toncenter.com/api/v3"
WELCOME_IMAGE_PATH = "boris.jpg"
TONAPI_KEY = "AHZNMH2YZTTI2NIAAAACRWPE4TMJORYEHELN4ADWSJYBYH475H4AN4FYZUNVNZV4JM74HJY"
SHIVA_TOKEN_ADDRESS = "EQAQAYqUr9IDiiMQKvXXHtLhT77WvbhH7VGhvPPJmBVF3O7y"
SHIVA_DEX_LINK = "https://dedust.io/trade/SHIVA-TON"

# Initialize bot and dispatcher
bot = Bot(token=API_TOKEN)
storage = MemoryStorage()
dp = Dispatcher(storage=storage)
logger = logging.getLogger(__name__)

# Messages in English
MESSAGES = {
    'username_required': """❌ You need to set a Telegram username before using this bot.

To set a username:
1. Go to Settings
2. Tap on 'Username'
3. Choose a username
4. Return here and try again""",

    'welcome_message': """👋 This is Boris.
Welcome {}!

I'm tonfans NFT checker bot. I'll help you verify your NFT ownership and get access to our exclusive group.

Please send me your TON wallet address to begin verification.""",

    'invalid_wallet': "❌ Invalid wallet address. Please send a valid TON wallet address.",
    
    'wallet_saved': """✅ Wallet address saved: `{}`

Checking NFT ownership...""",

    'verification_success': """🎉 Verification successful!

Your wallet owns a TONFANS NFT. Welcome to the club! 🚀

You can now join our exclusive group.""",

    'verification_failed': """❌ Verification failed.

No TONFANS NFT found in this wallet. To get access:
1. Buy a TONFANS NFT on GetGems
2. Try verification again with /verify""",

    'already_verified': "✅ You're already verified! Welcome back!",
    
    'start_verification': "Please start verification using the /start command.",
    
    'no_pending_verification': "No pending verification requests found. Please start again with /start.",
    
    'whale_checking_balance': "🐳 Checking your $SHIVA balance...",
    'whale_verification_success': "🐳 Congratulations! You qualify as a whale!",
    'whale_verification_failed': "❌ Sorry, you don't qualify as a whale yet.",
    
    'price': """💰 *SHIVA Token Price*

*USD:* ${:.8f} ({})
*TON:* {:.8f} TON ({})

Buy on DeDust: {}""",

    'buy_shiva': """💎 *How to Buy SHIVA Tokens*

1️⃣ Get TON coins from any exchange
2️⃣ Transfer TON to your wallet
3️⃣ Visit DeDust.io using the link below
4️⃣ Connect your wallet
5️⃣ Swap TON for SHIVA

*Contract Address:*
`{}`

*Current Price:* ${:.8f}

Click the button below to start trading! 🚀""",

    'buy_nft': """🖼 *How to Buy TONFANS NFT*

1️⃣ Get TON coins from any exchange
2️⃣ Transfer TON to your wallet
3️⃣ Visit GetGems using the link below
4️⃣ Connect your wallet
5️⃣ Choose your favorite NFT

*Collection Address:*
`{}`

Click the button below to view the collection! 🎨""",

    'help_message': """🤖 *Available Commands*

*Basic Commands:*
/start - Start the bot and begin verification
/help - Show this help message

*Verification Commands:*
/wallet - Submit your wallet address
/verify - Verify your NFT ownership

*Token Commands:*
/whale - Check if you qualify as a whale
/price - Check current SHIVA token price
/top - View top SHIVA token holders

*Purchase Information:*
/buy - Learn how to buy SHIVA tokens
/nft - Learn how to buy TONFANS NFTs

Need assistance? Start with /start to begin the verification process!"""
}

class UserState(StatesGroup):
    waiting_for_wallet = State()
    waiting_for_transaction = State()

# Remove language-related fields from database
def setup_database():
    conn = sqlite3.connect('members.db')
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS members (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            wallet_address TEXT UNIQUE,
            last_checked TIMESTAMP,
            has_nft BOOLEAN,
            verification_memo TEXT
        )
    ''')
    conn.commit()
    conn.close()

async def get_user_data(user_id: int):
    conn = sqlite3.connect('members.db')
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM members WHERE user_id = ?', (user_id,))
    result = cursor.fetchone()
    conn.close()
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
    cursor.execute('''
        INSERT OR REPLACE INTO members 
        (user_id, username, wallet_address, last_checked, has_nft, verification_memo)
        VALUES (?, ?, ?, CURRENT_TIMESTAMP, ?, ?)
    ''', (user_id, username, wallet_address, has_nft, verification_memo))
    conn.commit()
    conn.close()

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

async def check_token_balance(user_address: str, jetton_master_address: str) -> Tuple[int, float, Dict]:
    """
    Check SHIVA token balance and price for a given wallet address.
    Returns raw balance, formatted balance, and price data.
    """
    try:
        url = f"https://tonapi.io/v2/accounts/{user_address}/jettons/{jetton_master_address}"
        headers = {
            "Authorization": f"Bearer {TONAPI_KEY}"
        }
        
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=headers) as response:
                if response.status != 200:
                    logger.error(f"API request failed with status {response.status}")
                    return 0, 0.0, {}
                
                data = await response.json()
                balance = data.get("balance", "0")
                price_data = data.get("price", {})
                
                try:
                    raw_balance = int(balance)
                    formatted_balance = raw_balance / 1e9  # Convert to actual SHIVA tokens
                    logger.info(f"$SHIVA balance for address {user_address}: {formatted_balance:,.2f}")
                    return raw_balance, formatted_balance, price_data
                except (ValueError, TypeError) as e:
                    logger.error(f"Error converting balance to integer: {str(e)}")
                    return 0, 0.0, {}
                
    except Exception as e:
        logger.error(f"Error checking token balance: {str(e)}")
        logger.error(f"Error type: {type(e)}")
        logger.error("Error traceback: ", exc_info=True)
        return 0, 0.0, {}

async def get_shiva_price() -> Dict:
    """Get current SHIVA token price data."""
    try:
        url = f"https://tonapi.io/v2/accounts/{VERIFICATION_WALLET}/jettons/{SHIVA_TOKEN_ADDRESS}"
        params = {
            "currencies": "ton,usd",
            "supported_extensions": "custom_payload"
        }
        headers = {
            "Authorization": f"Bearer {TONAPI_KEY}"
        }
        async with aiohttp.ClientSession() as session:
            async with session.get(url, params=params, headers=headers) as response:
                if response.status != 200:
                    logger.error(f"API request failed with status {response.status}")
                    return {}
                data = await response.json()
                logger.info(f"Price API response: {data}")  # Log the response for debugging
                return data.get("price", {})
    except Exception as e:
        logger.error(f"Error getting SHIVA price: {str(e)}")
        return {}

async def get_top_holders() -> List[Dict]:
    """Get top SHIVA token holders."""
    try:
        url = f"https://tonapi.io/v2/jettons/{SHIVA_TOKEN_ADDRESS}/holders"
        params = {
            "limit": 10,
            "offset": 0
        }
        headers = {
            "Authorization": f"Bearer {TONAPI_KEY}"
        }
        
        async with aiohttp.ClientSession() as session:
            async with session.get(url, params=params, headers=headers) as response:
                if response.status != 200:
                    logger.error(f"API request failed with status {response.status}")
                    return []
                    
                data = await response.json()
                return data.get("addresses", [])
    except Exception as e:
        logger.error(f"Error getting top holders: {str(e)}")
        return []

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
            conn = sqlite3.connect('members.db')
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
            f"👤 User: @{username}\n"
            f"🆔 ID: `{user_id}`\n"
            f"👛 Wallet: `{wallet_address}`\n"
            f"🎨 NFT Status: {'✅ Has NFT' if has_nft else '❌ No NFT'}\n"
            f"💰 SHIVA Balance: {formatted_balance:,.2f}\n"
            f"⏰ Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S UTC')}"
        )
        
        # Send to all admins
        for admin_id in ADMIN_IDS:
            try:
                await bot.send_message(
                    chat_id=admin_id,
                    text=notification,
                    parse_mode="Markdown"
                )
            except Exception as e:
                logger.error(f"Failed to notify admin {admin_id}: {str(e)}")
                
    except Exception as e:
        logger.error(f"Error in admin notification: {str(e)}", exc_info=True)

@dp.message(Command('start'))
async def start_command(message: types.Message, state: FSMContext):
    """Start command handler"""
    user_id = message.from_user.id
    username = message.from_user.username

    # Reset any previous state
    await state.clear()
    
    # Check if user has a username
    if not username:
        await message.answer(MESSAGES['username_required'])
        return

    try:
        # Send welcome image with caption
        with open(WELCOME_IMAGE_PATH, 'rb') as photo:
            await message.answer_photo(
                FSInputFile(WELCOME_IMAGE_PATH),
                caption=f"👋 This is Boris.\nWelcome {message.from_user.first_name}!\n\nI'm tonfans NFT checker bot. I'll help you verify your NFT ownership and get access to our exclusive group.\n\nPlease send me your TON wallet address to begin verification.",
                parse_mode="Markdown"
            )
    except Exception as e:
        logger.error(f"Error sending welcome image: {e}")
        # Fallback to text-only welcome message
        await message.answer(
            f"👋 This is Boris.\nWelcome {message.from_user.first_name}!\n\nI'm tonfans NFT checker bot. I'll help you verify your NFT ownership and get access to our exclusive group.\n\nPlease send me your TON wallet address to begin verification.",
            parse_mode="Markdown"
        )
    
    await state.set_state(UserState.waiting_for_wallet)
    logger.info(f"Start command used by @{username} (ID: {user_id})")

@dp.message(Command("wallet"))
async def wallet_command(message: types.Message, state: FSMContext):
    """Handle /wallet command - directly saves wallet"""
    args = message.text.split(maxsplit=1)
    if len(args) < 2:
        await message.answer("Please provide a wallet address: /wallet <address>")
        return
    
    wallet_address = args[1].strip()
    user_id = message.from_user.id
    username = message.from_user.username

    # Basic wallet address validation
    if not (wallet_address.startswith('EQ') or wallet_address.startswith('UQ')):
        await message.answer(MESSAGES['invalid_wallet'])
        return
    
    # Direct save for /wallet command
    await save_user_data(user_id, username, wallet_address, False)
    await message.answer("✅ Wallet saved successfully!")
    
    # Notify admins about the new wallet registration
    await notify_admins_wallet_registration(user_id, username, wallet_address)

@dp.message(UserState.waiting_for_wallet)
async def handle_wallet_input(message: types.Message, state: FSMContext):
    """Handle wallet address input from normal flow"""
    user_id = message.from_user.id
    username = message.from_user.username
    wallet_address = message.text.strip()
    
    # Basic wallet address validation
    if not (wallet_address.startswith('EQ') or wallet_address.startswith('UQ')):
        await message.answer(MESSAGES['invalid_wallet'])
        return
    
    # Generate verification memo
    verification_memo = f"verify_{user_id}_{int(time_module.time())}"
    
    # Store wallet and memo temporarily in state
    await state.update_data(wallet_address=wallet_address, verification_memo=verification_memo)
    
    verification_msg = f"""To verify your wallet ownership, please:

1. Send a small transaction (0.01 TON) to this address:
`{VERIFICATION_WALLET}`

2. Include this exact memo in your transaction message:
`{verification_memo}`

3. Use /verify command after sending the transaction.

I'll check for your transaction and verify your NFT ownership."""
    
    await message.answer(verification_msg, parse_mode="Markdown")
    await state.set_state(UserState.waiting_for_transaction)

@dp.message(Command('verify'))
async def verify_command(message: types.Message, state: FSMContext):
    """Handle verification command"""
    user_id = message.from_user.id
    username = message.from_user.username
    
    # Get stored data from state
    state_data = await state.get_data()
    wallet_address = state_data.get('wallet_address')
    verification_memo = state_data.get('verification_memo')
    
    if not wallet_address or not verification_memo:
        await message.answer("Please start the verification process with /start first.")
        return
    
    await message.answer("🔍 Checking your verification transaction...")
    
    # Check for the verification transaction
    transaction_verified = await check_transaction(VERIFICATION_WALLET, verification_memo)
    
    if not transaction_verified:
        failed_msg = f"""❌ Transaction not found. Please make sure you:

1. Sent 0.01 TON to:
`{VERIFICATION_WALLET}`

2. Included this memo:
`{verification_memo}`

Try again with /verify after sending the transaction."""
        await message.answer(failed_msg, parse_mode="Markdown")
        return

    # If transaction verified, save wallet and check NFT ownership
    await save_user_data(user_id, username, wallet_address, False)
    has_nft = await check_nft_ownership(wallet_address)
    
    if has_nft:
        await save_user_data(user_id, username, wallet_address, True)
        await message.answer(MESSAGES['verification_success'])
        
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="Join Group", url=GROUP_INVITE_LINK)]
        ])
        await message.answer("You can now join our exclusive group!", reply_markup=keyboard)
    else:
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="Buy NFT", url=NFT_MARKETPLACE_LINK)]
        ])
        await message.answer(
            "To get access, buy a TONFANS NFT on GetGems and try verification again with /verify",
            reply_markup=keyboard
        )
    
    await state.clear()

@dp.message(Command('whale'))
async def whale_command(message: Message):
    """Check if user qualifies as a whale."""
    user_id = message.from_user.id
    username = message.from_user.username
    
    user_data = await get_user_data(user_id)
    
    if not user_data or not user_data[2]:  # Check if user exists and has wallet
        await message.reply(MESSAGES['start_verification'])
        return

    wallet_address = user_data[2]
    await message.reply(MESSAGES['whale_checking_balance'])
    
    # Check SHIVA token balance
    raw_balance, formatted_balance, _ = await check_token_balance(wallet_address, SHIVA_TOKEN_ADDRESS)
    
    # Show current balance regardless of whale status
    balance_message = f"Your $SHIVA balance: {formatted_balance:,.2f}"
    await message.reply(balance_message)
    
    if formatted_balance >= 10_000_000:  # 10M SHIVA threshold
        await message.reply(MESSAGES['whale_verification_success'])
    else:
        # Calculate how many more SHIVA needed
        shiva_needed = 10_000_000 - formatted_balance
        message_text = (
            f"{MESSAGES['whale_verification_failed']}\n"
            f"You need {shiva_needed:,.2f} more $SHIVA to qualify."
        )
        await message.reply(message_text)

@dp.message(Command('price'))
async def price_command(message: Message):
    """Show current SHIVA token price."""
    try:
        price_data = await get_shiva_price()
        if not price_data:
            await message.reply("❌ Unable to fetch price data. Please try again later.")
            return

        # Access the nested structure correctly
        prices = price_data.get("prices", {})
        changes = price_data.get("diff_24h", {})
        
        # Get prices with proper default values
        usd_price = prices.get("USD", 0)
        ton_price = prices.get("TON", 0)
        usd_change = changes.get("USD", "+0%")
        ton_change = changes.get("TON", "+0%")

        price_message = MESSAGES['price'].format(
            usd_price,
            usd_change,
            ton_price,
            ton_change,
            SHIVA_DEX_LINK
        )
        await message.reply(price_message, parse_mode="Markdown")
    except Exception as e:
        logger.error(f"Error in price command: {e}")
        await message.reply("❌ Error fetching price data. Please try again later.")

@dp.message(Command('top'))
async def top_command(message: Message):
    """Show top SHIVA token holders."""
    try:
        await message.reply("🔍 Fetching top SHIVA holders...")
        
        holders = await get_top_holders()
        if not holders:
            await message.reply("❌ Unable to fetch holders data. Please try again later.")
            return
            
        response = "🏆 *Top SHIVA Holders*\n\n"
        
        for i, holder in enumerate(holders, 1):
            balance = int(holder.get("balance", "0")) / 1e9  # Convert to actual SHIVA tokens
            holder_name = await get_holder_name(holder)
            response += f"{i}. {holder_name}: {balance:,.2f} SHIVA\n"
            
        response += f"\n💫 Total Holders: {len(holders):,}"
        
        await message.reply(response, parse_mode="Markdown")
        
    except Exception as e:
        logger.error(f"Error in top command: {e}")
        await message.reply("❌ Error fetching top holders. Please try again later.")

@dp.message(Command('buy'))
async def buy_command(message: Message):
    """Show information about buying SHIVA tokens."""
    try:
        # Get current price for display
        price_data = await get_shiva_price()
        current_price = price_data.get("prices", {}).get("USD", 0)
        
        # Create button to DeDust
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(
                text="🔄 Trade on DeDust",
                url=SHIVA_DEX_LINK
            )]
        ])
        
        # Send message with instructions
        await message.reply(
            MESSAGES['buy_shiva'].format(
                SHIVA_TOKEN_ADDRESS,
                current_price
            ),
            reply_markup=keyboard,
            parse_mode="Markdown"
        )
        
    except Exception as e:
        logger.error(f"Error in buy command: {e}")
        await message.reply("❌ Error fetching trading information. Please try again later.")

@dp.message(Command('nft'))
async def nft_command(message: Message):
    """Show information about buying TONFANS NFTs."""
    try:
        # Create button to GetGems
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(
                text="🖼 View on GetGems",
                url=NFT_MARKETPLACE_LINK
            )]
        ])
        
        # Send message with instructions
        await message.reply(
            MESSAGES['buy_nft'].format(NFT_COLLECTION_ADDRESS),
            reply_markup=keyboard,
            parse_mode="Markdown"
        )
        
    except Exception as e:
        logger.error(f"Error in nft command: {e}")
        await message.reply("❌ Error fetching NFT information. Please try again later.")

@dp.message(Command('help'))
async def help_command(message: Message):
    """Show available commands and their functions."""
    await message.reply(
        MESSAGES['help_message'],
        parse_mode="Markdown"
    )

# Main function
async def main():
    print("Starting NFT Checker Bot...")
    setup_database()
    
    try:
        # Initialize admin commands
        admin_commands = AdminCommands(bot)
        register_admin_handlers(dp, admin_commands)
        
        # Start polling
        await dp.start_polling(bot)
    except Exception as e:
        logger.error(f"Error: {e}")
    finally:
        await bot.session.close()

if __name__ == '__main__':
    asyncio.run(main())
