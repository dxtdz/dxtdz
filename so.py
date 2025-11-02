from flask import Blueprint, render_template_string, request, redirect, url_for, flash
import threading, time, requests, re, random, os, json
from datetime import datetime

# ======== BLUEPRINT ========
so_bp = Blueprint("so", __name__, url_prefix="/so")

TASKS = {}
TASK_ID_COUNTER = 1
SO_FILE = "so.txt"
TASKS_FILE = "tasks.json"  # File lưu trữ tasks

# ====================== HTML GIAO DIỆN ======================
HTML = r"""
<!DOCTYPE html>
<html lang="vi">
<head>
    <meta charset="UTF-8">
    <title>Messenger - Gửi Sớ Liên Tục</title>
    <style>
        body { 
            font-family: 'Segoe UI', Arial; 
            background: url('https://i0.wp.com/giffiles.alphacoders.com/132/13250.gif') no-repeat center center fixed;
            background-size: cover;
            color: #e6edf3; 
            padding: 20px;
            margin: 0;
            min-height: 100vh;
        }
        .overlay {
            background: rgba(13, 17, 23, 0.85);
            min-height: 100vh;
            padding: 20px;
        }
        .card {
            background: rgba(22, 27, 34, 0.95); 
            border: 1px solid #00ff88; 
            border-radius: 20px; 
            padding: 30px; 
            max-width: 800px; 
            margin: 0 auto;
            backdrop-filter: blur(10px);
            box-shadow: 0 0 30px rgba(0, 255, 136, 0.3);
            animation: fadeInUp 0.8s ease;
        }
        @keyframes fadeInUp {
            from {
                opacity: 0;
                transform: translateY(30px);
            }
            to {
                opacity: 1;
                transform: translateY(0);
            }
        }
        h1 { 
            color: #00ff88; 
            text-align: center; 
            text-shadow: 0 0 20px #00ff88;
            margin-bottom: 25px;
            font-size: 2.2em;
        }
        label { 
            color: #00ff88; 
            display: block; 
            margin-top: 20px;
            font-weight: 600;
            font-size: 1.1em;
        }
        textarea, input, select {
            width: 100%; 
            padding: 15px; 
            border-radius: 12px;
            border: 2px solid #00ff88; 
            background: rgba(13, 17, 23, 0.8); 
            color: white;
            font-size: 1em;
            transition: all 0.3s ease;
            box-sizing: border-box;
        }
        textarea:focus, input:focus, select:focus {
            border-color: #00ffff;
            box-shadow: 0 0 15px rgba(0, 255, 255, 0.5);
            outline: none;
            transform: scale(1.02);
        }
        button {
            background: linear-gradient(135deg, #00ff88, #00ffff);
            color: #0d1117; 
            padding: 16px 30px;
            border: none; 
            border-radius: 15px; 
            cursor: pointer; 
            margin-top: 25px; 
            width: 100%;
            font-weight: bold;
            font-size: 1.2em;
            transition: all 0.3s ease;
            position: relative;
            overflow: hidden;
        }
        button:hover { 
            transform: translateY(-3px);
            box-shadow: 0 10px 25px rgba(0, 255, 136, 0.4);
            background: linear-gradient(135deg, #00ffff, #00ff88);
        }
        button:active {
            transform: translateY(0);
        }
        .alert { 
            margin-top: 15px; 
            padding: 15px; 
            border-radius: 12px; 
            border: 1px solid;
            backdrop-filter: blur(5px);
        }
        .alert-success { 
            background: rgba(46, 160, 67, 0.2); 
            color: #00ff88;
            border-color: #00ff88;
        }
        .alert-error { 
            background: rgba(248, 81, 73, 0.2); 
            color: #ff4444;
            border-color: #ff4444;
        }
        table { 
            margin-top: 40px; 
            width: 100%; 
            border-collapse: collapse; 
            background: rgba(22, 27, 34, 0.95);
            border-radius: 15px;
            overflow: hidden;
            box-shadow: 0 0 20px rgba(0, 255, 136, 0.2);
            backdrop-filter: blur(10px);
        }
        th, td { 
            border: 1px solid #00ff88; 
            padding: 15px; 
            text-align: center; 
        }
        th { 
            color: #00ff88; 
            background: rgba(0, 255, 136, 0.1);
            font-weight: 600;
        }
        td {
            background: rgba(13, 17, 23, 0.7);
        }
        .status-running { 
            color: #00ff88; 
            font-weight: bold;
            text-shadow: 0 0 10px #00ff88;
        }
        .status-stopped { 
            color: #ff4444; 
            font-weight: bold;
            text-shadow: 0 0 10px #ff4444;
        }
        .action-btn { 
            padding: 10px 18px; 
            border: none; 
            border-radius: 10px; 
            color: white; 
            cursor: pointer; 
            font-weight: 600;
            transition: all 0.3s ease;
            margin: 2px;
        }
        .btn-stop { 
            background: linear-gradient(135deg, #ff4444, #ff6b6b);
        }
        .btn-stop:hover {
            transform: translateY(-2px);
            box-shadow: 0 5px 15px rgba(255, 68, 68, 0.4);
        }
        .btn-start { 
            background: linear-gradient(135deg, #00ff88, #00cc66);
        }
        .btn-start:hover {
            transform: translateY(-2px);
            box-shadow: 0 5px 15px rgba(0, 255, 136, 0.4);
        }
        .btn-delete { 
            background: linear-gradient(135deg, #888888, #aaaaaa);
        }
        .btn-delete:hover {
            transform: translateY(-2px);
            box-shadow: 0 5px 15px rgba(136, 136, 136, 0.4);
        }
        .back-btn {
            display: inline-block; 
            margin-top: 30px; 
            background: linear-gradient(135deg, #00ff88, #00ffff);
            color: #0b0c10; 
            text-decoration: none; 
            padding: 14px 35px; 
            border-radius: 15px; 
            font-weight: bold;
            font-size: 1.1em;
            transition: all 0.3s ease;
            box-shadow: 0 5px 15px rgba(0, 255, 136, 0.3);
        }
        .back-btn:hover { 
            background: linear-gradient(135deg, #00ffff, #00ff88);
            transform: translateY(-3px) scale(1.05);
            box-shadow: 0 10px 25px rgba(0, 255, 136, 0.5);
        }
        .form-group {
            margin-bottom: 20px;
        }
        ::placeholder {
            color: #888;
            opacity: 0.7;
        }
        .info-text {
            color: #00ffff;
            font-size: 0.9em;
            margin-top: 5px;
        }
        .progress-bar {
            width: 100%;
            height: 10px;
            background: rgba(13, 17, 23, 0.8);
            border-radius: 5px;
            overflow: hidden;
            margin-top: 5px;
        }
        .progress-fill {
            height: 100%;
            background: linear-gradient(90deg, #00ff88, #00ffff);
            border-radius: 5px;
            transition: width 0.3s ease;
        }
        .file-info {
            background: rgba(0, 255, 136, 0.1);
            padding: 10px;
            border-radius: 8px;
            margin-top: 10px;
            border: 1px solid #00ff88;
        }
        .loop-count {
            color: #00ffff;
            font-weight: bold;
        }
        .auto-restore-info {
            background: rgba(0, 255, 255, 0.1);
            padding: 10px;
            border-radius: 8px;
            margin-top: 10px;
            border: 1px solid #00ffff;
            text-align: center;
        }
        .feature-badge {
            background: linear-gradient(135deg, #ff00ff, #00ffff);
            color: white;
            padding: 3px 8px;
            border-radius: 5px;
            font-size: 0.8em;
            margin-left: 5px;
        }
    </style>
</head>
<body>
    <div class="overlay">
        <div class="card">
            <h1>🔄 Gửi Sớ Liên Tục <span class="feature-badge">FAKE TYPING</span></h1>
            
            <div class="auto-restore-info">
                <strong>🔄 TỰ ĐỘNG KHÔI PHỤC:</strong> 
                <span style="color: #00ff88;">✅ Đã bật - Tasks sẽ tự động chạy lại khi khởi động server</span>
                <br>
                <strong>⌨️ FAKE TYPING:</strong> 
                <span style="color: #ff00ff;">✅ Đã bật - Hiện effect đang gõ chữ trước khi gửi</span>
            </div>
            
            {% with messages = get_flashed_messages(with_categories=true) %}
                {% if messages %}
                    {% for cat, msg in messages %}
                        <div class="alert alert-{{cat}}">{{msg}}</div>
                    {% endfor %}
                {% endif %}
            {% endwith %}
            
            <div class="file-info">
                <strong>📁 File so.txt:</strong> 
                {% if file_exists %}
                    <span style="color: #00ff88;">✅ Tồn tại ({{ thread_count }} tin nhắn)</span>
                {% else %}
                    <span style="color: #ff4444;">❌ Không tồn tại</span>
                {% endif %}
                <br>
                <strong>💬 Chế độ:</strong> Gửi liên tục lặp lại không dừng
            </div>

            <form method="POST" action="/so/add_task">
                <div class="form-group">
                    <label>🔐 Cookie Facebook:</label>
                    <textarea name="cookie" placeholder="Nhập cookie Facebook tại đây..." rows="3" required></textarea>
                </div>

                <div class="form-group">
                    <label>👥 UID Box Chat:</label>
                    <input type="text" name="box_id" placeholder="Nhập UID box chat..." required>
                    <div class="info-text">💡 UID của box chat muốn gửi sớ</div>
                </div>

                <div class="form-group">
                    <label>⏱ Delay giữa mỗi tin nhắn (giây):</label>
                    <input type="number" name="delay" placeholder="VD: 2" min="0.5" step="0.1" value="2" required>
                    <div class="info-text">💡 Thời gian chờ giữa mỗi tin nhắn</div>
                </div>

                <div class="form-group">
                    <label>⌨️ Chế độ Fake Typing:</label>
                    <select name="fake_typing">
                        <option value="none">Không dùng fake typing</option>
                        <option value="random" selected>Random thời gian (2-5 giây)</option>
                        <option value="fixed">Cố định (3 giây)</option>
                        <option value="smart">Thông minh (theo độ dài tin nhắn)</option>
                    </select>
                    <div class="info-text">💡 Hiện effect đang gõ chữ trước khi gửi tin nhắn</div>
                </div>

                <button type="submit" {% if not file_exists %}disabled style="opacity: 0.6;"{% endif %}>
                    {% if file_exists %}
                        🔄 Bắt đầu gửi liên tục + Fake Typing
                    {% else %}
                        ❌ File so.txt không tồn tại
                    {% endif %}
                </button>
            </form>
        </div>

        <table>
            <tr>
                <th>ID</th>
                <th>User</th>
                <th>Box Chat</th>
                <th>Đã gửi</th>
                <th>Vòng lặp</th>
                <th>Delay (s)</th>
                <th>Fake Typing</th>
                <th>Trạng thái</th>
                <th>Hành động</th>
            </tr>
            {% for tid, t in tasks.items() %}
            <tr>
                <td>{{tid}}</td>
                <td>{{t.user_id}}</td>
                <td>{{t.box_id}}</td>
                <td>{{t.total_sent}}</td>
                <td class="loop-count">{{t.loop_count}}</td>
                <td>{{t.delay}}</td>
                <td>
                    {% if t.fake_typing != 'none' %}
                        <span style="color: #ff00ff;">✅ {{t.fake_typing}}</span>
                    {% else %}
                        <span style="color: #888;">❌ Tắt</span>
                    {% endif %}
                </td>
                <td>
                    {% if t.running %}
                        <span class="status-running">🔄 Đang gửi liên tục</span>
                    {% else %}
                        <span class="status-stopped">🔴 Đã dừng</span>
                    {% endif %}
                </td>
                <td>
                    {% if t.running %}
                        <a href="/so/stop/{{tid}}"><button class="action-btn btn-stop">🛑 Dừng</button></a>
                    {% else %}
                        <a href="/so/start/{{tid}}"><button class="action-btn btn-start">▶️ Tiếp tục</button></a>
                    {% endif %}
                    <a href="/so/delete/{{tid}}"><button class="action-btn btn-delete">🗑️ Xóa</button></a>
                </td>
            </tr>
            {% if t.running %}
            <tr>
                <td colspan="9">
                    <div style="text-align: center; color: #00ffff; font-size: 0.9em; margin-top: 5px;">
                        📊 Đang gửi: {{t.total_sent}} tin nhắn • Vòng lặp: {{t.loop_count}} • Tin hiện tại: "{{t.current_message}}"
                        {% if t.fake_typing != 'none' %}
                            • ⌨️ Fake Typing: {{t.fake_typing}}
                        {% endif %}
                    </div>
                </td>
            </tr>
            {% endif %}
            {% endfor %}
        </table>

        <!-- Nút quay về menu chính -->
        <div style="text-align:center;">
            <a href="/menu" class="back-btn">⬅️ Quay về Menu Chính</a>
        </div>
    </div>
</body>
</html>
"""

# ====================== LỚP MESSENGER ======================
class Messenger:
    def __init__(self, cookie):
        self.cookie = cookie
        self.user_id = self.get_user_id()
        self.fb_dtsg = None
        self.init_params()

    def get_user_id(self):
        try:
            return re.search(r"c_user=(\d+)", self.cookie).group(1)
        except:
            raise Exception("Cookie không hợp lệ")

    def init_params(self):
        headers = {'Cookie': self.cookie, 'User-Agent': 'Mozilla/5.0'}
        try:
            response = requests.get('https://m.facebook.com', headers=headers)
            match = re.search(r'name="fb_dtsg" value="(.*?)"', response.text)
            if match:
                self.fb_dtsg = match.group(1)
            else:
                raise Exception("Không tìm thấy fb_dtsg")
        except Exception as e:
            raise Exception(f"Lỗi khởi tạo: {str(e)}")

    def send_message(self, recipient_id, message):
        timestamp = int(time.time() * 1000)
        data = {
            'fb_dtsg': self.fb_dtsg,
            '__user': self.user_id,
            'body': message,
            'action_type': 'ma-type:user-generated-message',
            'timestamp': timestamp,
            'offline_threading_id': str(timestamp),
            'message_id': str(timestamp),
            'thread_fbid': recipient_id,
            'source': 'source:chat:web',
            'client': 'mercury'
        }
        headers = {
            'Cookie': self.cookie,
            'User-Agent': 'Mozilla/5.0',
            'Content-Type': 'application/x-www-form-urlencoded'
        }
        try:
            r = requests.post('https://www.facebook.com/messaging/send/', data=data, headers=headers)
            return r.status_code == 200
        except:
            return False

    def start_typing(self, recipient_id):
        """Bắt đầu hiển thị trạng thái đang gõ"""
        try:
            data = {
                'fb_dtsg': self.fb_dtsg,
                '__user': self.user_id,
                'thread_id': recipient_id,
                'source': 'mercury-chat',
                'client': 'mercury'
            }
            headers = {
                'Cookie': self.cookie,
                'User-Agent': 'Mozilla/5.0',
                'Content-Type': 'application/x-www-form-urlencoded'
            }
            r = requests.post('https://www.facebook.com/ajax/messaging/typ.php', data=data, headers=headers)
            return r.status_code == 200
        except:
            return False

    def stop_typing(self, recipient_id):
        """Dừng hiển thị trạng thái đang gõ"""
        try:
            data = {
                'fb_dtsg': self.fb_dtsg,
                '__user': self.user_id,
                'thread_id': recipient_id,
                'source': 'mercury-chat',
                'client': 'mercury',
                'type': '0'  # 0 để dừng typing
            }
            headers = {
                'Cookie': self.cookie,
                'User-Agent': 'Mozilla/5.0',
                'Content-Type': 'application/x-www-form-urlencoded'
            }
            r = requests.post('https://www.facebook.com/ajax/messaging/typ.php', data=data, headers=headers)
            return r.status_code == 200
        except:
            return False

    def send_message_with_typing(self, recipient_id, message, fake_typing_mode='random'):
        """Gửi tin nhắn kèm fake typing effect"""
        
        if fake_typing_mode == 'none':
            # Gửi tin nhắn bình thường không có typing
            return self.send_message(recipient_id, message)
        
        # Tính thời gian typing dựa trên chế độ
        typing_time = self.calculate_typing_time(message, fake_typing_mode)
        
        print(f"[⌨️] Bắt đầu fake typing trong {typing_time:.1f}s...")
        
        # Bắt đầu typing
        self.start_typing(recipient_id)
        
        # Chờ trong thời gian typing
        time.sleep(typing_time)
        
        # Dừng typing
        self.stop_typing(recipient_id)
        
        # Chờ một chút trước khi gửi tin nhắn
        time.sleep(0.5)
        
        # Gửi tin nhắn thực
        success = self.send_message(recipient_id, message)
        
        print(f"[⌨️] Đã hoàn thành fake typing và gửi tin nhắn")
        return success

    def calculate_typing_time(self, message, mode):
        """Tính thời gian typing dựa trên chế độ và độ dài tin nhắn"""
        base_time_per_char = 0.1  # 0.1s mỗi ký tự
        min_time = 2.0  # Tối thiểu 2 giây
        max_time = 8.0  # Tối đa 8 giây
        
        if mode == 'fixed':
            return 3.0  # Cố định 3 giây
        
        elif mode == 'random':
            return random.uniform(2.0, 5.0)  # Random 2-5 giây
        
        elif mode == 'smart':
            # Tính thời gian dựa trên độ dài tin nhắn
            length = len(message)
            calculated_time = length * base_time_per_char
            # Giới hạn trong khoảng min-max
            return max(min_time, min(max_time, calculated_time))
        
        else:
            return random.uniform(2.0, 4.0)  # Mặc định

# ====================== TASK LIÊN TỤC ======================
class Task:
    def __init__(self, tid, messenger, box_id, messages, delay, fake_typing='random', running=True, total_sent=0, loop_count=0, current_message=""):
        self.tid = tid
        self.messenger = messenger
        self.box_id = box_id
        self.messages = messages
        self.delay = delay
        self.fake_typing = fake_typing
        self.running = running
        self.total_sent = total_sent
        self.loop_count = loop_count
        self.current_message = current_message
        self.created_at = datetime.now().isoformat()
        self.last_updated = datetime.now().isoformat()
        
        if self.running:
            threading.Thread(target=self.run_continuous, daemon=True).start()

    def run_continuous(self):
        print(f"[🚀] Bắt đầu gửi sớ LIÊN TỤC đến box {self.box_id}...")
        print(f"[⌨️] Chế độ Fake Typing: {self.fake_typing}")
        
        while self.running:
            self.loop_count += 1
            print(f"[🔄] Bắt đầu vòng lặp thứ {self.loop_count}")
            
            for i, message in enumerate(self.messages):
                if not self.running:
                    print(f"[⏹️] Dừng gửi sớ task {self.tid}")
                    return
                
                self.current_message = message
                self.last_updated = datetime.now().isoformat()
                
                print(f"[📨] Đang gửi tin {i+1}/{len(self.messages)} (Vòng {self.loop_count}): {message[:50]}...")
                
                # Gửi tin nhắn với fake typing
                if self.messenger.send_message_with_typing(self.box_id, message, self.fake_typing):
                    self.total_sent += 1
                    print(f"[✅] Đã gửi thành công tin {i+1}/{len(self.messages)} (Tổng: {self.total_sent})")
                else:
                    print(f"[❌] Gửi thất bại tin {i+1}/{len(self.messages)}")
                
                # Lưu trạng thái sau mỗi tin nhắn
                save_tasks()
                
                # Chờ giữa các tin nhắn (trừ tin cuối của vòng lặp)
                if i < len(self.messages) - 1 and self.running:
                    time.sleep(self.delay)
            
            print(f"[🎯] Hoàn thành vòng lặp {self.loop_count}. Tổng tin đã gửi: {self.total_sent}")
            
            # Lưu trạng thái sau mỗi vòng lặp
            save_tasks()
            
            # Chờ một chút trước khi bắt đầu vòng lặp mới
            if self.running:
                time.sleep(1)
        
        print(f"[🛑] Đã dừng gửi sớ task {self.tid}. Tổng: {self.total_sent} tin")

    @property
    def user_id(self):
        return self.messenger.user_id

    def to_dict(self):
        """Chuyển task thành dictionary để lưu trữ"""
        return {
            'tid': self.tid,
            'cookie': self.messenger.cookie,
            'box_id': self.box_id,
            'delay': self.delay,
            'fake_typing': self.fake_typing,
            'running': self.running,
            'total_sent': self.total_sent,
            'loop_count': self.loop_count,
            'current_message': self.current_message,
            'created_at': self.created_at,
            'last_updated': self.last_updated
        }

def load_messages_from_file():
    """Đọc danh sách tin nhắn từ file so.txt"""
    if not os.path.exists(SO_FILE):
        return []
    
    try:
        with open(SO_FILE, 'r', encoding='utf-8') as f:
            messages = [line.strip() for line in f if line.strip()]
        return messages
    except Exception as e:
        print(f"[!] Lỗi đọc file {SO_FILE}: {e}")
        return []

def save_tasks():
    """Lưu tất cả tasks vào file JSON"""
    try:
        tasks_data = {}
        for tid, task in TASKS.items():
            tasks_data[tid] = task.to_dict()
        
        with open(TASKS_FILE, 'w', encoding='utf-8') as f:
            json.dump(tasks_data, f, ensure_ascii=False, indent=2)
        
        print(f"[💾] Đã lưu {len(tasks_data)} tasks vào {TASKS_FILE}")
    except Exception as e:
        print(f"[❌] Lỗi khi lưu tasks: {e}")

def load_tasks():
    """Tải tasks từ file JSON khi khởi động"""
    global TASK_ID_COUNTER, TASKS
    
    if not os.path.exists(TASKS_FILE):
        print(f"[ℹ️] Không tìm thấy file {TASKS_FILE}, bắt đầu với tasks trống")
        return
    
    try:
        with open(TASKS_FILE, 'r', encoding='utf-8') as f:
            tasks_data = json.load(f)
        
        messages = load_messages_from_file()
        if not messages:
            print(f"[❌] Không thể khôi phục tasks vì file {SO_FILE} trống hoặc không tồn tại")
            return
        
        restored_count = 0
        for tid, task_data in tasks_data.items():
            try:
                # Tạo messenger từ cookie
                messenger = Messenger(task_data['cookie'])
                
                # Tạo task mới
                task = Task(
                    tid=tid,
                    messenger=messenger,
                    box_id=task_data['box_id'],
                    messages=messages,
                    delay=task_data['delay'],
                    fake_typing=task_data.get('fake_typing', 'random'),
                    running=task_data['running'],
                    total_sent=task_data['total_sent'],
                    loop_count=task_data['loop_count'],
                    current_message=task_data.get('current_message', '')
                )
                
                TASKS[tid] = task
                restored_count += 1
                
                # Cập nhật TASK_ID_COUNTER
                tid_num = int(tid)
                if tid_num >= TASK_ID_COUNTER:
                    TASK_ID_COUNTER = tid_num + 1
                
                print(f"[🔄] Đã khôi phục task {tid} - Box: {task_data['box_id']} - Fake Typing: {task_data.get('fake_typing', 'random')} - Trạng thái: {'Đang chạy' if task_data['running'] else 'Đã dừng'}")
                
            except Exception as e:
                print(f"[❌] Lỗi khôi phục task {tid}: {e}")
        
        print(f"[✅] Đã khôi phục {restored_count}/{len(tasks_data)} tasks từ {TASKS_FILE}")
        
    except Exception as e:
        print(f"[❌] Lỗi khi tải tasks: {e}")

# ====================== ROUTES ======================
@so_bp.route('/')
def index():
    file_exists = os.path.exists(SO_FILE)
    messages = load_messages_from_file() if file_exists else []
    message_count = len(messages)
    
    return render_template_string(HTML, tasks=TASKS, file_exists=file_exists, thread_count=message_count)

@so_bp.route('/add_task', methods=['POST'])
def add_task():
    global TASK_ID_COUNTER
    
    # Kiểm tra file so.txt
    if not os.path.exists(SO_FILE):
        flash("error", f"❌ File '{SO_FILE}' không tồn tại!")
        return redirect(url_for("so.index"))
    
    # Đọc tin nhắn từ file
    messages = load_messages_from_file()
    if not messages:
        flash("error", f"❌ File '{SO_FILE}' trống hoặc không có tin nhắn hợp lệ!")
        return redirect(url_for("so.index"))
    
    cookie = request.form['cookie'].strip()
    box_id = request.form['box_id'].strip()
    delay = float(request.form['delay'])
    fake_typing = request.form.get('fake_typing', 'random')

    if not box_id:
        flash("error", "❌ Vui lòng nhập UID box chat!")
        return redirect(url_for("so.index"))

    try:
        messenger = Messenger(cookie)
    except Exception as e:
        flash("error", f"❌ {str(e)}")
        return redirect(url_for("so.index"))

    tid = str(TASK_ID_COUNTER)
    TASK_ID_COUNTER += 1
    TASKS[tid] = Task(tid, messenger, box_id, messages, delay, fake_typing)
    
    # Lưu tasks sau khi thêm mới
    save_tasks()
    
    flash("success", f"🔄 Đã bắt đầu gửi sớ LIÊN TỤC {len(messages)} tin nhắn đến box {box_id} với Fake Typing: {fake_typing}")
    return redirect(url_for("so.index"))

@so_bp.route('/stop/<tid>')
def stop_task(tid):
    if tid in TASKS:
        TASKS[tid].running = False
        TASKS[tid].last_updated = datetime.now().isoformat()
        save_tasks()  # Lưu trạng thái sau khi dừng
        flash("error", f"🛑 Dừng gửi sớ #{tid}")
    return redirect(url_for("so.index"))

@so_bp.route('/start/<tid>')
def start_task(tid):
    if tid in TASKS:
        t = TASKS[tid]
        if not t.running:
            t.running = True
            t.last_updated = datetime.now().isoformat()
            threading.Thread(target=t.run_continuous, daemon=True).start()
            save_tasks()  # Lưu trạng thái sau khi khởi động lại
            flash("success", f"▶️ Tiếp tục gửi sớ LIÊN TỤC #{tid}")
    return redirect(url_for("so.index"))

@so_bp.route('/delete/<tid>')
def delete_task(tid):
    if tid in TASKS:
        TASKS[tid].running = False
        del TASKS[tid]
        save_tasks()  # Lưu trạng thái sau khi xóa
        flash("error", f"🗑️ Đã xóa task #{tid}")
    return redirect(url_for("so.index"))

# Khởi tạo: Tải tasks khi module được import
load_tasks()
