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

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Admin Configuration
ADMIN_IDS = ["1499577590", "5851290427"]
GROUP_ID = -1002476568928

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
    dp.message.register(admin_commands.send_group_message, Command('sendMessage'))
    dp.message.register(admin_commands.broadcast_message, Command('broadcast'))
    dp.message.register(admin_commands.show_stats, Command('stats'))
    dp.message.register(admin_commands.admin_help, Command('admin'))
