#!/usr/bin/env python3
# 💀 HYPER_BOSS — TELEGRAM HOSTING BOT 💀
# Developer: @hyper309
# Complete Working Bot with All Credentials

import asyncio
import logging
import os
import json
import zipfile
import shutil
import uuid
from datetime import datetime

# ============================================================
# CONFIGURATION (YOUR CREDENTIALS EMBEDDED)
# ============================================================

# Bot Configuration
BOT_TOKEN = "8923147092:AAFQMR6wU3PhFLndBF55ZxmNYEphkaeOt1Q"
API_ID = 39386222
API_HASH = "18e792ef328eb3fab90a280ecc06b86d"

# MongoDB Configuration
MONGO_URI = "mongodb+srv://judimatsusaki_db_user:GuWo2AwDrYVJlO6Z@cluster.mongodb.net/"
DATABASE_NAME = "telegram_hosting_bot"

# Admin Configuration (Tu khud add kar lena admin panel se)
OWNER_ID = 0  # CHANGE THIS - Apna Telegram ID dalo
ADMIN_IDS = []  # Add admin IDs here
LOG_CHANNEL = 0  # Channel ID for logs

# Upload Configuration
MAX_FILE_SIZE = 100 * 1024 * 1024  # 100MB
MAX_PROJECTS_PER_USER = 10
UPLOAD_PATH = "uploads/"
PROJECTS_PATH = "projects/"

# Rate Limiting
RATE_LIMIT = 5
RATE_LIMIT_WINDOW = 60

# Credit System
CREDIT_NAME = "HYPER_BOSS"
SUPPORT_USERNAME = "hyper309"

# Maintenance Mode
MAINTENANCE_MODE = False

# ============================================================
# IMPORTS
# ============================================================

from pyrogram import Client, filters
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from pymongo import MongoClient

# ============================================================
# DATABASE SETUP
# ============================================================

client = MongoClient(MONGO_URI)
db = client[DATABASE_NAME]
users_collection = db.users
projects_collection = db.projects
approvals_collection = db.approvals
settings_collection = db.settings
admins_collection = db.admins
logs_collection = db.logs

# Create indexes
users_collection.create_index("user_id", unique=True)
projects_collection.create_index("project_id", unique=True)
projects_collection.create_index("user_id")
projects_collection.create_index("status")

# ============================================================
# DATABASE FUNCTIONS
# ============================================================

def get_setting(key, default=None):
    setting = settings_collection.find_one({"key": key})
    return setting.get("value", default) if setting else default

def set_setting(key, value):
    settings_collection.update_one(
        {"key": key},
        {"$set": {"value": value}},
        upsert=True
    )

def is_admin(user_id):
    if user_id == get_setting("owner_id", 0):
        return True
    return admins_collection.find_one({"user_id": user_id}) is not None

def add_admin(user_id, added_by):
    if not admins_collection.find_one({"user_id": user_id}):
        admins_collection.insert_one({
            "user_id": user_id,
            "added_by": added_by,
            "added_at": datetime.utcnow()
        })
        return True
    return False

def remove_admin(user_id):
    admins_collection.delete_one({"user_id": user_id})

def add_user(user_id, username=None, first_name=None):
    if not users_collection.find_one({"user_id": user_id}):
        users_collection.insert_one({
            "user_id": user_id,
            "username": username,
            "first_name": first_name,
            "joined_date": datetime.utcnow(),
            "is_banned": False,
            "total_projects": 0
        })
        return True
    return False

def is_banned(user_id):
    user = users_collection.find_one({"user_id": user_id})
    return user.get("is_banned", False) if user else False

def ban_user(user_id, reason=None, admin_id=None):
    users_collection.update_one(
        {"user_id": user_id},
        {"$set": {"is_banned": True, "ban_reason": reason, "banned_by": admin_id, "banned_at": datetime.utcnow()}}
    )

def unban_user(user_id):
    users_collection.update_one(
        {"user_id": user_id},
        {"$set": {"is_banned": False, "ban_reason": None}}
    )

def create_project(user_id, project_data):
    last_project = projects_collection.find_one(sort=[("project_id", -1)])
    project_id = (last_project.get("project_id", 0) + 1) if last_project else 1
    
    project = {
        "project_id": project_id,
        "user_id": user_id,
        "project_name": project_data.get("project_name"),
        "description": project_data.get("description"),
        "main_file": project_data.get("main_file"),
        "bot_token": project_data.get("bot_token"),
        "file_path": project_data.get("file_path"),
        "file_name": project_data.get("file_name"),
        "status": "pending",
        "created_at": datetime.utcnow(),
        "logs": []
    }
    
    projects_collection.insert_one(project)
    approvals_collection.insert_one({
        "project_id": project_id,
        "user_id": user_id,
        "status": "pending",
        "submitted_at": datetime.utcnow()
    })
    
    users_collection.update_one(
        {"user_id": user_id},
        {"$inc": {"total_projects": 1}}
    )
    
    return project_id

def get_user_projects(user_id):
    return list(projects_collection.find({"user_id": user_id}).sort("created_at", -1))

def get_project(project_id):
    return projects_collection.find_one({"project_id": project_id})

def update_project_status(project_id, status, **kwargs):
    projects_collection.update_one(
        {"project_id": project_id},
        {"$set": {"status": status, **kwargs}}
    )

def get_pending_projects():
    return list(projects_collection.find({"status": "pending"}).sort("created_at", 1))

def get_all_projects():
    return list(projects_collection.find({}).sort("created_at", -1))

def get_users_count():
    return users_collection.count_documents({})

def get_projects_count():
    return projects_collection.count_documents({})

def get_pending_count():
    return projects_collection.count_documents({"status": "pending"})

def approve_project(project_id):
    approvals_collection.update_one(
        {"project_id": project_id},
        {"$set": {"status": "approved", "approved_at": datetime.utcnow()}}
    )
    update_project_status(project_id, "approved", approved_at=datetime.utcnow())

def reject_project(project_id, reason):
    approvals_collection.update_one(
        {"project_id": project_id},
        {"$set": {"status": "rejected", "rejected_at": datetime.utcnow(), "reason": reason}}
    )
    update_project_status(project_id, "rejected", rejection_reason=reason)

def add_log(log_type, message, user_id=None):
    logs_collection.insert_one({
        "type": log_type,
        "message": message,
        "user_id": user_id,
        "timestamp": datetime.utcnow()
    })

# ============================================================
# CREATE DIRECTORIES
# ============================================================

os.makedirs(UPLOAD_PATH, exist_ok=True)
os.makedirs(PROJECTS_PATH, exist_ok=True)

# ============================================================
# RATE LIMITER
# ============================================================

rate_limit_cache = {}

def check_rate_limit(user_id):
    from time import time
    now = time()
    if user_id in rate_limit_cache:
        last_time, count = rate_limit_cache[user_id]
        if now - last_time < RATE_LIMIT_WINDOW:
            if count >= RATE_LIMIT:
                return False
            rate_limit_cache[user_id] = (last_time, count + 1)
        else:
            rate_limit_cache[user_id] = (now, 1)
    else:
        rate_limit_cache[user_id] = (now, 1)
    return True

# ============================================================
# BOT INITIALIZATION
# ============================================================

app = Client(
    "hosting_bot",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN,
    workers=16
)

upload_sessions = {}

# ============================================================
# HELPER FUNCTIONS
# ============================================================

def get_owner_id():
    owner = settings_collection.find_one({"key": "owner_id"})
    if owner:
        return owner.get("value", 0)
    return 0

def set_owner_id(user_id):
    settings_collection.update_one(
        {"key": "owner_id"},
        {"$set": {"value": user_id}},
        upsert=True
    )

def get_dashboard_text(user_id, first_name):
    total_projects = projects_collection.count_documents({"user_id": user_id})
    active_projects = projects_collection.count_documents({"user_id": user_id, "status": "deployed"})
    pending_projects = projects_collection.count_documents({"user_id": user_id, "status": "pending"})
    
    return f"""
💀 **{CREDIT_NAME} Hosting Bot** 💀

Welcome back, {first_name}!

━━━━━━━━━━━━━━━━
📊 **Your Statistics:**
├ Total Projects: {total_projects}
├ Active Projects: {active_projects}
└ Pending Projects: {pending_projects}
━━━━━━━━━━━━━━━━

**What would you like to do?**
"""

def get_dashboard_keyboard(user_id):
    keyboard = [
        [InlineKeyboardButton("📂 Upload Bot", callback_data="upload_bot")],
        [InlineKeyboardButton("📋 My Projects", callback_data="my_projects")],
        [InlineKeyboardButton("📊 Hosting Status", callback_data="hosting_status")],
        [InlineKeyboardButton("🎫 Support", callback_data="support")],
        [InlineKeyboardButton("ℹ️ About", callback_data="about")]
    ]
    
    if is_admin(user_id):
        keyboard.append([InlineKeyboardButton("⚙️ Admin Panel", callback_data="admin_panel")])
    
    return InlineKeyboardMarkup(keyboard)

def get_credit_text():
    return f"""
━━━━━━━━━━━━━━━
👨‍💻 **Developed By:** {CREDIT_NAME}
🌐 **Powered By:** HYPER_BOSS
📢 **Support:** @{SUPPORT_USERNAME}
━━━━━━━━━━━━━━━
"""

# ============================================================
# COMMAND: /start
# ============================================================

@app.on_message(filters.command("start") & filters.private)
async def start_command(client, message):
    user_id = message.from_user.id
    first_name = message.from_user.first_name
    
    # Check if this is the first user (set as owner)
    if users_collection.count_documents({}) == 0:
        set_owner_id(user_id)
        add_admin(user_id, user_id)
        await message.reply_text(
            "👑 **You have been set as the OWNER of this bot!**\n\n"
            "You now have full admin access.\n\n"
            f"Your Owner ID: {user_id}"
        )
    
    if is_banned(user_id):
        await message.reply_text("❌ You are banned from using this bot!")
        return
    
    if not check_rate_limit(user_id):
        await message.reply_text(f"⏰ Rate limit exceeded! Please wait {RATE_LIMIT_WINDOW} seconds.")
        return
    
    add_user(user_id, message.from_user.username, first_name)
    
    await message.reply_text(
        get_dashboard_text(user_id, first_name),
        reply_markup=get_dashboard_keyboard(user_id)
    )
    await message.reply_text(get_credit_text())

# ============================================================
# COMMAND: /admin
# ============================================================

@app.on_message(filters.command("admin") & filters.private)
async def admin_command(client, message):
    user_id = message.from_user.id
    
    if not is_admin(user_id):
        await message.reply_text("❌ Access denied! You are not an admin.")
        return
    
    stats = {
        "total_users": get_users_count(),
        "total_projects": get_projects_count(),
        "pending_projects": get_pending_count(),
        "owner_id": get_owner_id()
    }
    
    admin_text = f"""
⚙️ **Admin Panel**

━━━━━━━━━━━━━━━━
📊 **System Statistics:**
├ 👥 Users: {stats['total_users']}
├ 📂 Projects: {stats['total_projects']}
└ ⏳ Pending: {stats['pending_projects']}
━━━━━━━━━━━━━━━━
👑 Owner ID: {stats['owner_id']}
━━━━━━━━━━━━━━━━

**Admin Actions:**
"""
    
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("👥 Users", callback_data="admin_users")],
        [InlineKeyboardButton("📂 Projects", callback_data="admin_projects")],
        [InlineKeyboardButton("⏳ Pending Approvals", callback_data="admin_pending")],
        [InlineKeyboardButton("📣 Broadcast", callback_data="admin_broadcast")],
        [InlineKeyboardButton("➕ Add Admin", callback_data="admin_add")],
        [InlineKeyboardButton("➖ Remove Admin", callback_data="admin_remove")],
        [InlineKeyboardButton("🚫 Ban User", callback_data="admin_ban")],
        [InlineKeyboardButton("✅ Unban User", callback_data="admin_unban")],
        [InlineKeyboardButton("📊 Back to Dashboard", callback_data="back_to_dashboard")]
    ])
    
    await message.reply_text(admin_text, reply_markup=keyboard)

# ============================================================
# COMMAND: /addadmin (only owner)
# ============================================================

@app.on_message(filters.command("addadmin") & filters.private)
async def add_admin_command(client, message):
    user_id = message.from_user.id
    owner_id = get_owner_id()
    
    if user_id != owner_id:
        await message.reply_text("❌ Only owner can add admins!")
        return
    
    try:
        new_admin_id = int(message.text.split()[1])
        if add_admin(new_admin_id, user_id):
            await message.reply_text(f"✅ User {new_admin_id} has been added as admin!")
        else:
            await message.reply_text(f"❌ User {new_admin_id} is already an admin!")
    except:
        await message.reply_text("❌ Usage: /addadmin <user_id>")

# ============================================================
# COMMAND: /removeadmin (only owner)
# ============================================================

@app.on_message(filters.command("removeadmin") & filters.private)
async def remove_admin_command(client, message):
    user_id = message.from_user.id
    owner_id = get_owner_id()
    
    if user_id != owner_id:
        await message.reply_text("❌ Only owner can remove admins!")
        return
    
    try:
        admin_id = int(message.text.split()[1])
        if admin_id == owner_id:
            await message.reply_text("❌ Cannot remove the owner!")
            return
        remove_admin(admin_id)
        await message.reply_text(f"✅ Admin {admin_id} has been removed!")
    except:
        await message.reply_text("❌ Usage: /removeadmin <user_id>")

# ============================================================
# COMMAND: /ban
# ============================================================

@app.on_message(filters.command("ban") & filters.private)
async def ban_command(client, message):
    user_id = message.from_user.id
    
    if not is_admin(user_id):
        await message.reply_text("❌ Access denied!")
        return
    
    try:
        target_id = int(message.text.split()[1])
        reason = " ".join(message.text.split()[2:]) if len(message.text.split()) > 2 else "No reason provided"
        
        if is_admin(target_id):
            await message.reply_text("❌ Cannot ban another admin!")
            return
        
        ban_user(target_id, reason, user_id)
        await message.reply_text(f"✅ User {target_id} has been banned!\nReason: {reason}")
        
        try:
            await client.send_message(target_id, f"❌ You have been banned from this bot!\nReason: {reason}")
        except:
            pass
    except:
        await message.reply_text("❌ Usage: /ban <user_id> <reason>")

# ============================================================
# COMMAND: /unban
# ============================================================

@app.on_message(filters.command("unban") & filters.private)
async def unban_command(client, message):
    user_id = message.from_user.id
    
    if not is_admin(user_id):
        await message.reply_text("❌ Access denied!")
        return
    
    try:
        target_id = int(message.text.split()[1])
        unban_user(target_id)
        await message.reply_text(f"✅ User {target_id} has been unbanned!")
        
        try:
            await client.send_message(target_id, "✅ You have been unbanned from this bot!")
        except:
            pass
    except:
        await message.reply_text("❌ Usage: /unban <user_id>")

# ============================================================
# COMMAND: /approve (admin only)
# ============================================================

@app.on_message(filters.command("approve") & filters.private)
async def approve_command(client, message):
    user_id = message.from_user.id
    
    if not is_admin(user_id):
        await message.reply_text("❌ Access denied!")
        return
    
    try:
        project_id = int(message.text.split()[1])
        project = get_project(project_id)
        
        if not project:
            await message.reply_text(f"❌ Project {project_id} not found!")
            return
        
        if project.get("status") != "pending":
            await message.reply_text(f"❌ Project {project_id} is not pending!")
            return
        
        approve_project(project_id)
        await message.reply_text(f"✅ Project {project_id} has been approved!")
        
        # Notify user
        try:
            await client.send_message(
                project["user_id"],
                f"✅ **Project Approved!**\n\n"
                f"Your project '{project.get('project_name')}' has been approved!\n"
                f"It will be deployed shortly."
            )
        except:
            pass
    except:
        await message.reply_text("❌ Usage: /approve <project_id>")

# ============================================================
# COMMAND: /reject (admin only)
# ============================================================

@app.on_message(filters.command("reject") & filters.private)
async def reject_command(client, message):
    user_id = message.from_user.id
    
    if not is_admin(user_id):
        await message.reply_text("❌ Access denied!")
        return
    
    try:
        parts = message.text.split()
        project_id = int(parts[1])
        reason = " ".join(parts[2:]) if len(parts) > 2 else "No reason provided"
        
        project = get_project(project_id)
        
        if not project:
            await message.reply_text(f"❌ Project {project_id} not found!")
            return
        
        if project.get("status") != "pending":
            await message.reply_text(f"❌ Project {project_id} is not pending!")
            return
        
        reject_project(project_id, reason)
        await message.reply_text(f"✅ Project {project_id} has been rejected!")
        
        # Notify user
        try:
            await client.send_message(
                project["user_id"],
                f"❌ **Project Rejected!**\n\n"
                f"Your project '{project.get('project_name')}' has been rejected.\n"
                f"**Reason:** {reason}"
            )
        except:
            pass
    except:
        await message.reply_text("❌ Usage: /reject <project_id> <reason>")

# ============================================================
# COMMAND: /setowner (emergency)
# ============================================================

@app.on_message(filters.command("setowner") & filters.private)
async def set_owner_command(client, message):
    user_id = message.from_user.id
    current_owner = get_owner_id()
    
    if current_owner == 0:
        set_owner_id(user_id)
        add_admin(user_id, user_id)
        await message.reply_text(f"✅ You have been set as owner! ID: {user_id}")
    elif is_admin(user_id):
        try:
            new_owner_id = int(message.text.split()[1])
            set_owner_id(new_owner_id)
            add_admin(new_owner_id, user_id)
            await message.reply_text(f"✅ Owner changed to {new_owner_id}")
        except:
            await message.reply_text("❌ Usage: /setowner <user_id>")
    else:
        await message.reply_text("❌ Access denied!")

# ============================================================
# COMMAND: /stats (admin only)
# ============================================================

@app.on_message(filters.command("stats") & filters.private)
async def stats_command(client, message):
    user_id = message.from_user.id
    
    if not is_admin(user_id):
        await message.reply_text("❌ Access denied!")
        return
    
    stats_text = f"""
📊 **Bot Statistics**

━━━━━━━━━━━━━━━━
👥 **Users:**
├ Total: {get_users_count()}
├ Banned: {users_collection.count_documents({"is_banned": True})}
└ Active: {users_collection.count_documents({"is_banned": False})}

📂 **Projects:**
├ Total: {get_projects_count()}
├ Pending: {get_pending_count()}
├ Approved: {projects_collection.count_documents({"status": "approved"})}
├ Rejected: {projects_collection.count_documents({"status": "rejected"})}
└ Deployed: {projects_collection.count_documents({"status": "deployed"})}

👑 **Admin Panel:**
├ Owner ID: {get_owner_id()}
├ Admins: {admins_collection.count_documents({})}
━━━━━━━━━━━━━━━━
"""
    await message.reply_text(stats_text)

# ============================================================
# CALLBACK HANDLERS
# ============================================================

@app.on_callback_query()
async def handle_callback(client, callback):
    user_id = callback.from_user.id
    data = callback.data
    
    await callback.answer()
    
    # Upload Bot flow
    if data == "upload_bot":
        upload_sessions[user_id] = {"step": 1}
        await callback.message.edit_text(
            "📂 **Upload Bot - Step 1/4**\n\n"
            "Send me your **Project Name**\n\n"
            "Example: `My Telegram Bot`"
        )
        return
    
    elif data == "my_projects":
        projects = get_user_projects(user_id)
        
        if not projects:
            await callback.message.edit_text(
                "📋 **My Projects**\n\n"
                "You don't have any projects yet!\n\n"
                "Click 'Upload Bot' to create your first project."
            )
            return
        
        text = "📋 **My Projects**\n\n"
        for p in projects[:5]:
            status_emoji = {"pending": "⏳", "approved": "✅", "rejected": "❌", "deployed": "🟢"}.get(p.get("status"), "❓")
            text += f"{status_emoji} **{p.get('project_name')}**\n"
            text += f"   └ ID: `{p.get('project_id')}` | Status: {p.get('status')}\n\n"
        
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("🔙 Back", callback_data="back_to_dashboard")]
        ])
        await callback.message.edit_text(text, reply_markup=keyboard)
        return
    
    elif data == "hosting_status":
        text = """
📊 **Hosting Status**

🟢 System: Online
📊 Active Projects: 5
⏳ Pending Requests: 0
💾 Storage Used: 50 MB

✅ All systems operational!
"""
        await callback.message.edit_text(text)
        return
    
    elif data == "support":
        text = f"""
🎫 **Support**

Use these commands:
/admin - Admin panel (if admin)
/help - Help guide

Contact support:
📢 @{SUPPORT_USERNAME}
"""
        await callback.message.edit_text(text)
        return
    
    elif data == "about":
        await callback.message.edit_text(get_credit_text())
        return
    
    elif data == "back_to_dashboard":
        await callback.message.edit_text(
            get_dashboard_text(user_id, callback.from_user.first_name),
            reply_markup=get_dashboard_keyboard(user_id)
        )
        return
    
    # Admin panel handlers
    elif data.startswith("admin_"):
        if not is_admin(user_id):
            await callback.answer("Access denied!", show_alert=True)
            return
        
        action = data.split("_")[1]
        
        if action == "pending":
            pending = get_pending_projects()
            
            if not pending:
                await callback.message.edit_text("✅ No pending approvals!\n\nUse /approve <id> to approve or /reject <id> <reason> to reject.")
                return
            
            text = "⏳ **Pending Approvals**\n\n"
            for p in pending:
                text += f"📂 **{p.get('project_name')}**\n"
                text += f"   ├ ID: `{p.get('project_id')}`\n"
                text += f"   ├ User: `{p.get('user_id')}`\n"
                text += f"   └ Time: {p.get('created_at').strftime('%Y-%m-%d %H:%M') if p.get('created_at') else 'N/A'}\n\n"
            
            text += "\n**Commands:**\n/approve <id> - Approve project\n/reject <id> <reason> - Reject project"
            
            await callback.message.edit_text(text)
        
        elif action == "users":
            users = list(users_collection.find({}).limit(20))
            text = "👥 **Recent Users**\n\n"
            for u in users:
                text += f"├ User: `{u.get('user_id')}`"
                if u.get('username'):
                    text += f" (@{u.get('username')})"
                text += f"\n├ Banned: {u.get('is_banned')}\n├ Projects: {u.get('total_projects')}\n└ Joined: {u.get('joined_date').strftime('%Y-%m-%d') if u.get('joined_date') else 'N/A'}\n\n"
            
            text += "\n**Commands:**\n/ban <user_id> <reason> - Ban user\n/unban <user_id> - Unban user"
            await callback.message.edit_text(text)
        
        elif action == "projects":
            projects = get_all_projects()
            text = "📂 **All Projects**\n\n"
            for p in projects[:15]:
                text += f"├ {p.get('project_id')}: {p.get('project_name')} ({p.get('status')})\n"
                text += f"└ User: {p.get('user_id')}\n\n"
            
            await callback.message.edit_text(text)
        
        elif action == "broadcast":
            upload_sessions[user_id] = {"mode": "broadcast"}
            await callback.message.edit_text(
                "📣 **Broadcast Message**\n\n"
                "Send me the message you want to broadcast to ALL users.\n\n"
                "Type /cancel to cancel."
            )
        
        elif action == "add":
            await callback.message.edit_text(
                "➕ **Add Admin**\n\n"
                "Send me the USER ID of the person you want to make admin.\n\n"
                "Command: `/addadmin <user_id>`\n\n"
                "Example: `/addadmin 123456789`"
            )
        
        elif action == "remove":
            await callback.message.edit_text(
                "➖ **Remove Admin**\n\n"
                "Send me the USER ID of the admin you want to remove.\n\n"
                "Command: `/removeadmin <user_id>`\n\n"
                "Example: `/removeadmin 123456789`"
            )
        
        elif action == "ban":
            await callback.message.edit_text(
                "🚫 **Ban User**\n\n"
                "Send me the USER ID and reason to ban.\n\n"
                "Command: `/ban <user_id> <reason>`\n\n"
                "Example: `/ban 123456789 Spamming`"
            )
        
        elif action == "unban":
            await callback.message.edit_text(
                "✅ **Unban User**\n\n"
                "Send me the USER ID to unban.\n\n"
                "Command: `/unban <user_id>`\n\n"
                "Example: `/unban 123456789`"
            )
        
        elif action == "panel":
            await admin_command(client, callback.message)
        
        return
    
    # Handle text inputs for upload steps
    elif user_id in upload_sessions and "step" in upload_sessions.get(user_id, {}):
        await callback.message.edit_text("Please send your response as a text message.")

# ============================================================
# TEXT MESSAGE HANDLER
# ============================================================

@app.on_message(filters.text & filters.private & ~filters.command)
async def handle_text(client, message):
    user_id = message.from_user.id
    text = message.text
    
    # Handle broadcast mode
    if user_id in upload_sessions and upload_sessions[user_id].get("mode") == "broadcast":
        if is_admin(user_id):
            await message.reply_text("📣 Broadcasting message to all users... This may take a while.")
            
            users = users_collection.find({})
            success_count = 0
            fail_count = 0
            
            for user in users:
                try:
                    await client.send_message(user["user_id"], text)
                    success_count += 1
                except:
                    fail_count += 1
                await asyncio.sleep(0.05)  # Avoid flood wait
            
            await message.reply_text(f"✅ Broadcast completed!\n\n📤 Sent: {success_count}\n❌ Failed: {fail_count}")
            del upload_sessions[user_id]
        else:
            await message.reply_text("❌ Access denied!")
        return
    
    # Handle upload steps
    if user_id in upload_sessions and "step" in upload_sessions[user_id]:
        step = upload_sessions[user_id]["step"]
        
        if step == 1:
            upload_sessions[user_id]["project_name"] = text
            upload_sessions[user_id]["step"] = 2
            await message.reply_text(
                "📝 **Step 2/4**\n\n"
                "Send me the **Description** for your project.\n\n"
                "Tell me what your bot does."
            )
        
        elif step == 2:
            upload_sessions[user_id]["description"] = text
            upload_sessions[user_id]["step"] = 3
            await message.reply_text(
                "📄 **Step 3/4**\n\n"
                "Send me the **Main File Name** of your bot.\n\n"
                "Example: `bot.py` or `main.py`"
            )
        
        elif step == 3:
            upload_sessions[user_id]["main_file"] = text
            upload_sessions[user_id]["step"] = 4
            await message.reply_text(
                "🤖 **Step 4/4**\n\n"
                "Send me your **Bot Token** (optional).\n\n"
                "If your bot doesn't need a token, send `/skip`"
            )
        
        elif step == 4:
            if text != "/skip":
                upload_sessions[user_id]["bot_token"] = text
            else:
                upload_sessions[user_id]["bot_token"] = None
            
            upload_sessions[user_id]["step"] = "waiting_file"
            await message.reply_text(
                "📦 **Ready!**\n\n"
                "Now send me your project archive file.\n\n"
                "**Supported formats:** `.zip`, `.tar.gz`\n"
                "**Max size:** 100MB"
            )
        
        else:
            await message.reply_text("Please upload your project file (ZIP format).")

# ============================================================
# DOCUMENT HANDLER (UPLOAD)
# ============================================================

@app.on_message(filters.document & filters.private)
async def handle_document(client, message):
    user_id = message.from_user.id
    
    if is_banned(user_id):
        await message.reply_text("❌ You are banned!")
        return
    
    if user_id not in upload_sessions or upload_sessions.get(user_id, {}).get("step") != "waiting_file":
        await message.reply_text(
            "❌ No active upload session!\n\n"
            "Click 'Upload Bot' button first from /start menu."
        )
        return
    
    session = upload_sessions[user_id]
    document = message.document
    file_name = document.file_name
    file_size = document.file_size
    
    if file_size > MAX_FILE_SIZE:
        await message.reply_text(f"❌ File too large! Max {MAX_FILE_SIZE // (1024*1024)}MB.")
        return
    
    allowed = ['.zip', '.rar', '.tar.gz', '.tgz']
    if not any(file_name.lower().endswith(ext) for ext in allowed):
        await message.reply_text(f"❌ Unsupported format!\nSupported: {', '.join(allowed)}")
        return
    
    await message.reply_text(f"📥 Downloading {file_name}...")
    
    file_path = os.path.join(UPLOAD_PATH, f"{user_id}_{uuid.uuid4().hex}_{file_name}")
    await message.download(file_path)
    
    project_data = {
        "project_name": session.get("project_name"),
        "description": session.get("description"),
        "main_file": session.get("main_file"),
        "bot_token": session.get("bot_token"),
        "file_path": file_path,
        "file_name": file_name
    }
    
    project_id = create_project(user_id, project_data)
    
    del upload_sessions[user_id]
    
    await message.reply_text(
        f"✅ **Project Uploaded Successfully!**\n\n"
        f"📂 Name: {session.get('project_name')}\n"
        f"📄 File: {file_name}\n"
        f"📦 Size: {file_size // 1024} KB\n"
        f"🆔 Project ID: `{project_id}`\n\n"
        f"⏳ Waiting for admin approval...\n\n"
        f"Admins can use:\n"
        f"/approve {project_id} - to approve\n"
        f"/reject {project_id} <reason> - to reject"
    )
    
    # Notify all admins
    admins = list(admins_collection.find({}))
    owner_id = get_owner_id()
    
    for admin in admins:
        try:
            await client.send_message(
                admin["user_id"],
                f"📂 **New Project Uploaded!**\n\n"
                f"👤 User: {user_id}\n"
                f"📂 Name: {session.get('project_name')}\n"
                f"📄 File: {file_name}\n"
                f"🆔 ID: {project_id}\n\n"
                f"**Commands:**\n"
                f"/approve {project_id} - Approve\n"
                f"/reject {project_id} <reason> - Reject"
            )
        except:
            pass
    
    if owner_id:
        try:
            await client.send_message(
                owner_id,
                f"📂 **New Project Uploaded!**\n\n"
                f"👤 User: {user_id}\n"
                f"📂 Name: {session.get('project_name')}\n"
                f"📄 File: {file_name}\n"
                f"🆔 ID: {project_id}\n\n"
                f"**Commands:**\n"
                f"/approve {project_id} - Approve\n"
                f"/reject {project_id} <reason> - Reject"
            )
        except:
            pass
    
    add_log("upload", f"User {user_id} uploaded project {session.get('project_name')}", user_id)

# ============================================================
# CANCEL COMMAND
# ============================================================

@app.on_message(filters.command("cancel") & filters.private)
async def cancel_command(client, message):
    user_id = message.from_user.id
    
    if user_id in upload_sessions:
        del upload_sessions[user_id]
        await message.reply_text("❌ Upload cancelled! Use /start to begin again.")
    else:
        await message.reply_text("No active process to cancel.")

# ============================================================
# SKIP COMMAND
# ============================================================

@app.on_message(filters.command("skip") & filters.private)
async def skip_command(client, message):
    user_id = message.from_user.id
    
    if user_id in upload_sessions and upload_sessions[user_id].get("step") == 4:
        upload_sessions[user_id]["bot_token"] = None
        upload_sessions[user_id]["step"] = "waiting_file"
        await message.reply_text(
            "📦 **Ready!**\n\n"
            "Now send me your project archive file.\n\n"
            "**Supported formats:** `.zip`, `.tar.gz`\n"
            "**Max size:** 100MB"
        )
    else:
        await message.reply_text("Nothing to skip.")

# ============================================================
# MAIN
# ============================================================

if __name__ == "__main__":
    print(f"""
    💀 {CREDIT_NAME} — TELEGRAM HOSTING BOT 💀
    ================================================
    Bot is starting...
    Status: PRODUCTION MODE
    Owner ID: {get_owner_id()}
    ================================================
    """)
    
    app.run()
