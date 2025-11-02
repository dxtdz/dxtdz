from flask import Blueprint, render_template_string, request, jsonify, session, redirect
import requests
import random
import time
import threading
import os
import json
from datetime import datetime

dis3_bp = Blueprint('dis3', __name__)

# Biến toàn cục để quản lý task
dis3_tasks = {}
task_id_counter = 1
TASK_SAVE_FILE = "dis3_tasks.json"

def get_keys_and_functions():
    """Hàm import động từ main để tránh lỗi circular import"""
    try:
        from main import KEYS, get_remaining_tasks, use_task
        return KEYS, get_remaining_tasks, use_task
    except ImportError:
        # Fallback nếu không import được
        return {}, lambda *args: 0, lambda *args: 0

def load_file_lines(filename):
    """Hàm đọc file và trả về danh sách các dòng (bỏ qua dòng trống)"""
    try:
        if os.path.exists(filename):
            with open(filename, 'r', encoding='utf-8') as f:
                lines = [line.strip() for line in f.readlines() if line.strip()]
            return lines
        else:
            print(f"⚠️ File {filename} không tồn tại")
            return []
    except Exception as e:
        print(f"❌ Lỗi đọc file {filename}: {e}")
        return []

def save_tasks_to_file():
    """Lưu tasks vào file JSON"""
    try:
        # Chỉ lưu thông tin cần thiết, không lưu thread
        tasks_to_save = {}
        for task_id, task in dis3_tasks.items():
            tasks_to_save[task_id] = {
                'token': task['token'],
                'channel_id': task['channel_id'],
                'delay': task['delay'],
                'questions_count': task['questions_count'],
                'answers_count': task['answers_count'],
                'status': task['status'],
                'poll_count': task['poll_count'],
                'created_at': task.get('created_at', datetime.now().isoformat())
            }
        
        with open(TASK_SAVE_FILE, 'w', encoding='utf-8') as f:
            json.dump(tasks_to_save, f, indent=2, ensure_ascii=False)
        
        print(f"💾 Đã lưu {len(tasks_to_save)} tasks vào file")
    except Exception as e:
        print(f"❌ Lỗi lưu tasks: {e}")

def load_tasks_from_file():
    """Tải tasks từ file JSON và khởi động lại các task đang chạy"""
    global dis3_tasks, task_id_counter
    
    try:
        if os.path.exists(TASK_SAVE_FILE):
            with open(TASK_SAVE_FILE, 'r', encoding='utf-8') as f:
                saved_tasks = json.load(f)
            
            print(f"📂 Đang khôi phục {len(saved_tasks)} tasks từ file...")
            
            for task_id, task_data in saved_tasks.items():
                # Cập nhật task_id_counter
                task_id_int = int(task_id)
                if task_id_int >= task_id_counter:
                    task_id_counter = task_id_int + 1
                
                # Khôi phục task
                dis3_tasks[task_id] = {
                    'token': task_data['token'],
                    'channel_id': task_data['channel_id'],
                    'delay': task_data['delay'],
                    'questions_count': task_data['questions_count'],
                    'answers_count': task_data['answers_count'],
                    'status': 'stopped',  # Tạm dừng, sẽ start lại nếu cần
                    'poll_count': task_data['poll_count'],
                    'created_at': task_data.get('created_at', datetime.now().isoformat()),
                    'thread': None
                }
                
                # Tự động start lại các task đang chạy trước đó
                if task_data.get('status') == 'running':
                    print(f"🔄 Tự động khởi động lại task {task_id}...")
                    start_task_internal(task_id)
            
            print("✅ Khôi phục tasks hoàn tất!")
        else:
            print("ℹ️ Không tìm thấy file lưu tasks")
    except Exception as e:
        print(f"❌ Lỗi tải tasks: {e}")

def start_task_internal(task_id):
    """Hàm nội bộ để start task"""
    if task_id not in dis3_tasks:
        return False
    
    task = dis3_tasks[task_id]
    
    if task['status'] == 'running':
        return True
    
    task['status'] = 'running'
    thread = threading.Thread(
        target=spam_poll_thread,
        args=(task_id, task['token'], task['channel_id'], task['delay']),
        daemon=True
    )
    task['thread'] = thread
    thread.start()
    
    # Lưu ngay sau khi start
    save_tasks_to_file()
    
    return True

def update_task_counter():
    """Cập nhật task_id_counter từ các task hiện có"""
    global task_id_counter
    if dis3_tasks:
        max_id = max(int(task_id) for task_id in dis3_tasks.keys())
        task_id_counter = max_id + 1

# Tải tasks khi module được import
load_tasks_from_file()

# HTML template (giữ nguyên như cũ)
DIS3_HTML = """
<!DOCTYPE html>
<html lang="vi">
<head>
    <meta charset="UTF-8">
    <title>Discord - Auto Nhây Poll</title>
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
        textarea, input {
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
        textarea:focus, input:focus {
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
        .file-info {
            background: rgba(0, 255, 255, 0.1);
            padding: 15px;
            border-radius: 10px;
            margin: 15px 0;
            border: 1px solid #00ffff;
        }
        .file-info div {
            margin: 5px 0;
            color: #00ff88;
        }
        ::placeholder {
            color: #888;
            opacity: 0.7;
        }
        .task-info {
            background: rgba(0, 255, 136, 0.1);
            padding: 15px;
            border-radius: 10px;
            margin: 15px 0;
            border: 1px solid #00ff88;
        }
    </style>
</head>
<body>
    <div class="overlay">
        <div class="card">
            <h1>📊 Auto Nhây Poll Discord</h1>
            
            <div class="task-info">
                <h3 style="color: #00ff88; margin-top: 0;">🔄 Tính năng mới:</h3>
                <div>✅ Tasks được lưu tự động - Web khởi động lại vẫn chạy tiếp</div>
                <div>💾 Dữ liệu lưu trong file: <code>dis3_tasks.json</code></div>
            </div>
            
            <div class="file-info">
                <h3 style="color: #00ffff; margin-top: 0;">📁 Thông tin File:</h3>
                <div>📝 ch.txt: <span id="questionsCount">0</span> câu hỏi</div>
                <div>📄 tl.txt: <span id="answersCount">0</span> câu trả lời</div>
                <div>🎯 Mỗi poll sẽ chọn: <span id="answersSelectCount">0</span> câu trả lời</div>
            </div>

            <form id="taskForm">
                <div class="form-group">
                    <label>🔑 Discord Token:</label>
                    <input type="text" id="token" name="token" placeholder="Nhập Discord token tại đây..." required>
                </div>

                <div class="form-group">
                    <label>📱 Channel ID:</label>
                    <input type="text" id="channel_id" name="channel_id" placeholder="Nhập Channel ID..." required>
                </div>

                <div class="form-group">
                    <label>⏱ Delay giữa mỗi poll (giây):</label>
                    <input type="number" id="delay" name="delay" placeholder="VD: 10" min="5" max="3600" value="10" required>
                </div>

                <button type="submit">🚀 Bắt Đầu Nhây Poll</button>
            </form>
        </div>

        <table>
            <tr>
                <th>ID</th>
                <th>Channel</th>
                <th>Câu hỏi</th>
                <th>Câu trả lời</th>
                <th>Delay (s)</th>
                <th>Poll đã gửi</th>
                <th>Trạng thái</th>
                <th>Hành động</th>
            </tr>
            {% for task_id, task in tasks.items() %}
            <tr>
                <td>{{ task_id }}</td>
                <td>{{ task.channel_id }}</td>
                <td>{{ task.questions_count }}</td>
                <td>{{ task.answers_count }}</td>
                <td>{{ task.delay }}</td>
                <td id="count-{{ task_id }}">{{ task.poll_count }}</td>
                <td>
                    {% if task.status == "running" %}
                        <span class="status-running">🟢 Đang chạy</span>
                    {% else %}
                        <span class="status-stopped">🔴 Đã dừng</span>
                    {% endif %}
                </td>
                <td>
                    {% if task.status == "running" %}
                        <button class="action-btn btn-stop" onclick="stopTask('{{ task_id }}')">🛑 Dừng</button>
                    {% else %}
                        <button class="action-btn btn-start" onclick="startTask('{{ task_id }}')">▶️ Chạy</button>
                    {% endif %}
                    <button class="action-btn btn-delete" onclick="deleteTask('{{ task_id }}')">🗑️ Xóa</button>
                </td>
            </tr>
            {% endfor %}
        </table>

        <!-- 🟢 Nút quay về menu chính -->
        <div style="text-align:center;">
            <a href="/menu" class="back-btn">⬅️ Quay về Menu Chính</a>
        </div>
    </div>

    <script>
        let remainingTasks = {{ remaining_tasks }};

        // Kiểm tra file và cập nhật thông tin
        function checkFiles() {
            fetch('/dis3/check_files')
                .then(response => response.json())
                .then(result => {
                    document.getElementById('questionsCount').textContent = result.questions_count;
                    document.getElementById('answersCount').textContent = result.answers_count;
                    document.getElementById('answersSelectCount').textContent = result.answers_select_count;
                    
                    // Hiển thị cảnh báo nếu file không đủ
                    if (result.questions_count === 0) {
                        alert('❌ File ch.txt trống hoặc không tồn tại!');
                    }
                    if (result.answers_count < 2) {
                        alert('❌ File tl.txt cần ít nhất 2 câu trả lời!');
                    }
                });
        }

        // Tự động kiểm tra file khi trang được load
        document.addEventListener('DOMContentLoaded', function() {
            checkFiles();
        });

        document.getElementById('taskForm').addEventListener('submit', function(e) {
            e.preventDefault();
            
            if (remainingTasks <= 0) {
                alert('❌ Bạn đã hết số task cho tính năng này!');
                return;
            }

            const formData = new FormData(this);
            const data = {
                token: formData.get('token'),
                channel_id: formData.get('channel_id'),
                delay: parseInt(formData.get('delay'))
            };

            fetch('/dis3/add_task', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify(data)
            })
            .then(response => response.json())
            .then(result => {
                if (result.success) {
                    alert('✅ Task created and started successfully!');
                    remainingTasks--;
                    location.reload();
                } else {
                    alert('❌ Error: ' + result.message);
                }
            })
            .catch(error => {
                alert('❌ Network error: ' + error);
            });
        });

        function startTask(taskId) {
            fetch('/dis3/start_task/' + taskId)
                .then(response => response.json())
                .then(result => {
                    if (result.success) {
                        alert('✅ Task started!');
                        location.reload();
                    } else {
                        alert('❌ Error: ' + result.message);
                    }
                });
        }

        function stopTask(taskId) {
            fetch('/dis3/stop_task/' + taskId)
                .then(response => response.json())
                .then(result => {
                    if (result.success) {
                        alert('🛑 Task stopped!');
                        location.reload();
                    } else {
                        alert('❌ Error: ' + result.message);
                    }
                });
        }

        function deleteTask(taskId) {
            if (confirm('🗑️ Xóa task này?')) {
                fetch('/dis3/delete_task/' + taskId)
                    .then(response => response.json())
                    .then(result => {
                        if (result.success) {
                            alert('✅ Task deleted!');
                            location.reload();
                        } else {
                            alert('❌ Error: ' + result.message);
                        }
                    });
            }
        }

        // Auto refresh task status
        setInterval(() => {
            fetch('/dis3/get_tasks')
                .then(response => response.json())
                .then(tasks => {
                    for (const [taskId, task] of Object.entries(tasks)) {
                        const countElement = document.getElementById('count-' + taskId);
                        if (countElement) {
                            countElement.textContent = task.poll_count || 0;
                        }
                    }
                });
        }, 5000);
    </script>
</body>
</html>
"""

def spam_poll_thread(task_id, token, channel_id, delay):
    """Hàm chạy trong thread để spam poll - Tự động đọc từ file"""
    headers = {
        "Authorization": token,
        "Content-Type": "application/json",
        "User-Agent": "Mozilla/5.0"
    }

    # Đọc file mỗi khi bắt đầu task
    questions = load_file_lines('ch.txt')
    answers = load_file_lines('tl.txt')

    if not questions:
        print(f"❌ Task {task_id}: File ch.txt trống hoặc không tồn tại")
        dis3_tasks[task_id]['status'] = 'stopped'
        save_tasks_to_file()
        return
    if not answers:
        print(f"❌ Task {task_id}: File tl.txt trống hoặc không tồn tại")
        dis3_tasks[task_id]['status'] = 'stopped'
        save_tasks_to_file()
        return

    print(f"🚀 Task {task_id} started: {len(questions)} câu hỏi, {len(answers)} câu trả lời")

    try:
        while task_id in dis3_tasks and dis3_tasks[task_id]['status'] == 'running':
            # Chọn ngẫu nhiên 1 câu hỏi
            selected_question = random.choice(questions)
            
            # Chọn ngẫu nhiên 10 câu trả lời (hoặc ít hơn nếu không đủ 10)
            num_answers_to_select = min(10, len(answers))
            selected_answers = random.sample(answers, num_answers_to_select)

            # Fake typing 1-3 giây
            typing_time = random.uniform(1.5, 3.5)
            try:
                requests.post(f"https://discord.com/api/v9/channels/{channel_id}/typing", 
                            headers=headers, timeout=10)
                print(f"💬 Task {task_id}: Giả lập đang gõ ({typing_time:.1f}s)...")
            except Exception as e:
                print(f"⚠️ Task {task_id}: Lỗi typing - {e}")

            time.sleep(typing_time)

            # Gửi poll
            payload = {
                "poll": {
                    "question": {"text": selected_question},
                    "answers": [{"poll_media": {"text": answer, "emoji": None}} for answer in selected_answers],
                    "duration": 300,
                    "allow_multiselect": False,
                    "layout_type": 1
                }
            }

            try:
                r = requests.post(f"https://discord.com/api/v9/channels/{channel_id}/messages",
                                headers=headers, json=payload, timeout=30)
                if r.status_code in [200, 201]:
                    dis3_tasks[task_id]['poll_count'] += 1
                    print(f"[✅] Task {task_id}: Poll #{dis3_tasks[task_id]['poll_count']}")
                    print(f"    Câu hỏi: {selected_question}")
                    print(f"    Câu trả lời: {selected_answers}")
                    
                    # Lưu sau mỗi poll thành công
                    save_tasks_to_file()
                else:
                    print(f"[❌ {r.status_code}] Task {task_id}: {r.text}")
            except Exception as e:
                print(f"[❌] Task {task_id}: Lỗi gửi poll - {e}")

            # Chờ delay
            print(f"⏳ Task {task_id}: Chờ {delay} giây...")
            for i in range(int(delay)):
                if task_id not in dis3_tasks or dis3_tasks[task_id]['status'] != 'running':
                    break
                time.sleep(1)
                
    except Exception as e:
        print(f"[❌] Task {task_id}: Lỗi thread - {e}")
    finally:
        if task_id in dis3_tasks:
            dis3_tasks[task_id]['status'] = 'stopped'
            save_tasks_to_file()  # Lưu khi dừng task
            print(f"🛑 Task {task_id} stopped")

@dis3_bp.route('/')
def dis3_page():
    if 'key' not in session:
        return redirect('/')
    
    KEYS, get_remaining_tasks, _ = get_keys_and_functions()
    
    key = session['key']
    if key not in KEYS:
        session.pop('key', None)
        return redirect('/')
    
    expire, permissions, task_limits = KEYS[key]
    
    if 'dis3' not in permissions and 'admin' not in permissions:
        return "🚫 Không có quyền truy cập tính năng này!", 403
    
    remaining_tasks = get_remaining_tasks(key, 'dis3')
    running_tasks = sum(1 for task in dis3_tasks.values() if task['status'] == 'running')
    
    return render_template_string(DIS3_HTML, 
                                tasks=dis3_tasks,
                                remaining_tasks=remaining_tasks,
                                running_tasks=running_tasks,
                                total_tasks=len(dis3_tasks))

@dis3_bp.route('/check_files')
def check_files():
    """API để kiểm tra file"""
    questions = load_file_lines('ch.txt')
    answers = load_file_lines('tl.txt')
    
    return jsonify({
        "questions_count": len(questions),
        "answers_count": len(answers),
        "answers_select_count": min(10, len(answers))
    })

@dis3_bp.route('/add_task', methods=['POST'])
def add_task():
    if 'key' not in session:
        return jsonify({"success": False, "message": "Chưa đăng nhập"}), 401
    
    key = session['key']
    KEYS, get_remaining_tasks, use_task = get_keys_and_functions()
    
    if key not in KEYS:
        return jsonify({"success": False, "message": "Key không hợp lệ"}), 403
    
    remaining = get_remaining_tasks(key, 'dis3')
    if remaining <= 0:
        return jsonify({"success": False, "message": "Đã hết số task cho tính năng này!"}), 403
    
    data = request.get_json()
    
    if not data.get('token') or not data.get('channel_id'):
        return jsonify({"success": False, "message": "Token và Channel ID là bắt buộc!"}), 400
    
    # Đọc file để kiểm tra
    questions = load_file_lines('ch.txt')
    answers = load_file_lines('tl.txt')
    
    if len(questions) == 0:
        return jsonify({"success": False, "message": "File ch.txt trống hoặc không tồn tại!"}), 400
    
    if len(answers) < 2:
        return jsonify({"success": False, "message": "File tl.txt cần ít nhất 2 câu trả lời!"}), 400
    
    global task_id_counter
    task_id = str(task_id_counter)
    task_id_counter += 1
    
    # Tạo task và tự động chạy luôn
    dis3_tasks[task_id] = {
        'token': data['token'],
        'channel_id': data['channel_id'],
        'delay': data['delay'],
        'questions_count': len(questions),
        'answers_count': len(answers),
        'status': 'running',  # Tự động chạy luôn
        'poll_count': 0,
        'thread': None,
        'created_at': datetime.now().isoformat()
    }
    
    # Start task ngay lập tức
    thread = threading.Thread(
        target=spam_poll_thread,
        args=(task_id, data['token'], data['channel_id'], data['delay']),
        daemon=True
    )
    dis3_tasks[task_id]['thread'] = thread
    thread.start()
    
    # Lưu task vào file
    save_tasks_to_file()
    
    # Sử dụng 1 task
    use_task(key, 'dis3')
    
    return jsonify({
        "success": True, 
        "message": "Task created and started successfully!",
        "task_id": task_id
    })

@dis3_bp.route('/start_task/<task_id>')
def start_task_route(task_id):
    if task_id not in dis3_tasks:
        return jsonify({"success": False, "message": "Task không tồn tại!"}), 404
    
    success = start_task_internal(task_id)
    
    if success:
        return jsonify({"success": True, "message": "Task started!"})
    else:
        return jsonify({"success": False, "message": "Không thể start task!"})

@dis3_bp.route('/stop_task/<task_id>')
def stop_task(task_id):
    if task_id not in dis3_tasks:
        return jsonify({"success": False, "message": "Task không tồn tại!"}), 404
    
    dis3_tasks[task_id]['status'] = 'stopped'
    save_tasks_to_file()  # Lưu khi dừng task
    
    return jsonify({"success": True, "message": "Task stopped!"})

@dis3_bp.route('/delete_task/<task_id>')
def delete_task(task_id):
    if task_id not in dis3_tasks:
        return jsonify({"success": False, "message": "Task không tồn tại!"}), 404
    
    dis3_tasks[task_id]['status'] = 'stopped'
    del dis3_tasks[task_id]
    save_tasks_to_file()  # Lưu khi xóa task
    
    return jsonify({"success": True, "message": "Task deleted!"})

@dis3_bp.route('/get_tasks')
def get_tasks():
    return jsonify(dis3_tasks)

@dis3_bp.route('/save_tasks')
def save_tasks():
    """API để manual save tasks (cho testing)"""
    save_tasks_to_file()
    return jsonify({"success": True, "message": f"Đã lưu {len(dis3_tasks)} tasks"})
