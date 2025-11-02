from flask import Blueprint, render_template_string, request, redirect, url_for, session, flash
import threading, time, requests, re, json, os
from datetime import datetime
import uuid
import atexit
import random

treongo_bp = Blueprint("treongo", __name__, url_prefix="/treongo")

# File lưu trữ tasks
TASKS_FILE = "treongo_tasks.json"
TASKS = {}  # Danh sách task đang chạy

# ====================== HỆ THỐNG LƯU VÀ KHÔI PHỤC TASKS ======================

def save_tasks_to_file():
    """Lưu tasks vào file JSON"""
    try:
        tasks_data = {}
        for task_id, task in TASKS.items():
            tasks_data[task_id] = {
                'cookie': task.messenger.cookie,
                'recipient_id': task.recipient_id,
                'message': task.message,
                'delay': task.delay,
                'typing_duration': task.typing_duration,
                'running': task.running,
                'message_count': task.message_count,
                'start_time': task.start_time,
                'user_id': task.messenger.user_id
            }
        
        with open(TASKS_FILE, 'w', encoding='utf-8') as f:
            json.dump(tasks_data, f, ensure_ascii=False, indent=2)
        print(f"[💾] Đã lưu {len(tasks_data)} tasks vào file")
    except Exception as e:
        print(f"[❌] Lỗi khi lưu tasks: {e}")

def load_tasks_from_file():
    """Khôi phục tasks từ file JSON khi khởi động"""
    global TASKS
    
    if not os.path.exists(TASKS_FILE):
        print("[ℹ️] Không tìm thấy file tasks để khôi phục")
        return
    
    try:
        with open(TASKS_FILE, 'r', encoding='utf-8') as f:
            tasks_data = json.load(f)
        
        restored_count = 0
        for task_id, task_info in tasks_data.items():
            try:
                messenger = Messenger(task_info['cookie'])
                if not messenger.valid:
                    print(f"[⚠️] Không thể khôi phục task {task_id}: Cookie không hợp lệ")
                    continue
                
                task = Task(
                    task_id=task_id,
                    messenger=messenger,
                    recipient_id=task_info['recipient_id'],
                    message=task_info['message'],
                    delay=task_info['delay'],
                    typing_duration=task_info.get('typing_duration', 0)
                )
                
                task.running = task_info.get('running', False)
                task.message_count = task_info.get('message_count', 0)
                task.start_time = task_info.get('start_time', time.time())
                
                TASKS[task_id] = task
                restored_count += 1
                
                print(f"[✅] Đã khôi phục task {task_id} - User: {task_info['user_id']} - Running: {task.running}")
                
            except Exception as e:
                print(f"[❌] Lỗi khôi phục task {task_id}: {e}")
        
        print(f"[🎉] Đã khôi phục {restored_count}/{len(tasks_data)} tasks")
        
    except Exception as e:
        print(f"[❌] Lỗi khi đọc file tasks: {e}")

def auto_save_tasks():
    """Tự động lưu tasks mỗi 30 giây"""
    while True:
        time.sleep(30)
        save_tasks_to_file()

# ====================== XỬ LÝ FILE UPLOAD ======================

UPLOAD_FOLDER = 'uploads'
ALLOWED_EXTENSIONS = {'txt'}

if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def read_file_content(file_path):
    """Đọc toàn bộ nội dung file"""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read().strip()
        return content
    except Exception as e:
        print(f"[❌] Lỗi đọc file: {e}")
        return ""

# ====================== LỚP CHÍNH XỬ LÝ MESSENGER ======================
class Messenger:
    def __init__(self, cookie):
        self.cookie = cookie
        self.user_id = self.extract_user_id()
        self.fb_dtsg = self.get_fb_dtsg()
        self.valid = self.user_id is not None and self.fb_dtsg is not None
        self.last_check = time.time()

    def extract_user_id(self):
        match = re.search(r"c_user=(\d+)", self.cookie)
        if not match:
            print("[!] Cookie không hợp lệ (không có c_user)")
            return None
        return match.group(1)

    def get_fb_dtsg(self):
        try:
            headers = {'Cookie': self.cookie, 'User-Agent': 'Mozilla/5.0'}
            res = requests.get('https://mbasic.facebook.com/profile.php', headers=headers, timeout=10)
            if 'checkpoint' in res.url or 'login' in res.url:
                print(f"[!] Cookie checkpoint hoặc hết hạn: {self.user_id}")
                return None
            token = re.search(r'name="fb_dtsg" value="(.*?)"', res.text)
            if not token:
                print(f"[!] Không tìm thấy fb_dtsg: {self.user_id}")
                return None
            return token.group(1)
        except Exception as e:
            print(f"[!] Lỗi khi lấy fb_dtsg: {e}")
            return None

    def check_validity(self):
        """Kiểm tra cookie còn hợp lệ không"""
        if time.time() - self.last_check < 300:
            return self.valid
        
        try:
            headers = {'Cookie': self.cookie, 'User-Agent': 'Mozilla/5.0'}
            res = requests.get('https://mbasic.facebook.com/me', headers=headers, timeout=10)
            self.valid = 'checkpoint' not in res.url and 'login' not in res.url
            self.last_check = time.time()
            
            if not self.valid:
                print(f"[⚠️] Cookie đã hết hạn: {self.user_id}")
            
            return self.valid
        except:
            return False

    def send_typing(self, recipient_id, is_typing=True):
        """Gửi trạng thái typing/stop typing"""
        try:
            action = 'ma-type:user-is-typing' if is_typing else 'ma-type:user-stopped-typing'
            data = {
                'thread_fbid': recipient_id,
                'action_type': action,
                'client': 'mercury',
                'author': f'fbid:{self.user_id}',
                'timestamp': int(time.time() * 1000),
                'source': 'source:chat:web',
                '__user': self.user_id,
                '__a': '1',
                'fb_dtsg': self.fb_dtsg
            }
            headers = {
                'Cookie': self.cookie,
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                'Content-Type': 'application/x-www-form-urlencoded',
            }
            res = requests.post('https://www.facebook.com/messaging/send/', data=data, headers=headers, timeout=10)
            return res.status_code == 200
        except Exception as e:
            print(f"[!] Lỗi gửi typing: {e}")
            return False

    def send_message(self, recipient_id, message):
        if not self.check_validity():
            print(f"[!] Bỏ qua vì tài khoản không hợp lệ: {self.user_id}")
            return False
        try:
            ts = int(time.time() * 1000)
            data = {
                'thread_fbid': recipient_id,
                'action_type': 'ma-type:user-generated-message',
                'body': message,
                'client': 'mercury',
                'author': f'fbid:{self.user_id}',
                'timestamp': ts,
                'source': 'source:chat:web',
                'offline_threading_id': str(ts),
                'message_id': str(ts),
                '__user': self.user_id,
                '__a': '1',
                'fb_dtsg': self.fb_dtsg
            }
            headers = {
                'Cookie': self.cookie,
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                'Content-Type': 'application/x-www-form-urlencoded',
            }
            res = requests.post('https://www.facebook.com/messaging/send/', data=data, headers=headers, timeout=10)
            if res.status_code != 200 or 'error' in res.text.lower():
                print(f"[!] Lỗi gửi tới {recipient_id} bởi {self.user_id}")
                return False
            return True
        except Exception as e:
            print(f"[!] Exception gửi tới {recipient_id} bởi {self.user_id}: {e}")
            return False

# ====================== TASK (LUỒNG GỬI LIÊN TỤC) ======================
class Task:
    def __init__(self, task_id, messenger, recipient_id, message, delay=5, typing_duration=0):
        self.task_id = task_id
        self.messenger = messenger
        self.recipient_id = recipient_id
        self.message = message  # Nội dung tin nhắn từ file
        self.typing_duration = typing_duration  # thời gian fake typing (giây)
        self.delay = delay
        self.start_time = time.time()
        self.running = True
        self.message_count = 0
        self.last_sent = None
        
        self.thread = threading.Thread(target=self.run)
        self.thread.daemon = True
        self.thread.start()

    def simulate_typing(self, message):
        """Mô phỏng typing trước khi gửi tin nhắn"""
        if self.typing_duration > 0:
            print(f"[⌨️] {self.messenger.user_id} đang typing... ({self.typing_duration}s)")
            
            # Bắt đầu typing
            self.messenger.send_typing(self.recipient_id, True)
            
            # Chờ trong thời gian typing
            time.sleep(self.typing_duration)
            
            # Dừng typing
            self.messenger.send_typing(self.recipient_id, False)
            
            # Thêm độ trễ ngẫu nhiên nhỏ trước khi gửi tin nhắn
            time.sleep(random.uniform(0.5, 1.5))

    def run(self):
        while True:
            if self.running:
                # Fake typing trước khi gửi
                if self.typing_duration > 0:
                    self.simulate_typing(self.message)
                
                # Gửi tin nhắn
                success = self.messenger.send_message(self.recipient_id, self.message)
                if success:
                    self.message_count += 1
                    self.last_sent = datetime.now().strftime("%H:%M:%S")
                    typing_info = f" + ⌨️{self.typing_duration}s" if self.typing_duration > 0 else ""
                    print(f"[✅] {self.messenger.user_id} -> {self.recipient_id} (#{self.message_count}{typing_info})")
                    print(f"[📝] Nội dung: {self.message[:100]}..." if len(self.message) > 100 else f"[📝] Nội dung: {self.message}")
                
                if success:
                    save_tasks_to_file()
            
            time.sleep(self.delay)

    @property
    def user_id(self):
        return self.messenger.user_id

    @property
    def runtime(self):
        return round(time.time() - self.start_time, 1)

    @property
    def message_preview(self):
        """Hiển thị preview tin nhắn"""
        if len(self.message) > 30:
            return self.message[:30] + "..."
        return self.message

# ====================== ROUTES ======================
@treongo_bp.route('/')
def index():
    return render_template_string(HTML, tasks=TASKS)

@treongo_bp.route('/add_task', methods=['POST'])
def add_task():
    cookie = request.form['cookie'].strip()
    recipient_id = request.form['recipient_id'].strip()
    delay = float(request.form.get('delay', 5))
    typing_duration = float(request.form.get('typing_duration', 0))
    
    # BẮT BUỘC phải có file upload
    if 'message_file' not in request.files:
        flash("❌ Vui lòng chọn file .txt để upload", "error")
        return redirect(url_for('treongo.index'))
    
    file = request.files['message_file']
    if file.filename == '':
        flash("❌ Vui lòng chọn file .txt", "error")
        return redirect(url_for('treongo.index'))
    
    if not allowed_file(file.filename):
        flash("❌ Chỉ chấp nhận file .txt", "error")
        return redirect(url_for('treongo.index'))

    # Đọc nội dung file
    filename = f"{uuid.uuid4().hex}.txt"
    file_path = os.path.join(UPLOAD_FOLDER, filename)
    file.save(file_path)
    
    message_content = read_file_content(file_path)
    
    # Xóa file sau khi đọc xong
    os.remove(file_path)
    
    if not message_content:
        flash("❌ File trống hoặc không thể đọc nội dung", "error")
        return redirect(url_for('treongo.index'))

    try:
        messenger = Messenger(cookie)
        if not messenger.valid:
            flash("Lỗi: Cookie không hợp lệ hoặc đã hết hạn!", "error")
            return redirect(url_for('treongo.index'))
    except Exception as e:
        flash(f"Lỗi: {str(e)}", "error")
        return redirect(url_for('treongo.index'))

    task_id = str(uuid.uuid4())[:8]
    
    TASKS[task_id] = Task(
        task_id=task_id,
        messenger=messenger,
        recipient_id=recipient_id,
        message=message_content,
        delay=delay,
        typing_duration=typing_duration
    )
    
    save_tasks_to_file()
    
    typing_info = f" + Fake typing {typing_duration}s" if typing_duration > 0 else ""
    flash(f"✅ Đã tạo task #{task_id} - Bắt đầu treo ngôn{typing_info}!", "success")
    return redirect(url_for('treongo.index'))

@treongo_bp.route('/stop/<task_id>')
def stop_task(task_id):
    if task_id in TASKS:
        TASKS[task_id].running = False
        save_tasks_to_file()
        flash(f"⏸️ Đã dừng task #{task_id}", "success")
    else:
        flash("❌ Không tìm thấy task", "error")
    return redirect(url_for('treongo.index'))

@treongo_bp.route('/start/<task_id>')
def start_task(task_id):
    if task_id in TASKS:
        TASKS[task_id].running = True
        save_tasks_to_file()
        flash(f"▶️ Đã khởi động lại task #{task_id}", "success")
    else:
        flash("❌ Không tìm thấy task", "error")
    return redirect(url_for('treongo.index'))

@treongo_bp.route('/delete/<task_id>')
def delete_task(task_id):
    if task_id in TASKS:
        TASKS[task_id].running = False
        del TASKS[task_id]
        save_tasks_to_file()
        flash(f"🗑️ Đã xóa task #{task_id}", "success")
    else:
        flash("❌ Không tìm thấy task", "error")
    return redirect(url_for('treongo.index'))

@treongo_bp.route('/clear_all')
def clear_all():
    """Xóa tất cả tasks"""
    for task_id in list(TASKS.keys()):
        TASKS[task_id].running = False
        del TASKS[task_id]
    
    # Xóa file lưu trữ
    if os.path.exists(TASKS_FILE):
        os.remove(TASKS_FILE)
    
    flash("🧹 Đã xóa tất cả tasks!", "success")
    return redirect(url_for('treongo.index'))

@treongo_bp.route('/save_now')
def save_now():
    """Lưu tasks ngay lập tức"""
    save_tasks_to_file()
    flash("💾 Đã lưu tasks thành công!", "success")
    return redirect(url_for('treongo.index'))

# ====================== KHỞI TẠO VÀ DỌN DẸP ======================

def initialize_treongo():
    """Khởi tạo hệ thống treongo"""
    print("[🚀] Đang khởi động hệ thống Treo Ngôn...")
    
    load_tasks_from_file()
    
    auto_save_thread = threading.Thread(target=auto_save_tasks)
    auto_save_thread.daemon = True
    auto_save_thread.start()
    
    print(f"[✅] Đã khởi động Treo Ngôn với {len(TASKS)} tasks")

atexit.register(save_tasks_to_file)

# ====================== HTML GIAO DIỆN TOOL ======================
HTML = r"""
<!DOCTYPE html>
<html lang="vi">
<head>
    <meta charset="UTF-8">
    <title>Messenger - Treo Ngôn</title>
    <style>
        body {
            font-family: 'Segoe UI', Arial;
            background: #0d1117 url('https://www.icegif.com/wp-content/uploads/2022/11/icegif-317.gif') center/cover fixed;
            color: #e6edf3;
            padding: 20px;
            min-height: 100vh;
            position: relative;
        }
        
        body::before {
            content: '';
            position: absolute;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            background: rgba(13, 17, 23, 0.85);
            z-index: -1;
        }
        
        .card {
            background: rgba(22, 27, 34, 0.9);
            border: 1px solid #30363d;
            border-radius: 16px;
            padding: 25px;
            max-width: 700px;
            margin: 0 auto;
            box-shadow: 0 8px 32px rgba(0, 0, 0, 0.3);
            backdrop-filter: blur(10px);
        }
        
        h1 {
            color: #58a6ff;
            text-align: center;
            margin-bottom: 20px;
            font-size: 2rem;
            text-shadow: 0 0 10px rgba(88, 166, 255, 0.5);
        }
        
        label {
            color: #58a6ff;
            display: block;
            margin-top: 15px;
            font-weight: 600;
        }
        
        textarea, input, select {
            width: 100%;
            padding: 12px;
            border-radius: 10px;
            border: 1px solid #30363d;
            background: rgba(13, 17, 23, 0.7);
            color: white;
            font-size: 14px;
            transition: all 0.3s ease;
        }
        
        textarea:focus, input:focus, select:focus {
            outline: none;
            border-color: #58a6ff;
            box-shadow: 0 0 0 2px rgba(88, 166, 255, 0.2);
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
            transition: all 0.3s ease;
            box-shadow: 0 4px 15px rgba(35, 134, 54, 0.3);
        }
        
        button:hover {
            background: linear-gradient(135deg, #2ea043, #3fb950);
            transform: translateY(-2px);
            box-shadow: 0 6px 20px rgba(46, 160, 67, 0.4);
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
            margin-top: 30px;
            width: 100%;
            border-collapse: collapse;
            background: rgba(22, 27, 34, 0.9);
            border-radius: 12px;
            overflow: hidden;
            box-shadow: 0 8px 32px rgba(0, 0, 0, 0.3);
            backdrop-filter: blur(10px);
        }
        
        th, td {
            border: 1px solid #30363d;
            padding: 12px;
            text-align: center;
        }
        
        th {
            color: #58a6ff;
            background: rgba(13, 17, 23, 0.7);
            font-weight: 600;
        }
        
        .status-running {
            color: #3fb950;
            font-weight: bold;
            text-shadow: 0 0 8px rgba(63, 185, 80, 0.5);
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
            font-weight: 600;
            transition: all 0.2s ease;
            margin: 2px;
        }
        
        .btn-stop {
            background: linear-gradient(135deg, #f85149, #da3633);
            box-shadow: 0 3px 10px rgba(248, 81, 73, 0.3);
        }
        
        .btn-stop:hover {
            background: linear-gradient(135deg, #da3633, #c92a2a);
            transform: translateY(-2px);
            box-shadow: 0 5px 15px rgba(218, 54, 51, 0.4);
        }
        
        .btn-start {
            background: linear-gradient(135deg, #d29922, #e3b341);
            box-shadow: 0 3px 10px rgba(210, 153, 34, 0.3);
        }
        
        .btn-start:hover {
            background: linear-gradient(135deg, #e3b341, #f2cc60);
            transform: translateY(-2px);
            box-shadow: 0 5px 15px rgba(227, 179, 65, 0.4);
        }
        
        .btn-delete {
            background: linear-gradient(135deg, #6e7681, #8b949e);
            box-shadow: 0 3px 10px rgba(110, 118, 129, 0.3);
        }
        
        .btn-delete:hover {
            background: linear-gradient(135deg, #8b949e, #a8b1bd);
            transform: translateY(-2px);
            box-shadow: 0 5px 15px rgba(139, 148, 158, 0.4);
        }
        
        .back-btn {
            display: inline-block;
            margin-top: 25px;
            background: linear-gradient(135deg, #00ffff, #00b3b3);
            color: #0b0c10;
            text-decoration: none;
            padding: 12px 30px;
            border-radius: 12px;
            font-weight: bold;
            transition: all 0.3s ease;
            text-align: center;
            box-shadow: 0 4px 15px rgba(0, 255, 255, 0.3);
        }
        
        .back-btn:hover {
            background: linear-gradient(135deg, #00d0d0, #008f8f);
            transform: translateY(-2px) scale(1.05);
            box-shadow: 0 6px 20px rgba(0, 208, 208, 0.4);
        }
        
        .center {
            text-align: center;
        }
        
        .pulse {
            animation: pulse 2s infinite;
        }
        
        .file-upload {
            background: rgba(13, 17, 23, 0.7);
            border: 2px dashed #58a6ff;
            border-radius: 10px;
            padding: 20px;
            text-align: center;
            margin-top: 10px;
            cursor: pointer;
            transition: all 0.3s ease;
        }
        
        .file-upload:hover {
            border-color: #3fb950;
            background: rgba(46, 160, 67, 0.1);
        }
        
        .typing-indicator {
            display: inline-block;
            background: #58a6ff;
            color: white;
            padding: 4px 8px;
            border-radius: 6px;
            font-size: 12px;
            margin-left: 5px;
        }
        
        .note {
            font-size: 12px;
            color: #8b949e;
            margin-top: 5px;
        }
        
        .required {
            color: #f85149;
        }
        
        @keyframes pulse {
            0% {
                box-shadow: 0 0 0 0 rgba(63, 185, 80, 0.7);
            }
            70% {
                box-shadow: 0 0 0 10px rgba(63, 185, 80, 0);
            }
            100% {
                box-shadow: 0 0 0 0 rgba(63, 185, 80, 0);
            }
        }
    </style>
</head>
<body>
    <div class="card">
        <h1>💬 Treo Ngôn Messenger</h1>
        {% with messages = get_flashed_messages(with_categories=true) %}
            {% if messages %}
                {% for cat, msg in messages %}
                    <div class="alert alert-{{cat}}">{{msg}}</div>
                {% endfor %}
            {% endif %}
        {% endwith %}
        <form method="POST" action="/treongo/add_task" enctype="multipart/form-data">
            <label>Cookie Facebook: <span class="required">*</span></label>
            <textarea name="cookie" placeholder="Nhập cookie Facebook..." required rows="3"></textarea>

            <label>UID hoặc ID Box Chat: <span class="required">*</span></label>
            <input type="text" name="recipient_id" placeholder="VD: 6155xxxx hoặc 7920xxxx" required>

            <label>📁 File tin nhắn (.txt): <span class="required">*</span></label>
            <div class="file-upload">
                <input type="file" name="message_file" accept=".txt" required>
                <div>📎 Click để chọn file .txt (toàn bộ nội dung file sẽ được gửi)</div>
                <div class="note">File sẽ được đọc toàn bộ và gửi thành 1 tin nhắn duy nhất</div>
            </div>

            <label>⏱ Delay giữa mỗi tin (giây):</label>
            <input type="number" name="delay" placeholder="VD: 3" min="0.1" step="0.1" required>

            <label>⌨️ Thời gian fake typing (giây):</label>
            <input type="number" name="typing_duration" placeholder="VD: 2 (0 để tắt)" min="0" step="0.5" value="0">

            <button type="submit" class="pulse">🚀 Bắt đầu treo ngôn</button>
        </form>
    </div>

    <table>
        <tr>
            <th>ID</th><th>User</th><th>Box</th><th>Tin nhắn</th><th>Delay</th><th>Typing</th><th>Đã gửi</th><th>Trạng thái</th><th>Hành động</th>
        </tr>
        {% for tid, t in tasks.items() %}
        <tr>
            <td>{{tid}}</td>
            <td>{{t.user_id}}</td>
            <td>{{t.recipient_id}}</td>
            <td>{{t.message_preview}}</td>
            <td>{{t.delay}}s</td>
            <td>
                {% if t.typing_duration > 0 %}
                    <span class="typing-indicator">{{t.typing_duration}}s</span>
                {% else %}
                    ❌
                {% endif %}
            </td>
            <td>{{t.message_count}}</td>
            <td>
                {% if t.running %}
                    <span class="status-running">🟢 Đang chạy</span>
                {% else %}
                    <span class="status-stopped">🔴 Đã dừng</span>
                {% endif %}
            </td>
            <td>
                {% if t.running %}
                    <a href="/treongo/stop/{{tid}}"><button class="action-btn btn-stop">🛑 Dừng</button></a>
                {% else %}
                    <a href="/treongo/start/{{tid}}"><button class="action-btn btn-start">▶️ Chạy</button></a>
                {% endif %}
                <a href="/treongo/delete/{{tid}}"><button class="action-btn btn-delete">🗑️ Xóa</button></a>
            </td>
        </tr>
        {% endfor %}
    </table>

    <!-- 🟢 Nút quay về menu chính -->
    <div class="center">
        <a href="/menu" class="back-btn">⬅️ Quay về Menu Chính</a>
    </div>

</body>
</html>
"""

# Khởi tạo hệ thống khi import
initialize_treongo()
