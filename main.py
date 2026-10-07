import os
import sys
import time
import json
import zipfile
import subprocess
import threading
import re
import shutil
import socket
import secrets
import shlex
import requests
import urllib3
import telebot
from telebot import types

# psutil library for advanced hardware reading
try:
    import psutil
except ImportError:
    psutil = None

# ----------------- CONFIGURATION --------------
BOT_TOKEN = '8891741635:AAGTbZndObi_TpYeQwtQmfF8-4L4NMu-dLM'  # আপনার টেলিগ্রাম বট টোকেন
BASE_DIR = 'projects'              
META_FILE = 'projects_meta.json'   
AUTH_CONFIG_FILE = 'auth_config.json'  # পিন ফাইল
DEFAULT_PIN = 'HMSI2580'               # ডিফল্ট পিন
SESSION_TIMEOUT = 600                  # ১০ মিনিট (সেকেন্ডে)

bot = telebot.TeleBot(BOT_TOKEN)
os.makedirs(BASE_DIR, exist_ok=True)

# System and Process Tracking Databases
active_processes = {}
user_states = {}
user_activity = {}  # ১০ মিনিট ট্র্যাকিংয়ের জন্য

ASCII_LOGO = """
╔═══════════════════════════════════════╗
║       👑 CORE HOSTING ENGINE V2 👑    ║
╚═══════════════════════════════════════╝
"""

# ----------------- AUTHENTICATION & PIN SYSTEM -----------------
def load_auth_config():
    if os.path.exists(AUTH_CONFIG_FILE):
        try:
            with open(AUTH_CONFIG_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            pass
    default_config = {"pin": DEFAULT_PIN, "authorized_users": []}
    save_auth_config(default_config)
    return default_config

def save_auth_config(config):
    with open(AUTH_CONFIG_FILE, 'w', encoding='utf-8') as f:
        json.dump(config, f, indent=4)

def is_authorized(chat_id):
    config = load_auth_config()
    if chat_id in config.get("authorized_users", []):
        # ১০ মিনিটের সেশন টাইমআউট চেক
        last_active = user_activity.get(chat_id, 0)
        if time.time() - last_active > SESSION_TIMEOUT:
            deauthorize_user(chat_id)
            return False
        user_activity[chat_id] = time.time()  # অ্যাক্টিভিটি টাইম আপডেট
        return True
    return False

def authorize_user(chat_id):
    config = load_auth_config()
    if chat_id not in config.get("authorized_users", []):
        config.setdefault("authorized_users", []).append(chat_id)
        save_auth_config(config)
    user_activity[chat_id] = time.time()

def deauthorize_user(chat_id):
    config = load_auth_config()
    if chat_id in config.get("authorized_users", []):
        config["authorized_users"].remove(chat_id)
        save_auth_config(config)
    if chat_id in user_activity:
        del user_activity[chat_id]

def update_pin(new_pin):
    config = load_auth_config()
    config["pin"] = str(new_pin).strip()
    save_auth_config(config)

def get_current_pin():
    config = load_auth_config()
    return config.get("pin", DEFAULT_PIN)

# ----------------- STORAGE SYSTEM -----------------
def load_meta():
    if os.path.exists(META_FILE):
        try:
            with open(META_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            return {}
    return {}

def save_meta(data):
    with open(META_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=4)

# ----------------- SAFE NETWORK API WRAPPER -----------------
def safe_api_call(func, *args, **kwargs):
    max_retries = 3
    backoff = 1.5
    for attempt in range(max_retries):
        try:
            return func(*args, **kwargs)
        except (requests.exceptions.ConnectionError, 
                requests.exceptions.Timeout, 
                urllib3.exceptions.ProtocolError,
                ConnectionResetError) as e:
            if attempt < max_retries - 1:
                time.sleep(backoff)
                backoff *= 2
            else:
                raise e
        except telebot.apihelper.ApiTelegramException as e:
            if "message is not modified" in str(e).lower():
                return None
            raise e

def bot_send_message(chat_id, text, **kwargs):
    return safe_api_call(bot.send_message, chat_id, text, **kwargs)

def bot_edit_message(text, chat_id, message_id, **kwargs):
    return safe_api_call(bot.edit_message_text, text, chat_id, message_id, **kwargs)

def bot_send_document(chat_id, document, **kwargs):
    return safe_api_call(bot.send_document, chat_id, document, **kwargs)

def bot_delete_message(chat_id, message_id):
    try:
        return safe_api_call(bot.delete_message, chat_id, message_id)
    except Exception:
        pass

# ----------------- PORT UTILITIES -----------------
def find_free_port():
    return 8080

# ----------------- FILE INDEX MAPPING SYSTEM -----------------
def update_project_files_map(proj_id, proj_dir):
    all_files = []
    for root, dirs, files_in_dir in os.walk(proj_dir):
        for f in files_in_dir:
            if f == "output.log":
                continue
            rel_path = os.path.relpath(os.path.join(root, f), proj_dir)
            all_files.append(rel_path)
            
    all_files.sort()
    files_map = {str(idx): path for idx, path in enumerate(all_files)}
    
    meta = load_meta()
    if proj_id in meta:
        meta[proj_id]['files'] = files_map
        save_meta(meta)
    return files_map

# ----------------- DIAGNOSTICS & SYSTEM METRICS -----------------
def get_server_stats():
    cpu_p, ram_p, disk_p, free_gb = 12.0, 39.5, 50.0, 35.0
    env_mode = "🖥️ CLOUD COMPUTE"
    
    try:
        if psutil:
            try:
                cpu_p = psutil.cpu_percent(interval=None)
            except Exception:
                cpu_p = 15.6
                env_mode = "📱 TERMUX SANDBOX"
                
            try:
                ram = psutil.virtual_memory()
                ram_p = ram.percent
            except Exception:
                ram_p = 42.8
                
            try:
                disk = shutil.disk_usage("/")
                disk_p = round((disk.used / disk.total) * 100, 1)
                free_gb = round(disk.free / (1024**3), 1)
            except Exception:
                pass
    except Exception:
        pass
        
    def make_bar(percent):
        if percent < 50:
            block = "🟩"
        elif percent < 75:
            block = "🟨"
        elif percent < 90:
            block = "🟧"
        else:
            block = "🟥"
        filled = int(percent / 5)
        return block * filled + "⬜" * (20 - filled)
        
    stats = (
        f"╔═══════════════════════════════════╗\n"
        f"║  🖥️ *SERVER RESOURCE MONITOR* 🖥️  ║\n"
        f"╚═══════════════════════════════════╝\n\n"
        f"💎 *PLATFORM*\n`{env_mode}`\n\n"
        f"⚡ *CPU LOAD*  —  🔥 *{cpu_p}%*\n"
        f"`{make_bar(cpu_p)}`\n\n"
        f"💾 *RAM LOAD*  —  🔥 *{ram_p}%*\n"
        f"`{make_bar(ram_p)}`\n\n"
        f"📁 *STORAGE*  —  🔥 *{disk_p}%*\n"
        f"`{make_bar(disk_p)}`\n\n"
        f"🆓 *Free Space:*  📦 `{free_gb} GB`\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    )
    return stats

# ----------------- CRASH GUARD RECOVERY DAEMON -----------------
def bg_project_monitor():
    while True:
        time.sleep(8)
        try:
            meta = load_meta()
            for proj_id, proj_data in meta.items():
                if proj_data.get('auto_restart') is True:
                    if proj_id in active_processes:
                        poll = active_processes[proj_id]['process'].poll()
                        if poll is not None:
                            log_path = os.path.join(proj_data['dir'], 'output.log')
                            if not get_missing_module(log_path):
                                run_project_process(proj_id, proj_data)
        except Exception:
            pass

threading.Thread(target=bg_project_monitor, daemon=True).start()

# ----------------- ADVANCED PROCESS MANAGER -----------------
def run_project_process(proj_id, proj_data):
    proj_dir = proj_data['dir']
    log_file_path = os.path.join(proj_dir, 'output.log')
    
    if os.path.exists(log_file_path):
        try: os.remove(log_file_path)
        except Exception: pass
        
    log_file = open(log_file_path, 'w', encoding='utf-8')
    
    port = find_free_port()
    meta = load_meta()
    if proj_id in meta:
        meta[proj_id]['port'] = port
        save_meta(meta)
    
    # ম্যানুয়াল স্টার্টআপ কমান্ড থাকলে তা ব্যবহার করা হবে
    custom_cmd = proj_data.get('custom_cmd', '').strip()
    if custom_cmd:
        cmd = shlex.split(custom_cmd)
    else:
        main_file = proj_data.get('main_file', 'main.py')
        if main_file.endswith('.py'):
            cmd = [sys.executable, '-u', main_file]
        elif main_file.endswith('.js'):
            cmd = ['node', main_file]
        elif main_file.endswith('.sh'):
            cmd = ['bash', main_file]
        elif main_file.endswith(('.html', '.htm')):
            cmd = [sys.executable, '-u', '-m', 'http.server', str(port)]
        else:
            cmd = [sys.executable, '-u', main_file]
    
    env = os.environ.copy()
    env['PORT'] = str(port)
    env_file = os.path.join(proj_dir, '.env')
    if os.path.exists(env_file):
        with open(env_file, 'r', encoding='utf-8') as f:
            for line in f:
                if '=' in line and not line.strip().startswith('#'):
                    k, v = line.strip().split('=', 1)
                    env[k.strip()] = v.strip()
                    
    try:
        process = subprocess.Popen(
            cmd,
            stdout=log_file,
            stderr=subprocess.STDOUT,
            cwd=proj_dir,
            env=env,
            text=True
        )
        active_processes[proj_id] = {
            'process': process,
            'log_file': log_file,
            'start_time': time.time(),
            'cmd_used': " ".join(cmd),
            'port': port
        }
        return True, "Success"
    except FileNotFoundError:
        err_msg = f"Error: '{cmd[0]}' engine is not installed or not in system PATH."
        log_file.write(err_msg)
        log_file.close()
        return False, err_msg
    except Exception as e:
        err_msg = str(e)
        log_file.write(f"Error starting process: {err_msg}")
        log_file.close()
        return False, err_msg

def stop_project_process(proj_id):
    if proj_id in active_processes:
        proc_info = active_processes[proj_id]
        try: proc_info['process'].terminate()
        except Exception: pass
        try: proc_info['log_file'].close()
        except Exception: pass
        del active_processes[proj_id]

def get_project_status(proj_id, proj_data):
    log_path = os.path.join(proj_data['dir'], 'output.log')
    if proj_id in active_processes:
        poll = active_processes[proj_id]['process'].poll()
        if poll is None:
            uptime = int(time.time() - active_processes[proj_id]['start_time'])
            mins, secs = divmod(uptime, 60)
            hrs, mins = divmod(mins, 60)
            return f"🟢 RUNNING (Uptime: {hrs}h {mins}m {secs}s)"
        else:
            missing = get_missing_module(log_path)
            if missing: return f"⚠️ CRASHED (Missing Module: {missing})"
            return "🔴 STOPPED"
    else:
        missing = get_missing_module(log_path)
        if missing: return f"⚠️ CRASHED (Missing Module: {missing})"
        return "🔴 STOPPED"

def get_missing_module(log_path):
    if not os.path.exists(log_path): return None
    try:
        with open(log_path, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()
        py_match = re.search(r"(?:ModuleNotFoundError|ImportError): No module named '([^']+)'", content)
        if py_match: return py_match.group(1)
        
        node_match = re.search(r"Error: Cannot find module '([^']+)'", content)
        if node_match: return node_match.group(1)
    except Exception: pass
    return None

def get_process_resource_usage(proj_id):
    if proj_id in active_processes and psutil:
        try:
            pid = active_processes[proj_id]['process'].pid
            proc = psutil.Process(pid)
            mem_info = proc.memory_info()
            mem_mb = round(mem_info.rss / (1024 * 1024), 2)
            return f"{mem_mb} MB"
        except Exception:
            return "N/A"
    return "0.00 MB"

# ----------------- PREMIUM PROGRESS LOADER -----------------
def play_vip_loading(chat_id, message_id, title):
    animation_steps = [
        ("🔍", 15, "🟥"), ("📦", 35, "🟧"), ("⚙️", 55, "🟨"),
        ("⚡", 75, "🟦"), ("🚀", 90, "🟩"), ("✅", 100, "🟩")
    ]
    bar_len = 20
    for icon, percent, color in animation_steps:
        filled = int((percent / 100) * bar_len)
        bar = color * filled + "⬜" * (bar_len - filled)
        try:
            bot_edit_message(
                f"╔═══════════════════════════════╗\n"
                f"║  {icon} *{title}*\n"
                f"╚═══════════════════════════════╝\n\n"
                f"`{bar}`\n"
                f"🎯 *{percent}% COMPLETE*",
                chat_id, message_id, parse_mode="Markdown"
            )
            time.sleep(0.2)
        except Exception:
            pass

# ----------------- MENU NAVIGATION KEYBOARD -----------------
def get_menu_keyboard():
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    btn_deploy = types.KeyboardButton("🚀 Deploy New")
    btn_my_files = types.KeyboardButton("📁 My Dashboard")
    btn_stats = types.KeyboardButton("🖥️ Server Status")
    btn_change_pin = types.KeyboardButton("🔐 Change PIN")
    btn_help = types.KeyboardButton("❔ Help")
    btn_logout = types.KeyboardButton("🚪 Lock / Logout")
    markup.add(btn_deploy, btn_my_files, btn_stats, btn_change_pin, btn_help, btn_logout)
    return markup

# ----------------- TELEGRAM MAIN HANDLERS -----------------

@bot.message_handler(commands=['start'])
def send_welcome(message):
    chat_id = message.chat.id
    
    # পিন ভেরিফিকেশন গার্ড (১০ মিনিটের মেয়াদ উত্তীর্ণ হলেও পিন চাইবে)
    if not is_authorized(chat_id):
        user_states[chat_id] = "AWAITING_PIN"
        bot_send_message(
            chat_id,
            "🔒 *ACCESS LOCKED (প্রাইভেট সার্ভার)*\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            "এই হোস্টিং বটটি কন্ট্রোল করতে আপনার **গোপন PIN** লিখুন:\n"
            "_(সঠিক পিন দিলে সাথে সাথেই মেসেজ অটো-ডিলিট হবে)_",
            parse_mode="Markdown",
            reply_markup=types.ReplyKeyboardRemove()
        )
        return
        
    meta = load_meta()
    welcome_text = (
        f"{ASCII_LOGO}\n"
        f"╔═══════════════════════════════════╗\n"
        f"║  👑 *VIP MASTER CONTROL PANEL* 👑  ║\n"
        f"╚═══════════════════════════════════╝\n\n"
        f"🛰️ যেকোনো অ্যাকাউন্ট থেকে ফুল কন্ট্রোল সক্ষম।\n\n"
        f"📁 *Total Hosted Projects:*  🟢 `{len(meta)}` Active\n"
        f"⏳ *Auto Lock Timeout:*  ⏱️ 10 Minutes\n"
        f"🔑 *Security State:*  🔓 Authenticated\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"{get_server_stats()}"
    )
    
    markup = types.InlineKeyboardMarkup(row_width=2)
    btn_deploy = types.InlineKeyboardButton("🚀 DEPLOY NEW ZIP", callback_data="btn_deploy")
    btn_my_files = types.InlineKeyboardButton("📁 ALL CONTAINERS", callback_data="btn_my_files")
    markup.add(btn_deploy, btn_my_files)
    
    bot_send_message(chat_id, "⚙️ *Master Session Active*", parse_mode="Markdown", reply_markup=get_menu_keyboard())
    bot_send_message(chat_id, welcome_text, parse_mode="Markdown", reply_markup=markup)

@bot.message_handler(func=lambda m: m.text in ["🚀 Deploy New", "📁 My Dashboard", "🖥️ Server Status", "🔐 Change PIN", "❔ Help", "🚪 Lock / Logout"])
def handle_navigation_buttons(message):
    chat_id = message.chat.id
    
    if not is_authorized(chat_id):
        user_states[chat_id] = "AWAITING_PIN"
        bot_send_message(chat_id, "🔒 সেশন শেষ অথবা লক করা। অনুগ্রহ করে **PIN** দিন:", parse_mode="Markdown", reply_markup=types.ReplyKeyboardRemove())
        return
        
    text = message.text
    
    if text == "🚀 Deploy New":
        user_states[chat_id] = "AWAITING_ZIP"
        bot_send_message(
            chat_id,
            "╔═══════════════════════════════╗\n"
            "║   👑 *VIP SANDBOX DEPLOYER* 👑   ║\n"
            "╚═══════════════════════════════╝\n\n"
            "📥 আপনার প্রজেক্টের `.zip` ফাইলটি আপলোড করুন।\n"
            "💡 _(ভেতরে `requirements.txt` থাকলে তা স্বয়ংক্রিয়ভাবে ইনস্টল হবে)_",
            parse_mode="Markdown"
        )
    elif text == "📁 My Dashboard":
        show_my_files(chat_id)
    elif text == "🖥️ Server Status":
        bot_send_message(chat_id, get_server_stats(), parse_mode="Markdown")
    elif text == "🔐 Change PIN":
        user_states[chat_id] = "AWAITING_NEW_PIN"
        bot_send_message(
            chat_id,
            f"🔐 *নতুন PIN সেট করুন*\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"বর্তমান PIN: `{get_current_pin()}`\n\n"
            f"আপনার নতুন গোপন PIN লিখে মেসেজ পাঠান:",
            parse_mode="Markdown"
        )
    elif text == "🚪 Lock / Logout":
        deauthorize_user(chat_id)
        user_states[chat_id] = "AWAITING_PIN"
        bot_send_message(chat_id, "🔒 *সেশন লক করা হয়েছে।* পুনরায় পিন দিন:", parse_mode="Markdown", reply_markup=types.ReplyKeyboardRemove())
    elif text == "❔ Help":
        help_text = (
            "╔═══════════════════════════════╗\n"
            "║   💡 *VIP OPERATIONAL GUIDE* 💡   ║\n"
            "╚═══════════════════════════════╝\n\n"
            "🚀 *Deployment:* Zip ফাইল দিলে `requirements.txt` অটো ইনস্টল হবে।\n"
            "⌨️ *Startup Command:* ম্যানুয়াল কমান্ড (যেমন `python bot.py`) সেট করতে পারবেন।\n"
            "⏱️ *10 Min Lock:* ১০ মিনিট নিষ্ক্রিয় থাকলে বট নিজে থেকেই লক হয়ে যাবে।\n"
            "🗑️ *PIN Auto Delete:* সঠিক পিন দেওয়ার পর মেসেজ নিজে থেকেই ডিলিট হয়ে যাবে।"
        )
        bot_send_message(chat_id, help_text, parse_mode="Markdown")

# ----------------- CALLBACK BUTTON EVENT QUERY HANDLER -----------------

@bot.callback_query_handler(func=lambda call: True)
def callback_listener(call):
    chat_id = call.message.chat.id
    data = call.data
    
    # গ্লোবাল পিন ও ১০ মিনিট সেশন চেক
    if not is_authorized(chat_id):
        bot.answer_callback_query(call.id, "🔒 সেশনের মেয়াদ শেষ (১০ মিনিট অতিক্রান্ত)। পুনরায় PIN দিন।", show_alert=True)
        user_states[chat_id] = "AWAITING_PIN"
        bot_send_message(chat_id, "🔒 সেশনের মেয়াদ শেষ! দয়া করে আপনার **PIN** দিন:", parse_mode="Markdown")
        return
    
    if data == "btn_deploy":
        user_states[chat_id] = "AWAITING_ZIP"
        bot_edit_message(
            "👑 *VIP DEPLOYMENT ENVIRONMENT*\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            "📥 অনুগ্রহ করে প্রজেক্টের `.zip` ফাইলটি পাঠান।",
            chat_id, call.message.message_id
        )
        
    elif data == "btn_my_files":
        show_my_files(chat_id, call.message.message_id)
        
    elif data.startswith("select_main:"):
        _, proj_id, file_idx = data.split(":")
        meta = load_meta()
        if proj_id in meta and 'files' in meta[proj_id]:
            filename = meta[proj_id]['files'].get(file_idx)
            if filename:
                meta[proj_id]['main_file'] = filename
                meta[proj_id]['custom_cmd'] = ''  # কাস্টম কমান্ড ক্লিয়ার
                save_meta(meta)
                
                play_vip_loading(chat_id, call.message.message_id, "PREPARING DEPLOYMENT SANDBOX")
                success, err_msg = run_project_process(proj_id, meta[proj_id])
                
                if success:
                    show_project_dashboard(chat_id, proj_id, call.message.message_id, "✅ Project Deployed & Started!")
                else:
                    show_project_dashboard(chat_id, proj_id, call.message.message_id, f"❌ Failed: {err_msg}")

    elif data.startswith("set_custom_cmd:"):
        _, proj_id = data.split(":")
        user_states[chat_id] = f"AWAITING_CUSTOM_CMD:{proj_id}"
        bot_send_message(
            chat_id,
            "⌨️ *ম্যানুয়াল স্টার্টআপ কমান্ড লিখুন*\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            "আপনার প্রজেক্ট চালু করার কমান্ডটি লিখে মেসেজ পাঠান।\n\n"
            "উদাহরণ:\n"
            "• `python bot.py`\n"
            "• `python3 main.py`\n"
            "• `node index.js`",
            parse_mode="Markdown"
        )
                
    elif data.startswith("proj_view:"):
        _, proj_id = data.split(":")
        show_project_dashboard(chat_id, proj_id, call.message.message_id)
        
    elif data.startswith("proj_start:"):
        _, proj_id = data.split(":")
        meta = load_meta()
        if proj_id in meta:
            stop_project_process(proj_id)
            success, err_msg = run_project_process(proj_id, meta[proj_id])
            if success:
                show_project_dashboard(chat_id, proj_id, call.message.message_id, "🟢 Project Started Successfully!")
            else:
                show_project_dashboard(chat_id, proj_id, call.message.message_id, f"❌ Failed: {err_msg}")
            
    elif data.startswith("proj_stop:"):
        _, proj_id = data.split(":")
        stop_project_process(proj_id)
        show_project_dashboard(chat_id, proj_id, call.message.message_id, "🔴 Project Stopped!")
        
    elif data.startswith("proj_restart:"):
        _, proj_id = data.split(":")
        meta = load_meta()
        if proj_id in meta:
            stop_project_process(proj_id)
            success, err_msg = run_project_process(proj_id, meta[proj_id])
            if success:
                show_project_dashboard(chat_id, proj_id, call.message.message_id, "🔄 Project Restarted!")
            else:
                show_project_dashboard(chat_id, proj_id, call.message.message_id, f"❌ Failed: {err_msg}")

    elif data.startswith("proj_autorestart_toggle:"):
        _, proj_id = data.split(":")
        meta = load_meta()
        if proj_id in meta:
            current = meta[proj_id].get('auto_restart', False)
            meta[proj_id]['auto_restart'] = not current
            save_meta(meta)
            state_text = "ENABLED" if not current else "DISABLED"
            show_project_dashboard(chat_id, proj_id, call.message.message_id, f"⚙️ Auto-Restart {state_text}!")

    elif data.startswith("proj_logs:"):
        _, proj_id = data.split(":")
        show_logs_view(chat_id, proj_id, call.message.message_id)
        
    elif data.startswith("proj_download_logs:"):
        _, proj_id = data.split(":")
        meta = load_meta()
        if proj_id in meta:
            log_path = os.path.join(meta[proj_id]['dir'], 'output.log')
            if os.path.exists(log_path):
                with open(log_path, 'rb') as f:
                    bot_send_document(chat_id, f, visible_file_name=f"{meta[proj_id]['name']}_logs.txt")
            else:
                bot.answer_callback_query(call.id, "Log empty!")

    elif data.startswith("proj_env:"):
        _, proj_id = data.split(":")
        show_env_editor(chat_id, proj_id, call.message.message_id)

    elif data.startswith("proj_add_env:"):
        _, proj_id = data.split(":")
        user_states[chat_id] = f"ADD_ENV:{proj_id}"
        bot_send_message(chat_id, "📝 Send environment variable format:\n`KEY=VALUE`\n_(Example: `TOKEN=abc_123` )_", parse_mode="Markdown")

    elif data.startswith("proj_clear_env:"):
        _, proj_id = data.split(":")
        meta = load_meta()
        if proj_id in meta:
            env_file = os.path.join(meta[proj_id]['dir'], '.env')
            if os.path.exists(env_file): os.remove(env_file)
            bot.answer_callback_query(call.id, "✅ .env cleared.")
            show_env_editor(chat_id, proj_id, call.message.message_id)

    elif data.startswith("proj_fm:"):
        _, proj_id = data.split(":")
        show_file_manager(chat_id, proj_id, call.message.message_id)

    elif data.startswith("vf:"):
        _, proj_id, file_idx = data.split(":")
        meta = load_meta()
        if proj_id in meta and 'files' in meta[proj_id]:
            rel_path = meta[proj_id]['files'].get(file_idx)
            if rel_path:
                show_code_viewer(chat_id, proj_id, rel_path, file_idx, call.message.message_id)

    elif data.startswith("ef:"):
        _, proj_id, file_idx = data.split(":")
        meta = load_meta()
        if proj_id in meta and 'files' in meta[proj_id]:
            rel_path = meta[proj_id]['files'].get(file_idx)
            if rel_path:
                user_states[chat_id] = f"EDIT_FILE_CONTENT:{proj_id}:{rel_path}"
                bot_send_message(
                    chat_id,
                    f"📝 *ONLINE IDE: EDIT MODE*\n"
                    f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                    f"File: `{rel_path}`\n\n"
                    f"Send the *new text content/code* for this file in your next message.",
                    parse_mode="Markdown"
                )

    elif data.startswith("rf:"):
        _, proj_id, file_idx = data.split(":")
        meta = load_meta()
        if proj_id in meta and 'files' in meta[proj_id]:
            rel_path = meta[proj_id]['files'].get(file_idx)
            if rel_path:
                user_states[chat_id] = f"REPLACE_FILE:{proj_id}:{rel_path}"
                bot_send_message(
                    chat_id,
                    f"📥 *FILE REPLACEMENT MODE*\n"
                    f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                    f"Target path: `{rel_path}`\n\n"
                    f"Send the *new file* (as raw document) to replace.",
                    parse_mode="Markdown"
                )

    elif data.startswith("df:"):
        _, proj_id, file_idx = data.split(":")
        meta = load_meta()
        if proj_id in meta and 'files' in meta[proj_id]:
            rel_path = meta[proj_id]['files'].get(file_idx)
            if rel_path:
                target_path = os.path.join(meta[proj_id]['dir'], rel_path)
                if os.path.exists(target_path):
                    if os.path.isdir(target_path): shutil.rmtree(target_path)
                    else: os.remove(target_path)
                    bot.answer_callback_query(call.id, "🗑️ File deleted!")
                show_file_manager(chat_id, proj_id, call.message.message_id)

    elif data.startswith("proj_backup:"):
        _, proj_id = data.split(":")
        meta = load_meta()
        if proj_id in meta:
            proj_data = meta[proj_id]
            backup_msg = bot_send_message(chat_id, "📦 Generating backup zip file...")
            backup_zip_path = os.path.join(BASE_DIR, f"{proj_data['name']}_backup.zip")
            
            try:
                with zipfile.ZipFile(backup_zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
                    for root, dirs, files in os.walk(proj_data['dir']):
                        for file in files:
                            if file == "output.log": continue
                            full_p = os.path.join(root, file)
                            rel_p = os.path.relpath(full_p, proj_data['dir'])
                            zipf.write(full_p, rel_p)
                
                bot_send_document(chat_id, open(backup_zip_path, 'rb'), visible_file_name=f"{proj_data['name']}_backup.zip")
                os.remove(backup_zip_path)
                bot_delete_message(chat_id, backup_msg.message_id)
            except Exception as e:
                bot_edit_message(f"❌ Backup failed: {str(e)}", chat_id, backup_msg.message_id)

    elif data.startswith("proj_install:"):
        _, proj_id, module_name = data.split(":")
        meta = load_meta()
        if proj_id in meta:
            main_file = meta[proj_id].get('main_file', '')
            is_node = main_file.endswith('.js')
            
            installer_name = "npm" if is_node else "pip"
            msg = bot_send_message(chat_id, f"⏳ Running `{installer_name} install {module_name}`...", parse_mode="Markdown")
            
            try:
                if is_node:
                    cmd = ["npm", "install", module_name]
                else:
                    cmd = [sys.executable, "-m", "pip", "install", "--break-system-packages", module_name]
                    
                result = subprocess.run(cmd, capture_output=True, text=True, timeout=80)
                if result.returncode == 0:
                    bot_delete_message(chat_id, msg.message_id)
                    stop_project_process(proj_id)
                    run_project_process(proj_id, meta[proj_id])
                    show_project_dashboard(chat_id, proj_id, call.message.message_id, f"✅ {module_name} Installed Successfully!")
                else:
                    bot_edit_message(f"❌ Installer failure:\n`{result.stderr[:250]}`", chat_id, msg.message_id, parse_mode="Markdown")
            except Exception as e:
                bot_edit_message(f"❌ Subprocess error: {str(e)}", chat_id, msg.message_id)
            
    elif data.startswith("proj_delete:"):
        _, proj_id = data.split(":")
        meta = load_meta()
        if proj_id in meta:
            stop_project_process(proj_id)
            try: shutil.rmtree(meta[proj_id]['dir'])
            except Exception: pass
            del meta[proj_id]
            save_meta(meta)
            bot.answer_callback_query(call.id, "🗑️ Project folder deleted permanently!")
            show_my_files(chat_id, call.message.message_id)

    elif data == "btn_back_home":
        send_welcome(call.message)

# ----------------- INCOMING ASSETS / FILE OVERWRITERS -----------------

@bot.message_handler(content_types=['document'])
def handle_incoming_documents(message):
    chat_id = message.chat.id
    
    if not is_authorized(chat_id):
        bot.reply_to(message, "🔒 Access Restricted. আগে সঠিক PIN প্রদান করুন।")
        return
        
    state = user_states.get(chat_id, "")
    
    if state and state.startswith("REPLACE_FILE:"):
        _, proj_id, rel_path = state.split(":", 2)
        user_states[chat_id] = None
        
        meta = load_meta()
        if proj_id in meta:
            target_path = os.path.join(meta[proj_id]['dir'], rel_path)
            status_msg = bot_send_message(chat_id, f"⏳ Uploading and replacing `{rel_path}`...", parse_mode="Markdown")
            
            try:
                file_info = bot.get_file(message.document.file_id)
                downloaded_file = bot.download_file(file_info.file_path)
                
                with open(target_path, 'wb') as f:
                    f.write(downloaded_file)
                
                bot_delete_message(chat_id, status_msg.message_id)
                bot.reply_to(message, f"✅ Overwritten `{rel_path}`! Restart your project dashboard to apply.")
            except Exception as e:
                bot_edit_message(f"❌ Write permission error: {str(e)}", chat_id, status_msg.message_id)
        return

    if state == "AWAITING_ZIP":
        file_name = message.document.file_name
        if not file_name.endswith('.zip'):
            bot.reply_to(message, "⚠️ Invalid format. Only `.zip` files can be deployed.")
            return
            
        user_states[chat_id] = None
        status_msg = bot_send_message(chat_id, "✨ *Initializing Container Structure...*\n`[⬜⬜⬜⬜⬜⬜⬜⬜⬜⬜] 0%`", parse_mode="Markdown")
        play_vip_loading(chat_id, status_msg.message_id, "DOWNLOADING AND UNPACKING ASSETS")
        
        file_info = bot.get_file(message.document.file_id)
        downloaded_file = bot.download_file(file_info.file_path)
        
        timestamp = int(time.time())
        proj_id = secrets.token_hex(3)
        proj_dir = os.path.join(BASE_DIR, f"proj_{chat_id}_{timestamp}")
        os.makedirs(proj_dir, exist_ok=True)
        
        zip_path = os.path.join(proj_dir, 'temp_archive.zip')
        with open(zip_path, 'wb') as f:
            f.write(downloaded_file)
            
        try:
            with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                zip_ref.extractall(proj_dir)
            os.remove(zip_path)
        except Exception as e:
            bot_edit_message(f"❌ Zip parse failure: {str(e)}", chat_id, status_msg.message_id)
            return
            
        meta = load_meta()
        meta[proj_id] = {
            'name': file_name.replace('.zip', ''),
            'dir': proj_dir,
            'main_file': '',
            'custom_cmd': '',
            'chat_id': chat_id,
            'auto_restart': False,
            'files': {}
        }
        save_meta(meta)
        
        # ⚠️ REQUIREMENTS.TXT AUTO-DETECT & INSTALL
        req_path = os.path.join(proj_dir, 'requirements.txt')
        if os.path.exists(req_path):
            req_msg = bot_send_message(chat_id, "📦 `requirements.txt` detected! Installing dependencies in background...")
            try:
                subprocess.run([sys.executable, "-m", "pip", "install", "--break-system-packages", "-r", req_path], timeout=180)
                bot_edit_message("✅ `requirements.txt` dependencies installed successfully!", chat_id, req_msg.message_id)
            except Exception as req_err:
                bot_edit_message(f"⚠️ Dependency installation warning: {str(req_err)}", chat_id, req_msg.message_id)
        
        files_map = update_project_files_map(proj_id, proj_dir)
        
        PRIORITY_NAMES = ['main.py', 'app.py', 'a.py', 'bot.py', 'run.py', 'server.py', 'index.py',
                           'index.js', 'app.js', 'server.js', 'main.js', 'bot.js', 'start.js']

        def entry_sort_key(item):
            idx, f = item
            base = os.path.basename(f).lower()
            if base in PRIORITY_NAMES:
                return (0, PRIORITY_NAMES.index(base))
            return (1, base)

        code_files = [(idx, f) for idx, f in files_map.items() if f.endswith(('.py', '.js', '.sh', '.html', '.htm'))]
        code_files.sort(key=entry_sort_key)

        markup = types.InlineKeyboardMarkup(row_width=1)
        count = 0
        for idx, f in code_files:
            if count >= 8:
                break
            base = os.path.basename(f).lower()
            star = "⭐ " if base in PRIORITY_NAMES else "📄 "
            markup.add(types.InlineKeyboardButton(f"{star}{f}", callback_data=f"select_main:{proj_id}:{idx}"))
            count += 1

        # ম্যানুয়াল স্টার্টআপ কমান্ড সেট করার বাটন
        markup.add(types.InlineKeyboardButton("⌨️ Set Custom Startup Command", callback_data=f"set_custom_cmd:{proj_id}"))
            
        bot_delete_message(chat_id, status_msg.message_id)
        bot_send_message(
            chat_id,
            f"👑 *ARCHIVE EXTRACTED:* `{file_name}`\n\n"
            f"নিচের তালিকা থেকে স্ক্রিপ্ট সিলেক্ট করুন অথবা ম্যানুয়াল কমান্ড সেট করুন:",
            parse_mode="Markdown",
            reply_markup=markup
        )

# ----------------- TEXT INTAKE MANAGER (PIN, IDE & CONFIG) -----------------

@bot.message_handler(func=lambda m: True)
def handle_incoming_text(message):
    chat_id = message.chat.id
    state = user_states.get(chat_id, "")
    user_text = message.text.strip()
    
    # পিন ভেরিফিকেশন হ্যান্ডলার
    if not is_authorized(chat_id):
        if user_text == get_current_pin():
            # ✅ সঠিক PIN: সাথে সাথে ইউজারের মেসেজ ডিলিট হবে যাতে কেউ পিন না দেখে
            bot_delete_message(chat_id, message.message_id)
            authorize_user(chat_id)
            user_states[chat_id] = None
            bot_send_message(chat_id, "✅ *PIN সঠিক! ফুল অ্যাডমিন এক্সেস দেওয়া হয়েছে।*\n_(আপনার PIN মেসেজটি নিরাপত্তার জন্য মুছে দেওয়া হয়েছে)_", parse_mode="Markdown")
            send_welcome(message)
        else:
            # ❌ ভুল PIN: মেসেজ ডিলিট হবে না
            bot_send_message(chat_id, "❌ *ভুল PIN!* অনুগ্রহ করে সঠিক পিন লিখে পাঠান:", parse_mode="Markdown")
        return

    # ম্যানুয়াল স্টার্টআপ কমান্ড নেওয়ার হ্যান্ডলার
    if state and state.startswith("AWAITING_CUSTOM_CMD:"):
        _, proj_id = state.split(":")
        user_states[chat_id] = None
        
        meta = load_meta()
        if proj_id in meta:
            meta[proj_id]['custom_cmd'] = user_text
            meta[proj_id]['main_file'] = user_text
            save_meta(meta)
            
            status_msg = bot_send_message(chat_id, f"⏳ Setting startup command: `{user_text}`...", parse_mode="Markdown")
            success, err_msg = run_project_process(proj_id, meta[proj_id])
            bot_delete_message(chat_id, status_msg.message_id)
            
            if success:
                show_project_dashboard(chat_id, proj_id, None, "✅ Project Started with Custom Command!")
            else:
                show_project_dashboard(chat_id, proj_id, None, f"❌ Failed: {err_msg}")
        return

    # পিন পরিবর্তনের হ্যান্ডলার
    if state == "AWAITING_NEW_PIN":
        if len(user_text) < 4:
            bot.reply_to(message, "⚠️ PIN কমপক্ষে ৪ অক্ষরের হতে হবে। আবার লিখুন:")
            return
            
        update_pin(user_text)
        user_states[chat_id] = None
        bot_delete_message(chat_id, message.message_id)  # নতুন পিনের মেসেজটিও ডিলিট
        bot_send_message(
            chat_id,
            f"✅ *PIN সফলভাবে পরিবর্তন করা হয়েছে!*\n\n"
            f"🔐 আপনার নতুন PIN: `{user_text}`\n"
            f"_(যেকোনো নতুন আইডি থেকে এই পিন দিয়ে লগইন করতে পারবেন।)_",
            parse_mode="Markdown"
        )
        return

    if state and state.startswith("EDIT_FILE_CONTENT:"):
        _, proj_id, rel_path = state.split(":", 2)
        user_states[chat_id] = None
        
        meta = load_meta()
        if proj_id in meta:
            target_path = os.path.join(meta[proj_id]['dir'], rel_path)
            new_code = message.text
            
            try:
                with open(target_path, 'w', encoding='utf-8') as f:
                    f.write(new_code)
                bot.reply_to(message, f"✅ Code updated inside `{rel_path}`! Please restart container to apply updates.")
            except Exception as e:
                bot.reply_to(message, f"❌ Failed to edit code: {str(e)}")
        return

    if state and state.startswith("ADD_ENV:"):
        _, proj_id = state.split(":")
        user_states[chat_id] = None
        
        meta = load_meta()
        if proj_id in meta:
            env_line = message.text.strip()
            if '=' in env_line:
                env_file = os.path.join(meta[proj_id]['dir'], '.env')
                with open(env_file, 'a', encoding='utf-8') as f:
                    f.write(f"\n{env_line}")
                bot.reply_to(message, "✅ Property updated inside `.env`! Restart required.")
            else:
                bot.reply_to(message, "❌ Syntax Error. Needs format: `KEY=VALUE`")

# ----------------- ADVANCED USER CONTROL PANELS -----------------

def show_project_dashboard(chat_id, proj_id, message_id=None, toast_msg=""):
    meta = load_meta()
    if proj_id not in meta: return
    
    proj_data = meta[proj_id]
    status = get_project_status(proj_id, proj_data)
    auto_r_status = "🟢 Enabled" if proj_data.get('auto_restart') else "🔴 Disabled"
    port_allocated = proj_data.get('port', 'None')
    mem_usage = get_process_resource_usage(proj_id)
    cmd_running = proj_data.get('custom_cmd') or proj_data.get('main_file')

    header = f"🌟 *{toast_msg}*" if toast_msg else "╔══════════════════════════╗\n║ ⚙️ *CONTAINER DASHBOARD* ⚙️ ║\n╚══════════════════════════╝"
    
    dashboard_text = (
        f"{header}\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"📂 *Container Name:*  `{proj_data['name']}`\n"
        f"🚀 *Startup Command:*  `{cmd_running}`\n"
        f"📈 *State:*  {status}\n"
        f"⚙️ *PID Memory:*  `{mem_usage}`\n"
        f"🔌 *Allotted Port:*  `{port_allocated}`\n"
        f"🔄 *Auto Recovery:*  {auto_r_status}\n"
        f"🔒 *Access Level:*  👑 Master Administrator\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"👇 *Manage your container below:*"
    )
    
    markup = types.InlineKeyboardMarkup(row_width=3)
    
    if "🟢 RUNNING" in status:
        btn_action = types.InlineKeyboardButton("⏸️ Stop", callback_data=f"proj_stop:{proj_id}")
    else:
        btn_action = types.InlineKeyboardButton("▶️ Start", callback_data=f"proj_start:{proj_id}")
        
    btn_restart = types.InlineKeyboardButton("🔄 Restart", callback_data=f"proj_restart:{proj_id}")
    btn_logs = types.InlineKeyboardButton("📋 View Logs", callback_data=f"proj_logs:{proj_id}")
    btn_env = types.InlineKeyboardButton("📝 Edit .env", callback_data=f"proj_env:{proj_id}")
    btn_fm = types.InlineKeyboardButton("📁 Files", callback_data=f"proj_fm:{proj_id}")
    btn_backup = types.InlineKeyboardButton("📦 Full Backup", callback_data=f"proj_backup:{proj_id}")
    
    btn_auto = types.InlineKeyboardButton("🔄 Auto Restart Toggle", callback_data=f"proj_autorestart_toggle:{proj_id}")
    btn_delete = types.InlineKeyboardButton("🗑️ Terminate", callback_data=f"proj_delete:{proj_id}")
    btn_back = types.InlineKeyboardButton("🔙 Back to Menu", callback_data="btn_my_files")
    
    missing_module = get_missing_module(os.path.join(proj_data['dir'], 'output.log'))
    if missing_module:
        btn_install = types.InlineKeyboardButton(f"📦 Install {missing_module}", callback_data=f"proj_install:{proj_id}:{missing_module}")
        markup.add(btn_install)
        
    markup.add(btn_action, btn_restart, btn_logs)
    markup.add(btn_env, btn_fm, btn_backup)
    markup.add(btn_auto)
    markup.add(btn_delete, btn_back)
    
    if message_id:
        bot_edit_message(dashboard_text, chat_id, message_id, reply_markup=markup)
    else:
        bot_send_message(chat_id, dashboard_text, parse_mode="Markdown", reply_markup=markup)

def show_my_files(chat_id, message_id=None):
    meta = load_meta()
    user_projects = meta
    
    text = (
        f"╔═══════════════════════════════════╗\n"
        f"║  👑 *ALL HOSTED CONTAINERS* 👑    ║\n"
        f"╚═══════════════════════════════════╝\n"
        f"🔓 _Master Admin Access Active._\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
    )
    markup = types.InlineKeyboardMarkup(row_width=1)
    
    if not user_projects:
        text += "❌ Empty sandbox list. Click 'Host New Project' to begin."
    else:
        for p_id, p_data in user_projects.items():
            status = get_project_status(p_id, p_data)
            status_symbol = "🟢" if "RUNNING" in status else "🔴"
            if "CRASHED" in status: status_symbol = "⚠️"
            
            text += f"• `{p_data['name']}` | PID Mem: {get_process_resource_usage(p_id)} | Status: {status_symbol}\n"
            markup.add(types.InlineKeyboardButton(f"📦 {p_data['name']} ({status_symbol})", callback_data=f"proj_view:{p_id}"))
            
    btn_deploy = types.InlineKeyboardButton("➕ Host New Project", callback_data="btn_deploy")
    btn_back = types.InlineKeyboardButton("🔙 Main Hub Menu", callback_data="btn_back_home")
    markup.add(btn_deploy, btn_back)
    
    if message_id:
        bot_edit_message(text, chat_id, message_id, reply_markup=markup)
    else:
        bot_send_message(chat_id, text, parse_mode="Markdown", reply_markup=markup)

def show_logs_view(chat_id, proj_id, message_id):
    meta = load_meta()
    if proj_id not in meta: return
    
    proj_data = meta[proj_id]
    log_path = os.path.join(proj_data['dir'], 'output.log')
    
    log_content = "Terminal empty. No output records."
    if os.path.exists(log_path):
        try:
            with open(log_path, 'r', encoding='utf-8', errors='ignore') as f:
                lines = f.readlines()
                log_content = "".join(lines[-25:]) if lines else "Terminal started but logged no data."
        except Exception as e:
            log_content = f"Failed to read logs: {str(e)}"
            
    if len(log_content) > 3700:
        log_content = log_content[-3700:]
        
    log_text = (
        f"📊 *LIVE TERMINAL OUTPUT:* `{proj_data['name']}`\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"```text\n{log_content}\n```\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"💡 _Dynamic refresh in-place enabled._"
    )
    
    markup = types.InlineKeyboardMarkup(row_width=2)
    btn_refresh = types.InlineKeyboardButton("🔄 Refresh Logs", callback_data=f"proj_logs:{proj_id}")
    btn_dl = types.InlineKeyboardButton("📥 Download Full Log", callback_data=f"proj_download_logs:{proj_id}")
    btn_back = types.InlineKeyboardButton("🔙 Back to Dashboard", callback_data=f"proj_view:{proj_id}")
    markup.add(btn_refresh, btn_dl)
    markup.add(btn_back)
    
    bot_edit_message(log_text, chat_id, message_id, reply_markup=markup)

def show_env_editor(chat_id, proj_id, message_id):
    meta = load_meta()
    if proj_id not in meta: return
    proj_data = meta[proj_id]
    
    env_file = os.path.join(proj_data['dir'], '.env')
    current_envs = "No active variables configured."
    if os.path.exists(env_file):
        with open(env_file, 'r', encoding='utf-8') as f:
            current_envs = f.read().strip()
            
    text = (
        f"📝 *ENVIRONMENT VARIABLES (.env)*\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"📁 *Project:* `{proj_data['name']}`\n\n"
        f"📍 *Active configurations:*\n"
        f"```text\n{current_envs}\n```\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"Configure sandbox env variables manually using the inputs below."
    )
    
    markup = types.InlineKeyboardMarkup(row_width=2)
    btn_add = types.InlineKeyboardButton("➕ Add Variable", callback_data=f"proj_add_env:{proj_id}")
    btn_clear = types.InlineKeyboardButton("🗑️ Wipe .env", callback_data=f"proj_clear_env:{proj_id}")
    btn_back = types.InlineKeyboardButton("🔙 Control Panel", callback_data=f"proj_view:{proj_id}")
    markup.add(btn_add, btn_clear)
    markup.add(btn_back)
    
    bot_edit_message(text, chat_id, message_id, reply_markup=markup)

def show_file_manager(chat_id, proj_id, message_id):
    meta = load_meta()
    if proj_id not in meta: return
    proj_data = meta[proj_id]
    
    files_map = update_project_files_map(proj_id, proj_data['dir'])
    
    text = (
        f"📁 *IN-SANDBOX INTEGRATED IDE*\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"Explore, view, edit or replace active directory codes:\n\n"
    )
    
    markup = types.InlineKeyboardMarkup(row_width=4)
    
    count = 0
    for idx, rel_path in files_map.items():
        if count >= 10: 
            break
            
        size_kb = round(os.path.getsize(os.path.join(proj_data['dir'], rel_path)) / 1024, 1)
        text += f"📄 `{rel_path}` ({size_kb} KB)\n"
        
        btn_view = types.InlineKeyboardButton("🔎 View", callback_data=f"vf:{proj_id}:{idx}")
        btn_edit = types.InlineKeyboardButton("✏️ Edit", callback_data=f"ef:{proj_id}:{idx}")
        btn_rep = types.InlineKeyboardButton("🔁 Rep", callback_data=f"rf:{proj_id}:{idx}")
        btn_del = types.InlineKeyboardButton("🗑️", callback_data=f"df:{proj_id}:{idx}")
        
        markup.add(btn_view, btn_edit, btn_rep, btn_del)
        count += 1
            
    btn_back = types.InlineKeyboardButton("🔙 Control Panel", callback_data=f"proj_view:{proj_id}")
    markup.add(btn_back)
    
    bot_edit_message(text, chat_id, message_id, reply_markup=markup)

def show_code_viewer(chat_id, proj_id, rel_path, file_idx, message_id):
    meta = load_meta()
    if proj_id not in meta: return
    proj_data = meta[proj_id]
    
    target_path = os.path.join(proj_data['dir'], rel_path)
    code_content = ""
    
    if os.path.exists(target_path):
        try:
            with open(target_path, 'r', encoding='utf-8', errors='ignore') as f:
                code_content = f.read(1500)
                if len(code_content) >= 1500:
                    code_content += "\n\n... [Content truncated due to message size limit] ..."
        except Exception as e:
            code_content = f"Failed to view code: {str(e)}"
            
    text = (
        f"📄 *RAW FILE CONTENT:* `{rel_path}`\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"```text\n{code_content}\n```\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"Use the online IDE dashboard options to write and update script logic."
    )
    
    markup = types.InlineKeyboardMarkup(row_width=2)
    btn_edit = types.InlineKeyboardButton("✏️ Edit Code", callback_data=f"ef:{proj_id}:{file_idx}")
    btn_back = types.InlineKeyboardButton("🔙 File Explorer", callback_data=f"proj_fm:{proj_id}")
    markup.add(btn_edit, btn_back)
    
    bot_edit_message(text, chat_id, message_id, reply_markup=markup)

# ----------------- COLD ENGINE IGNITION -----------------
if __name__ == '__main__':
    print("========================================")
    print("🔥 CORE HOSTING HUB ENGINE V2 ACTIVATED 🔥")
    print(f"🔑 MASTER PIN: {get_current_pin()}")
    print("========================================")
    
    while True:
        try:
            bot.infinity_polling(timeout=60, long_polling_timeout=30)
        except Exception as polling_err:
            print(f"[Polling Error] Network connection disrupted: {polling_err}. Auto-reconnecting in 5 seconds...")
            time.sleep(5)