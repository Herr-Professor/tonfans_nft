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
from ton_utils import check_token_balance, check_nft_ownership, escape_md, SHIVA_TOKEN_ADDRESS

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
                    text=escape_md(message),
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
        
        conn = aiosqlite.connect('members.db')
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
                f"*Username:* @{escape_md(username)}\n"
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
            conn = aiosqlite.connect('members.db')
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
    
        try:
            from ton_utils import check_token_balance, SHIVA_TOKEN_ADDRESS
        except ImportError as e:
            await message.reply(f"❌ Critical error: {str(e)}")
            logger.error(f"Failed to import dependencies: {e}")
            return
    
        msg = await message.reply(f"🔍 Fetching whale list (>= {WHALE_THRESHOLD:,.0f} $SHIVA). This may take some time...")
    
        try:
            # Async database connection
            async with aiosqlite.connect('members.db') as conn:
                cursor = await conn.execute(
                    'SELECT user_id, username, wallet_address FROM members '
                    'WHERE wallet_address IS NOT NULL AND wallet_address != ""'
                )
                potential_whales = await cursor.fetchall()
    
            if not potential_whales:
                await msg.edit_text("❌ No users with registered wallets found.")
                return
    
            whales_found = []
            total = len(potential_whales)
            start_time = datetime.now(timezone.utc)
            
            for index, (user_id, username, wallet) in enumerate(potential_whales, 1):
                try:
                    # Validate wallet format
                    if not isinstance(wallet, str) or not wallet.startswith(('EQ', 'UQ')):
                        continue
    
                    # Check balance with error handling
                    raw_balance, formatted_balance, _ = await check_token_balance(wallet, SHIVA_TOKEN_ADDRESS)
                    
                    if formatted_balance >= WHALE_THRESHOLD:
                        whales_found.append({
                            'user_id': user_id,
                            'username': username,
                            'wallet': wallet,
                            'balance': formatted_balance
                        })
    
                    # Update progress every 5 users or 3 seconds
                    if index % 5 == 0 or (datetime.now(timezone.utc) - start_time).seconds % 3 == 0:
                        progress = (
                            f"🔍 Checked {index}/{total} users\n"
                            f"🐳 Found: {len(whales_found)}\n"
                            f"⏱ {(datetime.now(timezone.utc) - start_time).seconds}s"
                        )
                        await msg.edit_text(progress)
                        
                    await asyncio.sleep(1)  # Increased delay for API limits
    
                except Exception as e:
                    logger.error(f"Error checking {wallet}: {str(e)}")
                    continue
    
            # Compile final results
            duration = (datetime.now(timezone.utc) - start_time).seconds
            response = [f"✅ Checked {total} users in {duration}s"]
            
            if whales_found:
                whales_found.sort(key=lambda x: x['balance'], reverse=True)
                response.append(f"🐳 *Top Whales* (≥{WHALE_THRESHOLD:,.0f} $SHIVA):")
                for i, whale in enumerate(whales_found, 1):
                    # Escape all dynamic content
                    safe_username = escape_md(whale['username']) if whale['username'] else "Anonymous"
                    safe_balance = escape_md(f"{whale['balance']:,.2f}")
                    response.append(f"{i}\\. @{safe_username} \\- {safe_balance} $SHIVA")
            else:
                response.append("❌ No whales found")
    
            await msg.edit_text("\n".join(response), parse_mode="Markdown")
    
        except Exception as e:
            logger.error(f"Critical error in list_whales: {str(e)}")
            await message.reply(f"❌ Failed to list whales: {str(e)}")
    
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

        conn = aiosqlite.connect('members.db')
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
        """List all NFT holders with proper Markdown escaping"""
        if not await self.is_admin(message.from_user.id):
            return
    
        try:
            async with aiosqlite.connect('members.db') as conn:
                cursor = await conn.execute(
                    'SELECT username, wallet_address FROM members WHERE has_nft = 1'
                )
                holders = await cursor.fetchall()
    
            if not holders:
                await message.reply("❌ No NFT holders found!")
                return
    
            response = ["💎 *NFT Holders:*"]
            for username, wallet in holders:
                # Escape special characters using our custom function
                safe_username = escape_md(username or "NoUsername")
                safe_wallet = escape_md(wallet)
                response.append(f"• @{safe_username}\n  `{safe_wallet}`")
    
            # Split long messages into multiple parts
            full_text = "\n\n".join(response)
            if len(full_text) > 4000:
                parts = []
                current_part = []
                current_length = 0
                
                for line in response:
                    line_length = len(line)
                    if current_length + line_length > 4000:
                        parts.append("\n\n".join(current_part))
                        current_part = []
                        current_length = 0
                    current_part.append(line)
                    current_length += line_length + 2  # +2 for newlines
                
                if current_part:
                    parts.append("\n\n".join(current_part))
    
                for part in parts:
                    try:
                        await message.reply(part, parse_mode="Markdown")
                        await asyncio.sleep(1)  # Avoid rate limits
                    except Exception as e:
                        logger.error(f"Error sending message part: {str(e)}")
            else:
                await message.reply(full_text, parse_mode="Markdown")
    
        except Exception as e:
            error_msg = escape_md(f"Error: {str(e)}")
            await message.reply(f"❌ {error_msg}", parse_mode="Markdown")
        
    async def check_to_kick(self, message: Message):
        """List users without NFTs"""
        if not await self.is_admin(message.from_user.id):
            return
    
        try:
            async with aiosqlite.connect('members.db') as conn:
                cursor = await conn.execute(
                    'SELECT username, wallet_address, user_id FROM members WHERE has_nft = 0'
                )
                non_holders = await cursor.fetchall()
    
            if not non_holders:
                await message.reply("✅ All users have NFTs!")
                return
    
            response = ["🚫 *Non-NFT Holders:*"]
            for username, wallet, uid in non_holders:
                # Use custom escape function
                safe_username = escape_md(username or "NoUsername")
                safe_wallet = escape_md(wallet)
                safe_uid = escape_md(str(uid))
                
                response.append(
                    f"• @{safe_username}\n"
                    f"  ID: `{safe_uid}`\n"
                    f"  Wallet: `{safe_wallet}`"
                )
    
            # Split long messages
            full_text = "\n\n".join(response)
            if len(full_text) > 4000:
                parts = [full_text[i:i+4000] for i in range(0, len(full_text), 4000)]
                for part in parts:
                    await message.reply(part, parse_mode="Markdown")
                    await asyncio.sleep(1)
            else:
                await message.reply(full_text, parse_mode="Markdown")
    
        except Exception as e:
            error_msg = escape_md(f"Error: {str(e)}")
            await message.reply(f"❌ {error_msg}", parse_mode="Markdown")
                
    async def update_nft_status(self, message: Message):
        """Update NFT status for all users in database"""
        if not await self.is_admin(message.from_user.id):
            return

        msg = await message.reply("🔄 Starting NFT status update...")
        
        try:
            async with aiosqlite.connect('members.db') as conn:
                # Get all users with wallets
                cursor = await conn.execute(
                    'SELECT user_id, wallet_address FROM members '
                    'WHERE wallet_address IS NOT NULL AND wallet_address != ""'
                )
                users = await cursor.fetchall()
                total_users = len(users)
                
                if not total_users:
                    await msg.edit_text("❌ No users with wallets in database")
                    return
    
                updated_count = 0
                errors = []
                start_time = datetime.now(timezone.utc)
                
                for index, (user_id, wallet) in enumerate(users, 1):
                    try:
                        # Check NFT status
                        has_nft = await check_nft_ownership(wallet)
                        
                        # Update database
                        await conn.execute(
                            'UPDATE members SET has_nft = ?, last_checked = CURRENT_TIMESTAMP '
                            'WHERE user_id = ?',
                            (1 if has_nft else 0, user_id)
                        )
                        await conn.commit()
                        
                        updated_count += 1
                        
                        # Update progress every 5 users or 10 seconds
                        if index % 5 == 0 or (datetime.now(timezone.utc) - start_time).seconds % 10 == 0:
                            progress = (
                                f"🔄 Processed {index}/{total_users} users\n"
                                f"✅ Updated: {updated_count}\n"
                                f"⏱ Elapsed: {(datetime.now(timezone.utc) - start_time).seconds}s"
                            )
                            await msg.edit_text(progress)
                        
                        await asyncio.sleep(1)  # Rate limiting
                        
                    except Exception as e:
                        errors.append(f"User {user_id}: {str(e)}")
                        continue
    
                # Final report
                duration = (datetime.now(timezone.utc) - start_time).seconds
                report = (
                    f"✅ Update complete!\n"
                    f"• Total users: {total_users}\n"
                    f"• Successfully updated: {updated_count}\n"
                    f"• Errors: {len(errors)}\n"
                    f"• Time taken: {duration}s"
                )
                
                if errors:
                    report += "\n\n❌ Errors:\n" + "\n".join(errors[:5])  # Show first 5 errors
                    if len(errors) > 5:
                        report += f"\n...and {len(errors)-5} more errors"
                
                await msg.edit_text(report)
    
        except Exception as e:
            logger.error(f"Critical error in update: {str(e)}")
            await message.reply(f"❌ Update failed: {escape_md(str(e))}", parse_mode="Markdown")
            
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

        users = []
        async with aiosqlite.connect('members.db') as conn:
            cursor = await conn.cursor()
            await cursor.execute('SELECT user_id FROM members')
            users = await cursor.fetchall()

        success = 0
        failed = 0

        for user_id_tuple in users:
            try:
                await self.bot.send_message(user_id_tuple[0], content)
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

        total_users = 0
        nft_holders = 0
        users_with_wallet = 0

        async with aiosqlite.connect('members.db') as conn:
            cursor = await conn.cursor()
            
            # Get total users
            await cursor.execute('SELECT COUNT(*) FROM members')
            total_users_result = await cursor.fetchone()
            total_users = total_users_result[0] if total_users_result else 0
            
            # Get NFT holders
            await cursor.execute('SELECT COUNT(*) FROM members WHERE has_nft = 1')
            nft_holders_result = await cursor.fetchone()
            nft_holders = nft_holders_result[0] if nft_holders_result else 0
            
            # Get users with wallets
            await cursor.execute('SELECT COUNT(*) FROM members WHERE wallet_address IS NOT NULL')
            users_with_wallet_result = await cursor.fetchone()
            users_with_wallet = users_with_wallet_result[0] if users_with_wallet_result else 0

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
    dp.message.register(admin_commands.update_nft_status, Command('update'))
    dp.message.register(admin_commands.check_to_kick, Command('to_kick'))
    dp.message.register(admin_commands.list_whales, Command('list_whales'))
    dp.message.register(admin_commands.send_group_message, Command('sendMessage'))
    dp.message.register(admin_commands.broadcast_message, Command('broadcast'))
    dp.message.register(admin_commands.show_stats, Command('stats'))
    dp.message.register(admin_commands.admin_help, Command('admin'))
    # If you add the callback handler for kick_all_non_holders, register it here too
    # dp.callback_query.register(admin_commands.handle_kick_all_callback, F.data.startswith("kick_all_non_holders:"))
