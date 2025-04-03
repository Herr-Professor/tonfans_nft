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

# Import from the new utility file
from ton_utils import (
    check_nft_ownership,
    check_transaction,
    check_token_balance,
    get_shiva_price,
    get_top_holders,
    SHIVA_TOKEN_ADDRESS,
    NFT_COLLECTION_ADDRESS,
    VERIFICATION_WALLET,
    TONAPI_KEY
)


# At the top of the file
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Basic Configuration
API_TOKEN = '8067666224:AAELEOrjl0lHDUsqP7NUFU8FTYuzRt972ik'
# NFT_COLLECTION_ADDRESS = 'EQDmUOKwwa6KU0YFbA_CZTGccRdh5SWIQdBDKg741ecOqzR0' # Defined in ton_utils
GROUP_INVITE_LINK = "https://t.me/+X44w-gPPj3AzYWU0"
NFT_MARKETPLACE_LINK = f"https://getgems.io/collection/{NFT_COLLECTION_ADDRESS}" # Use constant
ADMIN_IDS = ["1499577590","5851290427"]
# VERIFICATION_WALLET = "UQA53kg3IzUo2PTuaZxXB3qK7fICyc1u_Yu8d0JDYJRPVWpz" # Defined in ton_utils
# TON_API_KEY = "..." # Defined in ton_utils (for toncenter)
GROUP_ID = -1002476568928
# BASE_URL = "https://toncenter.com/api/v3" # Not used directly anymore
WELCOME_IMAGE_PATH = "boris.jpg"
# TONAPI_KEY = "..." # Defined in ton_utils (for tonapi.io)
# SHIVA_TOKEN_ADDRESS = "EQAQAYqUr9IDiiMQKvXXHtLhT77WvbhH7VGhvPPJmBVF3O7y" # Defined in ton_utils
SHIVA_DEX_LINK = f"https://dedust.io/trade/{SHIVA_TOKEN_ADDRESS}-TON" # Use constant

# Initialize bot and dispatcher
bot = Bot(token=API_TOKEN)
storage = MemoryStorage()
dp = Dispatcher(storage=storage)
# Logger is already configured

# Messages in English (Keep as is)
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

    'invalid_wallet': "❌ Invalid wallet address. Please send a valid TON wallet address (starting with EQ or UQ).", # Added prefix hint

    'wallet_saved': """✅ Wallet address saved: `{}`

Now, please verify ownership.""", # Adjusted flow message slightly

    'verification_success': """🎉 Verification successful!

Your wallet owns a TONFANS NFT. Welcome to the club! 🚀

You can now join our exclusive group.""",

    'verification_failed_nft': """❌ Verification successful, but NFT not found.

Your wallet ownership is confirmed, but no TONFANS NFT found in this wallet (`{}`). To get access:
1. Buy a TONFANS NFT on GetGems
2. Try verification again with /verify""", # More specific message

     'verification_failed_tx': """❌ Transaction not found or invalid. Please make sure you:

1. Sent at least 0.01 TON to:
`{}`

2. Included this exact memo:
`{}`

3. The transaction is recent.

Try again with /verify after sending the correct transaction.""", # More specific message


    'already_verified': "✅ You're already verified and own the NFT! Welcome back!", # Clarified NFT ownership included

    'start_verification': "Please start the process using the /start command to register or verify your wallet.", # Slightly rephrased

    'no_pending_verification': "No pending verification found. Please use /start first to provide your wallet address.",

    'whale_checking_balance': "🐳 Checking your $SHIVA balance...",
    'whale_verification_success': "🐳 Congratulations! You have {balance:,.2f} $SHIVA and qualify as a whale!", # Include balance
    'whale_verification_failed': "❌ Sorry, you currently have {balance:,.2f} $SHIVA, which is below the 10,000,000 threshold.", # Include balance

    'price': """💰 *SHIVA Token Price*

*USD:* ${:.8f} ({})
*TON:* {:.8f} TON ({})

Data from TonAPI.io. Trade on DeDust: {}""", # Added source

    'buy_shiva': """💎 *How to Buy SHIVA Tokens*

1️⃣ Get TON coins (e.g., via @wallet bot or exchanges)
2️⃣ Transfer TON to your wallet (e.g., Tonkeeper, MyTonWallet)
3️⃣ Visit DeDust.io using the link below
4️⃣ Connect your wallet
5️⃣ Swap TON for SHIVA

*Contract Address:*
`{}`

*Current Price:* ${:.8f} (approx)

Click the button below to start trading! 🚀""",

    'buy_nft': """🖼 *How to Buy TONFANS NFT*

1️⃣ Get TON coins
2️⃣ Transfer TON to your wallet
3️⃣ Visit GetGems using the link below
4️⃣ Connect your wallet
5️⃣ Choose and purchase your favorite NFT from the collection!

*Collection Address:*
`{}`

Click the button below to view the collection! 🎨""",

    'help_message': """🤖 *Available Commands*

*Start Here:*
/start - Begin bot interaction & wallet registration

*Verification:*
/verify - Check your verification transaction & NFT status

*Account:*
/wallet <address> - Directly register/update your wallet (alternative)

*$SHIVA Token:*
/price - Check current SHIVA token price
/top - View top SHIVA token holders
/whale - Check if your registered wallet meets the whale threshold
/buy - Learn how to buy SHIVA tokens

*NFT:*
/nft - Learn how to buy TONFANS NFTs

*Other:*
/help - Show this help message

Need assistance? Start with /start!""" # Updated help
}


class UserState(StatesGroup):
    waiting_for_wallet = State()
    waiting_for_transaction = State()

# Database setup function (Keep as is)
def setup_database():
    conn = sqlite3.connect('members.db')
    cursor = conn.cursor()
    # Check if columns exist before adding (simple approach)
    try:
        cursor.execute("SELECT verification_memo FROM members LIMIT 1")
    except sqlite3.OperationalError:
        logger.info("Adding verification_memo column to members table.")
        cursor.execute("ALTER TABLE members ADD COLUMN verification_memo TEXT")

    # Ensure other columns exist and table is created
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS members (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            wallet_address TEXT UNIQUE,
            last_checked TIMESTAMP,
            has_nft BOOLEAN DEFAULT 0,
            verification_memo TEXT
        )
    ''')
    conn.commit()

    # Add index on wallet_address if it doesn't exist
    try:
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_wallet_address ON members (wallet_address);")
        conn.commit()
    except sqlite3.Error as e:
        logger.warning(f"Could not create index on wallet_address: {e}")

    conn.close()


async def get_user_data(user_id: int):
    conn = sqlite3.connect('members.db')
    cursor = conn.cursor()
    cursor.execute('SELECT user_id, username, wallet_address, last_checked, has_nft, verification_memo FROM members WHERE user_id = ?', (user_id,))
    result = cursor.fetchone()
    conn.close()
    if result:
        # Return as a dictionary for easier access
        keys = ["user_id", "username", "wallet_address", "last_checked", "has_nft", "verification_memo"]
        return dict(zip(keys, result))
    return None

async def get_user_by_wallet(wallet_address: str):
    conn = sqlite3.connect('members.db')
    cursor = conn.cursor()
    cursor.execute('SELECT user_id, username, wallet_address, last_checked, has_nft, verification_memo FROM members WHERE wallet_address = ?', (wallet_address,))
    result = cursor.fetchone()
    conn.close()
    if result:
         keys = ["user_id", "username", "wallet_address", "last_checked", "has_nft", "verification_memo"]
         return dict(zip(keys, result))
    return None


async def save_user_data(user_id: int, username: str, wallet_address: str = None, has_nft: bool = None, verification_memo: str = None):
    """Saves or updates user data. Only updates non-None fields provided."""
    conn = sqlite3.connect('members.db')
    cursor = conn.cursor()

    # Check if user exists
    cursor.execute('SELECT user_id FROM members WHERE user_id = ?', (user_id,))
    exists = cursor.fetchone()

    fields_to_update = {
        'username': username,
        'last_checked': datetime.now().isoformat()
    }
    if wallet_address is not None:
        fields_to_update['wallet_address'] = wallet_address
    if has_nft is not None:
        fields_to_update['has_nft'] = has_nft
    if verification_memo is not None:
        fields_to_update['verification_memo'] = verification_memo

    if exists:
        # Update existing user
        set_clause = ", ".join([f"{key} = ?" for key in fields_to_update])
        values = list(fields_to_update.values())
        values.append(user_id)
        sql = f'UPDATE members SET {set_clause} WHERE user_id = ?'
    else:
        # Insert new user
        # Ensure required fields have defaults if not provided
        fields_to_update['user_id'] = user_id
        if 'has_nft' not in fields_to_update: fields_to_update['has_nft'] = False # Default has_nft to False

        columns = ", ".join(fields_to_update.keys())
        placeholders = ", ".join(["?"] * len(fields_to_update))
        values = list(fields_to_update.values())
        sql = f'INSERT INTO members ({columns}) VALUES ({placeholders})'

    try:
        cursor.execute(sql, tuple(values))
        conn.commit()
        logger.info(f"User data {'updated' if exists else 'inserted'} for user_id {user_id}")
    except sqlite3.IntegrityError as e:
         # Handle potential unique constraint violation (e.g., wallet address already linked to another user)
         logger.error(f"Database integrity error saving user {user_id} (@{username}): {e}")
         if 'UNIQUE constraint failed: members.wallet_address' in str(e):
              # Optionally, notify the user or admin
              existing_user = await get_user_by_wallet(wallet_address)
              raise ValueError(f"Wallet address `{wallet_address}` is already registered by user @{existing_user['username']} (ID: {existing_user['user_id']}).")
         else:
              raise e # Re-raise other integrity errors
    except Exception as e:
         logger.error(f"Unexpected error saving user {user_id}: {e}")
         raise e # Re-raise other exceptions
    finally:
        conn.close()


# --- Blockchain interaction functions are now imported from ton_utils.py ---
# async def check_nft_ownership(wallet_address: str) -> bool: ... (Removed)
# async def check_transaction(address: str, memo: str) -> bool: ... (Removed)
# async def check_token_balance(...): ... (Removed)
# async def get_shiva_price() -> Dict: ... (Removed)
# async def get_top_holders() -> List[Dict]: ... (Removed)


# --- Helper function for holder names (Consider moving to ton_utils if complex) ---
async def get_holder_name(holder_data: Dict) -> str:
    """Get holder name from owner data or database."""
    try:
        owner = holder_data.get("owner", {})
        owner_address = owner.get("address")

        # Prioritize known name from API response if available
        if owner.get("name"):
            return owner["name"]

        # Check our database by address
        if owner_address:
            # Use the existing async db function
            user_db_data = await get_user_by_wallet(owner_address)
            if user_db_data and user_db_data.get('username'):
                 # Add '@' prefix for Telegram usernames
                 return f"@{user_db_data['username']}"

        # Fallback to a shortened address if no name found
        if owner_address:
             return f"{owner_address[:6]}...{owner_address[-4:]}"

        return "Unknown Holder" # Absolute fallback
    except Exception as e:
        logger.error(f"Error getting holder name: {str(e)}")
        return "Error Name"


async def notify_admins_wallet_registration(user_id: int, username: str, wallet_address: str):
    """Send detailed notification to admins about new wallet registration."""
    # This function remains useful here as it combines bot logic (sending message)
    # with data fetching (using utils)
    try:
        # Use imported functions
        has_nft = await check_nft_ownership(wallet_address)
        raw_balance, formatted_balance, _ = await check_token_balance(wallet_address, SHIVA_TOKEN_ADDRESS)

        # Save/Update the user data with the fetched NFT status
        await save_user_data(user_id, username, wallet_address=wallet_address, has_nft=has_nft)

        notification = (
            f"🔔 *New Wallet Registration/Update*\n\n"
            f"👤 User: @{username} (ID: `{user_id}`)\n"
            f"👛 Wallet: `{wallet_address}`\n"
            f"🎨 NFT Status: {'✅ Has NFT' if has_nft else '❌ No NFT'}\n"
            f"💰 SHIVA Balance: {formatted_balance:,.2f}\n"
            f"⏰ Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S UTC')}"
        )

        for admin_id in ADMIN_IDS:
            try:
                await bot.send_message(
                    chat_id=admin_id,
                    text=notification,
                    parse_mode="Markdown"
                )
            except Exception as e:
                logger.error(f"Failed to notify admin {admin_id}: {str(e)}")

    except ValueError as ve: # Catch the specific error from save_user_data
        logger.warning(f"Admin notification skipped for user @{username} due to wallet conflict: {ve}")
        # Optionally notify the user or just log it
    except Exception as e:
        logger.error(f"Error in admin notification for @{username}: {str(e)}", exc_info=True)

# --- Command Handlers ---

@dp.message(Command('start'))
async def start_command(message: types.Message, state: FSMContext):
    user_id = message.from_user.id
    username = message.from_user.username
    first_name = message.from_user.first_name

    await state.clear()

    if not username:
        await message.answer(MESSAGES['username_required'])
        return

    logger.info(f"/start command from @{username} (ID: {user_id})")

    # Check if user already exists and is verified
    user_data = await get_user_data(user_id)
    if user_data and user_data.get('wallet_address') and user_data.get('has_nft'):
         await message.answer(MESSAGES['already_verified'])
         keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="➡️ Go to Group", url=GROUP_INVITE_LINK)]
         ])
         await message.answer("Here's the link again:", reply_markup=keyboard)
         return
    elif user_data and user_data.get('wallet_address'):
         await message.answer(f"👋 Welcome back, {first_name}!\nYour registered wallet is `{user_data['wallet_address']}`.\nUse /verify to check NFT status or send a different wallet address to update.")
         await state.set_state(UserState.waiting_for_wallet) # Allow changing wallet
         return


    try:
        # Send welcome image with caption using FSInputFile
        welcome_caption = MESSAGES['welcome_message'].format(first_name)
        await message.answer_photo(
            FSInputFile(WELCOME_IMAGE_PATH),
            caption=welcome_caption,
            parse_mode="Markdown"
        )
    except Exception as e:
        logger.error(f"Error sending welcome image: {e}. Falling back to text.")
        await message.answer(
            MESSAGES['welcome_message'].format(first_name),
            parse_mode="Markdown"
        )

    await state.set_state(UserState.waiting_for_wallet)

@dp.message(Command("wallet"))
async def wallet_command(message: types.Message, state: FSMContext):
    """
    Handles the /wallet <address> command.
    Directly registers/updates the user's wallet, checks NFT ownership,
    and saves the status WITHOUT requiring transaction verification.
    """
    user_id = message.from_user.id
    username = message.from_user.username

    # Ensure user has a username set in Telegram
    if not username:
         await message.answer(MESSAGES['username_required'])
         return

    # Clear any potentially lingering state from previous interactions
    await state.clear()

    args = message.text.split(maxsplit=1)
    if len(args) < 2:
        await message.answer("Please provide your TON wallet address after the command:\n`/wallet EQ...` or `/wallet UQ...`", parse_mode="Markdown")
        return

    wallet_address = args[1].strip()

    # Validate wallet address format
    if not isinstance(wallet_address, str) or not (wallet_address.startswith('EQ') or wallet_address.startswith('UQ')) or len(wallet_address) != 48:
        await message.answer(MESSAGES['invalid_wallet'])
        return

    logger.info(f"/wallet command from @{username} with address {wallet_address}")
    await message.reply("🔄 Checking wallet and NFT status...") # Initial feedback

    try:
        # --- Direct NFT Check (No Transaction Verification) ---
        has_nft = await check_nft_ownership(wallet_address)
        logger.info(f"NFT check for {wallet_address} via /wallet command: {'Found' if has_nft else 'Not Found'}")

        # --- Save/Update User Data ---
        # Save user with wallet and determined NFT status. No memo, no state change.
        await save_user_data(
            user_id=user_id,
            username=username,
            wallet_address=wallet_address,
            has_nft=has_nft,
            verification_memo=None # Explicitly set memo to None or omit
        )

        # --- Inform User ---
        if has_nft:
            reply_text = (
                f"✅ Wallet `{wallet_address}` successfully registered.\n"
                f"🎉 **TONFANS NFT found!** Welcome to the club."
            )
            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🚀 Join Group", url=GROUP_INVITE_LINK)]
            ])
            await message.edit_text(reply_text, parse_mode="Markdown", reply_markup=keyboard)
        else:
            reply_text = (
                f"✅ Wallet `{wallet_address}` successfully registered.\n"
                f"❌ **TONFANS NFT not found** in this wallet.\n\n"
                f"To gain access, please purchase an NFT from the collection:"
            )
            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                 [InlineKeyboardButton(text="🛒 Buy NFT on GetGems", url=NFT_MARKETPLACE_LINK)]
            ])
            await message.edit_text(reply_text, parse_mode="Markdown", reply_markup=keyboard)

        # --- Notify Admins (Still useful) ---
        # This will re-check balance/NFT for the notification details
        await notify_admins_wallet_registration(user_id, username, wallet_address)

    except ValueError as ve: # Catch wallet conflict from save_user_data
        logger.warning(f"Wallet conflict during /wallet command for @{username}: {ve}")
        await message.edit_text(f"❌ Error: {str(ve)}") # Edit the "Checking..." message
    except Exception as e:
        logger.error(f"Error processing /wallet command for @{username}: {e}", exc_info=True)
        await message.edit_text("❌ An error occurred while processing your request. Please try again or contact support.") 

@dp.message(UserState.waiting_for_wallet)
async def handle_wallet_input(message: types.Message, state: FSMContext):
    """Handle wallet address input from the normal /start flow."""
    user_id = message.from_user.id
    username = message.from_user.username
    wallet_address = message.text.strip()

    if not username: # Should have been caught by /start, but double-check
         await message.answer(MESSAGES['username_required'])
         return

    # Wallet address validation
    if not isinstance(wallet_address, str) or not (wallet_address.startswith('EQ') or wallet_address.startswith('UQ')) or len(wallet_address) != 48:
        await message.answer(MESSAGES['invalid_wallet'])
        # Keep state as waiting_for_wallet
        return

    logger.info(f"Wallet input from @{username}: {wallet_address}")

    try:
        # Generate verification memo
        verification_memo = f"verify_{user_id}_{int(time_module.time())}"

        # Save user data with memo, reset NFT status
        await save_user_data(user_id, username, wallet_address=wallet_address, verification_memo=verification_memo, has_nft=False)

        # Store in state for /verify
        await state.update_data(wallet_address=wallet_address, verification_memo=verification_memo)

        verification_msg = f"""✅ Wallet address set to: `{wallet_address}`

To verify ownership, please send a small transaction (e.g., 0.01 TON) **from this wallet** to:
`{VERIFICATION_WALLET}`

Include this exact memo in your transaction message:
`{verification_memo}`

Then, use the /verify command. This confirms you control the wallet."""

        await message.answer(verification_msg, parse_mode="Markdown")
        await state.set_state(UserState.waiting_for_transaction) # Proceed to next state

        # Notify admins
        await notify_admins_wallet_registration(user_id, username, wallet_address)

    except ValueError as ve: # Catch wallet conflict
        await message.reply(str(ve))
        # Potentially reset state or ask for a different wallet?
        # await state.set_state(UserState.waiting_for_wallet) # Revert state
    except Exception as e:
        logger.error(f"Error processing wallet input for @{username}: {e}")
        await message.reply("An error occurred while saving your wallet. Please try again.")
        # Consider resetting state here too if appropriate


@dp.message(UserState.waiting_for_wallet)
async def handle_wallet_input(message: types.Message, state: FSMContext):
    """Handle wallet address input from the normal /start flow - REQUIRES VERIFICATION TX."""
    user_id = message.from_user.id
    username = message.from_user.username
    wallet_address = message.text.strip()

    if not username:
         await message.answer(MESSAGES['username_required'])
         return

    # Wallet address validation
    if not isinstance(wallet_address, str) or not (wallet_address.startswith('EQ') or wallet_address.startswith('UQ')) or len(wallet_address) != 48:
        await message.answer(MESSAGES['invalid_wallet'])
        return # Keep state as waiting_for_wallet

    logger.info(f"Wallet input (via /start flow) from @{username}: {wallet_address}")

    try:
        # Generate verification memo for THIS flow
        verification_memo = f"verify_{user_id}_{int(time_module.time())}"

        # Save user data with memo, reset NFT status pending verification
        await save_user_data(user_id, username, wallet_address=wallet_address, verification_memo=verification_memo, has_nft=False)

        # Store in state for /verify check
        await state.update_data(wallet_address=wallet_address, verification_memo=verification_memo)

        # Send INSTRUCTIONS FOR VERIFICATION TRANSACTION
        verification_msg = f"""✅ Wallet address set to: `{wallet_address}`

To verify ownership (**required for this method**), please send a small transaction (e.g., 0.01 TON) **from this wallet** to:
`{VERIFICATION_WALLET}`

Include this exact memo in your transaction message:
`{verification_memo}`

Then, use the /verify command. This confirms you control the wallet."""

        await message.answer(verification_msg, parse_mode="Markdown")
        # Set state to wait for /verify command
        await state.set_state(UserState.waiting_for_transaction)

        # Notify admins
        await notify_admins_wallet_registration(user_id, username, wallet_address)

    except ValueError as ve:
        await message.reply(str(ve))
        # await state.set_state(UserState.waiting_for_wallet) # Revert state? Maybe not needed, let them try /wallet cmd
    except Exception as e:
        logger.error(f"Error processing wallet input for @{username}: {e}")
        await message.reply("An error occurred while saving your wallet. Please try again using /start or the /wallet command.")
        await state.clear()


# --- Other Commands using utils ---

@dp.message(Command('whale'))
async def whale_command(message: Message):
    user_id = message.from_user.id
    username = message.from_user.username

    user_data = await get_user_data(user_id)

    if not user_data or not user_data.get('wallet_address'):
        await message.reply(MESSAGES['start_verification'])
        return

    wallet_address = user_data['wallet_address']
    logger.info(f"/whale check requested by @{username} for wallet {wallet_address}")
    await message.reply(MESSAGES['whale_checking_balance'])

    # Use imported function
    raw_balance, formatted_balance, _ = await check_token_balance(wallet_address, SHIVA_TOKEN_ADDRESS)

    whale_threshold = 10_000_000 # Define threshold (could be moved to config)
    if formatted_balance >= whale_threshold:
        await message.reply(MESSAGES['whale_verification_success'].format(balance=formatted_balance))
    else:
        await message.reply(MESSAGES['whale_verification_failed'].format(balance=formatted_balance))


@dp.message(Command('price'))
async def price_command(message: Message):
    """Show current SHIVA token price."""
    try:
        await message.reply("💸 Fetching latest $SHIVA price...")
        # Use imported function
        price_data = await get_shiva_price() # price_data is expected to be the 'prices' dict directly

        if not price_data:
            await message.edit_text("❌ Unable to fetch price data currently. Please try again later.")
            return

        # Access prices directly from the returned dict
        usd_price = price_data.get("USD", 0)
        ton_price = price_data.get("TON", 0)

        # Note: The get_shiva_price util now only returns prices. Fetching diff_24h separately if needed.
        # For simplicity, let's omit the 24h change for now unless the util is updated to return it.
        # Placeholder changes:
        usd_change = "N/A"
        ton_change = "N/A"

        # If you modify get_shiva_price to return the full structure with 'diff_24h':
        # full_price_data = await get_shiva_price() # Assuming it returns {'prices': {...}, 'diff_24h': {...}}
        # prices = full_price_data.get("prices", {})
        # changes = full_price_data.get("diff_24h", {})
        # usd_price = prices.get("USD", 0)
        # ton_price = prices.get("TON", 0)
        # usd_change = changes.get("USD", "N/A")
        # ton_change = changes.get("TON", "N/A")


        price_message = MESSAGES['price'].format(
            usd_price, usd_change,
            ton_price, ton_change,
            SHIVA_DEX_LINK
        )
        await message.edit_text(price_message, parse_mode="Markdown", disable_web_page_preview=True) # Edit the "Fetching..." message

    except Exception as e:
        logger.error(f"Error in /price command: {e}", exc_info=True)
        await message.edit_text("❌ Error fetching price data. Please try again later.")


@dp.message(Command('top'))
async def top_command(message: Message):
    """Show top SHIVA token holders."""
    try:
        await message.reply("🏆 Fetching top $SHIVA holders...")
        # Use imported function
        holders = await get_top_holders(SHIVA_TOKEN_ADDRESS, limit=10)

        if not holders:
            await message.edit_text("❌ Unable to fetch holders data currently. Please try again later.")
            return

        response_lines = ["🏆 *Top 10 SHIVA Holders*\n"]
        total_supply_response = None # Placeholder if we can get total supply info

        # Fetch holder names concurrently for speed (optional optimization)
        # name_tasks = [get_holder_name(h) for h in holders]
        # holder_names = await asyncio.gather(*name_tasks)

        for i, holder in enumerate(holders, 1):
            balance = int(holder.get("balance", "0")) / 1e9 # Assuming 9 decimals
            # Use sequential name fetching for simplicity first:
            holder_name = await get_holder_name(holder)
            # Or use pre-fetched names: holder_name = holder_names[i-1]
            response_lines.append(f"{i}. {holder_name}: **{balance:,.2f}** SHIVA")

        # Optional: Get total holders count (might require another API call or be part of get_top_holders response)
        # Example: total_holders_count = await get_total_holders_count(SHIVA_TOKEN_ADDRESS)
        # if total_holders_count:
        #     response_lines.append(f"\n👥 Total Holders: {total_holders_count:,}")

        response = "\n".join(response_lines)

        await message.edit_text(response, parse_mode="Markdown", disable_web_page_preview=True) # Edit the "Fetching..." message

    except Exception as e:
        logger.error(f"Error in /top command: {e}", exc_info=True)
        await message.edit_text("❌ Error fetching top holders. Please try again later.")

@dp.message(Command('buy'))
async def buy_command(message: Message):
    """Show information about buying SHIVA tokens."""
    try:
        # Fetch current price for display (optional, could show N/A if fails)
        current_price_usd = 0
        try:
            price_data = await get_shiva_price()
            current_price_usd = price_data.get("USD", 0)
        except Exception as price_error:
            logger.warning(f"Could not fetch price for /buy command: {price_error}")

        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔄 Trade SHIVA on DeDust", url=SHIVA_DEX_LINK)]
        ])

        await message.reply(
            MESSAGES['buy_shiva'].format(SHIVA_TOKEN_ADDRESS, current_price_usd),
            reply_markup=keyboard,
            parse_mode="Markdown",
            disable_web_page_preview=True
        )

    except Exception as e:
        logger.error(f"Error in /buy command: {e}")
        await message.reply("❌ Error generating buy information. Please try again later.")


@dp.message(Command('nft'))
async def nft_command(message: Message):
    """Show information about buying TONFANS NFTs."""
    try:
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🖼 View TONFANS Collection on GetGems", url=NFT_MARKETPLACE_LINK)]
        ])

        await message.reply(
            MESSAGES['buy_nft'].format(NFT_COLLECTION_ADDRESS),
            reply_markup=keyboard,
            parse_mode="Markdown",
            disable_web_page_preview=True
        )

    except Exception as e:
        logger.error(f"Error in /nft command: {e}")
        await message.reply("❌ Error generating NFT information. Please try again later.")

@dp.message(Command('help'))
async def help_command(message: Message):
    """Show available commands and their functions."""
    await message.reply(
        MESSAGES['help_message'],
        parse_mode="Markdown"
    )

# --- Main function ---
async def main():
    logger.info("Starting NFT Checker Bot...")
    setup_database() # Ensure DB schema is up-to-date

    # Initialize admin commands instance
    admin_commands = AdminCommands(bot)
    # Register all handlers (admin and regular user)
    register_admin_handlers(dp, admin_commands)

    # Set bot commands for Telegram UI hint
    await bot.set_my_commands([
        types.BotCommand(command="/start", description="Start verification / Show status"),
        types.BotCommand(command="/verify", description="Verify wallet transaction & NFT"),
        types.BotCommand(command="/wallet", description="Register/update wallet address"),
        types.BotCommand(command="/price", description="Check $SHIVA price"),
        types.BotCommand(command="/top", description="Top $SHIVA holders"),
        types.BotCommand(command="/whale", description="Check $SHIVA whale status"),
        types.BotCommand(command="/buy", description="How to buy $SHIVA"),
        types.BotCommand(command="/nft", description="How to buy TONFANS NFT"),
        types.BotCommand(command="/help", description="Show help message"),
    ])


    logger.info("Bot polling started...")
    try:
        await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())
    except Exception as e:
        logger.critical(f"Critical error during polling: {e}", exc_info=True)
    finally:
        logger.info("Closing bot session...")
        await bot.session.close()
        logger.info("Bot stopped.")


if __name__ == '__main__':
    asyncio.run(main())
