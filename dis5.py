from flask import Blueprint, render_template_string, request, flash, redirect, url_for, session, send_from_directory
import os
import sys
import time
import json
import asyncio
import threading
import websockets
import random
from datetime import datetime
import discord
from discord.ext import commands, tasks
import uuid
import atexit
import requests
import re
from werkzeug.utils import secure_filename

# Tạo Blueprint
dis5_bp = Blueprint('dis5', __name__)

# Thư mục upload
UPLOAD_FOLDER = 'uploads/mp3'
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

ALLOWED_EXTENSIONS = {'mp3', 'wav', 'ogg'}

# Biến lưu trữ tasks
SPAM_TASKS = {}
HANG_TASKS = {}

# ====================== HÀM HỖ TRỢ UPLOAD ======================

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def get_uploaded_files():
    """Lấy danh sách file đã upload"""
    try:
        files = []
        for filename in os.listdir(UPLOAD_FOLDER):
            if allowed_file(filename):
                file_path = os.path.join(UPLOAD_FOLDER, filename)
                file_size = os.path.getsize(file_path) / (1024 * 1024)  # MB
                files.append({
                    'name': filename,
                    'size': round(file_size, 2),
                    'path': file_path
                })
        return files
    except:
        return []

# ====================== DISCORD BOT CODE ======================

TOKEN_URL = "https://discord.com/api/v9/users/@me"

async def check_token(token):
    headers = {"Authorization": token}
    async with websockets.connect("wss://gateway.discord.gg/?v=9&encoding=json") as ws:
        await ws.send(json.dumps({"op": 2, "d": {"token": token, "properties": {"$os": "windows", "$browser": "chrome", "$device": "pc"}}}))
        response = await ws.recv()
        if "Invalid" in response:
            return False
        return True

async def fetch_guild_id_for_channel(token, channel_id):
    try:
        headers = {
            "Authorization": token,
            "Content-Type": "application/json"
        }
        
        import aiohttp
        async with aiohttp.ClientSession() as session:
            async with session.get(f"https://discord.com/api/v9/channels/{channel_id}", headers=headers) as response:
                if response.status == 200:
                    channel_data = await response.json()
                    return channel_data.get("guild_id")
                elif response.status == 404:
                    print(f"[{datetime.now().strftime('%H:%M:%S')}] Channel not found (404): The channel ID {channel_id} does not exist or your token doesn't have access to it.")
                    return None
                else:
                    print(f"[{datetime.now().strftime('%H:%M:%S')}] Failed to fetch channel info: HTTP {response.status}")
                    return None
    except Exception as e:
        print(f"[{datetime.now().strftime('%H:%M:%S')}] Error fetching guild ID: {e}")
        return None

class SpamVoice:
    def __init__(self, task_id, token, channel_id, mp3_file):
        self.task_id = task_id
        self.token = token
        self.channel_id = channel_id
        self.mp3_file = mp3_file
        self.client = commands.Bot(command_prefix="!", self_bot=True)
        self.is_running = True
        self.voice = None
        self.status = "🟢 Đang chạy"
        self.start_time = datetime.now()
        
        self.client.event(self.on_ready)
        self.spam_voice = tasks.loop()(self.spam_voice_func)
    
    async def on_ready(self):
        print(f"Login - {self.client.user}")
        self.spam_voice.start()
    
    async def spam_voice_func(self):
        try:
            voice_channel = self.client.get_channel(int(self.channel_id))
            if not voice_channel:
                print(f"Khong Tim Thay Kenh Voice Voi ID: {self.channel_id}")
                return
            
            if not self.voice or not self.voice.is_connected():
                self.voice = await voice_channel.connect()
            
            while self.is_running:
                self.voice.play(discord.FFmpegPCMAudio(self.mp3_file), after=lambda e: print(f'Đa Phat Xong Lap Lai: {e}' if e else 'Đa Phat xong, Lap Laii'))
                while self.voice.is_playing():
                    await asyncio.sleep(1)
        except Exception as e:
            print(f"Loi Trong Qua Trinh Xa Mic: {e}")
            await asyncio.sleep(5)
            await self.reconnect()
    
    async def reconnect(self):
        try:
            voice_channel = self.client.get_channel(int(self.channel_id))
            if voice_channel:
                if self.voice:
                    await self.voice.disconnect()
                self.voice = await voice_channel.connect()
                print(f"Đa Ket Noi Lai Voi Kenh: {voice_channel.name}")
        except Exception as e:
            print(f"Loi Khi Ket Noi Lai: {e}")
    
    def start(self):
        try:
            self.client.run(self.token)
        except Exception as e:
            print(f"Loi: {e}")
    
    def stop(self):
        self.is_running = False
        self.status = "🔴 Đã dừng"
        try:
            self.spam_voice.cancel()
            asyncio.run_coroutine_threadsafe(self.client.close(), self.client.loop)
        except:
            pass

class HangVoice:
    def __init__(self, task_id, token, channel_id, mute, deaf, stream):
        self.task_id = task_id
        self.token = token
        self.channel_id = channel_id
        self.mute = mute
        self.deaf = deaf
        self.stream = stream
        self.ws = None
        self.heartbeat_interval = None
        self.session_id = None
        self.resume_gateway_url = None
        self.last_sequence = None
        self.is_running = True
        self.reconnect_attempts = 0
        self.max_reconnect_attempts = 10
        self.heartbeat_task = None
        self.last_heartbeat_ack = True
        self.ws_connected = False
        self.guild_id = None
        self.HEARTBEAT_TIMEOUT = 30
        self.user_id = None
        self.last_activity = time.time()
        self.idle_timeout = 300
        self.connected = False
        self.status = "🟢 Đang chạy"
        self.start_time = datetime.now()
        
    async def connect(self):
        try:
            self.ws = await websockets.connect("wss://gateway.discord.gg/?v=9&encoding=json", 
                                             ping_interval=None,
                                             max_size=10_000_000,
                                             close_timeout=5)
            self.ws_connected = True
            self.connected = True
            print(f"[{datetime.now().strftime('%H:%M:%S')}] Đa Ket Noi Voi Gateway")
            
            await self.ws.send(json.dumps({
                "op": 2,
                "d": {
                    "token": self.token,
                    "capabilities": 16381,
                    "properties": {
                        "$os": "windows",
                        "$browser": "chrome",
                        "$device": "desktop"
                    },
                    "presence": {
                        "status": "online",
                        "since": 0,
                        "activities": [],
                        "afk": False
                    },
                    "intents": 641
                }
            }))
            print(f"[{datetime.now().strftime('%H:%M:%S')}] Đa Gui Thong Tin Đang Nhap")
            
            self.guild_id = await fetch_guild_id_for_channel(self.token, self.channel_id)
            if self.guild_id:
                print(f"[{datetime.now().strftime('%H:%M:%S')}] Đa Lay Guild ID: {self.guild_id}")
            
            while self.is_running and self.ws_connected:
                try:
                    data = await asyncio.wait_for(self.ws.recv(), timeout=self.HEARTBEAT_TIMEOUT)
                    self.last_activity = time.time()
                    await self.handle_event(json.loads(data))
                except asyncio.TimeoutError:
                    if not self.last_heartbeat_ack:
                        self.ws_connected = False
                        self.connected = False
                        await self.reconnect()
                        break
                except websockets.exceptions.ConnectionClosed as e:
                    self.ws_connected = False
                    self.connected = False
                    await self.reconnect()
                    break
                except Exception as e:
                    await asyncio.sleep(2)
                
        except Exception as e:
            self.ws_connected = False
            self.connected = False
            await self.reconnect()
    
    async def start_stream(self):
        if not self.session_id or not self.stream or not self.connected:
            return False
            
        stream_payload = {
            "op": 18,
            "d": {
                "type": "guild",
                "guild_id": self.guild_id,
                "channel_id": self.channel_id,
                "preferred_region": "vietnam",
                "quality": 0,
                "framerate": 15,
                "width": 854,
                "height": 480
            }
        }
        
        try:
            await self.ws.send(json.dumps(stream_payload))
            return True
        except Exception as e:
            return False
            
    async def heartbeat_loop(self):
        try:
            jitter_offset = random.uniform(0, 1)
            first_heartbeat = True
            
            while self.is_running and self.connected:
                if first_heartbeat:
                    await asyncio.sleep(self.heartbeat_interval * jitter_offset)
                    first_heartbeat = False
                    
                heartbeat = {
                    "op": 1,
                    "d": self.last_sequence
                }
                
                try:
                    await self.ws.send(json.dumps(heartbeat))
                except Exception as e:
                    break
                    
                jitter = random.uniform(0.9, 1.0)
                await asyncio.sleep(self.heartbeat_interval * jitter)
                
                if time.time() - self.last_activity > self.idle_timeout:
                    self.connected = False
                    break
        except asyncio.CancelledError:
            pass
        except Exception as e:
            pass
    
    async def reconnect(self):
        if not self.is_running:
            return
            
        self.reconnect_attempts += 1
        if self.reconnect_attempts > self.max_reconnect_attempts:
            self.reconnect_attempts = 0
            await asyncio.sleep(40)
            
        try:
            if self.ws is not None:
                try:
                    await self.ws.close()
                except:
                    pass
                finally:
                    self.ws = None
                    self.ws_connected = False
                    self.connected = False
            
            if self.heartbeat_task is not None:
                try:
                    self.heartbeat_task.cancel()
                except:
                    pass
                finally:
                    self.heartbeat_task = None
                
            wait_time = min(self.reconnect_attempts * 5, 30)
            await asyncio.sleep(wait_time)
            
            if not self.guild_id:
                self.guild_id = await fetch_guild_id_for_channel(self.token, self.channel_id) 
                
            gateway_url = await get_gateway_url(self.token)
            if not gateway_url:
                gateway_url = "wss://gateway.discord.gg/?v=9&encoding=json"
            
            if self.session_id and self.resume_gateway_url and self.reconnect_attempts < 3:
                try:
                    resume_url = self.resume_gateway_url
                    if not resume_url.startswith("wss://"):
                        resume_url = f"wss://{resume_url}"
                        
                    self.ws = await websockets.connect(f"{resume_url}/?v=9&encoding=json", 
                                                     ping_interval=None,
                                                     max_size=10_000_000,
                                                     close_timeout=5)
                    self.ws_connected = True
                    self.connected = True
                    
                    await self.ws.send(json.dumps({
                        "op": 6,
                        "d": {
                            "token": self.token,
                            "session_id": self.session_id,
                            "seq": self.last_sequence or 0
                        }
                    }))
                    
                    await self.connect()
                except Exception as e:
                    self.session_id = None
                    await asyncio.sleep(3)
                    await self.connect()
            else:
                self.session_id = None
                self.last_sequence = None
                await asyncio.sleep(3)
                await self.connect()
                
        except Exception as e:
            await asyncio.sleep(5)
            asyncio.create_task(self.reconnect())
    
    async def handle_event(self, data):
        op = data.get('op')
        t = data.get('t')
        d = data.get('d')
        s = data.get('s')
        
        if s is not None:
            self.last_sequence = s
            
        if op == 10:
            self.heartbeat_interval = d['heartbeat_interval'] / 1000
            await self.start_heartbeat()
            
        elif op == 0:
            if t == "READY":
                self.session_id = d['session_id']
                self.resume_gateway_url = d.get('resume_gateway_url')
                self.user_id = d.get('user', {}).get('id')
                
                if not self.guild_id:
                    self.guild_id = await fetch_guild_id_for_channel(self.token, self.channel_id)
                    if not self.guild_id and 'guilds' in d and d['guilds']:
                        random_guild = random.choice(d['guilds'])
                        self.guild_id = random_guild.get('id')
                
                self.reconnect_attempts = 0
                await self.join_voice()
                
            elif t == "VOICE_STATE_UPDATE":
                user_id = d.get('user_id')
                if user_id == self.user_id:
                    if d.get('channel_id') and d.get('channel_id') != self.channel_id:
                        await asyncio.sleep(2)
                        await self.join_voice()
                        
            elif t == "VOICE_SERVER_UPDATE":
                await asyncio.sleep(1)
                try:
                    await self.ensure_voice_connected()
                    if self.stream:
                        await self.start_stream()
                except Exception as e:
                    await asyncio.sleep(2)
                    await self.join_voice()
                
        elif op == 9:
            resumable = data.get('d', False)
            if not resumable:
                self.session_id = None
                self.last_sequence = None
            await asyncio.sleep(random.uniform(1, 5))
            await self.reconnect()
            
        elif op == 7:
            await self.reconnect()
            
        elif op == 11:
            self.last_heartbeat_ack = True
    
    async def join_voice(self):
        if not self.is_running or not self.ws_connected:
            return
            
        try:
            if not self.guild_id:
                self.guild_id = await fetch_guild_id_for_channel(self.token, self.channel_id)
                if not self.guild_id:
                    await asyncio.sleep(5)
                    return
            
            payload = {
                "op": 4,
                "d": {
                    "guild_id": self.guild_id,
                    "channel_id": self.channel_id,
                    "self_mute": self.mute,
                    "self_deaf": self.deaf,
                    "self_video": False,
                    "self_stream": True
                }
            }
            
            await self.ws.send(json.dumps(payload))
            
            await asyncio.sleep(2)
            
            stream_payload = {
                "op": 4,
                "d": {
                    "guild_id": self.guild_id,
                    "channel_id": self.channel_id,
                    "self_mute": self.mute,
                    "self_deaf": self.deaf,
                    "self_video": self.stream,
                    "self_stream": True
                }
            }
            
            await self.ws.send(json.dumps(stream_payload))
            
            if self.stream:
                await asyncio.sleep(1)
                await self.start_stream()
            
        except websockets.exceptions.ConnectionClosed as e:
            self.ws_connected = False
            self.connected = False
            await self.reconnect()
        except Exception as e:
            await asyncio.sleep(5)
            await self.rejoin_voice()
    
    async def ensure_voice_connected(self):
        if not self.is_running or not self.ws_connected:
            return
            
        try:
            if not self.guild_id:
                self.guild_id = await fetch_guild_id_for_channel(self.token, self.channel_id)
                
            payload = {
                "op": 4,
                "d": {
                    "guild_id": self.guild_id,
                    "channel_id": self.channel_id,
                    "self_mute": self.mute,
                    "self_deaf": self.deaf,
                    "self_video": self.stream,
                    "self_stream": True
                }
            }
            
            await self.ws.send(json.dumps(payload))
            
            await asyncio.sleep(1)
            
            if self.stream:
                await self.start_stream()
            
        except websockets.exceptions.ConnectionClosed as e:
            self.ws_connected = False
            self.connected = False
            await self.reconnect()
        except Exception as e:
            pass
    
    async def rejoin_voice(self):
        if not self.is_running:
            return
            
        try:
            await asyncio.sleep(2)
            await self.join_voice()
            
        except Exception as e:
            await asyncio.sleep(5)
            await self.rejoin_voice()
    
    async def start_heartbeat(self):
        if self.heartbeat_task is not None:
            try:
                self.heartbeat_task.cancel()
            except:
                pass
        
        async def heartbeat_loop():
            initial_delay = random.random() * self.heartbeat_interval
            await asyncio.sleep(initial_delay)
            
            while self.is_running and self.ws_connected:
                try:
                    if not self.ws_connected:
                        break
                        
                    self.last_heartbeat_ack = False
                    
                    payload = {
                        "op": 1,
                        "d": self.last_sequence
                    }
                    
                    await self.ws.send(json.dumps(payload))
                    
                    ack_timeout = min(self.heartbeat_interval, 15)
                    for _ in range(int(ack_timeout * 2)):
                        if self.last_heartbeat_ack or not self.ws_connected:
                            break
                        await asyncio.sleep(0.5)
                    
                    if not self.last_heartbeat_ack and self.ws_connected:
                        self.ws_connected = False
                        self.connected = False
                        await self.reconnect()
                        return
                    
                    await asyncio.sleep(self.heartbeat_interval)
                    
                except websockets.exceptions.ConnectionClosed as e:
                    self.ws_connected = False
                    self.connected = False
                    await self.reconnect()
                    return
                except Exception as e:
                    if self.is_running:
                        await asyncio.sleep(5)
                        if self.ws_connected:
                            continue
                        else:
                            break
            
            if self.is_running:
                self.ws_connected = False
                self.connected = False
                await self.reconnect()
        
        self.heartbeat_task = asyncio.create_task(heartbeat_loop())
    
    def start(self):
        try:
            asyncio.run(self.connect())
        except KeyboardInterrupt:
            self.stop()
        except Exception as e:
            pass
    
    def stop(self):
        self.is_running = False
        self.status = "🔴 Đã dừng"
        self.ws_connected = False
        self.connected = False
        
        if self.heartbeat_task is not None:
            try:
                self.heartbeat_task.cancel()
            except:
                pass
        
        if self.ws is not None:
            try:
                asyncio.run(self.ws.close())
            except:
                pass

async def get_gateway_url(token):
    try:
        import aiohttp
        async with aiohttp.ClientSession() as session:
            async with session.get(
                "https://discord.com/api/v9/gateway",
                headers={"Authorization": token}
            ) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    url = data["url"] + "/?v=9&encoding=json"
                    return url
                return None
    except Exception as e:
        return None

# ====================== FLASK ROUTES CHO DIS5 ======================

@dis5_bp.route('/')
def dis5_page():
    """Trang chính của dis5 - Discord Voice Tool"""
    
    if 'key' not in session:
        flash('🔒 Vui lòng đăng nhập lại!', 'error')
        return redirect('/')
    
    key = session['key']
    
    # Kiểm tra quyền truy cập dis5
    if 'dis5' not in session.get('permissions', []) and 'admin' not in session.get('permissions', []):
        return render_template_string('''
        <!DOCTYPE html>
        <html>
        <head>
            <title>🚫 Không có quyền</title>
            <style>body{background:linear-gradient(135deg,#ff6b6b,#c23636);font-family:Arial;display:flex;justify-content:center;align-items:center;height:100vh;margin:0;color:white;text-align:center;}.error-box{background:rgba(0,0,0,0.7);padding:40px;border-radius:15px;box-shadow:0 0 20px rgba(0,0,0,0.3);}a{color:#ffcc00;text-decoration:none;display:block;margin-top:20px;padding:10px;border:1px solid #ffcc00;border-radius:5px;}a:hover{background:#ffcc00;color:black;}</style>
        </head>
        <body>
            <div class="error-box">
                <h1>🚫 Không có quyền truy cập!</h1>
                <p>Key của bạn không có quyền sử dụng tính năng <strong>Discord Voice Tool</strong>.</p>
                <a href="/menu">↩️ Quay về Menu</a>
            </div>
        </body>
        </html>
        ''', key=key, permissions=session.get('permissions', [])), 403
    
    # Kiểm tra số task còn lại
    try:
        from app import get_remaining_tasks
        remaining_tasks = get_remaining_tasks(key, 'dis5')
    except:
        remaining_tasks = 10
    
    if remaining_tasks <= 0:
        return render_template_string('''
        <!DOCTYPE html>
        <html>
        <head>
            <title>❌ Hết task</title>
            <style>body{background:linear-gradient(135deg,#ff6b6b,#c23636);font-family:Arial;display:flex;justify-content:center;align-items:center;height:100vh;margin:0;color:white;text-align:center;}.error-box{background:rgba(0,0,0,0.7);padding:40px;border-radius:15px;box-shadow:0 0 20px rgba(0,0,0,0.3);}a{color:#ffcc00;text-decoration:none;display:block;margin-top:20px;padding:10px;border:1px solid #ffcc00;border-radius:5px;}a:hover{background:#ffcc00;color:black;}</style>
        </head>
        <body>
            <div class="error-box">
                <h1>❌ Đã hết task!</h1>
                <p>Bạn đã sử dụng hết số task được cấp cho tính năng <strong>Discord Voice Tool</strong>.</p>
                <p><strong>Task còn lại:</strong> {{ remaining }} / {{ task_limit }}</p>
                <a href="/menu">↩️ Quay về Menu</a>
            </div>
        </body>
        </html>
        ''', remaining=remaining_tasks, task_limit=session.get('task_limits', {}).get('dis5', 0)), 403

    uploaded_files = get_uploaded_files()
    return render_template_string(HTML, spam_tasks=SPAM_TASKS, hang_tasks=HANG_TASKS, 
                                remaining_tasks=remaining_tasks, uploaded_files=uploaded_files)

@dis5_bp.route('/upload_mp3', methods=['POST'])
def upload_mp3():
    """Upload file MP3"""
    if 'key' not in session:
        flash('🔒 Vui lòng đăng nhập lại!', 'error')
        return redirect('/')
    
    if 'mp3_file' not in request.files:
        flash('❌ Không có file được chọn', 'error')
        return redirect(url_for('dis5.dis5_page'))
    
    file = request.files['mp3_file']
    if file.filename == '':
        flash('❌ Không có file được chọn', 'error')
        return redirect(url_for('dis5.dis5_page'))
    
    if file and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        file_path = os.path.join(UPLOAD_FOLDER, filename)
        file.save(file_path)
        flash(f'✅ Đã upload file: {filename}', 'success')
    else:
        flash('❌ File không hợp lệ. Chỉ chấp nhận file MP3, WAV, OGG', 'error')
    
    return redirect(url_for('dis5.dis5_page'))

@dis5_bp.route('/delete_mp3/<filename>')
def delete_mp3(filename):
    """Xóa file MP3"""
    if 'key' not in session:
        flash('🔒 Vui lòng đăng nhập lại!', 'error')
        return redirect('/')
    
    try:
        file_path = os.path.join(UPLOAD_FOLDER, secure_filename(filename))
        if os.path.exists(file_path):
            os.remove(file_path)
            flash(f'✅ Đã xóa file: {filename}', 'success')
        else:
            flash('❌ File không tồn tại', 'error')
    except Exception as e:
        flash(f'❌ Lỗi khi xóa file: {str(e)}', 'error')
    
    return redirect(url_for('dis5.dis5_page'))

@dis5_bp.route('/add_spam_task', methods=['POST'])
def add_spam_task():
    """Thêm task xả mic"""
    if 'key' not in session:
        flash('🔒 Vui lòng đăng nhập lại!', 'error')
        return redirect('/')
    
    # Sử dụng 1 task
    try:
        from app import use_task
        key = session['key']
        remaining = use_task(key, 'dis5')
        
        if remaining < 0:
            flash('❌ Đã hết task cho tính năng này!', 'error')
            return redirect(url_for('dis5.dis5_page'))
    except:
        remaining = 9

    token = request.form['token'].strip()
    channel_id = request.form['channel_id'].strip()
    mp3_file = request.form['mp3_file'].strip()
    
    if not token or not channel_id or not mp3_file:
        flash("❌ Vui lòng điền đầy đủ thông tin", "error")
        return redirect(url_for('dis5.dis5_page'))
    
    # Kiểm tra file có tồn tại không
    if not os.path.exists(mp3_file):
        flash("❌ File MP3 không tồn tại", "error")
        return redirect(url_for('dis5.dis5_page'))
    
    task_id = str(uuid.uuid4())[:8]
    
    # Chạy trong thread riêng
    def run_spam_task():
        spam = SpamVoice(task_id, token, channel_id, mp3_file)
        SPAM_TASKS[task_id] = spam
        spam.start()
    
    thread = threading.Thread(target=run_spam_task)
    thread.daemon = True
    thread.start()
    
    flash(f"✅ Đã tạo task xả mic #{task_id}. Task còn lại: {remaining}", "success")
    return redirect(url_for('dis5.dis5_page'))

@dis5_bp.route('/add_hang_task', methods=['POST'])
def add_hang_task():
    """Thêm task treo room"""
    if 'key' not in session:
        flash('🔒 Vui lòng đăng nhập lại!', 'error')
        return redirect('/')
    
    # Sử dụng 1 task
    try:
        from app import use_task
        key = session['key']
        remaining = use_task(key, 'dis5')
        
        if remaining < 0:
            flash('❌ Đã hết task cho tính năng này!', 'error')
            return redirect(url_for('dis5.dis5_page'))
    except:
        remaining = 9

    token = request.form['token'].strip()
    channel_id = request.form['channel_id'].strip()
    mute = 'mute' in request.form
    deaf = 'deaf' in request.form
    stream = 'stream' in request.form
    
    if not token or not channel_id:
        flash("❌ Vui lòng điền token và channel ID", "error")
        return redirect(url_for('dis5.dis5_page'))
    
    task_id = str(uuid.uuid4())[:8]
    
    # Chạy trong thread riêng
    def run_hang_task():
        hang = HangVoice(task_id, token, channel_id, mute, deaf, stream)
        HANG_TASKS[task_id] = hang
        hang.start()
    
    thread = threading.Thread(target=run_hang_task)
    thread.daemon = True
    thread.start()
    
    flash(f"✅ Đã tạo task treo room #{task_id}. Task còn lại: {remaining}", "success")
    return redirect(url_for('dis5.dis5_page'))

@dis5_bp.route('/stop_spam/<task_id>')
def stop_spam_task(task_id):
    """Dừng task xả mic"""
    if task_id in SPAM_TASKS:
        SPAM_TASKS[task_id].stop()
        flash(f"⏸️ Đã dừng task xả mic #{task_id}", "success")
    else:
        flash("❌ Không tìm thấy task", "error")
    return redirect(url_for('dis5.dis5_page'))

@dis5_bp.route('/stop_hang/<task_id>')
def stop_hang_task(task_id):
    """Dừng task treo room"""
    if task_id in HANG_TASKS:
        HANG_TASKS[task_id].stop()
        flash(f"⏸️ Đã dừng task treo room #{task_id}", "success")
    else:
        flash("❌ Không tìm thấy task", "error")
    return redirect(url_for('dis5.dis5_page'))

@dis5_bp.route('/delete_spam/<task_id>')
def delete_spam_task(task_id):
    """Xóa task xả mic"""
    if task_id in SPAM_TASKS:
        SPAM_TASKS[task_id].stop()
        del SPAM_TASKS[task_id]
        flash(f"🗑️ Đã xóa task xả mic #{task_id}", "success")
    else:
        flash("❌ Không tìm thấy task", "error")
    return redirect(url_for('dis5.dis5_page'))

@dis5_bp.route('/delete_hang/<task_id>')
def delete_hang_task(task_id):
    """Xóa task treo room"""
    if task_id in HANG_TASKS:
        HANG_TASKS[task_id].stop()
        del HANG_TASKS[task_id]
        flash(f"🗑️ Đã xóa task treo room #{task_id}", "success")
    else:
        flash("❌ Không tìm thấy task", "error")
    return redirect(url_for('dis5.dis5_page'))

# ====================== HTML TEMPLATE ======================

HTML = '''
<!DOCTYPE html>
<html lang="vi">
<head>
    <meta charset="UTF-8">
    <title>Discord Voice Tool</title>
    <style>
        body {
            font-family: 'Segoe UI', Arial;
            background: #0d1117;
            color: #e6edf3;
            padding: 20px;
            min-height: 100vh;
        }
        
        .container {
            max-width: 1200px;
            margin: 0 auto;
        }
        
        .card {
            background: rgba(22, 27, 34, 0.9);
            border: 1px solid #30363d;
            border-radius: 16px;
            padding: 25px;
            margin-bottom: 20px;
            box-shadow: 0 8px 32px rgba(0, 0, 0, 0.3);
        }
        
        h1, h2 {
            color: #58a6ff;
            text-align: center;
        }
        
        .tab-container {
            display: flex;
            margin-bottom: 20px;
            background: rgba(13, 17, 23, 0.7);
            border-radius: 10px;
            padding: 5px;
        }
        
        .tab {
            flex: 1;
            padding: 12px;
            text-align: center;
            cursor: pointer;
            border-radius: 8px;
            transition: all 0.3s ease;
        }
        
        .tab.active {
            background: #58a6ff;
            color: white;
        }
        
        .tab-content {
            display: none;
        }
        
        .tab-content.active {
            display: block;
        }
        
        label {
            color: #58a6ff;
            display: block;
            margin-top: 15px;
            font-weight: 600;
        }
        
        input, textarea, select {
            width: 100%;
            padding: 12px;
            border-radius: 10px;
            border: 1px solid #30363d;
            background: rgba(13, 17, 23, 0.7);
            color: white;
            font-size: 14px;
            margin-bottom: 10px;
        }
        
        button {
            background: linear-gradient(135deg, #238636, #2ea043);
            color: white;
            padding: 14px 20px;
            border: none;
            border-radius: 12px;
            cursor: pointer;
            margin-top: 20px;
            width: 100%;
            font-size: 16px;
            font-weight: bold;
        }
        
        button:hover {
            background: linear-gradient(135deg, #2ea043, #3fb950);
        }
        
        .alert {
            margin-top: 15px;
            padding: 12px;
            border-radius: 10px;
            font-weight: 500;
        }
        
        .alert-success {
            background: rgba(46, 160, 67, 0.2);
            color: #3fb950;
            border: 1px solid rgba(63, 185, 80, 0.3);
        }
        
        .alert-error {
            background: rgba(248, 81, 73, 0.2);
            color: #f85149;
            border: 1px solid rgba(248, 81, 73, 0.3);
        }
        
        table {
            width: 100%;
            border-collapse: collapse;
            background: rgba(22, 27, 34, 0.9);
            border-radius: 12px;
            overflow: hidden;
        }
        
        th, td {
            border: 1px solid #30363d;
            padding: 12px;
            text-align: center;
        }
        
        th {
            color: #58a6ff;
            background: rgba(13, 17, 23, 0.7);
        }
        
        .status-running {
            color: #3fb950;
            font-weight: bold;
        }
        
        .status-stopped {
            color: #f85149;
            font-weight: bold;
        }
        
        .action-btn {
            padding: 8px 15px;
            border: none;
            border-radius: 8px;
            color: white;
            cursor: pointer;
            margin: 2px;
            text-decoration: none;
            display: inline-block;
        }
        
        .btn-stop {
            background: #f85149;
        }
        
        .btn-delete {
            background: #6e7681;
        }
        
        .checkbox-group {
            display: flex;
            gap: 20px;
            margin: 15px 0;
        }
        
        .checkbox-item {
            display: flex;
            align-items: center;
            gap: 5px;
        }
        
        .task-info {
            background: rgba(13, 17, 23, 0.7);
            padding: 15px;
            border-radius: 10px;
            margin: 15px 0;
            border-left: 4px solid #58a6ff;
        }
        
        .back-btn {
            display: inline-block;
            margin-top: 20px;
            background: linear-gradient(135deg, #f093fb, #f5576c);
            color: white;
            text-decoration: none;
            padding: 12px 25px;
            border-radius: 12px;
            font-weight: bold;
            transition: all 0.3s ease;
            text-align: center;
        }
        
        .back-btn:hover {
            transform: translateY(-2px);
            box-shadow: 0 5px 15px rgba(245, 87, 108, 0.4);
        }
        
        .center {
            text-align: center;
        }
        
        .upload-section {
            background: rgba(13, 17, 23, 0.7);
            padding: 20px;
            border-radius: 10px;
            margin: 15px 0;
            border: 2px dashed #58a6ff;
        }
        
        .file-list {
            margin-top: 15px;
        }
        
        .file-item {
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 10px;
            background: rgba(22, 27, 34, 0.9);
            margin: 5px 0;
            border-radius: 8px;
            border: 1px solid #30363d;
        }
        
        .file-info {
            flex: 1;
        }
        
        .file-actions {
            display: flex;
            gap: 10px;
        }
        
        .btn-small {
            padding: 5px 10px;
            font-size: 12px;
            width: auto;
        }
        
        .btn-upload {
            background: linear-gradient(135deg, #667eea, #764ba2);
        }
        
        .form-group {
            display: flex;
            gap: 15px;
            margin-bottom: 15px;
        }
        
        .form-group > div {
            flex: 1;
        }
    </style>
</head>
<body>
    <div class="container">
        <h1>🎵 Discord Voice Tool</h1>
        
        <div class="task-info">
            <strong>📊 Thông tin task:</strong><br>
            • Key: <code>{{ session.key }}</code><br>
            • Task còn lại: <strong>{{ remaining_tasks }}</strong>/{{ session.task_limits.dis5 }}<br>
            • Quyền: {{ session.permissions }}
        </div>
        
        {% with messages = get_flashed_messages(with_categories=true) %}
            {% if messages %}
                {% for cat, msg in messages %}
                    <div class="alert alert-{{cat}}">{{msg}}</div>
                {% endfor %}
            {% endif %}
        {% endwith %}
        
        <div class="tab-container">
            <div class="tab active" onclick="switchTab('spam')">Xả Mic</div>
            <div class="tab" onclick="switchTab('hang')">Treo Room</div>
            <div class="tab" onclick="switchTab('upload')">Upload MP3</div>
            <div class="tab" onclick="switchTab('tasks')">Tasks Đang Chạy</div>
        </div>
        
        <!-- Tab Xả Mic -->
        <div id="spam" class="tab-content active">
            <div class="card">
                <h2>🔊 Xả Mic</h2>
                <form method="POST" action="{{ url_for('dis5.add_spam_task') }}">
                    <label>Token Discord:</label>
                    <input type="text" name="token" placeholder="Nhập token Discord" required>
                    
                    <label>Channel ID:</label>
                    <input type="text" name="channel_id" placeholder="Nhập ID kênh voice" required>
                    
                    <label>Chọn file MP3:</label>
                    <select name="mp3_file" required>
                        <option value="">-- Chọn file MP3 --</option>
                        {% for file in uploaded_files %}
                        <option value="{{ file.path }}">{{ file.name }} ({{ file.size }} MB)</option>
                        {% endfor %}
                    </select>
                    <small style="color: #8b949e;">Chưa có file? Hãy upload file MP3 trong tab "Upload MP3"</small>
                    
                    <button type="submit">🚀 Bắt Đầu Xả Mic</button>
                </form>
            </div>
        </div>
        
        <!-- Tab Treo Room -->
        <div id="hang" class="tab-content">
            <div class="card">
                <h2>🎤 Treo Room Voice</h2>
                <form method="POST" action="{{ url_for('dis5.add_hang_task') }}">
                    <label>Token Discord:</label>
                    <input type="text" name="token" placeholder="Nhập token Discord" required>
                    
                    <label>Channel ID:</label>
                    <input type="text" name="channel_id" placeholder="Nhập ID kênh voice" required>
                    
                    <div class="checkbox-group">
                        <div class="checkbox-item">
                            <input type="checkbox" name="mute" id="mute">
                            <label for="mute">Tắt Mic</label>
                        </div>
                        <div class="checkbox-item">
                            <input type="checkbox" name="deaf" id="deaf">
                            <label for="deaf">Tắt Loa</label>
                        </div>
                        <div class="checkbox-item">
                            <input type="checkbox" name="stream" id="stream">
                            <label for="stream">Bật Video</label>
                        </div>
                    </div>
                    
                    <button type="submit">🚀 Bắt Đầu Treo Room</button>
                </form>
            </div>
        </div>
        
        <!-- Tab Upload MP3 -->
        <div id="upload" class="tab-content">
            <div class="card">
                <h2>📁 Upload File MP3</h2>
                
                <div class="upload-section">
                    <h3>📤 Upload file mới</h3>
                    <form method="POST" action="{{ url_for('dis5.upload_mp3') }}" enctype="multipart/form-data">
                        <div class="form-group">
                            <div>
                                <label>Chọn file MP3:</label>
                                <input type="file" name="mp3_file" accept=".mp3,.wav,.ogg" required>
                            </div>
                        </div>
                        <button type="submit" class="btn-upload">📁 Upload File</button>
                    </form>
                </div>
                
                <div class="file-list">
                    <h3>📂 File đã upload</h3>
                    {% if uploaded_files %}
                        {% for file in uploaded_files %}
                        <div class="file-item">
                            <div class="file-info">
                                <strong>{{ file.name }}</strong><br>
                                <small>Kích thước: {{ file.size }} MB</small>
                            </div>
                            <div class="file-actions">
                                <button class="action-btn btn-small" onclick="selectFile('{{ file.path }}')">✅ Chọn</button>
                                <a href="{{ url_for('dis5.delete_mp3', filename=file.name) }}" class="action-btn btn-small btn-delete">🗑️ Xóa</a>
                            </div>
                        </div>
                        {% endfor %}
                    {% else %}
                        <p style="text-align: center; color: #8b949e;">Chưa có file nào được upload</p>
                    {% endif %}
                </div>
            </div>
        </div>
        
        <!-- Tab Tasks -->
        <div id="tasks" class="tab-content">
            <!-- Tasks Xả Mic -->
            <div class="card">
                <h2>🔊 Tasks Xả Mic Đang Chạy</h2>
                <table>
                    <tr>
                        <th>ID</th>
                        <th>Channel ID</th>
                        <th>File MP3</th>
                        <th>Trạng Thái</th>
                        <th>Thời Gian</th>
                        <th>Hành Động</th>
                    </tr>
                    {% for task_id, task in spam_tasks.items() %}
                    <tr>
                        <td>{{ task_id }}</td>
                        <td>{{ task.channel_id }}</td>
                        <td>{{ task.mp3_file.split('/')[-1] if '/' in task.mp3_file else task.mp3_file }}</td>
                        <td>
                            <span class="{{ 'status-running' if task.is_running else 'status-stopped' }}">
                                {{ task.status }}
                            </span>
                        </td>
                        <td>{{ task.start_time.strftime('%H:%M:%S') }}</td>
                        <td>
                            {% if task.is_running %}
                                <a href="{{ url_for('dis5.stop_spam_task', task_id=task_id) }}">
                                    <button class="action-btn btn-stop">🛑 Dừng</button>
                                </a>
                            {% endif %}
                            <a href="{{ url_for('dis5.delete_spam_task', task_id=task_id) }}">
                                <button class="action-btn btn-delete">🗑️ Xóa</button>
                            </a>
                        </td>
                    </tr>
                    {% endfor %}
                </table>
            </div>
            
            <!-- Tasks Treo Room -->
            <div class="card">
                <h2>🎤 Tasks Treo Room Đang Chạy</h2>
                <table>
                    <tr>
                        <th>ID</th>
                        <th>Channel ID</th>
                        <th>Mic</th>
                        <th>Loa</th>
                        <th>Video</th>
                        <th>Trạng Thái</th>
                        <th>Thời Gian</th>
                        <th>Hành Động</th>
                    </tr>
                    {% for task_id, task in hang_tasks.items() %}
                    <tr>
                        <td>{{ task_id }}</td>
                        <td>{{ task.channel_id }}</td>
                        <td>{{ '✅' if task.mute else '❌' }}</td>
                        <td>{{ '✅' if task.deaf else '❌' }}</td>
                        <td>{{ '✅' if task.stream else '❌' }}</td>
                        <td>
                            <span class="{{ 'status-running' if task.is_running else 'status-stopped' }}">
                                {{ task.status }}
                            </span>
                        </td>
                        <td>{{ task.start_time.strftime('%H:%M:%S') }}</td>
                        <td>
                            {% if task.is_running %}
                                <a href="{{ url_for('dis5.stop_hang_task', task_id=task_id) }}">
                                    <button class="action-btn btn-stop">🛑 Dừng</button>
                                </a>
                            {% endif %}
                            <a href="{{ url_for('dis5.delete_hang_task', task_id=task_id) }}">
                                <button class="action-btn btn-delete">🗑️ Xóa</button>
                            </a>
                        </td>
                    </tr>
                    {% endfor %}
                </table>
            </div>
        </div>

        <div class="center">
            <a href="/menu" class="back-btn">⬅️ Quay về Menu Chính</a>
        </div>
    </div>

    <script>
        function switchTab(tabName) {
            // Ẩn tất cả tab content
            document.querySelectorAll('.tab-content').forEach(tab => {
                tab.classList.remove('active');
            });
            
            // Hiện tab được chọn
            document.getElementById(tabName).classList.add('active');
            
            // Cập nhật tab active
            document.querySelectorAll('.tab').forEach(tab => {
                tab.classList.remove('active');
            });
            event.target.classList.add('active');
        }
        
        function selectFile(filePath) {
            // Chuyển sang tab xả mic và chọn file
            switchTab('spam');
            const selectElement = document.querySelector('select[name="mp3_file"]');
            selectElement.value = filePath;
        }
        
        // Auto refresh tasks every 10 seconds
        setInterval(() => {
            if (document.getElementById('tasks').classList.contains('active')) {
                window.location.reload();
            }
        }, 10000);
    </script>
</body>
</html>
'''
