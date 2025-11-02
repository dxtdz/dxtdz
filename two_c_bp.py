from flask import Blueprint, render_template_string, request, redirect, url_for, flash, jsonify
import threading, time, requests, re, random, os, json
from datetime import datetime

# ======== BLUEPRINT ========
two_c_bp = Blueprint("two_c", __name__, url_prefix="/two_c")

TASKS = {}
TASK_ID_COUNTER = 1
TWO_C_FILE = "2c.txt"
TASK_SAVE_FILE = "two_c_tasks.json"

# ======== HÀM LƯU VÀ KHÔI PHỤC TASK ========
def save_tasks_to_file():
    """Lưu tasks vào file JSON"""
    try:
        tasks_to_save = {}
        for task_id, task in TASKS.items():
            tasks_to_save[task_id] = {
                'cookie': task.messenger.cookie,
                'box_id': task.box_id,
                'delay': task.delay,
                'max_loops': task.max_loops,
                'running': False,  # Luôn lưu là False để tránh conflict
                'total_sent': task.total_sent,
                'success_count': task.success_count,
                'loops_completed': task.loops_completed,
                'current_message': task.current_message,
                'user_id': task.messenger.user_id,
                'created_at': getattr(task, 'created_at', datetime.now().isoformat())
            }
        
        with open(TASK_SAVE_FILE, 'w', encoding='utf-8') as f:
            json.dump(tasks_to_save, f, indent=2, ensure_ascii=False)
        
        print(f"💾 Đã lưu {len(tasks_to_save)} tasks vào file two_c")
    except Exception as e:
        print(f"❌ Lỗi lưu tasks two_c: {e}")

def load_tasks_from_file():
    """Tải tasks từ file JSON"""
    global TASKS, TASK_ID_COUNTER
    
    try:
        if os.path.exists(TASK_SAVE_FILE):
            with open(TASK_SAVE_FILE, 'r', encoding='utf-8') as f:
                saved_tasks = json.load(f)
            
            print(f"📂 Đang khôi phục {len(saved_tasks)} tasks từ file two_c...")
            
            for task_id, task_data in saved_tasks.items():
                try:
                    # Tạo messenger instance
                    messenger = Messenger(task_data['cookie'])
                    
                    # Đọc tin nhắn từ file
                    messages = load_messages_from_file()
                    if not messages:
                        print(f"⚠️ Không thể khôi phục task {task_id}: File 2c.txt trống")
                        continue
                    
                    # Tạo task object
                    task = Task(
                        task_id, messenger, task_data['box_id'], 
                        messages, task_data['delay'], task_data['max_loops']
                    )
                    
                    # Khôi phục trạng thái
                    task.running = False  # Khởi tạo là stopped
                    task.total_sent = task_data['total_sent']
                    task.success_count = task_data['success_count']
                    task.loops_completed = task_data['loops_completed']
                    task.current_message = task_data['current_message']
                    task.created_at = task_data.get('created_at', datetime.now().isoformat())
                    
                    TASKS[task_id] = task
                    
                    # Cập nhật task_id_counter
                    task_id_int = int(task_id)
                    if task_id_int >= TASK_ID_COUNTER:
                        TASK_ID_COUNTER = task_id_int + 1
                        
                except Exception as e:
                    print(f"❌ Lỗi khôi phục task {task_id}: {e}")
            
            print("✅ Khôi phục tasks two_c hoàn tất!")
        else:
            print("ℹ️ Không tìm thấy file lưu tasks two_c")
    except Exception as e:
        print(f"❌ Lỗi tải tasks two_c: {e}")

def auto_save_task(task_id=None):
    """Tự động lưu tasks"""
    try:
        save_tasks_to_file()
    except Exception as e:
        print(f"❌ Lỗi tự động lưu tasks: {e}")

# Tải tasks khi module được import
load_tasks_from_file()

# ====================== HTML GIAO DIỆN ======================
HTML = r"""
<!DOCTYPE html>
<html lang="vi">
<head>
    <meta charset="UTF-8">
    <title>Tool 2C </title>
    <style>
        body { 
            font-family: 'Segoe UI', Arial; 
            background: url('https://tse1.mm.bing.net/th/id/OIP.ZbArfCYEqyg-W3qWxsYyMQHaEK?pid=Api&P=0&h=220') no-repeat center center fixed;
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
            border: 1px solid #ff6b35; 
            border-radius: 20px; 
            padding: 30px; 
            max-width: 800px; 
            margin: 0 auto;
            backdrop-filter: blur(10px);
            box-shadow: 0 0 30px rgba(255, 107, 53, 0.3);
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
            color: #ff6b35; 
            text-align: center; 
            text-shadow: 0 0 20px #ff6b35;
            margin-bottom: 25px;
            font-size: 2.2em;
        }
        label { 
            color: #ff6b35; 
            display: block; 
            margin-top: 20px;
            font-weight: 600;
            font-size: 1.1em;
        }
        textarea, input {
            width: 100%; 
            padding: 15px; 
            border-radius: 12px;
            border: 2px solid #ff6b35; 
            background: rgba(13, 17, 23, 0.8); 
            color: white;
            font-size: 1em;
            transition: all 0.3s ease;
            box-sizing: border-box;
        }
        textarea:focus, input:focus {
            border-color: #ffa500;
            box-shadow: 0 0 15px rgba(255, 165, 0, 0.5);
            outline: none;
            transform: scale(1.02);
        }
        button {
            background: linear-gradient(135deg, #ff6b35, #ffa500);
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
            box-shadow: 0 10px 25px rgba(255, 107, 53, 0.4);
            background: linear-gradient(135deg, #ffa500, #ff6b35);
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
            box-shadow: 0 0 20px rgba(255, 107, 53, 0.2);
            backdrop-filter: blur(10px);
        }
        th, td { 
            border: 1px solid #ff6b35; 
            padding: 15px; 
            text-align: center; 
        }
        th { 
            color: #ff6b35; 
            background: rgba(255, 107, 53, 0.1);
            font-weight: 600;
        }
        td {
            background: rgba(13, 17, 23, 0.7);
        }
        .status-running { 
            color: #ff6b35; 
            font-weight: bold;
            text-shadow: 0 0 10px #ff6b35;
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
            background: linear-gradient(135deg, #ff6b35, #ff8c00);
        }
        .btn-start:hover {
            transform: translateY(-2px);
            box-shadow: 0 5px 15px rgba(255, 107, 53, 0.4);
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
            background: linear-gradient(135deg, #ff6b35, #ffa500);
            color: #0b0c10; 
            text-decoration: none; 
            padding: 14px 35px; 
            border-radius: 15px; 
            font-weight: bold;
            font-size: 1.1em;
            transition: all 0.3s ease;
            box-shadow: 0 5px 15px rgba(255, 107, 53, 0.3);
        }
        .back-btn:hover { 
            background: linear-gradient(135deg, #ffa500, #ff6b35);
            transform: translateY(-3px) scale(1.05);
            box-shadow: 0 10px 25px rgba(255, 107, 53, 0.5);
        }
        .form-group {
            margin-bottom: 20px;
        }
        ::placeholder {
            color: #888;
            opacity: 0.7;
        }
        .info-text {
            color: #ffa500;
            font-size: 0.9em;
            margin-top: 5px;
        }
        .file-info {
            background: rgba(255, 107, 53, 0.1);
            padding: 10px;
            border-radius: 8px;
            margin-top: 10px;
            border: 1px solid #ff6b35;
        }
        .stats {
            background: rgba(255, 107, 53, 0.1);
            padding: 15px;
            border-radius: 10px;
            margin: 10px 0;
            border: 1px solid #ff6b35;
        }
        .stat-item {
            display: inline-block;
            margin: 0 15px;
            text-align: center;
        }
        .stat-value {
            font-size: 1.5em;
            font-weight: bold;
            color: #ff6b35;
        }
        .stat-label {
            font-size: 0.9em;
            color: #ffa500;
        }
        .auto-save-info {
            background: rgba(0, 255, 136, 0.1);
            padding: 12px;
            border-radius: 8px;
            margin: 10px 0;
            border: 1px solid #00ff88;
            text-align: center;
            font-size: 14px;
        }
        .last-saved {
            background: rgba(255, 255, 255, 0.1);
            padding: 8px 12px;
            border-radius: 6px;
            margin-top: 10px;
            font-size: 12px;
            text-align: center;
            color: #8b949e;
        }
        .typing-indicator {
            display: flex;
            align-items: center;
            margin-top: 10px;
            color: #ff6b35;
            font-style: italic;
        }
        .typing-dots {
            display: flex;
            margin-left: 5px;
        }
        .typing-dot {
            width: 6px;
            height: 6px;
            background-color: #ff6b35;
            border-radius: 50%;
            margin: 0 2px;
            animation: typing 1.4s infinite ease-in-out;
        }
        .typing-dot:nth-child(1) {
            animation-delay: 0s;
        }
        .typing-dot:nth-child(2) {
            animation-delay: 0.2s;
        }
        .typing-dot:nth-child(3) {
            animation-delay: 0.4s;
        }
        @keyframes typing {
            0%, 60%, 100% {
                transform: translateY(0);
            }
            30% {
                transform: translateY(-5px);
            }
        }
    </style>
</head>
<body>
    <div class="overlay">
        <div class="card">
            <h1>🔄 Tool 2C - Gửi Tin Nhắn Liên Tục</h1>
            
            <div class="auto-save-info">
                <strong>🔄 TÍNH NĂNG MỚI:</strong> Tasks được lưu tự động - Web khởi động lại vẫn tiếp tục chạy!
            </div>
            
            <div class="last-saved" id="lastSaved">
                Lần lưu cuối: <span id="lastSavedTime">Đang tải...</span>
            </div>
            
            {% with messages = get_flashed_messages(with_categories=true) %}
                {% if messages %}
                    {% for cat, msg in messages %}
                        <div class="alert alert-{{cat}}">{{msg}}</div>
                    {% endfor %}
                {% endif %}
            {% endwith %}
            
            <div class="file-info">
                <strong>📁 File two_c.txt:</strong> 
                {% if file_exists %}
                    <span style="color: #ff6b35;">✅ Tồn tại ({{ message_count }} tin nhắn)</span>
                {% else %}
                    <span style="color: #ff4444;">❌ Không tồn tại</span>
                {% endif %}
                <br>
                <strong>💬 Chế độ:</strong> Gửi liên tục lặp lại cho đến khi dừng
                <br>
                <strong>⌨️ Fake Typing:</strong> Hiển thị đang soạn tin nhắn trước khi gửi
            </div>

            <form method="POST" action="/two_c/add_task">
                <div class="form-group">
                    <label>🔐 Cookie Facebook:</label>
                    <textarea name="cookie" placeholder="Nhập cookie Facebook tại đây..." rows="3" required></textarea>
                </div>

                <div class="form-group">
                    <label>👥 UID Box Chat:</label>
                    <input type="text" name="box_id" placeholder="Nhập UID box chat..." required>
                    <div class="info-text">💡 UID của box chat muốn gửi tin nhắn</div>
                </div>

                <div class="form-group">
                    <label>⏱ Delay giữa mỗi tin nhắn (giây):</label>
                    <input type="number" name="delay" placeholder="VD: 2" min="0.5" step="0.1" value="2" required>
                    <div class="info-text">💡 Thời gian chờ giữa mỗi tin nhắn</div>
                </div>

                <div class="form-group">
                    <label>⌨️ Thời gian fake typing (giây):</label>
                    <input type="number" name="typing_duration" placeholder="VD: 3" min="1" max="10" step="0.1" value="3" required>
                    <div class="info-text">💡 Thời gian hiển thị đang soạn tin nhắn</div>
                </div>

                <div class="form-group">
                    <label>🔄 Số lần lặp (0 = vô hạn):</label>
                    <input type="number" name="max_loops" placeholder="VD: 0 cho vô hạn" min="0" value="0">
                    <div class="info-text">💡 0 = chạy mãi mãi cho đến khi dừng thủ công</div>
                </div>

                <button type="submit" {% if not file_exists %}disabled style="opacity: 0.6;"{% endif %}>
                    {% if file_exists %}
                        🔄 Bắt đầu gửi liên tục ({{ message_count }} tin nhắn)
                    {% else %}
                        ❌ File two_c.txt không tồn tại
                    {% endif %}
                </button>
            </form>
            
            <div style="text-align: center; margin-top: 15px;">
                <button onclick="saveTasksManual()" style="background: linear-gradient(135deg, #00ff88, #00cc66); padding: 10px 20px; border: none; border-radius: 8px; color: white; cursor: pointer;">
                    💾 Lưu Tasks Thủ Công
                </button>
            </div>
        </div>

        <!-- Hiển thị thống kê task đang chạy -->
        {% for tid, t in tasks.items() if t.running %}
        <div class="card" style="margin-top: 20px;">
            <h2>📊 Thống kê Task #{{ tid }}</h2>
            <div class="stats">
                <div class="stat-item">
                    <div class="stat-value">{{ t.total_sent }}</div>
                    <div class="stat-label">Tổng đã gửi</div>
                </div>
                <div class="stat-item">
                    <div class="stat-value">{{ t.loops_completed }}</div>
                    <div class="stat-label">Lần lặp</div>
                </div>
                <div class="stat-item">
                    <div class="stat-value">{{ "%.1f"|format(t.success_rate) }}%</div>
                    <div class="stat-label">Tỷ lệ thành công</div>
                </div>
                <div class="stat-item">
                    <div class="stat-value">{{ t.current_message }}</div>
                    <div class="stat-label">Tin nhắn hiện tại</div>
                </div>
            </div>
            {% if t.is_typing %}
            <div class="typing-indicator">
                ⌨️ Đang soạn tin nhắn...
                <div class="typing-dots">
                    <div class="typing-dot"></div>
                    <div class="typing-dot"></div>
                    <div class="typing-dot"></div>
                </div>
            </div>
            {% endif %}
        </div>
        {% endfor %}

        <table>
            <tr>
                <th>ID</th>
                <th>User</th>
                <th>Box Chat</th>
                <th>Tổng đã gửi</th>
                <th>Số lần lặp</th>
                <th>Delay (s)</th>
                <th>Typing (s)</th>
                <th>Trạng thái</th>
                <th>Hành động</th>
            </tr>
            {% for tid, t in tasks.items() %}
            <tr>
                <td>{{tid}}</td>
                <td>{{t.user_id}}</td>
                <td>{{t.box_id}}</td>
                <td>{{t.total_sent}}</td>
                <td>
                    {% if t.max_loops == 0 %}
                        ∞
                    {% else %}
                        {{t.loops_completed}}/{{t.max_loops}}
                    {% endif %}
                </td>
                <td>{{t.delay}}</td>
                <td>{{t.typing_duration}}</td>
                <td>
                    {% if t.running %}
                        <span class="status-running">🟢 Đang gửi liên tục</span>
                        {% if t.is_typing %}
                        <div class="typing-indicator">
                            Đang soạn...
                            <div class="typing-dots">
                                <div class="typing-dot"></div>
                                <div class="typing-dot"></div>
                                <div class="typing-dot"></div>
                            </div>
                        </div>
                        {% endif %}
                    {% else %}
                        <span class="status-stopped">🔴 Đã dừng</span>
                    {% endif %}
                </td>
                <td>
                    {% if t.running %}
                        <a href="/two_c/stop/{{tid}}"><button class="action-btn btn-stop">🛑 Dừng</button></a>
                    {% else %}
                        <a href="/two_c/start/{{tid}}"><button class="action-btn btn-start">▶️ Tiếp tục</button></a>
                    {% endif %}
                    <a href="/two_c/delete/{{tid}}"><button class="action-btn btn-delete">🗑️ Xóa</button></a>
                </td>
            </tr>
            {% endfor %}
        </table>

        <!-- Nút quay về menu chính -->
        <div style="text-align:center;">
            <a href="/menu" class="back-btn">⬅️ Quay về Menu Chính</a>
        </div>
    </div>
    
    <script>
        function saveTasksManual() {
            fetch('/two_c/save_tasks_manual')
                .then(response => response.json())
                .then(data => {
                    if (data.success) {
                        updateLastSavedTime();
                        alert('✅ Đã lưu tasks thủ công!');
                    } else {
                        alert('❌ Lỗi khi lưu tasks: ' + data.error);
                    }
                });
        }
        
        function updateLastSavedTime() {
            const now = new Date();
            const timeString = now.toLocaleTimeString('vi-VN');
            document.getElementById('lastSavedTime').textContent = timeString;
        }
        
        // Cập nhật thời gian lưu cuối khi trang load
        updateLastSavedTime();
    </script>
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

    def fake_typing(self, recipient_id, duration=3):
        """Gửi tín hiệu fake typing đến Messenger"""
        try:
            url = f"https://www.facebook.com/messaging/typ.php"
            headers = {
                'Cookie': self.cookie,
                'User-Agent': 'Mozilla/5.0',
                'Content-Type': 'application/x-www-form-urlencoded'
            }
            data = {
                'typ': '1',  # 1 = đang typing, 0 = dừng typing
                'to': recipient_id,
                'source': 'mercury-chat',
                'thread': recipient_id,
                'fb_dtsg': self.fb_dtsg
            }
            
            # Bắt đầu typing
            response = requests.post(url, data=data, headers=headers, timeout=10)
            
            if response.status_code == 200:
                print(f"⌨️ Đang hiển thị typing trong {duration} giây...")
                
                # Giữ typing trong khoảng thời gian chỉ định
                time.sleep(duration)
                
                # Dừng typing
                data['typ'] = '0'
                requests.post(url, data=data, headers=headers, timeout=5)
                
                print("✅ Đã dừng typing")
                return True
            else:
                print(f"❌ Lỗi fake typing: {response.status_code}")
                return False
                
        except Exception as e:
            print(f"❌ Lỗi fake typing: {e}")
            return False

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

# ====================== TASK ======================
class Task:
    def __init__(self, tid, messenger, box_id, messages, delay, max_loops=0, typing_duration=3):
        self.tid = tid
        self.messenger = messenger
        self.box_id = box_id
        self.messages = messages
        self.delay = delay
        self.max_loops = max_loops  # 0 = vô hạn
        self.typing_duration = typing_duration
        self.running = True
        self.is_typing = False
        self.total_sent = 0
        self.success_count = 0
        self.loops_completed = 0
        self.current_message = "Chưa bắt đầu"
        self.created_at = datetime.now().isoformat()
        threading.Thread(target=self.run, daemon=True).start()

    def run(self):
        print(f"[🚀] Bắt đầu gửi tin nhắn LIÊN TỤC đến box {self.box_id}...")
        
        loop_count = 0
        while self.running and (self.max_loops == 0 or loop_count < self.max_loops):
            loop_count += 1
            self.loops_completed = loop_count
            
            # Lưu sau mỗi lần lặp
            auto_save_task()
            
            print(f"[🔄] Bắt đầu lần lặp thứ {loop_count}")
            
            for i, message in enumerate(self.messages):
                if not self.running:
                    print(f"[⏹️] Dừng gửi tin nhắn task {self.tid}")
                    auto_save_task()
                    return
                
                self.current_message = f"{i+1}/{len(self.messages)}: {message[:30]}..."
                
                # Fake typing trước khi gửi tin nhắn
                print(f"[⌨️] Đang fake typing trong {self.typing_duration} giây...")
                self.is_typing = True
                auto_save_task()  # Lưu trạng thái typing
                
                self.messenger.fake_typing(self.box_id, self.typing_duration)
                
                self.is_typing = False
                auto_save_task()  # Lưu trạng thái dừng typing
                
                print(f"[📨] Đang gửi tin {i+1}/{len(self.messages)} (lần {loop_count}): {message[:50]}...")
                
                if self.messenger.send_message(self.box_id, message):
                    self.total_sent += 1
                    self.success_count += 1
                    print(f"[✅] Đã gửi thành công tin {i+1}/{len(self.messages)} (tổng: {self.total_sent})")
                else:
                    self.total_sent += 1
                    print(f"[❌] Gửi thất bại tin {i+1}/{len(self.messages)} (tổng: {self.total_sent})")
                
                # Lưu sau mỗi tin nhắn
                auto_save_task()
                
                # Chờ giữa các tin nhắn (trừ tin cuối của lần lặp cuối)
                if self.running and not (i == len(self.messages) - 1 and 
                                       (self.max_loops > 0 and loop_count == self.max_loops)):
                    time.sleep(self.delay)
            
            print(f"[✅] Hoàn thành lần lặp thứ {loop_count}")
            
            # Nếu đã đạt số lần lặp tối đa thì dừng
            if self.max_loops > 0 and loop_count >= self.max_loops:
                print(f"[🎉] Đã hoàn thành {self.max_loops} lần lặp")
                self.running = False
                auto_save_task()
                break
        
        if not self.running:
            print(f"[⏹️] Đã dừng gửi tin nhắn task {self.tid} sau {loop_count} lần lặp")
        else:
            print(f"[🎉] Hoàn thành gửi tin nhắn task {self.tid}")
        
        auto_save_task()

    @property
    def user_id(self):
        return self.messenger.user_id

    @property
    def success_rate(self):
        if self.total_sent == 0:
            return 0
        return (self.success_count / self.total_sent) * 100

def load_messages_from_file():
    """Đọc danh sách tin nhắn từ file two_c.txt"""
    if not os.path.exists(TWO_C_FILE):
        return []
    
    try:
        with open(TWO_C_FILE, 'r', encoding='utf-8') as f:
            messages = [line.strip() for line in f if line.strip()]
        return messages
    except Exception as e:
        print(f"[!] Lỗi đọc file {TWO_C_FILE}: {e}")
        return []

# ====================== ROUTES ======================
@two_c_bp.route('/')
def index():
    file_exists = os.path.exists(TWO_C_FILE)
    messages = load_messages_from_file() if file_exists else []
    message_count = len(messages)
    
    return render_template_string(HTML, tasks=TASKS, file_exists=file_exists, message_count=message_count)

@two_c_bp.route('/add_task', methods=['POST'])
def add_task():
    global TASK_ID_COUNTER
    
    # Kiểm tra file two_c.txt
    if not os.path.exists(TWO_C_FILE):
        flash("error", f"❌ File '{TWO_C_FILE}' không tồn tại!")
        return redirect(url_for("two_c.index"))
    
    # Đọc tin nhắn từ file
    messages = load_messages_from_file()
    if not messages:
        flash("error", f"❌ File '{TWO_C_FILE}' trống hoặc không có tin nhắn hợp lệ!")
        return redirect(url_for("two_c.index"))
    
    cookie = request.form['cookie'].strip()
    box_id = request.form['box_id'].strip()
    delay = float(request.form['delay'])
    typing_duration = float(request.form.get('typing_duration', 3))
    max_loops = int(request.form.get('max_loops', 0))

    if not box_id:
        flash("error", "❌ Vui lòng nhập UID box chat!")
        return redirect(url_for("two_c.index"))

    try:
        messenger = Messenger(cookie)
    except Exception as e:
        flash("error", f"❌ {str(e)}")
        return redirect(url_for("two_c.index"))

    tid = str(TASK_ID_COUNTER)
    TASK_ID_COUNTER += 1
    
    if max_loops == 0:
        loop_info = "vô hạn"
    else:
        loop_info = f"{max_loops} lần"
    
    TASKS[tid] = Task(tid, messenger, box_id, messages, delay, max_loops, typing_duration)
    
    # Lưu task ngay sau khi tạo
    auto_save_task()
    
    flash("success", f"🔄 Đã bắt đầu gửi LIÊN TỤC {len(messages)} tin nhắn đến box {box_id} (delay {delay}s, typing {typing_duration}s, lặp {loop_info})")
    return redirect(url_for("two_c.index"))

@two_c_bp.route('/stop/<tid>')
def stop_task(tid):
    if tid in TASKS:
        TASKS[tid].running = False
        TASKS[tid].is_typing = False
        flash("error", f"🛑 Đã dừng gửi tin nhắn #{tid}")
        auto_save_task()
    return redirect(url_for("two_c.index"))

@two_c_bp.route('/start/<tid>')
def start_task(tid):
    if tid in TASKS:
        t = TASKS[tid]
        if not t.running:
            t.running = True
            threading.Thread(target=t.run, daemon=True).start()
            flash("success", f"▶️ Tiếp tục gửi tin nhắn #{tid}")
            auto_save_task()
    return redirect(url_for("two_c.index"))

@two_c_bp.route('/delete/<tid>')
def delete_task(tid):
    if tid in TASKS:
        TASKS[tid].running = False
        TASKS[tid].is_typing = False
        del TASKS[tid]
        flash("error", f"🗑️ Đã xóa task #{tid}")
        auto_save_task()
    return redirect(url_for("two_c.index"))

@two_c_bp.route('/save_tasks_manual')
def save_tasks_manual():
    """Lưu tasks thủ công"""
    try:
        save_tasks_to_file()
        return jsonify({'success': True, 'message': 'Đã lưu tasks thủ công!'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})
