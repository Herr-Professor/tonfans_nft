import asyncio
import aiohttp
import base64
import requests
import time as time_module
from datetime import datetime
from aiogram import Bot, Dispatcher, types
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, FSInputFile
from aiogram.filters import Command
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.memory import MemoryStorage
import sqlite3
import logging

# Basic Configuration
API_TOKEN = '7529302576:AAEBzlzCiwI6nrSpadpb89eYDNBhoQUNmvo'
NFT_COLLECTION_ADDRESS = 'EQDmUOKwwa6KU0YFbA_CZTGccRdh5SWIQdBDKg741ecOqzR0'
GROUP_INVITE_LINK = "https://t.me/+X44w-gPPj3AzYWU0"
NFT_MARKETPLACE_LINK = "https://getgems.io/collection/EQDmUOKwwa6KU0YFbA_CZTGccRdh5SWIQdBDKg741ecOqzR0"
ADMIN_IDS = ["1499577590"]
VERIFICATION_WALLET = "UQA53kg3IzUo2PTuaZxXB3qK7fICyc1u_Yu8d0JDYJRPVWpz"
TON_API_KEY = "6767227019a948426ee2ef5a310f490e43cc1ca23363b932303002e59988f833"
WELCOME_IMAGE_PATH = "boris.jpg"

# Initialize bot and dispatcher
bot = Bot(token=API_TOKEN)
storage = MemoryStorage()
dp = Dispatcher(storage=storage)
logger = logging.getLogger(__name__)

class UserState(StatesGroup):
    waiting_for_wallet = State()
    waiting_for_transaction = State()

# Database setup

def setup_database():
    conn = sqlite3.connect('members.db')
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS members (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            wallet_address TEXT,
            last_checked TIMESTAMP,
            has_nft BOOLEAN,
            verification_memo TEXT
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

# Wallet submission handler
@dp.message(UserState.waiting_for_wallet)
async def handle_wallet_input(message: types.Message, state: FSMContext):
    wallet_address = message.text.strip()
    user_id = message.from_user.id
    username = message.from_user.username
    
    # Basic wallet address validation
    if not wallet_address.startswith('EQ') and not wallet_address.startswith('UQ'):
        await message.answer("❌ Invalid wallet address format. Please send a valid TON wallet address.")
        return
    
    # Generate verification memo
    verification_memo = f"verify_{user_id}_{int(time_module.time())}"
    await save_user_data(user_id, username, wallet_address, False, verification_memo)
    
    verification_message = (
        "To verify your wallet ownership, please:\n\n"
        "1. Send a small transaction (0.01 TON) to this address:\n"
        f"`{VERIFICATION_WALLET}`\n\n"
        "2. Include this exact memo in your transaction message:\n"
        f"`{verification_memo}`\n\n"
        "3. Use /verify command after sending the transaction.\n\n"
        "I'll check for your transaction and verify your NFT ownership."
    )
    await message.answer(verification_message, parse_mode="Markdown")
    await state.set_state(UserState.waiting_for_transaction)
    
    # Notify admin about new verification attempt
    admin_message = (
        "🆕 New User Verification Started:\n"
        f"Username: @{username}\n"
        f"User ID: {user_id}\n"
        f"Wallet: {wallet_address}\n"
        f"Verification Memo: {verification_memo}"
    )
    await notify_admin(admin_message)

# Updated start command handler
@dp.message(Command('start'))
async def start_command(message: types.Message, state: FSMContext):
    user_id = message.from_user.id
    username = message.from_user.username or "Anonymous"
    
    # Check if user exists in database
    existing_user = await get_user_data(user_id)
    user_status = "Returning" if existing_user else "New"
    
    # Notify admin about user interaction
    admin_message = (
        f"🔔 *{user_status} User Started Bot:*\n"
        f"Username: @{username}\n"
        f"User ID: `{user_id}`\n"
        f"Previous Wallet: `{existing_user[2] if existing_user else 'None'}`\n"
        f"Previous NFT Status: {'Yes' if existing_user and existing_user[4] else 'No' if existing_user else 'N/A'}"
    )
    await notify_admin(admin_message)
    
    # Send welcome message with image
    try:
        welcome_image = FSInputFile(WELCOME_IMAGE_PATH)
        welcome_message = (
            f"👋 This is Boris. \n Welcome {'back ' if existing_user else ''}@{username}!\n\n"
            "I'm tonfans NFT checker bot. I'll help you verify your NFT "
            "ownership and get access to our exclusive group.\n\n"
            "Please send me your TON wallet address to begin verification."
        )
        await message.answer_photo(photo=welcome_image, caption=welcome_message)
    except Exception as e:
        logger.error(f"Failed to send welcome image: {e}")
        await message.answer(welcome_message)
    
    await state.set_state(UserState.waiting_for_wallet)

# Updated wallet submission handler
@dp.message(UserState.waiting_for_wallet)
async def handle_wallet_input(message: types.Message, state: FSMContext):
    wallet_address = message.text.strip()
    user_id = message.from_user.id
    username = message.from_user.username or "Anonymous"
    
    # Basic wallet address validation
    if not wallet_address.startswith('EQ') and not wallet_address.startswith('UQ'):
        await message.answer("❌ Invalid wallet address format. Please send a valid TON wallet address.")
        await notify_admin(f"❌ *Invalid Wallet Attempt:*\n"
                         f"User: @{username}\n"
                         f"ID: `{user_id}`\n"
                         f"Invalid Input: `{wallet_address}`")
        return
    
    # Check if wallet is already registered
    existing_wallet_user = await get_user_by_wallet(wallet_address)
    if existing_wallet_user and existing_wallet_user[0] != user_id:
        await message.answer("❌ This wallet is already registered to another user.")
        await notify_admin(f"⚠️ *Duplicate Wallet Attempt:*\n"
                         f"User: @{username}\n"
                         f"ID: `{user_id}`\n"
                         f"Wallet: `{wallet_address}`\n"
                         f"Already registered to ID: `{existing_wallet_user[0]}`")
        return
    
    # Generate verification memo
    verification_memo = f"verify_{user_id}_{int(time_module.time())}"
    await save_user_data(user_id, username, wallet_address, False, verification_memo)
    
    verification_message = (
        "To verify your wallet ownership, please:\n\n"
        "1. Send a small transaction (0.01 TON) to my address:\n"
        f"`{VERIFICATION_WALLET}`\n\n"
        "2. Include this exact memo in your transaction message:\n"
        f"`{verification_memo}`\n\n"
        "3. Use /verify command after sending the transaction.\n\n"
        "I'll check for your transaction and verify your NFT ownership."
    )
    await message.answer(verification_message, parse_mode="Markdown")
    await state.set_state(UserState.waiting_for_transaction)
    
    # Notify admin about verification attempt
    admin_message = (
        "🆕 *New Verification Attempt:*\n"
        f"Username: @{username}\n"
        f"User ID: `{user_id}`\n"
        f"Wallet: `{wallet_address}`\n"
        f"Verification Memo: `{verification_memo}`"
    )
    await notify_admin(admin_message)

# Update the verify command handler with admin notifications
@dp.message(Command('verify'))
async def verify_command(message: types.Message, state: FSMContext):
    user_id = message.from_user.id
    username = message.from_user.username or "Anonymous"
    user_data = await get_user_data(user_id)
    
    # Notify admin about verification attempt
    await notify_admin(f"🔍 *Verification Attempt:*\n"
                      f"User: @{username}\n"
                      f"ID: `{user_id}`")
    
    if not user_data:
        await message.answer("❌ Please start the verification process first using /start command.")
        return
    
    verification_memo = user_data[5]
    wallet_address = user_data[2]
    
    if not verification_memo or not wallet_address:
        await message.answer("❌ No pending verification found. Please start over using /start command.")
        return
    
    await message.answer("🔍 Checking your verification transaction...")
    
    # Check if transaction exists
    transaction_verified = await check_transaction(VERIFICATION_WALLET, verification_memo)
    
    if not transaction_verified:
        verification_instructions = (
            "❌ Transaction not found. Please make sure you:\n\n"
            f"1. Sent 0.01 TON to: `{VERIFICATION_WALLET}`\n"
            f"2. Included this memo: `{verification_memo}`\n\n"
            "Try again with /verify after sending the transaction."
        )
        await message.answer(verification_instructions, parse_mode="Markdown")
        return
    
    await message.answer("✅ Transaction verified! Now checking NFT ownership...")
    await notify_admin(f"✅ *Transaction Verified:*\n"
                      f"User: @{username}\n"
                      f"ID: `{user_id}`\n"
                      f"Wallet: `{wallet_address}`\n"
                      f"Checking NFT ownership...")
    
    # Check NFT ownership
    has_nft = await check_nft_ownership(wallet_address)
    await save_user_data(user_id, user_data[1], wallet_address, has_nft)
    
    if has_nft:
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="Join Group", url=GROUP_INVITE_LINK)]
        ])
        await message.answer(
            "🎉 Congratulations! Your wallet is verified and your tonfans NFT ownership confirmed.\n"
            "You can now join our exclusive group:",
            reply_markup=keyboard
        )
        await notify_admin(f"✅ *NFT Verification Successful:*\n"
                         f"User: @{username}\n"
                         f"ID: `{user_id}`\n"
                         f"Wallet: `{wallet_address}`")
    else:
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="Buy NFT", url=NFT_MARKETPLACE_LINK)]
        ])
        await message.answer(
            "✅ Wallet verified but no NFT found in your wallet.\n"
            "To join our group, you need to own at least one NFT from our collection.\n"
            "You can get one here:",
            reply_markup=keyboard
        )
        await notify_admin(f"❌ *No NFT Found:*\n"
                         f"User: @{username}\n"
                         f"ID: `{user_id}`\n"
                         f"Wallet: `{wallet_address}`")
    
    await state.clear()

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
                report += "\n\n⚠️ Database has been updated with new NFT status"
            
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
        report = "❌ No NFT holders found in database!"
    
    await message.answer(report)

# Periodic verification system
async def verify_all_members():
    conn = sqlite3.connect('members.db')
    cursor = conn.cursor()
    cursor.execute('SELECT user_id, username, wallet_address FROM members')
    members = cursor.fetchall()
    conn.close()
    
    removed_members = []
    for user_id, username, wallet_address in members:
        has_nft = await check_nft_ownership(wallet_address)
        
        if not has_nft:
            removed_members.append((username or "Unknown", wallet_address))
            try:
                # Notify user about removal
                await bot.send_message(
                    user_id,
                    "⚠️ You have been removed from the group because you no longer hold the required NFT. "
                    "You can rejoin after acquiring a new NFT from our collection."
                )
                # Kick user from group (requires bot to be admin)
                try:
                    chat_id = GROUP_INVITE_LINK.split('/')[-1]  # Extract chat ID from invite link
                    await bot.ban_chat_member(chat_id, user_id)
                except Exception as e:
                    logger.error(f"Failed to kick user {user_id}: {e}")
            except Exception as e:
                logger.error(f"Failed to notify user {user_id}: {e}")
        
        await save_user_data(user_id, username, wallet_address, has_nft)
    
    if removed_members:
        report = "🚨 Members removed (no longer hold NFT):\n\n"
        for username, wallet in removed_members:
            report += f"• @{username}\n  Wallet: {wallet}\n\n"
        await notify_admin(report)

# Scheduled verification task
async def scheduled_check():
    while True:
        now = datetime.now().time()
        # Check at 00:00 and 12:00
        if now.hour in [0, 12] and now.minute == 0:
            logger.info("Starting scheduled NFT verification")
            await verify_all_members()
            await asyncio.sleep(3600)  # Sleep for an hour after check
        await asyncio.sleep(30)

# Main function
async def main():
    print("Starting NFT Checker Bot...")
    setup_database()

    # Start periodic checks
    asyncio.create_task(scheduled_check())
    
    try:
        await dp.start_polling(bot)
    except Exception as e:
        logger.error(f"Error: {e}")
    finally:
        await bot.session.close()

if __name__ == '__main__':
    asyncio.run(main())