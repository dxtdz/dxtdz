from flask import Blueprint, render_template_string, request, redirect, url_for, flash
import threading, time, requests, re, random, os, json, atexit

# ======== BLUEPRINT ========
nhaydz_bp = Blueprint("nhaydz", __name__, url_prefix="/nhaydz")

TASKS = {}
TASK_ID_COUNTER = 1
NHAY_FILE = "nhay.txt"
TASKS_FILE = "tasks.json"  # File để lưu trữ tasks

# ====================== HTML GIAO DIỆN ======================
HTML = r"""
<!DOCTYPE html>
<html lang="vi">
<head>
    <meta charset="UTF-8">
    <title>Messenger - Auto Nhây</title>
    <style>
        body { 
            font-family: 'Segoe UI', Arial; 
            background: url('https://www.icegif.com/wp-content/uploads/2022/11/icegif-317.gif') no-repeat center center fixed;
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
            border: 1px solid #00ffff; 
            border-radius: 20px; 
            padding: 30px; 
            max-width: 700px; 
            margin: 0 auto;
            backdrop-filter: blur(10px);
            box-shadow: 0 0 30px rgba(0, 255, 255, 0.3);
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
            color: #00ffff; 
            text-align: center; 
            text-shadow: 0 0 20px #00ffff;
            margin-bottom: 25px;
            font-size: 2.2em;
        }
        label { 
            color: #00ffff; 
            display: block; 
            margin-top: 20px;
            font-weight: 600;
            font-size: 1.1em;
        }
        textarea, input, select {
            width: 100%; 
            padding: 15px; 
            border-radius: 12px;
            border: 2px solid #00ffff; 
            background: rgba(13, 17, 23, 0.8); 
            color: white;
            font-size: 1em;
            transition: all 0.3s ease;
            box-sizing: border-box;
        }
        textarea:focus, input:focus, select:focus {
            border-color: #00ff88;
            box-shadow: 0 0 15px rgba(0, 255, 136, 0.5);
            outline: none;
            transform: scale(1.02);
        }
        button {
            background: linear-gradient(135deg, #00ffff, #00ff88);
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
            box-shadow: 0 10px 25px rgba(0, 255, 255, 0.4);
            background: linear-gradient(135deg, #00ff88, #00ffff);
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
            box-shadow: 0 0 20px rgba(0, 255, 255, 0.2);
            backdrop-filter: blur(10px);
        }
        th, td { 
            border: 1px solid #00ffff; 
            padding: 15px; 
            text-align: center; 
        }
        th { 
            color: #00ffff; 
            background: rgba(0, 255, 255, 0.1);
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
            background: linear-gradient(135deg, #00ffff, #0099ff);
            color: #0b0c10; 
            text-decoration: none; 
            padding: 14px 35px; 
            border-radius: 15px; 
            font-weight: bold;
            font-size: 1.1em;
            transition: all 0.3s ease;
            box-shadow: 0 5px 15px rgba(0, 255, 255, 0.3);
        }
        .back-btn:hover { 
            background: linear-gradient(135deg, #0099ff, #00ffff);
            transform: translateY(-3px) scale(1.05);
            box-shadow: 0 10px 25px rgba(0, 255, 255, 0.5);
        }
        .form-group {
            margin-bottom: 20px;
        }
        ::placeholder {
            color: #888;
            opacity: 0.7;
        }
        .checkbox-group {
            display: flex;
            align-items: center;
            gap: 10px;
            margin-top: 10px;
        }
        .checkbox-group input[type="checkbox"] {
            width: auto;
            transform: scale(1.2);
        }
        .typing-options {
            background: rgba(0, 255, 255, 0.1);
            padding: 15px;
            border-radius: 10px;
            margin-top: 10px;
            border: 1px solid #00ffff;
        }
    </style>
</head>
<body>
    <div class="overlay">
        <div class="card">
            <h1>💬 Auto Nhây Messenger</h1>
            {% with messages = get_flashed_messages(with_categories=true) %}
                {% if messages %}
                    {% for cat, msg in messages %}
                        <div class="alert alert-{{cat}}">{{msg}}</div>
                    {% endfor %}
                {% endif %}
            {% endwith %}
            <form method="POST" action="/nhaydz/add_task">
                <div class="form-group">
                    <label>🔐 Cookie Facebook:</label>
                    <textarea name="cookie" placeholder="Nhập cookie Facebook tại đây..." rows="3" required></textarea>
                </div>

                <div class="form-group">
                    <label>👤 UID hoặc ID Box Chat:</label>
                    <input type="text" name="recipient_id" placeholder="VD: 6155xxxx hoặc 7920xxxx" required>
                </div>

                <div class="form-group">
                    <label>⏱ Delay giữa mỗi tin (giây):</label>
                    <input type="number" name="delay" placeholder="VD: 3" min="0.1" step="0.1" required>
                </div>

                <div class="form-group">
                    <label>🎭 Fake Typing:</label>
                    <div class="checkbox-group">
                        <input type="checkbox" id="fake_typing" name="fake_typing" value="1" checked>
                        <label for="fake_typing">Bật hiệu ứng đang gõ chữ trước khi gửi tin</label>
                    </div>
                    
                    <div class="typing-options">
                        <label>⏱ Thời gian fake typing (giây):</label>
                        <input type="number" name="typing_duration" placeholder="VD: 2" min="0.5" max="10" step="0.1" value="2">
                        
                        <label style="margin-top: 10px;">🎯 Kiểu typing:</label>
                        <select name="typing_mode">
                            <option value="random">Ngẫu nhiên (0.5-3 giây)</option>
                            <option value="fixed">Cố định</option>
                            <option value="progressive">Tăng dần theo độ dài tin nhắn</option>
                        </select>
                    </div>
                </div>

                <button type="submit">🚀 Bắt Đầu Nhây</button>
            </form>
        </div>

        <table>
            <tr>
                <th>ID</th>
                <th>User</th>
                <th>Box</th>
                <th>Tin đã gửi</th>
                <th>Delay (s)</th>
                <th>Fake Typing</th>
                <th>Trạng thái</th>
                <th>Hành động</th>
            </tr>
            {% for tid, t in tasks.items() %}
            <tr>
                <td>{{tid}}</td>
                <td>{{t.user_id}}</td>
                <td>{{t.recipient_id}}</td>
                <td>{{t.message_count}}</td>
                <td>{{t.delay}}</td>
                <td>
                    {% if t.fake_typing %}
                        <span style="color: #00ff88;">✅ Bật</span>
                    {% else %}
                        <span style="color: #ff4444;">❌ Tắt</span>
                    {% endif %}
                </td>
                <td>
                    {% if t.running %}
                        <span class="status-running">🟢 Đang chạy</span>
                    {% else %}
                        <span class="status-stopped">🔴 Đã dừng</span>
                    {% endif %}
                </td>
                <td>
                    {% if t.running %}
                        <a href="/nhaydz/stop/{{tid}}"><button class="action-btn btn-stop">🛑 Dừng</button></a>
                    {% else %}
                        <a href="/nhaydz/start/{{tid}}"><button class="action-btn btn-start">▶️ Chạy</button></a>
                    {% endif %}
                    <a href="/nhaydz/delete/{{tid}}"><button class="action-btn btn-delete">🗑️ Xóa</button></a>
                </td>
            </tr>
            {% endfor %}
        </table>

        <!-- 🟢 Nút quay về menu chính -->
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
        self.user_id = self.extract_user_id()
        self.fb_dtsg = self.get_fb_dtsg()
        self.valid = self.user_id is not None and self.fb_dtsg is not None

    def extract_user_id(self):
        match = re.search(r"c_user=(\d+)", self.cookie)
        if not match:
            print("[!] Cookie không hợp lệ (không có c_user)")
            return None
        return match.group(1)

    def get_fb_dtsg(self):
        try:
            headers = {'Cookie': self.cookie, 'User-Agent': 'Mozilla/5.0'}
            res = requests.get('https://mbasic.facebook.com/profile.php', headers=headers)
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

    def send_message(self, recipient_id, message):
        if not self.valid:
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
                'User-Agent': 'python-http',
                'Content-Type': 'application/x-www-form-urlencoded',
            }
            res = requests.post('https://www.facebook.com/messaging/send/', data=data, headers=headers)
            if res.status_code != 200 or 'error' in res.text:
                print(f"[!] Lỗi gửi tới {recipient_id} bởi {self.user_id}: {res.text[:100]}")
                return False
            return True
        except Exception as e:
            print(f"[!] Exception gửi tới {recipient_id} bởi {self.user_id}: {e}")
            return False

    def start_typing(self, recipient_id):
        """Bật hiệu ứng đang gõ chữ"""
        if not self.valid:
            return False
        try:
            data = {
                'typ': '1',
                'thread': recipient_id,
                'to': recipient_id,
                'source': 'mercury-chat',
                '__user': self.user_id,
                '__a': '1',
                'fb_dtsg': self.fb_dtsg
            }
            headers = {
                'Cookie': self.cookie,
                'User-Agent': 'Mozilla/5.0',
                'Content-Type': 'application/x-www-form-urlencoded',
            }
            res = requests.post('https://www.facebook.com/messaging/typ.php', data=data, headers=headers)
            return res.status_code == 200
        except Exception as e:
            print(f"[!] Lỗi khi bật typing: {e}")
            return False

    def stop_typing(self, recipient_id):
        """Tắt hiệu ứng đang gõ chữ"""
        if not self.valid:
            return False
        try:
            data = {
                'typ': '0',
                'thread': recipient_id,
                'to': recipient_id,
                'source': 'mercury-chat',
                '__user': self.user_id,
                '__a': '1',
                'fb_dtsg': self.fb_dtsg
            }
            headers = {
                'Cookie': self.cookie,
                'User-Agent': 'Mozilla/5.0',
                'Content-Type': 'application/x-www-form-urlencoded',
            }
            res = requests.post('https://www.facebook.com/messaging/typ.php', data=data, headers=headers)
            return res.status_code == 200
        except Exception as e:
            print(f"[!] Lỗi khi tắt typing: {e}")
            return False

    def simulate_typing(self, recipient_id, message, typing_duration=2, typing_mode="random"):
        """Mô phỏng hiệu ứng gõ chữ"""
        if typing_mode == "random":
            # Ngẫu nhiên từ 0.5 đến 3 giây
            typing_time = random.uniform(0.5, 3.0)
        elif typing_mode == "progressive":
            # Tính thời gian dựa trên độ dài tin nhắn
            base_time = max(1.0, len(message) * 0.1)  # 0.1 giây mỗi ký tự, tối thiểu 1 giây
            typing_time = min(base_time, 5.0)  # Tối đa 5 giây
        else:  # fixed
            typing_time = typing_duration

        print(f"[⌨️] Fake typing trong {typing_time:.1f}s cho tin nhắn {len(message)} ký tự...")

        # Bật typing
        self.start_typing(recipient_id)
        
        # Chờ trong thời gian typing
        time.sleep(typing_time)
        
        # Tắt typing
        self.stop_typing(recipient_id)
        
        # Thêm delay ngẫu nhiên nhỏ trước khi gửi thật
        time.sleep(random.uniform(0.1, 0.5))

# ====================== TASK ======================
class Task:
    def __init__(self, tid, messenger, recipient_id, messages, delay, 
                 fake_typing=True, typing_duration=2, typing_mode="random",
                 message_count=0, running=True):
        self.tid = tid
        self.messenger = messenger
        self.recipient_id = recipient_id
        self.messages = messages
        self.delay = delay
        self.fake_typing = fake_typing
        self.typing_duration = typing_duration
        self.typing_mode = typing_mode
        self.running = running
        self.message_count = message_count
        if self.running:
            threading.Thread(target=self.run, daemon=True).start()

    def run(self):
        while self.running:
            msg = random.choice(self.messages)
            
            # Fake typing trước khi gửi tin nhắn
            if self.fake_typing:
                self.messenger.simulate_typing(
                    self.recipient_id, 
                    msg, 
                    self.typing_duration, 
                    self.typing_mode
                )
            
            # Gửi tin nhắn thật
            if self.messenger.send_message(self.recipient_id, msg):
                self.message_count += 1
                save_tasks()  # Lưu sau mỗi tin nhắn
            
            time.sleep(self.delay)

    @property
    def user_id(self):
        return self.messenger.user_id

    def to_dict(self):
        """Chuyển task thành dictionary để lưu trữ"""
        return {
            'tid': self.tid,
            'cookie': self.messenger.cookie,
            'recipient_id': self.recipient_id,
            'delay': self.delay,
            'fake_typing': self.fake_typing,
            'typing_duration': self.typing_duration,
            'typing_mode': self.typing_mode,
            'message_count': self.message_count,
            'running': self.running
        }

# ====================== LƯU VÀ KHÔI PHỤC TASKS ======================
def save_tasks():
    """Lưu tasks vào file JSON"""
    try:
        tasks_data = {}
        for tid, task in TASKS.items():
            tasks_data[tid] = task.to_dict()
        
        with open(TASKS_FILE, 'w', encoding='utf-8') as f:
            json.dump(tasks_data, f, ensure_ascii=False, indent=2)
        print(f"[+] Đã lưu {len(tasks_data)} tasks vào {TASKS_FILE}")
    except Exception as e:
        print(f"[!] Lỗi khi lưu tasks: {e}")

def load_tasks():
    """Khôi phục tasks từ file JSON khi khởi động"""
    global TASK_ID_COUNTER, TASKS
    
    if not os.path.exists(TASKS_FILE):
        print(f"[!] Không tìm thấy file {TASKS_FILE}, bỏ qua khôi phục tasks")
        return
    
    try:
        with open(TASKS_FILE, 'r', encoding='utf-8') as f:
            tasks_data = json.load(f)
        
        if not os.path.exists(NHAY_FILE):
            print(f"[!] Không tìm thấy file '{NHAY_FILE}'!")
            return
            
        with open(NHAY_FILE, 'r', encoding='utf-8') as f:
            messages = [line.strip() for line in f if line.strip()]
        
        if not messages:
            print(f"[!] File '{NHAY_FILE}' trống!")
            return
        
        restored_count = 0
        for tid, task_data in tasks_data.items():
            try:
                messenger = Messenger(task_data['cookie'])
                if not messenger.valid:
                    print(f"[!] Không thể khôi phục task {tid}: Cookie không hợp lệ")
                    continue
                
                task = Task(
                    tid=tid,
                    messenger=messenger,
                    recipient_id=task_data['recipient_id'],
                    messages=messages,
                    delay=task_data['delay'],
                    fake_typing=task_data.get('fake_typing', True),
                    typing_duration=task_data.get('typing_duration', 2),
                    typing_mode=task_data.get('typing_mode', 'random'),
                    message_count=task_data['message_count'],
                    running=task_data['running']
                )
                
                TASKS[tid] = task
                restored_count += 1
                
                # Cập nhật TASK_ID_COUNTER
                tid_num = int(tid)
                if tid_num >= TASK_ID_COUNTER:
                    TASK_ID_COUNTER = tid_num + 1
                    
            except Exception as e:
                print(f"[!] Lỗi khi khôi phục task {tid}: {e}")
        
        print(f"[+] Đã khôi phục {restored_count}/{len(tasks_data)} tasks từ {TASKS_FILE}")
        
    except Exception as e:
        print(f"[!] Lỗi khi đọc file tasks: {e}")

# ====================== ROUTES ======================
@nhaydz_bp.route('/')
def index():
    return render_template_string(HTML, tasks=TASKS)

@nhaydz_bp.route('/add_task', methods=['POST'])
def add_task():
    global TASK_ID_COUNTER
    cookie = request.form['cookie'].strip()
    recipient_id = request.form['recipient_id'].strip()
    delay = float(request.form['delay'])
    fake_typing = 'fake_typing' in request.form
    typing_duration = float(request.form.get('typing_duration', 2))
    typing_mode = request.form.get('typing_mode', 'random')

    if not os.path.exists(NHAY_FILE):
        flash(("error", f"❌ Không tìm thấy file '{NHAY_FILE}'!"))
        return redirect(url_for("nhaydz.index"))

    with open(NHAY_FILE, 'r', encoding='utf-8') as f:
        messages = [line.strip() for line in f if line.strip()]
    if not messages:
        flash(("error", f"❌ File '{NHAY_FILE}' trống!"))
        return redirect(url_for("nhaydz.index"))

    messenger = Messenger(cookie)
    if not messenger.valid:
        flash(("error", "❌ Cookie không hợp lệ hoặc đã hết hạn!"))
        return redirect(url_for("nhaydz.index"))

    tid = str(TASK_ID_COUNTER)
    TASK_ID_COUNTER += 1
    TASKS[tid] = Task(
        tid=tid, 
        messenger=messenger, 
        recipient_id=recipient_id, 
        messages=messages, 
        delay=delay,
        fake_typing=fake_typing,
        typing_duration=typing_duration,
        typing_mode=typing_mode
    )
    
    # Lưu tasks sau khi thêm mới
    save_tasks()
    
    typing_status = "có fake typing" if fake_typing else "không fake typing"
    flash(("success", f"✅ Đã bắt đầu nhây UID {recipient_id} (delay {delay}s, {len(messages)} câu, {typing_status})"))
    return redirect(url_for("nhaydz.index"))

@nhaydz_bp.route('/stop/<tid>')
def stop_task(tid):
    if tid in TASKS:
        TASKS[tid].running = False
        save_tasks()  # Lưu sau khi dừng
        flash(("error", f"🛑 Dừng task #{tid}"))
    return redirect(url_for("nhaydz.index"))

@nhaydz_bp.route('/start/<tid>')
def start_task(tid):
    if tid in TASKS:
        t = TASKS[tid]
        if not t.running:
            t.running = True
            threading.Thread(target=t.run, daemon=True).start()
            save_tasks()  # Lưu sau khi khởi động lại
            flash(("success", f"▶️ Tiếp tục task #{tid}"))
    return redirect(url_for("nhaydz.index"))

@nhaydz_bp.route('/delete/<tid>')
def delete_task(tid):
    if tid in TASKS:
        TASKS[tid].running = False
        del TASKS[tid]
        save_tasks()  # Lưu sau khi xóa
        flash(("error", f"🗑️ Đã xóa task #{tid}"))
    return redirect(url_for("nhaydz.index"))

# ====================== KHỞI TẠO VÀ DỌN DẸP ======================
def cleanup():
    """Dọn dẹp khi ứng dụng tắt"""
    print("[!] Đang lưu tasks trước khi tắt...")
    save_tasks()

# Đăng ký hàm cleanup để chạy khi ứng dụng tắt
atexit.register(cleanup)

# Khôi phục tasks khi module được import
load_tasks()
