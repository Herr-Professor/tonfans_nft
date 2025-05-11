# --- START OF FILE admin.py ---

from aiogram import Bot, Dispatcher, types
from aiogram.types import (
    Message,
    CallbackQuery,
    InlineKeyboardMarkup,
    InlineKeyboardButton
)
from aiogram.filters import Command
from datetime import datetime, timezone
import asyncio
import logging
import aiosqlite
from ton_utils import (
    check_token_balance,
    check_nft_ownership,
    # escape_md is primarily for MarkdownV2, less needed for Markdown
    escape_md, # Keep it available for potential use on user input if needed
    SHIVA_TOKEN_ADDRESS,
    ADMIN_IDS,
    GROUP_ID,
    NFT_MARKETPLACE_LINK,
    GROUP_INVITE_LINK,
    SHIVA_DEX_LINK
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Admin Configuration
WHALE_THRESHOLD = 10_000_000
VERIFICATION_SHIVA_THRESHOLD = 250_000

# Admin Messages (Using Markdown syntax)
MESSAGES = {
    'admin_help': """🛠 *Admin Commands*

*User Management:*
`/search [username]` - Search for a user
`/kick [user_id]` - Kick user from group

*Member Management:*
`/add` - Add members manually
`/mem` - List users marked as verified in DB
`/list_failing` or `/to_kick` - List users failing requirements (Live Check)
`/update_status` or `/update` - Update DB status based on live checks (NFT & SHIVA)
`/list_whales` - List users with ≥ 10M SHIVA (Live Check)

*Group Management:*
`/sendMessage [text]` - Send message to group
`/broadcast [text]` - Send message to all users

*Statistics:*
`/stats` - Show bot statistics
`/admin` - Show this help message"""
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
                # Use simpler Markdown
                await self.bot.send_message(
                    chat_id=admin_id,
                    text=message, # No need to escape the whole message for basic Markdown
                    parse_mode="Markdown"
                )
            except Exception as e:
                logger.error(f"Failed to notify admin {admin_id}: {e}")

    # --- User Management ---
    async def search_user(self, message: Message):
        """Search for a user in the database."""
        if not await self.is_admin(message.from_user.id): return
        args = message.text.split(maxsplit=1)
        if len(args) < 2:
            await message.answer("❌ Please provide a username to search. Format: `/search username`", parse_mode="Markdown")
            return

        search_username = args[1].replace('@', '')

        async with aiosqlite.connect('members.db') as conn:
            cursor = await conn.execute('SELECT user_id, username, wallet_address, last_checked, has_nft FROM members WHERE username LIKE ?', (f"%{search_username}%",))
            results = await cursor.fetchall()

        if not results:
            # Use backticks for username for code formatting
            await message.answer(f"❌ No users found matching username `{search_username}`", parse_mode="Markdown")
            return

        for user_id, username, wallet_address, last_checked, has_nft_db in results:
            last_checked_str = datetime.fromisoformat(last_checked).strftime("%Y-%m-%d %H:%M:%S UTC") if last_checked else "Never"
            # Basic Markdown formatting
            report = (
                f"👤 *User Information*\n\n"
                f"*Username:* @{username or 'N/A'}\n" # Keep @ for mentions
                f"*User ID:* `{user_id}`\n" # Use backticks for code
                f"*Wallet:* `{wallet_address or 'N/A'}`\n"
                f"*Verified in DB:* {'✅' if has_nft_db else '❌'} (Based on last check)\n"
                f"*Last Checked:* {last_checked_str}\n"
            )
            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🚫 Kick User", callback_data=f"admin_kick_{user_id}")]
            ])
            await message.answer(report, parse_mode="Markdown", reply_markup=keyboard)

    async def handle_admin_kick_callback(self, callback_query: CallbackQuery):
        """Handles the kick button press from admin search."""
        if not await self.is_admin(callback_query.from_user.id):
            await callback_query.answer("Unauthorized", show_alert=True)
            return

        try:
            user_id_to_kick = int(callback_query.data.split('_')[-1])
            await callback_query.message.edit_text(f"Attempting to kick user `{user_id_to_kick}`...", parse_mode="Markdown")

            # Get user info for notification
            username = None
            async with aiosqlite.connect('members.db') as conn:
                cursor = await conn.execute('SELECT username FROM members WHERE user_id = ?', (user_id_to_kick,))
                result = await cursor.fetchone()
                if result:
                    username = result[0]
            
            # Notify user about being kicked
            try:
                notification_msg = f"""❗️ *Group Membership Notice*

You have been removed from the TONFANS group by an admin.

To rejoin the group, please:
1. Ensure you own at least 1 TONFANS NFT
2. Have at least 250,000 SHIVA tokens
3. Reverify using the bot with /start command

If you believe this is a mistake, please reverify your wallet again."""
                
                await self.bot.send_message(
                    chat_id=user_id_to_kick,
                    text=notification_msg,
                    parse_mode="Markdown"
                )
            except Exception as notify_err:
                logger.error(f"Failed to notify user {user_id_to_kick} about admin kick: {notify_err}")

            # Kick the user
            await self.bot.ban_chat_member(GROUP_ID, user_id_to_kick)
            await asyncio.sleep(0.5)
            await self.bot.unban_chat_member(GROUP_ID, user_id_to_kick)

            # Update database - set has_nft to False instead of deleting
            async with aiosqlite.connect('members.db') as conn:
                cursor = await conn.execute('UPDATE members SET has_nft = ? WHERE user_id = ?', (False, user_id_to_kick))
                rows_affected = cursor.rowcount
                await conn.commit()

            status = f"✅ User `{user_id_to_kick}` has been kicked from group"
            if rows_affected > 0: 
                status += " and marked as not verified in database."
            else: 
                status += " but was not found in database."

            await callback_query.message.edit_text(status, parse_mode="Markdown")
            await self.notify_admins(
                f"👢 Admin @{callback_query.from_user.username} kicked user `{user_id_to_kick}` (@{username or 'NoUsername'}) using button.",
                exclude_admin=callback_query.from_user.id
            )
        except Exception as e:
            logger.error(f"Error handling admin kick callback for {callback_query.data}: {e}", exc_info=True)
            await callback_query.message.edit_text(f"❌ Failed to kick user: {str(e)}", parse_mode="Markdown")
        await callback_query.answer()

    async def kick_member_cmd(self, message: Message):
        """Kick a member from the group and remove from database via command."""
        if not await self.is_admin(message.from_user.id): return

        args = message.text.split()
        if len(args) != 2:
             await message.reply("Usage: `/kick <user_id>`", parse_mode="Markdown")
             return

        try:
            user_id = int(args[1])
            
            # Get user info for notification
            username = None
            async with aiosqlite.connect('members.db') as conn:
                cursor = await conn.execute('SELECT username FROM members WHERE user_id = ?', (user_id,))
                result = await cursor.fetchone()
                if result:
                    username = result[0]
            
            # Notify user about being kicked
            try:
                notification_msg = f"""❗️ *Group Membership Notice*

You have been removed from the TONFANS group by an admin.

To rejoin the group, please:
1. Ensure you own at least 1 TONFANS NFT
2. Have at least 250,000 SHIVA tokens
3. Reverify using the bot with /start command

If you believe this is a mistake, please reverify your wallet again."""
                
                await self.bot.send_message(
                    chat_id=user_id,
                    text=notification_msg,
                    parse_mode="Markdown"
                )
            except Exception as notify_err:
                logger.error(f"Failed to notify user {user_id} about admin kick: {notify_err}")
            
            # Kick the user
            await self.bot.ban_chat_member(GROUP_ID, user_id)
            await asyncio.sleep(0.5)
            await self.bot.unban_chat_member(GROUP_ID, user_id)

            # Update database - set has_nft to False instead of deleting
            rows_affected = 0
            async with aiosqlite.connect('members.db') as conn:
                cursor = await conn.execute('UPDATE members SET has_nft = ? WHERE user_id = ?', (False, user_id))
                rows_affected = cursor.rowcount
                await conn.commit()

            status = f"✅ User `{user_id}` has been kicked from group"
            if rows_affected > 0: 
                status += " and marked as not verified in database."
            else: 
                status += " but was not found in database."
                
            await message.reply(status , parse_mode="Markdown")
            await self.notify_admins(
                f"👢 Admin kicked user `{user_id}` (@{username or 'NoUsername'}) via command.",
                exclude_admin=message.from_user.id
            )
        except ValueError:
            await message.reply("❌ Invalid user ID format. Usage: `/kick <user_id>`", parse_mode="Markdown")
        except Exception as e:
            logger.error(f"Error in kick_member_cmd for user {args[1]}: {e}", exc_info=True)
            await message.reply(f"❌ Failed to kick user: {str(e)}", parse_mode="Markdown")

    # --- Member Management ---
    async def add_members(self, message: Message):
        """Add new members manually."""
        if not await self.is_admin(message.from_user.id): return
        lines = message.text.split('\n')
        if len(lines) == 1:
            await message.answer(
                 "❌ Please provide member data in the format:\n\n"
                 "`/add`\n"
                 "`Username: @username1`\n"
                 "`Wallet: WALLET_ADDRESS1`\n"
                 "`User ID: USER_ID1`\n\n"
                 "`Username: @username2`\n"
                 # ... etc
                 , parse_mode="Markdown"
            )
            return

        members_to_add = []
        current_member = {}
        success_count = 0
        failed_entries = []
        successful_adds_details = [] # To list successful ones

        # ... (parsing logic remains largely the same as before) ...
        for line_num, line in enumerate(lines[1:], 2):
            line = line.strip()
            if not line:
                if current_member:
                     if len(current_member) == 3 and 'malformed' not in current_member:
                         members_to_add.append(current_member)
                     elif not current_member.get('malformed'):
                          failed_entries.append(f"Incomplete entry ending line {line_num-1}: {current_member}")
                     current_member = {}
                continue

            if ':' in line:
                key, value = [x.strip() for x in line.split(':', 1)]
                key_lower = key.lower()

                if 'username' in key_lower:
                    if 'username' in current_member:
                         failed_entries.append(f"Missing fields before new Username on line {line_num}: {current_member}")
                         current_member = {}
                    current_member['username'] = value.replace('@', '')
                elif 'wallet' in key_lower:
                    if 'wallet' in current_member:
                        failed_entries.append(f"Duplicate Wallet key on line {line_num} for: {current_member.get('username', 'Unknown')}")
                    else:
                         current_member['wallet'] = value
                elif 'user id' in key_lower:
                     if 'user_id' in current_member:
                         failed_entries.append(f"Duplicate User ID key on line {line_num} for: {current_member.get('username', 'Unknown')}")
                     else:
                        try:
                            current_member['user_id'] = int(value)
                        except ValueError:
                            failed_entries.append(f"Invalid User ID format on line {line_num}: '{value}'")
                            current_member['malformed'] = True
            else:
                 failed_entries.append(f"Invalid format on line {line_num} (missing ':'): '{line}'")
                 if 'username' in current_member:
                     current_member = {}

            if len(current_member) == 3 and 'malformed' not in current_member :
                 members_to_add.append(current_member)
                 current_member = {}

        if current_member:
             if len(current_member) == 3 and 'malformed' not in current_member:
                 members_to_add.append(current_member)
             elif not current_member.get('malformed'):
                  failed_entries.append(f"Incomplete entry at end of input: {current_member}")

        # --- Database Insertion ---
        db_errors = []
        async with aiosqlite.connect('members.db') as conn:
            cursor = await conn.cursor()
            for member in members_to_add:
                if not isinstance(member['wallet'], str) or not (member['wallet'].startswith('EQ') or member['wallet'].startswith('UQ')):
                    failed_entries.append(f"Invalid wallet format for @{member['username']}: `{member['wallet']}`")
                    continue
                if not isinstance(member['user_id'], int):
                     failed_entries.append(f"Internal error: User ID not integer for @{member['username']}")
                     continue

                try:
                    await cursor.execute('''
                        INSERT OR REPLACE INTO members
                        (user_id, username, wallet_address, has_nft, last_checked)
                        VALUES (?, ?, ?, NULL, NULL)
                    ''', (member['user_id'], member['username'], member['wallet']))
                    # Use backticks for User ID
                    successful_adds_details.append(f"@{member['username']} (`{member['user_id']}`)")
                    success_count += 1
                except Exception as e:
                    # Use backticks for username
                    err_msg = f"DB Error adding @{member['username']}: {str(e)}"
                    db_errors.append(err_msg)
                    logger.error(f"Database error adding member {member}: {e}", exc_info=True)

            await conn.commit()

        # --- Response Compilation ---
        response_parts = []
        if success_count > 0:
            response_parts.append(f"✅ Successfully added/updated {success_count} member{'s' if success_count > 1 else ''}:")
            # Join with newline, not comma
            response_parts.append("\n".join([f"• {s}" for s in successful_adds_details]))

        if failed_entries:
            response_parts.append(f"\n\n❌ Failed to parse {len(failed_entries)} entr{'ies' if len(failed_entries) > 1 else 'y'} due to formatting/validation errors:")
            # Format with bullet points
            response_parts.append("\n".join([f"• {e}" for e in failed_entries]))

        if db_errors:
             response_parts.append(f"\n\n❌ Encountered {len(db_errors)} database errors:")
             response_parts.append("\n".join([f"• {e}" for e in db_errors]))


        if not response_parts:
            response_parts.append("No operation performed. Check input format.")

        full_response = "\n".join(response_parts)

        MAX_LEN = 4096
        for i in range(0, len(full_response), MAX_LEN):
             # Use Markdown for sending report chunks
             await message.answer(full_response[i:i+MAX_LEN], parse_mode="Markdown")
             if i + MAX_LEN < len(full_response):
                 await asyncio.sleep(0.5)

    async def list_verified_members(self, message: Message):
        """List members marked as verified (has_nft=1) in the database."""
        if not await self.is_admin(message.from_user.id): return
    
        try:
            async with aiosqlite.connect('members.db') as conn:
                cursor = await conn.execute(
                    'SELECT username, wallet_address FROM members WHERE has_nft = 1 ORDER BY username COLLATE NOCASE'
                )
                holders = await cursor.fetchall()
    
            if not holders:
                await message.reply("❌ No members marked as verified in the database\\.", parse_mode="Markdown")
                return
    
            response = [f"✅ *Verified Members in DB* \\({len(holders)}\\):"]
            for username, wallet in holders:
                escaped_username = escape_md(username or 'NoUsername')
                wallet_code = f"`{wallet or 'NoWallet'}`"
                response.append(f"• @{escaped_username}\n  {wallet_code}")
    
            full_text = "\n\n".join(response)
            MAX_LEN = 4096
            for i in range(0, len(full_text), MAX_LEN):
                await message.reply(full_text[i:i+MAX_LEN], parse_mode="MarkdownV2")
                if i + MAX_LEN < len(full_text):
                    await asyncio.sleep(0.5)
    
        except Exception as e:
            logger.error(f"Error in list_verified_members: {e}", exc_info=True)
            error_msg = f"Error fetching verified members: {str(e)}"
            await message.reply(f"❌ {escape_md(error_msg)}", parse_mode="MarkdownV2")
    
    async def list_failing_users(self, message: Message):
        """Perform LIVE check and list users failing NFT or SHIVA requirements."""
        if not await self.is_admin(message.from_user.id): return
    
        msg = await message.reply("🔄 Starting live check for users failing requirements \\(NFT & SHIVA\\)\\...", parse_mode="Markdown")
    
        users_failing = []
        errors = []
        processed_count = 0
    
        try:
            async with aiosqlite.connect('members.db') as conn:
                cursor = await conn.execute(
                    'SELECT user_id, username, wallet_address FROM members WHERE wallet_address IS NOT NULL AND wallet_address != ""'
                )
                users_to_check = await cursor.fetchall()
    
            total_users = len(users_to_check)
            if not total_users:
                await msg.edit_text("❌ No users with wallets found in database\\.", parse_mode="Markdown")
                return
    
            start_time = datetime.now(timezone.utc)
    
            for index, (user_id, username, wallet) in enumerate(users_to_check, 1):
                if str(user_id) in ADMIN_IDS or str(user_id) == '718025267': continue
                processed_count += 1
                try:
                    has_nft = await check_nft_ownership(wallet)
                    await asyncio.sleep(0.5)
                    _, shiva_balance, _ = await check_token_balance(wallet, SHIVA_TOKEN_ADDRESS)
    
                    meets_requirements = has_nft and shiva_balance >= VERIFICATION_SHIVA_THRESHOLD
    
                    if not meets_requirements:
                        reason_parts = []
                        if not has_nft: reason_parts.append("No NFT")
                        if shiva_balance < VERIFICATION_SHIVA_THRESHOLD: reason_parts.append(f"Low SHIVA \\({shiva_balance:,.0f}\\)")
                        reason = ", ".join(reason_parts) if reason_parts else "Unknown"
    
                        users_failing.append({
                            'id': user_id,
                            'user': username or "NoUsername",
                            'wallet': wallet or "NoWallet",
                            'reason': reason
                        })
    
                    if index % 10 == 0 or (datetime.now(timezone.utc) - start_time).total_seconds() > 15:
                        elapsed = (datetime.now(timezone.utc) - start_time).total_seconds()
                        progress_text = (
                            f"🔄 Checking {index}/{total_users}\n"
                            f"🚫 Found failing: {len(users_failing)}\n"
                            f"⏱ Elapsed: {elapsed:.1f}s"
                        )
                        try:
                            await msg.edit_text(escape_md(progress_text), parse_mode="MarkdownV2")
                        except Exception as edit_err:
                            logger.warning(f"Could not edit progress message: {edit_err}")
    
                except Exception as e:
                    logger.error(f"Error checking user {user_id} ({username}) wallet {wallet}: {e}")
                    errors.append(f"User `{user_id}` (@{username or 'N/A'}): {str(e)}")
                finally:
                    await asyncio.sleep(1.5)
    
            # --- Final Report ---
            duration = (datetime.now(timezone.utc) - start_time).total_seconds()
            report_parts = [f"✅ *Live check complete* Checked {processed_count} users\\."]

            if users_failing:
                report_parts.append(f"\n🚫 Found {len(users_failing)} user{'s' if len(users_failing) > 1 else ''} *failing requirements*:")
                for data in users_failing:
                    escaped_user = escape_md(str(data['user']))
                    wallet_code = f"`{data['wallet']}`"
                    escaped_reason = escape_md(str(data['reason']))
                    report_parts.append(
                        f"\n• @{escaped_user} ID: `{data['id']}`\n"  # Remove parentheses
                        f"  Wallet: {wallet_code}\n"
                        f"  Reason: {escaped_reason}"
                    )
            else:
                report_parts.append("\n✅ All checked users currently meet requirements\\.")

            if errors:
                report_parts.append(f"\n\n⚠️ Encountered {len(errors)} errors during checks:")
                report_parts.extend([f"• {escape_md(str(e))}" for e in errors[:10]])
                if len(errors) > 10: report_parts.append(f"\\.\\.\\. and {len(errors)-10} more errors - see logs")

            full_report = "\n".join(report_parts)
            logger.info(f"Full report: {repr(full_report)}")  # Add debugging

            MAX_LEN = 4096
            if len(full_report) <= MAX_LEN:
                await msg.edit_text(full_report, parse_mode="MarkdownV2")
            else:
                await msg.edit_text(f"✅ Check complete\\. Report is long, sending in parts\\...", parse_mode="MarkdownV2")
                for i in range(0, len(full_report), MAX_LEN):
                    await message.reply(full_report[i:i+MAX_LEN], parse_mode="MarkdownV2")
                    if i + MAX_LEN < len(full_report):
                        await asyncio.sleep(0.5)
    
        except Exception as e:
            logger.error(f"Critical error in list_failing_users: {e}", exc_info=True)
            await msg.edit_text(f"❌ Critical error during check: {escape_md(str(e))}", parse_mode="MarkdownV2")
    
    async def update_verification_status(self, message: Message):
        """Perform LIVE check (NFT & SHIVA) and update DB status (has_nft column)."""
        if not await self.is_admin(message.from_user.id): return

        msg = await message.reply("🔄 Starting live update of verification status (NFT & SHIVA)...")

        updated_verified = 0
        updated_unverified = 0
        errors = []
        processed_count = 0

        try:
            async with aiosqlite.connect('members.db') as conn:
                cursor = await conn.execute(
                    'SELECT user_id, username, wallet_address FROM members WHERE wallet_address IS NOT NULL AND wallet_address != ""'
                )
                users_to_update = await cursor.fetchall()
                total_users = len(users_to_update)

                if not total_users:
                    await msg.edit_text("❌ No users with wallets found in database to update.")
                    return

                start_time = datetime.now(timezone.utc)

                for index, (user_id, username, wallet) in enumerate(users_to_update, 1):
                    processed_count += 1
                    db_status_to_set = 0
                    try:
                        has_nft = await check_nft_ownership(wallet)
                        await asyncio.sleep(0.5)
                        _, shiva_balance, _ = await check_token_balance(wallet, SHIVA_TOKEN_ADDRESS)

                        meets_requirements = has_nft and shiva_balance >= VERIFICATION_SHIVA_THRESHOLD
                        db_status_to_set = 1 if meets_requirements else 0

                        await conn.execute(
                            'UPDATE members SET has_nft = ?, last_checked = CURRENT_TIMESTAMP WHERE user_id = ?',
                            (db_status_to_set, user_id)
                        )
                        await conn.commit()

                        if db_status_to_set == 1: updated_verified += 1
                        else: updated_unverified += 1

                        if index % 10 == 0 or (datetime.now(timezone.utc) - start_time).total_seconds() > 15:
                            elapsed = (datetime.now(timezone.utc) - start_time).total_seconds()
                            progress_text = (
                                f"🔄 Updated {index}/{total_users}...\n"
                                f"✅ Set Verified: {updated_verified}\n"
                                f"❌ Set Unverified: {updated_unverified}\n"
                                f"⏱ Elapsed: {elapsed:.1f}s"
                            )
                            try:
                                await msg.edit_text(progress_text)
                            except Exception as edit_err:
                                logger.warning(f"Could not edit progress message: {edit_err}")

                    except Exception as e:
                        logger.error(f"Error updating status for user {user_id} ({username}) wallet {wallet}: {e}")
                        # Simple error format
                        errors.append(f"User `{user_id}` (@{username or 'N/A'}): Failed ({str(e)})")
                    finally:
                         await asyncio.sleep(1.5)

            # --- Final Report ---
            duration = (datetime.now(timezone.utc) - start_time).total_seconds()
            report_parts = [
                f"✅ *Status update complete* ({duration:.1f}s)!", # Use Markdown
                f"• Checked/Attempted: {processed_count}/{total_users}",
                f"• Set to Verified (✅): {updated_verified}",
                f"• Set to Unverified (❌): {updated_unverified}"
            ]

            if errors:
                report_parts.append(f"\n\n⚠️ Encountered {len(errors)} errors during update:")
                report_parts.extend([f"• {e}" for e in errors[:10]])
                if len(errors) > 10: report_parts.append(f"... and {len(errors)-10} more errors (see logs)")

            # Use Markdown for final report edit
            await msg.edit_text("\n".join(report_parts), parse_mode="Markdown")

        except Exception as e:
            logger.error(f"Critical error in update_verification_status: {e}", exc_info=True)
            # Use Markdown for critical error message
            await msg.edit_text(f"❌ Critical update error: {str(e)}", parse_mode="Markdown")

    # --- Whale Listing ---
    async def list_whales(self, message: Message):
        """Lists users who qualify as whales based on SHIVA balance."""
        if not await self.is_admin(message.from_user.id): return
        # Simple Markdown formatting for threshold
        msg = await message.reply(f"🔍 Fetching whale list (≥ {WHALE_THRESHOLD:,.0f} $SHIVA). This may take time...", parse_mode="Markdown")

        try:
            # ... (database query is the same) ...
            async with aiosqlite.connect('members.db') as conn:
                cursor = await conn.execute(
                    'SELECT user_id, username, wallet_address FROM members WHERE wallet_address IS NOT NULL AND wallet_address != ""'
                )
                potential_whales = await cursor.fetchall()

            if not potential_whales:
                await msg.edit_text("❌ No users with registered wallets found.")
                return

            whales_found = []
            total = len(potential_whales)
            processed_count = 0
            errors = []
            start_time = datetime.now(timezone.utc)

            for index, (user_id, username, wallet) in enumerate(potential_whales, 1):
                 processed_count += 1
                 try:
                    if not isinstance(wallet, str) or not wallet.startswith(('EQ', 'UQ')): continue

                    _, formatted_balance, _ = await check_token_balance(wallet, SHIVA_TOKEN_ADDRESS)

                    if formatted_balance >= WHALE_THRESHOLD:
                        whales_found.append({
                            'user_id': user_id,
                            'username': username or "Anonymous",
                            'wallet': wallet,
                            'balance': formatted_balance
                        })

                    if index % 5 == 0 or (datetime.now(timezone.utc) - start_time).total_seconds() > 10:
                        elapsed = (datetime.now(timezone.utc) - start_time).total_seconds()
                        progress = (
                            f"🔍 Checked {index}/{total} users\n"
                            f"🐳 Found: {len(whales_found)}\n"
                            f"⏱ {elapsed:.1f}s"
                        )
                        try: await msg.edit_text(progress)
                        except Exception as edit_err: logger.warning(f"Could not edit whale progress msg: {edit_err}")

                 except Exception as e:
                    logger.error(f"Error checking whale balance for {wallet}: {str(e)}")
                    # Simple error format
                    errors.append(f"Wallet `{wallet}`: {str(e)}")
                    continue
                 finally: await asyncio.sleep(1.0)

            # --- Compile final results ---
            duration = (datetime.now(timezone.utc) - start_time).total_seconds()
            response_parts = [f"✅ *Checked* {processed_count}/{total} users in {duration:.1f}s"] # Markdown

            if whales_found:
                whales_found.sort(key=lambda x: x['balance'], reverse=True)
                response_parts.append(f"\n🐳 *Top Whales* (≥{WHALE_THRESHOLD:,.0f} $SHIVA):")
                for i, whale in enumerate(whales_found, 1):
                    # Simple Markdown format for balance
                    response_parts.append(f"{i}. @{whale['username']} - {whale['balance']:,.2f} $SHIVA")
            else:
                response_parts.append("\n❌ No whales found meeting the threshold.")

            if errors:
                 response_parts.append(f"\n\n⚠️ Encountered {len(errors)} errors:")
                 response_parts.extend([f"• {e}" for e in errors[:5]])
                 if len(errors) > 5: response_parts.append("... and more.")

            full_response = "\n".join(response_parts)
            MAX_LEN = 4096
            if len(full_response) <= MAX_LEN:
                 await msg.edit_text(full_response, parse_mode="Markdown") # Use Markdown
            else:
                 await msg.edit_text(f"✅ Whale check complete. Report is long, sending in parts...")
                 for i in range(0, len(full_response), MAX_LEN):
                     await message.reply(full_response[i:i+MAX_LEN], parse_mode="Markdown") # Use Markdown
                     if i + MAX_LEN < len(full_response): await asyncio.sleep(0.5)

        except Exception as e:
            logger.error(f"Critical error in list_whales: {str(e)}", exc_info=True)
            await msg.edit_text(f"❌ Failed to list whales: {str(e)}", parse_mode="Markdown") # Use Markdown

    # --- Group Management ---
    async def send_group_message(self, message: Message):
        """Send a message to the group."""
        if not await self.is_admin(message.from_user.id): return
        content = message.text.replace("/sendMessage", "", 1).strip()
        if not content:
            await message.reply("❌ Please provide a message to send: `/sendMessage your text here`", parse_mode="Markdown")
            return

        try:
            await self.bot.send_message(GROUP_ID, content) # Send as plain text
            await message.reply("✅ Message sent successfully to group!")
            await self.notify_admins( # Uses Markdown internally
                f"📢 Admin sent group message:\n\n{content}",
                exclude_admin=message.from_user.id
            )
        except Exception as e:
            logger.error(f"Error sending group message: {e}", exc_info=True)
            await message.reply(f"❌ Error sending message: {str(e)}", parse_mode="Markdown") # Use Markdown

    async def broadcast_message(self, message: Message):
        """Send a message to all users in the database."""
        if not await self.is_admin(message.from_user.id): return
        content = message.text.replace("/broadcast", "", 1).strip()
        if not content:
            await message.reply("❌ Please provide a message to broadcast: `/broadcast your text here`", parse_mode="Markdown")
            return

        msg = await message.reply("📢 Starting broadcast...")

        users_to_send = []
        async with aiosqlite.connect('members.db') as conn:
            cursor = await conn.cursor()
            await cursor.execute('SELECT user_id FROM members')
            users_to_send = await cursor.fetchall()

        total_users = len(users_to_send)
        success_count = 0
        failed_count = 0
        start_time = datetime.now(timezone.utc)

        for index, user_id_tuple in enumerate(users_to_send, 1):
            user_id = user_id_tuple[0]
            try:
                await self.bot.send_message(user_id, content) # Send plain text
                success_count += 1
            except Exception as e:
                failed_count += 1
                logger.warning(f"Broadcast failed for user {user_id}: {e}")

            if index % 25 == 0 or (datetime.now(timezone.utc) - start_time).total_seconds() > 10:
                 elapsed = (datetime.now(timezone.utc) - start_time).total_seconds()
                 progress_text = (
                      f"📢 Broadcasting... ({index}/{total_users})\n"
                      f"✅ Sent: {success_count}\n"
                      f"❌ Failed: {failed_count}\n"
                      f"⏱ Elapsed: {elapsed:.1f}s"
                 )
                 try: await msg.edit_text(progress_text)
                 except Exception as edit_err: logger.warning(f"Could not edit broadcast progress: {edit_err}")

            await asyncio.sleep(0.1)

        duration = (datetime.now(timezone.utc) - start_time).total_seconds()
        final_status = (
            f"📢 *Broadcast Complete* ({duration:.1f}s)\n" # Use Markdown
            f"• Total recipients: {total_users}\n"
            f"✅ Sent successfully: {success_count}\n"
            f"❌ Failed attempts: {failed_count}"
        )
        await msg.edit_text(final_status, parse_mode="Markdown") # Use Markdown

        await self.notify_admins( # Uses Markdown internally
            f"📢 Admin completed broadcast:\n\n"
            f"Message:\n{content}\n\n{final_status}",
            exclude_admin=message.from_user.id
        )

    # --- Statistics & Help ---
    async def show_stats(self, message: Message):
        """Show bot statistics."""
        if not await self.is_admin(message.from_user.id): return

        total_users = 0
        nft_holders_db = 0
        users_with_wallet = 0

        async with aiosqlite.connect('members.db') as conn:
            cursor = await conn.cursor()
            await cursor.execute('SELECT COUNT(*) FROM members')
            total_users = (await cursor.fetchone())[0]
            await cursor.execute('SELECT COUNT(*) FROM members WHERE has_nft = 1')
            nft_holders_db = (await cursor.fetchone())[0]
            await cursor.execute('SELECT COUNT(*) FROM members WHERE wallet_address IS NOT NULL AND wallet_address != ""')
            users_with_wallet = (await cursor.fetchone())[0]

        # Define these BEFORE the f-string
        wallet_reg_rate_str = f"{(users_with_wallet / total_users * 100 if total_users > 0 else 0):.1f}"
        db_ver_rate_str = f"{(nft_holders_db / users_with_wallet * 100 if users_with_wallet > 0 else 0):.1f}"

        # Use Markdown format
        stats = f"""📊 *Bot Statistics*

*User Data (Database):*
Total Users Registered: {total_users:,}
Users with Wallet: {users_with_wallet:,}
Verified in DB (`has_nft = 1`): {nft_holders_db:,}

*Calculated Rates:*
Wallet Registration Rate: {wallet_reg_rate_str}%
DB Verification Rate (Verified / With Wallet): {db_ver_rate_str}%""" # No escaping needed here

        await message.reply(stats, parse_mode="Markdown") # Use Markdown

    async def admin_help(self, message: Message):
        """Show admin help message."""
        if not await self.is_admin(message.from_user.id): return
        # Help message already uses Markdown syntax
        await message.reply(MESSAGES['admin_help'], parse_mode="Markdown") # Use Markdown

# --- Registration ---
def register_admin_handlers(dp: Dispatcher, admin_commands: AdminCommands):
    """Register all admin command handlers."""
    # User Management
    dp.message.register(admin_commands.search_user, Command('search'))
    dp.message.register(admin_commands.kick_member_cmd, Command('kick'))
    dp.callback_query.register(admin_commands.handle_admin_kick_callback, lambda c: c.data.startswith("admin_kick_"))

    # Member Management
    dp.message.register(admin_commands.add_members, Command('add'))
    dp.message.register(admin_commands.list_verified_members, Command('mem'))
    dp.message.register(admin_commands.list_failing_users, Command('list_failing', 'to_kick'))
    dp.message.register(admin_commands.update_verification_status, Command('update_status', 'update'))
    dp.message.register(admin_commands.list_whales, Command('list_whales'))

    # Group Management
    dp.message.register(admin_commands.send_group_message, Command('sendMessage'))
    dp.message.register(admin_commands.broadcast_message, Command('broadcast'))

    # Stats & Help
    dp.message.register(admin_commands.show_stats, Command('stats'))
    dp.message.register(admin_commands.admin_help, Command('admin'))

# --- END OF FILE admin.py ---
