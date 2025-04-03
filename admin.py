from aiogram import Bot, Dispatcher, types
from aiogram.types import (
    Message, 
    CallbackQuery,
    InlineKeyboardMarkup, 
    InlineKeyboardButton
)
from aiogram.filters import Command
from datetime import datetime, timezone
import sqlite3
import asyncio
import logging
from ton_utils import check_token_balance, SHIVA_TOKEN_ADDRESS

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Admin Configuration
ADMIN_IDS = ["1499577590", "5851290427"]
GROUP_ID = -1002476568928
WHALE_THRESHOLD = 10_000_000

# Admin Messages
MESSAGES = {
    'admin_help': """🛠 *Admin Commands*

*User Management:*
/search [username] - Search for a user
/kick [user_id] - Kick user from group

*Member Management:*
/add - Add members manually
/mem - List NFT holders
/to_kick - List users without NFTs

*Group Management:*
/sendMessage [text] - Send message to group
/broadcast [text] - Send message to all users

*Statistics:*
/stats - Show bot statistics
/admin - Show this help message"""
}

class AdminCommands:
    def __init__(self, bot: Bot):
        self.bot = bot

    async def is_admin(self, user_id: int) -> bool:
        """Check if user is admin."""
        return str(user_id) in ADMIN_IDS

    async def notify_admins(self, message: str, exclude_admin: int = None):
        """Send notification to all admins except the specified one."""
        for admin_id in ADMIN_IDS:
            if exclude_admin and str(admin_id) == str(exclude_admin):
                continue
            try:
                await self.bot.send_message(
                    chat_id=admin_id,
                    text=message,
                    parse_mode="Markdown"
                )
            except Exception as e:
                logger.error(f"Failed to notify admin {admin_id}: {e}")

    async def search_user(self, message: Message):
        """Search for a user in the database."""
        if not await self.is_admin(message.from_user.id):
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
            
            # Format last checked time
            last_checked_str = datetime.fromisoformat(last_checked).strftime("%Y-%m-%d %H:%M:%S") if last_checked else "Never"
            
            report = (
                f"👤 *User Information*\n\n"
                f"*Username:* @{username}\n"
                f"*User ID:* `{user_id}`\n"
                f"*Wallet:* `{wallet_address}`\n"
                f"*Has NFT:* {'✅' if has_nft else '❌'}\n"
                f"*Last Checked:* {last_checked_str}\n"
            )
            
            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🚫 Kick User", callback_data=f"kick_{user_id}")]
            ])
            
            await message.answer(report, parse_mode="Markdown", reply_markup=keyboard)

    async def kick_member(self, message: Message):
        """Kick a member from the group and remove from database."""
        if not await self.is_admin(message.from_user.id):
            return

        try:
            user_id = int(message.text.split()[1])
            
            # First kick from group
            await self.bot.ban_chat_member(GROUP_ID, user_id)
            
            # Then remove from database
            conn = sqlite3.connect('members.db')
            cursor = conn.cursor()
            cursor.execute('DELETE FROM members WHERE user_id = ?', (user_id,))
            rows_affected = cursor.rowcount
            conn.commit()
            conn.close()
            
            status = "✅ User has been kicked from group"
            if rows_affected > 0:
                status += " and removed from database"
            
            await message.reply(f"{status}.")
            await self.notify_admins(
                f"👢 Admin @{message.from_user.username} kicked user {user_id}",
                exclude_admin=message.from_user.id
            )
        except ValueError:
            await message.reply("❌ Invalid user ID format. Usage: /kick [user_id]")
        except Exception as e:
            await message.reply(f"❌ Failed to kick user: {str(e)}")
            
    async def list_whales(self, message: Message):
        """Lists users who qualify as whales based on SHIVA balance."""
        if not await self.is_admin(message.from_user.id):
            return

        # --- Check if required function/constant was imported correctly ---
        local_check_token_balance = None
        local_shiva_token_address = None
        try:
            from bot import check_token_balance as ctb, SHIVA_TOKEN_ADDRESS as sta
            local_check_token_balance = ctb
            local_shiva_token_address = sta
            if not local_shiva_token_address or not callable(local_check_token_balance):
                 raise ImportError("Required components not loaded correctly.")
            logger.info("Using check_token_balance/SHIVA_TOKEN_ADDRESS from bot.py.")
        except ImportError as e:
            await message.reply(f"❌ Critical error: Cannot access balance checking components ({e}). Please check bot logs.")
            logger.error(f"list_whales: Failed to load check_token_balance or SHIVA_TOKEN_ADDRESS. Error: {e}")
            return
        # --- End Check ---

        msg = await message.reply(f"🔍 Fetching whale list (>= {WHALE_THRESHOLD:,.0f} $SHIVA). This may take some time...")

        conn = sqlite3.connect('members.db')
        cursor = conn.cursor()
        cursor.execute('SELECT user_id, username, wallet_address FROM members WHERE wallet_address IS NOT NULL AND wallet_address != ""')
        potential_whales = cursor.fetchall()
        conn.close()

        if not potential_whales:
            await msg.edit_text("❌ No users with registered wallets found in the database.")
            return

        whales_found = []
        checked_count = 0
        total_to_check = len(potential_whales)
        # Use timezone.utc for aware datetime
        start_time = datetime.now(timezone.utc) # Get start time as aware
        last_edit_time = start_time

        for user_id, username, wallet_address in potential_whales:
            checked_count += 1
            if not isinstance(wallet_address, str) or not (wallet_address.startswith('EQ') or wallet_address.startswith('UQ')):
                logger.warning(f"Skipping invalid wallet format for user {user_id} ('{wallet_address}') during whale check.")
                continue

            logger.debug(f"Checking whale status for @{username or user_id} ({wallet_address})...")
            try:
                raw_balance, formatted_balance, _ = await local_check_token_balance(wallet_address, local_shiva_token_address)

                if formatted_balance >= WHALE_THRESHOLD:
                    whales_found.append({
                        'user_id': user_id,
                        'username': username,
                        'wallet': wallet_address,
                        'balance': formatted_balance
                    })
                    logger.info(f"Whale found: @{username or user_id} ({formatted_balance:,.2f} SHIVA)")

                # --- Progress Update Logic ---
                # Use timezone.utc for aware datetime
                now = datetime.now(timezone.utc)
                if checked_count % 25 == 0 or (now - last_edit_time).total_seconds() > 5:
                     # Use the aware start_time for total elapsed calculation
                    elapsed = (now - start_time).total_seconds()
                    progress_text = (
                        f"🔍 Checked {checked_count}/{total_to_check} users...\n"
                        f"{len(whales_found)} whales found so far.\n"
                        f"({elapsed:.1f}s elapsed)"
                    )
                    try:
                        if (now - last_edit_time).total_seconds() > 1.5:
                             await msg.edit_text(progress_text)
                             last_edit_time = now # Update last edit time
                    except Exception as edit_err:
                        logger.warning(f"Could not edit progress message: {edit_err}")
                # --- End Progress Update ---

                await asyncio.sleep(0.25)

            except Exception as e:
                logger.error(f"Error checking balance for {wallet_address} (@{username or user_id}): {e}")
                await asyncio.sleep(0.5)

        # Final results processing
        # Use timezone.utc for aware datetime
        # The original error occurred here:
        final_now = datetime.now(timezone.utc)
        # msg.date is already aware (from Telegram)
        duration = (final_now - msg.date).total_seconds() # Now subtracting aware from aware
        final_message = f"✅ Finished checking {total_to_check} users in {duration:.2f} seconds.\n\n"

        if not whales_found:
            final_message += f"❌ No users found holding {WHALE_THRESHOLD:,.0f} $SHIVA or more."
            await msg.edit_text(final_message)
            return

        whales_found.sort(key=lambda x: x['balance'], reverse=True)

        response_lines = [f"🐳 *Whale List* ({len(whales_found)} found, >= {WHALE_THRESHOLD:,.0f} $SHIVA)\n"]
        for i, whale in enumerate(whales_found, 1):
            display_name = f"@{whale['username']}" if whale['username'] else f"User ID: `{whale['user_id']}`"
            response_lines.append(f"{i}. {display_name} - **{whale['balance']:,.2f}** $SHIVA\n  `{whale['wallet']}`")

        full_response = "\n".join(response_lines)

        if len(final_message) + len(full_response) > 4096:
             allowed_list_len = 4096 - len(final_message) - 50
             truncated_list = full_response[:allowed_list_len]
             last_newline = truncated_list.rfind('\n')
             if last_newline > 0:
                  truncated_list = truncated_list[:last_newline]
             final_message += "⚠️ Whale list is too long. Showing top portion:\n\n" + truncated_list + "\n..."
             await msg.edit_text(final_message, parse_mode="Markdown")
        else:
             final_message += full_response
             await msg.edit_text(final_message, parse_mode="Markdown")

    async def add_members(self, message: Message):
        """Add new members manually."""
        if not await self.is_admin(message.from_user.id):
            return

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

        members_to_add = []
        current_member = {}
        success_count = 0
        failed_members = []

        for line in lines[1:]:
            line = line.strip()
            if not line:
                continue

            if ':' in line:
                key, value = [x.strip() for x in line.split(':', 1)]
                
                if 'Username' in key:
                    if current_member and len(current_member) == 3:
                        members_to_add.append(current_member)
                        current_member = {}
                    value = value.replace('@', '')
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

        if current_member and len(current_member) == 3:
            members_to_add.append(current_member)

        conn = sqlite3.connect('members.db')
        cursor = conn.cursor()
        
        for member in members_to_add:
            if not (member['wallet'].startswith('EQ') or member['wallet'].startswith('UQ')):
                failed_members.append(f"Invalid wallet format for @{member['username']}")
                continue
                
            try:
                cursor.execute('''
                    INSERT OR REPLACE INTO members 
                    (user_id, username, wallet_address)
                    VALUES (?, ?, ?)
                ''', (member['user_id'], member['username'], member['wallet']))
                success_count += 1
            except Exception as e:
                failed_members.append(f"Error adding @{member['username']}: {str(e)}")
                
        conn.commit()
        conn.close()

        response = []
        if success_count > 0:
            response.append(f"✅ Successfully added {success_count} member{'s' if success_count > 1 else ''}")
        if failed_members:
            response.append("\n❌ Failed entries:")
            response.extend(failed_members)
        if not response:
            response.append("❌ No valid members to add")

        await message.answer('\n'.join(response))

    async def list_nft_holders(self, message: Message):
        """List all NFT holders."""
        if not await self.is_admin(message.from_user.id):
            return

        conn = sqlite3.connect('members.db')
        cursor = conn.cursor()
        cursor.execute('SELECT username, wallet_address FROM members WHERE has_nft = 1')
        holders = cursor.fetchall()
        conn.close()

        if not holders:
            await message.reply("❌ No NFT holders found in database!")
            return

        response = "💎 *Current NFT Holders:*\n\n"
        for username, wallet in holders:
            response += f"• @{username}\n  `{wallet}`\n\n"

        await message.reply(response, parse_mode="Markdown")

    async def check_to_kick(self, message: Message):
        """List users without NFTs."""
        if not await self.is_admin(message.from_user.id):
            return

        conn = sqlite3.connect('members.db')
        cursor = conn.cursor()
        cursor.execute('SELECT username, wallet_address, user_id FROM members WHERE has_nft = 0')
        non_holders = cursor.fetchall()
        conn.close()

        if not non_holders:
            await message.reply("✅ All users currently hold NFTs!")
            return

        response = "🚫 *Users without NFTs:*\n\n"
        for username, wallet, user_id in non_holders:
            response += f"• @{username}\n  ID: `{user_id}`\n  Wallet: `{wallet}`\n\n"

        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🚫 Kick All Listed Users", callback_data="kick_all_non_holders")]
        ])

        await message.reply(response, parse_mode="Markdown", reply_markup=keyboard)

    async def send_group_message(self, message: Message):
        """Send a message to the group."""
        if not await self.is_admin(message.from_user.id):
            return

        content = message.text.replace("/sendMessage", "", 1).strip()
        if not content:
            await message.reply("❌ Please provide a message to send: /sendMessage your text here")
            return

        try:
            await self.bot.send_message(GROUP_ID, content)
            await message.reply("✅ Message sent successfully!")
            await self.notify_admins(
                f"📢 Admin @{message.from_user.username} sent group message:\n\n{content}",
                exclude_admin=message.from_user.id
            )
        except Exception as e:
            await message.reply(f"❌ Error sending message: {str(e)}")

    async def broadcast_message(self, message: Message):
        """Send a message to all users."""
        if not await self.is_admin(message.from_user.id):
            return

        content = message.text.replace("/broadcast", "", 1).strip()
        if not content:
            await message.reply("❌ Please provide a message to broadcast")
            return

        conn = sqlite3.connect('members.db')
        cursor = conn.cursor()
        cursor.execute('SELECT user_id FROM members')
        users = cursor.fetchall()
        conn.close()

        success = 0
        failed = 0

        for user_id in users:
            try:
                await self.bot.send_message(user_id[0], content)
                success += 1
            except Exception:
                failed += 1

        status = f"📢 *Broadcast Complete*\n✅ Sent: {success}\n❌ Failed: {failed}"
        await message.reply(status, parse_mode="Markdown")
        await self.notify_admins(
            f"📢 Admin @{message.from_user.username} sent broadcast:\n\n{content}\n\n{status}",
            exclude_admin=message.from_user.id
        )

    async def show_stats(self, message: Message):
        """Show bot statistics."""
        if not await self.is_admin(message.from_user.id):
            return

        conn = sqlite3.connect('members.db')
        cursor = conn.cursor()
        
        # Get total users
        cursor.execute('SELECT COUNT(*) FROM members')
        total_users = cursor.fetchone()[0]
        
        # Get NFT holders
        cursor.execute('SELECT COUNT(*) FROM members WHERE has_nft = 1')
        nft_holders = cursor.fetchone()[0]
        
        # Get users with wallets
        cursor.execute('SELECT COUNT(*) FROM members WHERE wallet_address IS NOT NULL')
        users_with_wallet = cursor.fetchone()[0]
        
        conn.close()

        stats = f"""📊 *Bot Statistics*

*Users:*
Total Users: {total_users:,}
Users with Wallet: {users_with_wallet:,}
NFT Holders: {nft_holders:,}

*Rates:*
Wallet Registration: {(users_with_wallet/total_users*100 if total_users > 0 else 0):.1f}%
NFT Ownership: {(nft_holders/users_with_wallet*100 if users_with_wallet > 0 else 0):.1f}%"""

        await message.reply(stats, parse_mode="Markdown")

    async def admin_help(self, message: Message):
        """Show admin help message."""
        if not await self.is_admin(message.from_user.id):
            return

        await message.reply(MESSAGES['admin_help'], parse_mode="Markdown")

def register_admin_handlers(dp: Dispatcher, admin_commands: AdminCommands):
    """Register all admin command handlers."""
    dp.message.register(admin_commands.search_user, Command('search'))
    dp.message.register(admin_commands.kick_member, Command('kick'))
    dp.message.register(admin_commands.add_members, Command('add'))
    dp.message.register(admin_commands.list_nft_holders, Command('mem'))
    dp.message.register(admin_commands.check_to_kick, Command('to_kick'))
    dp.message.register(admin_commands.list_whales, Command('list_whales')) # <-- ADD THIS LINE
    dp.message.register(admin_commands.send_group_message, Command('sendMessage'))
    dp.message.register(admin_commands.broadcast_message, Command('broadcast'))
    dp.message.register(admin_commands.show_stats, Command('stats'))
    dp.message.register(admin_commands.admin_help, Command('admin'))
    # If you add the callback handler for kick_all_non_holders, register it here too
    # dp.callback_query.register(admin_commands.handle_kick_all_callback, F.data.startswith("kick_all_non_holders:"))
