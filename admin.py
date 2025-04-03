# --- START OF FILE admin.py ---

import asyncio # Needed for sleep
from aiogram import Bot, Dispatcher, types
from aiogram.types import (
    Message,
    CallbackQuery,
    InlineKeyboardMarkup,
    InlineKeyboardButton
)
from aiogram.filters import Command
from datetime import datetime
import sqlite3
import logging

# Import from the new utility file
from ton_utils import check_token_balance, SHIVA_TOKEN_ADDRESS # Make sure ton_utils.py is in the same directory orPYTHONPATH

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Admin Configuration
ADMIN_IDS = ["1499577590", "5851290427"]
GROUP_ID = -1002476568928
WHALE_THRESHOLD = 10_000_000 # 10 Million SHIVA

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
/list_whales - List users qualifying as whales (>= 10M $SHIVA)

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
            user_id_to_kick = int(message.text.split()[1]) # Renamed variable

            # First kick from group
            try:
                 await self.bot.ban_chat_member(GROUP_ID, user_id_to_kick)
                 kick_status_msg = f"✅ User {user_id_to_kick} kicked from group"
            except Exception as e:
                 kick_status_msg = f"⚠️ Could not kick {user_id_to_kick} from group (maybe not a member?): {e}"
                 logger.warning(f"Failed to kick {user_id_to_kick} from group {GROUP_ID}: {e}")


            # Then remove from database
            conn = sqlite3.connect('members.db')
            cursor = conn.cursor()
            cursor.execute('DELETE FROM members WHERE user_id = ?', (user_id_to_kick,))
            rows_affected = cursor.rowcount
            conn.commit()
            conn.close()

            db_status_msg = ""
            if rows_affected > 0:
                db_status_msg = "and removed from database"
            else:
                 db_status_msg = "but was not found in database"

            await message.reply(f"{kick_status_msg} {db_status_msg}.")
            await self.notify_admins(
                f"👢 Admin @{message.from_user.username} used /kick for user {user_id_to_kick}",
                exclude_admin=message.from_user.id
            )
        except IndexError:
             await message.reply("❌ Please provide a user ID. Usage: /kick [user_id]")
        except ValueError:
            await message.reply("❌ Invalid user ID format. Usage: /kick [user_id]")
        except Exception as e:
            await message.reply(f"❌ Failed to process kick command: {str(e)}")


    async def add_members(self, message: Message):
        """Add new members manually."""
        if not await self.is_admin(message.from_user.id):
            return

        lines = message.text.split('\n')
        if len(lines) <= 1 or not lines[1].strip(): # Check if there's actual data after /add
            await message.answer(
                "❌ Please provide member data in the following format (each member on new lines after /add):\n\n"
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
        failed_entries = [] # Renamed for clarity

        # Process lines starting from the second line
        for line in lines[1:]:
            line = line.strip()
            if not line: # Skip empty lines, signifies end of a member block
                if current_member and len(current_member) == 3:
                    members_to_add.append(current_member)
                current_member = {} # Reset for potential next member
                continue

            if ':' in line:
                key, value = [x.strip() for x in line.split(':', 1)]

                if 'Username' in key:
                    # If username is encountered and current_member is already complete, save previous and start new
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
                        failed_entries.append(f"Invalid User ID format for entry starting with '{line}'. Skipping block.")
                        current_member = {} # Discard this malformed block

        # Add the last member if valid and loop finished
        if current_member and len(current_member) == 3:
            members_to_add.append(current_member)

        if not members_to_add and not failed_entries:
             await message.answer("❌ No valid member entries found in the provided format.")
             return

        conn = sqlite3.connect('members.db')
        cursor = conn.cursor()

        for member in members_to_add:
            # Add wallet format validation
            if not (isinstance(member.get('wallet'), str) and (member['wallet'].startswith('EQ') or member['wallet'].startswith('UQ'))):
                failed_entries.append(f"Invalid or missing wallet format for @{member.get('username', 'Unknown')}. Entry skipped.")
                continue

            try:
                # Use INSERT OR REPLACE to handle existing users potentially being updated
                cursor.execute('''
                    INSERT OR REPLACE INTO members
                    (user_id, username, wallet_address, last_checked, has_nft, verification_memo)
                    VALUES (?, ?, ?, ?, COALESCE((SELECT has_nft FROM members WHERE user_id = ?), 0), COALESCE((SELECT verification_memo FROM members WHERE user_id = ?), NULL))
                ''', (member['user_id'], member['username'], member['wallet'], datetime.now().isoformat(), member['user_id'], member['user_id']))
                # Note: We preserve existing has_nft and memo status on replace, setting last_checked
                success_count += 1
            except sqlite3.Error as e:
                failed_entries.append(f"DB Error adding @{member.get('username', 'Unknown')} (ID: {member.get('user_id', 'N/A')}): {str(e)}")
            except Exception as e:
                 failed_entries.append(f"Unexpected error adding @{member.get('username', 'Unknown')}: {str(e)}")


        conn.commit()
        conn.close()

        response_parts = [] # Renamed for clarity
        if success_count > 0:
            response_parts.append(f"✅ Successfully added or updated {success_count} member{'s' if success_count > 1 else ''}.")
        if failed_entries:
            response_parts.append("\n❌ Failed or skipped entries:")
            response_parts.extend(failed_entries)
        if not response_parts:
            # This case should ideally not happen if validation above works, but as a fallback:
            response_parts.append("No actions performed. Check input format.")

        await message.answer('\n'.join(response_parts))
        if success_count > 0:
             await self.notify_admins(
                 f"✍️ Admin @{message.from_user.username} added/updated {success_count} members manually.",
                 exclude_admin=message.from_user.id
             )

    async def list_nft_holders(self, message: Message):
        """List all NFT holders."""
        if not await self.is_admin(message.from_user.id):
            return

        conn = sqlite3.connect('members.db')
        cursor = conn.cursor()
        # Ensure wallet_address is not NULL if needed for display
        cursor.execute('SELECT username, wallet_address FROM members WHERE has_nft = 1 AND wallet_address IS NOT NULL')
        holders = cursor.fetchall()
        conn.close()

        if not holders:
            await message.reply("❌ No NFT holders found in database!")
            return

        response = "💎 *Current NFT Holders:*\n\n"
        output_lines = []
        for username, wallet in holders:
            output_lines.append(f"• @{username}\n  `{wallet}`")

        # Join with double newline for spacing
        response += "\n\n".join(output_lines)

        # Handle potentially long messages (Telegram limit is 4096 chars)
        if len(response) > 4096:
             await message.reply("⚠️ Holder list is too long to display fully. Showing first part.")
             await message.reply(response[:4090] + "\n...", parse_mode="Markdown") # Truncate safely
        else:
             await message.reply(response, parse_mode="Markdown")

    async def check_to_kick(self, message: Message):
        """List users without NFTs."""
        if not await self.is_admin(message.from_user.id):
            return

        conn = sqlite3.connect('members.db')
        cursor = conn.cursor()
        # Select users who have registered a wallet but don't have an NFT
        cursor.execute('SELECT username, wallet_address, user_id FROM members WHERE has_nft = 0 AND wallet_address IS NOT NULL')
        non_holders = cursor.fetchall()
        conn.close()

        if not non_holders:
            await message.reply("✅ All registered users with wallets currently hold NFTs!")
            return

        response = "🚫 *Users without NFTs (candidates for kicking):*\n\n"
        output_lines = []
        user_ids_to_kick = []
        for username, wallet, user_id in non_holders:
            output_lines.append(f"• @{username}\n  ID: `{user_id}`\n  Wallet: `{wallet}`")
            user_ids_to_kick.append(str(user_id)) # Collect IDs for potential bulk kick

        response += "\n\n".join(output_lines)

        # Create comma-separated string of user IDs for the callback data
        user_ids_str = ",".join(user_ids_to_kick)

        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            # Pass the list of IDs in the callback data (might get long)
            [InlineKeyboardButton(text=f"🚫 Kick All {len(non_holders)} Listed Users", callback_data=f"kick_all_non_holders:{user_ids_str}")]
        ])

        if len(response) > 4096:
             await message.reply("⚠️ List of users without NFTs is too long. Showing first part.")
             # Only show button if the message isn't truncated? Or adjust callback data limit?
             # For now, show button but warn about potential callback data limits if list is huge.
             await message.reply(response[:4050] + "\n...", parse_mode="Markdown", reply_markup=keyboard)
        else:
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
            await self.bot.send_message(GROUP_ID, content, parse_mode="Markdown") # Allow markdown
            await message.reply("✅ Message sent successfully to the group!")
            await self.notify_admins(
                f"📢 Admin @{message.from_user.username} sent group message:\n\n{content}",
                exclude_admin=message.from_user.id
            )
        except Exception as e:
            await message.reply(f"❌ Error sending message to group {GROUP_ID}: {str(e)}")
            logger.error(f"Failed sending group message by @{message.from_user.username}: {e}")

    async def broadcast_message(self, message: Message):
        """Send a message to all users in the database."""
        if not await self.is_admin(message.from_user.id):
            return

        content = message.text.replace("/broadcast", "", 1).strip()
        if not content:
            await message.reply("❌ Please provide a message to broadcast: /broadcast your text here")
            return

        conn = sqlite3.connect('members.db')
        cursor = conn.cursor()
        cursor.execute('SELECT user_id FROM members')
        users = cursor.fetchall()
        conn.close()

        if not users:
             await message.reply("❌ No users found in the database to broadcast to.")
             return

        await message.reply(f"📢 Starting broadcast to {len(users)} users... This may take time.")

        success = 0
        failed = 0
        start_time = datetime.now()

        for user_tuple in users:
            user_id = user_tuple[0]
            try:
                await self.bot.send_message(user_id, content, parse_mode="Markdown") # Allow markdown
                success += 1
            except Exception as e:
                logger.warning(f"Broadcast failed for user {user_id}: {e}")
                failed += 1
            await asyncio.sleep(0.1) # Basic rate limiting (adjust as needed)

        end_time = datetime.now()
        duration = end_time - start_time

        status = (f"📢 *Broadcast Complete*\n\n"
                  f"Sent to {len(users)} users in {duration.total_seconds():.2f} seconds.\n"
                  f"✅ Successful: {success}\n"
                  f"❌ Failed: {failed}")

        await message.reply(status, parse_mode="Markdown")
        await self.notify_admins(
            f"📢 Admin @{message.from_user.username} completed broadcast:\n\n{content}\n\n{status}",
            exclude_admin=message.from_user.id
        )

    async def show_stats(self, message: Message):
        """Show bot statistics."""
        if not await self.is_admin(message.from_user.id):
            return

        conn = sqlite3.connect('members.db')
        cursor = conn.cursor()

        try:
            # Get total users
            cursor.execute('SELECT COUNT(*) FROM members')
            total_users = cursor.fetchone()[0]

            # Get NFT holders
            cursor.execute('SELECT COUNT(*) FROM members WHERE has_nft = 1')
            nft_holders = cursor.fetchone()[0]

            # Get users with wallets (non-null wallet address)
            cursor.execute('SELECT COUNT(*) FROM members WHERE wallet_address IS NOT NULL')
            users_with_wallet = cursor.fetchone()[0]

        except sqlite3.Error as e:
             await message.reply(f"❌ Database error fetching stats: {e}")
             logger.error(f"Stats DB error: {e}")
             conn.close()
             return
        finally:
            conn.close() # Ensure connection is closed


        stats = f"""📊 *Bot Statistics*

*Users:*
Total Users: {total_users:,}
Users with Wallet: {users_with_wallet:,}
NFT Holders: {nft_holders:,}
Users w/o NFT (w/ Wallet): {users_with_wallet - nft_holders:,}

*Rates:*
Wallet Registration Rate: {(users_with_wallet/total_users*100 if total_users > 0 else 0):.1f}%
NFT Ownership Rate (among wallet users): {(nft_holders/users_with_wallet*100 if users_with_wallet > 0 else 0):.1f}%"""

        await message.reply(stats, parse_mode="Markdown")

    # --- NEW COMMAND ---
    async def list_whales(self, message: Message):
        """Lists users who qualify as whales based on SHIVA balance."""
        if not await self.is_admin(message.from_user.id):
            return

        await message.reply(f"🔍 Fetching whale list (>= {WHALE_THRESHOLD:,.0f} $SHIVA). This might take a while...")

        conn = sqlite3.connect('members.db')
        cursor = conn.cursor()
        # Select users who have a registered wallet
        cursor.execute('SELECT user_id, username, wallet_address FROM members WHERE wallet_address IS NOT NULL')
        potential_whales = cursor.fetchall()
        conn.close()

        if not potential_whales:
            await message.reply("❌ No users with registered wallets found in the database.")
            return

        whales_found = []
        checked_count = 0
        start_time = datetime.now()

        for user_id, username, wallet_address in potential_whales:
            checked_count += 1
            logger.debug(f"Checking whale status for @{username} ({wallet_address})...")
            try:
                # Use the imported function
                raw_balance, formatted_balance, _ = await check_token_balance(wallet_address, SHIVA_TOKEN_ADDRESS)

                if formatted_balance >= WHALE_THRESHOLD:
                    whales_found.append({
                        'username': username,
                        'wallet': wallet_address,
                        'balance': formatted_balance
                    })
                    logger.info(f"Whale found: @{username} ({formatted_balance:,.2f} SHIVA)")

                # Progress update for long lists
                if checked_count % 25 == 0:
                     elapsed = (datetime.now() - start_time).total_seconds()
                     await message.edit_text(f"🔍 Checked {checked_count}/{len(potential_whales)} users... {len(whales_found)} whales so far. ({elapsed:.1f}s elapsed)")

                await asyncio.sleep(0.2) # Rate limit API calls slightly

            except Exception as e:
                logger.error(f"Error checking balance for {wallet_address} (@{username}): {e}")
                await asyncio.sleep(0.5) # Longer sleep on error


        end_time = datetime.now()
        duration = end_time - start_time
        final_message = f"Finished checking {len(potential_whales)} users in {duration.total_seconds():.2f} seconds.\n\n"

        if not whales_found:
            final_message += f"❌ No users found holding {WHALE_THRESHOLD:,.0f} $SHIVA or more."
            await message.edit_text(final_message) # Edit the "Fetching..." message
            return

        # Sort whales by balance, descending
        whales_found.sort(key=lambda x: x['balance'], reverse=True)

        response_lines = [f"🐳 *Whale List* ({len(whales_found)} found, >= {WHALE_THRESHOLD:,.0f} $SHIVA)\n"]
        for whale in whales_found:
            response_lines.append(f"• @{whale['username']} - **{whale['balance']:,.2f}** $SHIVA\n  `{whale['wallet']}`")

        full_response = "\n".join(response_lines) # Use single newline between entries for compactness


        # Handle potentially long messages
        if len(full_response) > 4096:
             final_message += "⚠️ Whale list is too long to display fully. Showing top portion.\n\n" + full_response[:4000] + "\n..." # Truncate
        else:
             final_message += full_response

        await message.edit_text(final_message, parse_mode="Markdown") # Edit the "Fetching..." message

    # --- END OF NEW COMMAND ---

    async def admin_help(self, message: Message):
        """Show admin help message."""
        if not await self.is_admin(message.from_user.id):
            return

        await message.reply(MESSAGES['admin_help'], parse_mode="Markdown")

# --- Updated Registration Function ---
def register_admin_handlers(dp: Dispatcher, admin_commands: AdminCommands):
    """Register all admin command handlers."""
    dp.message.register(admin_commands.search_user, Command('search'))
    dp.message.register(admin_commands.kick_member, Command('kick'))
    dp.message.register(admin_commands.add_members, Command('add'))
    dp.message.register(admin_commands.list_nft_holders, Command('mem'))
    dp.message.register(admin_commands.check_to_kick, Command('to_kick'))
    dp.message.register(admin_commands.list_whales, Command('list_whales')) # Register new command
    dp.message.register(admin_commands.send_group_message, Command('sendMessage'))
    dp.message.register(admin_commands.broadcast_message, Command('broadcast'))
    dp.message.register(admin_commands.show_stats, Command('stats'))
    dp.message.register(admin_commands.admin_help, Command('admin'))
    # Add handler for the kick_all_non_holders callback if not already present elsewhere
    # dp.callback_query.register(admin_commands.handle_kick_all_callback, F.data.startswith("kick_all_non_holders:"))

# --- END OF FILE admin.py ---
