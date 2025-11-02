from flask import Blueprint, render_template_string, request, jsonify, session, redirect
import requests
import random
import time
import threading
import os
import json
import atexit

dis2_bp = Blueprint('dis2', __name__)

# File để lưu tasks
TASKS_FILE = "dis2_tasks.json"

# Biến toàn cục để quản lý task
dis2_tasks = {}
task_id_counter = 1

# ======= HỆ THỐNG LƯU VÀ TẢI TASKS =======
def save_tasks():
    """Lưu tasks vào file"""
    try:
        tasks_to_save = {}
        for task_id, task in dis2_tasks.items():
            tasks_to_save[task_id] = {
                'token': task['token'],
                'channel_id': task['channel_id'],
                'user_ids': task['user_ids'],
                'delay': task['delay'],
                'fake_typing': task['fake_typing'],
                'messages_count': task['messages_count'],
                'users_count': task['users_count'],
                'status': task['status'],
                'message_count': task['message_count']
            }
        
        with open(TASKS_FILE, 'w', encoding='utf-8') as f:
            json.dump(tasks_to_save, f, ensure_ascii=False, indent=2)
        print("✅ Đã lưu dis2 tasks")
    except Exception as e:
        print(f"❌ Lỗi lưu dis2 tasks: {e}")

def load_tasks():
    """Tải tasks từ file"""
    global dis2_tasks, task_id_counter
    try:
        if os.path.exists(TASKS_FILE):
            with open(TASKS_FILE, 'r', encoding='utf-8') as f:
                loaded_tasks = json.load(f)
            
            dis2_tasks = loaded_tasks
            
            # Tìm task_id_counter lớn nhất
            if dis2_tasks:
                task_id_counter = max(int(k) for k in dis2_tasks.keys()) + 1
            
            print(f"✅ Đã tải {len(dis2_tasks)} dis2 tasks từ file")
            
            # Tự động start lại các task đang running
            auto_restart_tasks()
        else:
            print("ℹ️ Chưa có file dis2 tasks")
    except Exception as e:
        print(f"❌ Lỗi tải dis2 tasks: {e}")

def auto_restart_tasks():
    """Tự động start lại các task đang running"""
    for task_id, task in dis2_tasks.items():
        if task.get('status') == 'running':
            print(f"🔄 Tự động restart dis2 task #{task_id}")
            start_task(task_id)

# Đăng ký lưu tasks khi thoát
atexit.register(save_tasks)

# Tải tasks khi import module
load_tasks()

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

def spam_tagged_task(task_id, token, channel_id, messages, uid_list, delay, fake_typing):
    """Hàm chạy trong thread để spam tag"""
    url = f"https://discord.com/api/v9/channels/{channel_id}/messages"
    headers = {"Authorization": token, "Content-Type": "application/json", "User-Agent": "Mozilla/5.0"}
    count = dis2_tasks[task_id].get('message_count', 0)
    
    try:
        while dis2_tasks[task_id]['status'] == 'running':
            # Chọn ngẫu nhiên tin nhắn và user ID
            selected_message = random.choice(messages)
            selected_uid = random.choice(uid_list)
            
            # Tạo nội dung tin nhắn với tag
            message_content = f"<@{selected_uid}> {selected_message}"
            
            # Fake typing nếu được bật
            if fake_typing:
                typing_time = random.uniform(1.5, 3.5)
                try:
                    requests.post(f"https://discord.com/api/v9/channels/{channel_id}/typing", 
                                headers=headers, timeout=10)
                    print(f"💬 Task {task_id}: Giả lập đang gõ ({typing_time:.1f}s)...")
                    time.sleep(typing_time)
                except Exception as e:
                    print(f"⚠️ Task {task_id}: Lỗi typing - {e}")
            
            # Gửi tin nhắn
            payload = {
                "content": message_content,
                "tts": False
            }
            
            try:
                r = requests.post(url, headers=headers, json=payload, timeout=30)
                if r.status_code in [200, 201]:
                    count += 1
                    dis2_tasks[task_id]['message_count'] = count
                    print(f"[✅] Task {task_id}: Message #{count}")
                    print(f"    Tag: <@{selected_uid}>")
                    print(f"    Nội dung: {selected_message}")
                    
                    # Lưu task sau mỗi tin nhắn thành công
                    save_tasks()
                    
                else:
                    print(f"[❌ {r.status_code}] Task {task_id}: {r.text}")
            except Exception as e:
                print(f"[❌] Task {task_id}: Lỗi gửi tin nhắn - {e}")
            
            # Chờ delay
            print(f"⏳ Task {task_id}: Chờ {delay} giây...")
            for i in range(int(delay)):
                if dis2_tasks[task_id]['status'] != 'running':
                    break
                time.sleep(1)
                
    except Exception as e:
        print(f"[❌] Task {task_id}: Lỗi thread - {e}")
    finally:
        if task_id in dis2_tasks:
            dis2_tasks[task_id]['status'] = 'stopped'
            save_tasks()  # Lưu trạng thái khi dừng
            print(f"🛑 Task {task_id} stopped")

# HTML template CŨ - GIỮ NGUYÊN
DIS2_HTML = '''
<!DOCTYPE html>
<html lang="vi">
<head>
    <meta charset="UTF-8">
    <title>Discord - Spam File Content với Fake Typing</title>
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
            color: #5865f2;
            text-align: center;
            margin-bottom: 20px;
            font-size: 2rem;
            text-shadow: 0 0 10px rgba(88, 101, 242, 0.5);
        }
        
        label {
            color: #58a6ff;
            display: block;
            margin-top: 15px;
            font-weight: 600;
        }
        
        textarea, input {
            width: 100%;
            padding: 12px;
            border-radius: 10px;
            border: 1px solid #30363d;
            background: rgba(13, 17, 23, 0.7);
            color: white;
            font-size: 14px;
            transition: all 0.3s ease;
        }
        
        textarea:focus, input:focus {
            outline: none;
            border-color: #58a6ff;
            box-shadow: 0 0 0 2px rgba(88, 166, 255, 0.2);
        }
        
        button {
            background: linear-gradient(135deg, #5865f2, #4752c4);
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
            box-shadow: 0 4px 15px rgba(88, 101, 242, 0.3);
        }
        
        button:hover {
            background: linear-gradient(135deg, #4752c4, #3c45a5);
            transform: translateY(-2px);
            box-shadow: 0 6px 20px rgba(88, 101, 242, 0.4);
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
            background: linear-gradient(135deg, #3fb950, #2ea043);
            box-shadow: 0 3px 10px rgba(63, 185, 80, 0.3);
        }
        
        .btn-start:hover {
            background: linear-gradient(135deg, #2ea043, #238636);
            transform: translateY(-2px);
            box-shadow: 0 5px 15px rgba(46, 160, 67, 0.4);
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
            border: 2px dashed #5865f2;
            padding: 20px;
            text-align: center;
            border-radius: 10px;
            cursor: pointer;
            transition: all 0.3s ease;
            margin-bottom: 15px;
        }
        
        .file-upload:hover {
            background: rgba(88, 101, 242, 0.1);
        }
        
        .file-upload input {
            display: none;
        }
        
        .file-name {
            margin-top: 10px;
            color: #58a6ff;
            font-weight: bold;
        }
        
        .file-preview {
            max-height: 150px;
            overflow-y: auto;
            background: rgba(0, 0, 0, 0.3);
            border-radius: 8px;
            padding: 10px;
            margin-top: 10px;
            font-family: monospace;
            font-size: 12px;
            white-space: pre-wrap;
        }
        
        .typing-indicator {
            display: flex;
            align-items: center;
            margin-top: 10px;
            color: #58a6ff;
            font-style: italic;
        }
        
        .typing-dots {
            display: flex;
            margin-left: 5px;
        }
        
        .typing-dot {
            width: 6px;
            height: 6px;
            background-color: #58a6ff;
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
        
        @keyframes pulse {
            0% {
                box-shadow: 0 0 0 0 rgba(88, 101, 242, 0.7);
            }
            70% {
                box-shadow: 0 0 0 10px rgba(88, 101, 242, 0);
            }
            100% {
                box-shadow: 0 0 0 0 rgba(88, 101, 242, 0);
            }
        }
        
        .user-ids-input {
            min-height: 120px;
            resize: vertical;
        }
        
        .info-box {
            background: rgba(88, 166, 255, 0.1);
            padding: 15px;
            border-radius: 10px;
            margin: 15px 0;
            border: 1px solid rgba(88, 166, 255, 0.3);
        }
        
        .file-status {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-top: 10px;
        }
        
        .file-count {
            color: #3fb950;
            font-weight: bold;
        }
    </style>
</head>
<body>
    <div class="card">
        <h1>📁 NHÂY TAG DISCORD</h1>
        
        <div class="info-box">
            <strong>📝 Hướng dẫn sử dụng:</strong>
            <ul style="margin: 10px 0; padding-left: 20px;">
                <li>File <strong>nhay.txt</strong> chứa danh sách tin nhắn (mỗi dòng 1 tin)</li>
                <li>User IDs: Mỗi dòng 1 ID user Discord để tag</li>
                <li>Tin nhắn và user sẽ được chọn ngẫu nhiên để spam</li>
            </ul>
        </div>
        
        {% with messages = get_flashed_messages(with_categories=true) %}
            {% if messages %}
                {% for cat, msg in messages %}
                    <div class="alert alert-{{cat}}">{{msg}}</div>
                {% endfor %}
            {% endif %}
        {% endwith %}
        
        <form id="taskForm">
            <label>🔑 Token Discord:</label>
            <input type="password" id="token" name="token" placeholder="Nhập token Discord..." required>

            <label>📱 Channel ID:</label>
            <input type="text" id="channel_id" name="channel_id" placeholder="Nhập Channel ID..." required>

            <label>👥 User IDs (mỗi dòng 1 ID):</label>
            <textarea class="user-ids-input" id="user_ids" name="user_ids" placeholder="123456789012345678&#10;987654321098765432&#10;112233445566778899" required></textarea>

            <div class="file-status">
                <span>📁 File nhay.txt:</span>
                <span class="file-count" id="fileMessageCount">Đang tải...</span>
            </div>

            <div id="filePreviewContainer">
                <label>Xem trước tin nhắn từ nhay.txt:</label>
                <div class="file-preview" id="filePreview">Đang tải nội dung file...</div>
            </div>

            <label>⏱ Delay giữa mỗi lần gửi (giây):</label>
            <input type="number" id="delay" name="delay" value="5" min="1" step="0.1" required>

            <label>🎭 Fake typing:</label>
<div style="display: flex; gap: 10px; margin-top: 10px; background: rgba(13, 17, 23, 0.5); padding: 8px; border-radius: 12px;">
    <button type="button" id="fakeTypingOn" class="typing-toggle-btn active" onclick="toggleFakeTyping(true)">
        <span style="font-size: 16px;">🎯</span>
        <span style="font-weight: 600;">Bật</span>
    </button>
    <button type="button" id="fakeTypingOff" class="typing-toggle-btn" onclick="toggleFakeTyping(false)">
        <span style="font-size: 16px;">⚡</span>
        <span style="font-weight: 600;">Tắt</span>
    </button>
</div>
<input type="hidden" id="fake_typing" name="fake_typing" value="true">

<style>
.typing-toggle-btn {
    flex: 1;
    padding: 12px 15px;
    border: none;
    border-radius: 8px;
    background: transparent;
    color: #8b949e;
    font-size: 14px;
    cursor: pointer;
    transition: all 0.3s ease;
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 8px;
}

.typing-toggle-btn:hover {
    background: rgba(88, 166, 255, 0.1);
    transform: translateY(-1px);
}

.typing-toggle-btn.active {
    background: linear-gradient(135deg, #5865f2, #4752c4);
    color: white;
    box-shadow: 0 4px 15px rgba(88, 101, 242, 0.3);
}

.typing-toggle-btn:not(.active) {
    background: rgba(110, 118, 129, 0.3);
    color: white;
}
</style>

<script>
function toggleFakeTyping(isOn) {
    const btnOn = document.getElementById('fakeTypingOn');
    const btnOff = document.getElementById('fakeTypingOff');
    const hiddenInput = document.getElementById('fake_typing');
    
    if (isOn) {
        btnOn.classList.add('active');
        btnOff.classList.remove('active');
        hiddenInput.value = 'true';
    } else {
        btnOn.classList.remove('active');
        btnOff.classList.add('active');
        hiddenInput.value = 'false';
    }
}
</script>

            <button type="submit" class="pulse">🚀 Bắt đầu nhây tag</button>
        </form>
    </div>

    <table>
        <tr>
            <th>ID Task</th>
            <th>Channel</th>
            <th>Số User</th>
            <th>Số Tin Nhắn</th>
            <th>Đã gửi</th>
            <th>Delay</th>
            <th>Fake Typing</th>
            <th>Trạng thái</th>
            <th>Hành động</th>
        </tr>
        {% for task_id, task in tasks.items() %}
        <tr>
            <td>{{ task_id }}</td>
            <td>{{ task.channel_id[:8] }}...</td>
            <td>{{ task.users_count }}</td>
            <td>{{ task.messages_count }}</td>
            <td>{{ task.message_count }}</td>
            <td>{{ task.delay }}s</td>
            <td>{{ "✅" if task.fake_typing else "❌" }}</td>
            <td>
                {% if task.status == 'running' %}
                    <span class="status-running">🟢 Đang chạy</span>
                    {% if task.fake_typing %}
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
                {% if task.status == 'running' %}
                    <button class="action-btn btn-stop" onclick="stopTask('{{ task_id }}')">🛑 Dừng</button>
                {% else %}
                    <button class="action-btn btn-start" onclick="startTask('{{ task_id }}')">▶️ Chạy</button>
                {% endif %}
                <button class="action-btn btn-delete" onclick="deleteTask('{{ task_id }}')">🗑️ Xóa</button>
            </td>
        </tr>
        {% endfor %}
    </table>

    <div class="center">
        <a href="/menu" class="back-btn">⬅️ Quay về Menu Chính</a>
    </div>

    <script>
        // Đếm số User ID
        function updateUserCount() {
            const user_ids = document.getElementById('user_ids').value.split('\\n').filter(id => id.trim());
            document.getElementById('userCount').textContent = user_ids.length;
        }

        // Load file nhay.txt
        function loadFileContent() {
            fetch('/dis2/check_files')
                .then(response => response.json())
                .then(data => {
                    const countElement = document.getElementById('fileMessageCount');
                    const previewElement = document.getElementById('filePreview');
                    
                    if (data.messages_count > 0) {
                        countElement.textContent = `${data.messages_count} tin nhắn`;
                        countElement.style.color = '#3fb950';
                        
                        // Load preview tin nhắn
                        fetch('/dis2/get_file_preview')
                            .then(response => response.json())
                            .then(previewData => {
                                if (previewData.messages && previewData.messages.length > 0) {
                                    let previewHTML = '';
                                    previewData.messages.slice(0, 10).forEach(msg => {
                                        previewHTML += `<div style="margin: 2px 0; padding: 2px;">${msg}</div>`;
                                    });
                                    if (previewData.messages.length > 10) {
                                        previewHTML += `<div style="color: #888; margin-top: 5px;">... và ${previewData.messages.length - 10} tin nhắn khác</div>`;
                                    }
                                    previewElement.innerHTML = previewHTML;
                                }
                            });
                    } else {
                        countElement.textContent = 'File trống hoặc không tồn tại';
                        countElement.style.color = '#f85149';
                        previewElement.textContent = 'Không có nội dung để hiển thị';
                    }
                })
                .catch(error => {
                    console.error('Lỗi tải file:', error);
                    document.getElementById('fileMessageCount').textContent = 'Lỗi tải file';
                    document.getElementById('fileMessageCount').style.color = '#f85149';
                });
        }

        document.getElementById('user_ids').addEventListener('input', updateUserCount);
        updateUserCount();
        loadFileContent();

        document.getElementById('taskForm').addEventListener('submit', function(e) {
            e.preventDefault();
            
            const remainingTasks = {{ remaining_tasks }};
            if (remainingTasks <= 0) {
                alert('❌ Bạn đã hết số task cho tính năng này!');
                return;
            }

            const formData = new FormData(this);
            const user_ids = document.getElementById('user_ids').value.split('\\n').filter(id => id.trim());

            if (user_ids.length === 0) {
                alert('❌ Vui lòng nhập ít nhất 1 User ID!');
                return;
            }

            const data = {
                token: document.getElementById('token').value,
                channel_id: document.getElementById('channel_id').value,
                user_ids: user_ids,
                delay: parseInt(document.getElementById('delay').value),
                fake_typing: document.getElementById('fake_typing').value === 'true'
            };

            // Hiển thị loading
            const createBtn = document.querySelector('#taskForm button[type="submit"]');
            createBtn.innerHTML = '⏳ Đang tạo task...';
            createBtn.disabled = true;

            fetch('/dis2/add_task', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify(data)
            })
            .then(response => response.json())
            .then(result => {
                if (result.success) {
                    alert('🎉 Tạo task thành công! Task đang chạy...');
                    location.reload();
                } else {
                    alert('❌ Lỗi: ' + result.message);
                }
            })
            .catch(error => {
                alert('❌ Lỗi kết nối: ' + error);
            })
            .finally(() => {
                createBtn.innerHTML = '🚀 Bắt đầu nhây tag';
                createBtn.disabled = false;
            });
        });

        function startTask(taskId) {
            fetch('/dis2/start_task/' + taskId)
                .then(response => response.json())
                .then(result => {
                    if (result.success) {
                        alert('🚀 Khởi chạy task thành công!');
                        location.reload();
                    } else {
                        alert('❌ Lỗi: ' + result.message);
                    }
                });
        }

        function stopTask(taskId) {
            fetch('/dis2/stop_task/' + taskId)
                .then(response => response.json())
                .then(result => {
                    if (result.success) {
                        alert('🛑 Dừng task thành công!');
                        location.reload();
                    } else {
                        alert('❌ Lỗi: ' + result.message);
                    }
                });
        }

        function deleteTask(taskId) {
            if (confirm('🗑️ Bạn có chắc chắn muốn xóa task này?')) {
                fetch('/dis2/delete_task/' + taskId)
                    .then(response => response.json())
                    .then(result => {
                        if (result.success) {
                            alert('✅ Xóa task thành công!');
                            location.reload();
                        } else {
                            alert('❌ Lỗi: ' + result.message);
                        }
                    });
            }
        }

        // Auto refresh task status
        setInterval(() => {
            fetch('/dis2/get_tasks')
                .then(response => response.json())
                .then(tasks => {
                    // Có thể cập nhật số tin đã gửi ở đây nếu cần
                    console.log('Tasks updated:', tasks);
                });
        }, 5000);
    </script>
</body>
</html>
'''

@dis2_bp.route('/')
def dis2_page():
    if 'key' not in session:
        return redirect('/')
    
    KEYS, get_remaining_tasks, _ = get_keys_and_functions()
    
    key = session['key']
    if key not in KEYS:
        session.pop('key', None)
        return redirect('/')
    
    expire, permissions, task_limits = KEYS[key]
    
    if 'dis2' not in permissions and 'admin' not in permissions:
        return "🚫 Không có quyền truy cập tính năng này!", 403
    
    remaining_tasks = get_remaining_tasks(key, 'dis2')
    running_tasks = sum(1 for task in dis2_tasks.values() if task['status'] == 'running')
    
    return render_template_string(DIS2_HTML, 
                                tasks=dis2_tasks,
                                remaining_tasks=remaining_tasks,
                                running_tasks=running_tasks,
                                total_tasks=len(dis2_tasks))

@dis2_bp.route('/check_files')
def check_files():
    """API để kiểm tra file"""
    messages = load_file_lines('nhay.txt')
    
    return jsonify({
        "messages_count": len(messages)
    })

@dis2_bp.route('/get_file_preview')
def get_file_preview():
    """API để lấy preview file nhay.txt"""
    messages = load_file_lines('nhay.txt')
    
    return jsonify({
        "messages": messages[:20]  # Trả về tối đa 20 tin nhắn đầu tiên
    })

@dis2_bp.route('/add_task', methods=['POST'])
def add_task():
    if 'key' not in session:
        return jsonify({"success": False, "message": "Chưa đăng nhập"}), 401
    
    key = session['key']
    KEYS, get_remaining_tasks, use_task = get_keys_and_functions()
    
    if key not in KEYS:
        return jsonify({"success": False, "message": "Key không hợp lệ"}), 403
    
    remaining = get_remaining_tasks(key, 'dis2')
    if remaining <= 0:
        return jsonify({"success": False, "message": "Đã hết số task cho tính năng này!"}), 403
    
    data = request.get_json()
    
    if not data.get('token') or not data.get('channel_id'):
        return jsonify({"success": False, "message": "Token và Channel ID là bắt buộc!"}), 400
    
    if not data.get('user_ids') or len(data['user_ids']) == 0:
        return jsonify({"success": False, "message": "Cần ít nhất 1 User ID!"}), 400
    
    # Đọc file để kiểm tra
    messages = load_file_lines('nhay.txt')
    
    if len(messages) == 0:
        return jsonify({"success": False, "message": "File nhay.txt trống hoặc không tồn tại!"}), 400
    
    global task_id_counter
    task_id = str(task_id_counter)
    task_id_counter += 1
    
    # Tạo task và tự động chạy luôn
    dis2_tasks[task_id] = {
        'token': data['token'],
        'channel_id': data['channel_id'],
        'user_ids': data['user_ids'],
        'delay': data['delay'],
        'fake_typing': data['fake_typing'],
        'messages_count': len(messages),
        'users_count': len(data['user_ids']),
        'status': 'running',  # Tự động chạy luôn
        'message_count': 0,
        'thread': None
    }
    
    # Start task ngay lập tức
    thread = threading.Thread(
        target=spam_tagged_task,
        args=(task_id, data['token'], data['channel_id'], messages, data['user_ids'], data['delay'], data['fake_typing']),
        daemon=True
    )
    dis2_tasks[task_id]['thread'] = thread
    thread.start()
    
    # Lưu task
    save_tasks()
    
    # Sử dụng 1 task
    use_task(key, 'dis2')
    
    return jsonify({
        "success": True, 
        "message": "Task created and started successfully!",
        "task_id": task_id
    })

def start_task(task_id):
    """Bắt đầu task"""
    if task_id not in dis2_tasks:
        return False
    
    task = dis2_tasks[task_id]
    
    if task['status'] == 'running':
        return True
    
    # Đọc lại file nhay.txt mỗi khi start
    messages = load_file_lines('nhay.txt')
    
    task['status'] = 'running'
    thread = threading.Thread(
        target=spam_tagged_task,
        args=(task_id, task['token'], task['channel_id'], messages, task['user_ids'], task['delay'], task['fake_typing']),
        daemon=True
    )
    task['thread'] = thread
    thread.start()
    
    save_tasks()  # Lưu trạng thái
    return True

@dis2_bp.route('/start_task/<task_id>')
def start_task_route(task_id):
    if start_task(task_id):
        return jsonify({"success": True, "message": "Task started!"})
    else:
        return jsonify({"success": False, "message": "Task không tồn tại!"}), 404

@dis2_bp.route('/stop_task/<task_id>')
def stop_task(task_id):
    if task_id not in dis2_tasks:
        return jsonify({"success": False, "message": "Task không tồn tại!"}), 404
    
    dis2_tasks[task_id]['status'] = 'stopped'
    save_tasks()
    return jsonify({"success": True, "message": "Task stopped!"})

@dis2_bp.route('/delete_task/<task_id>')
def delete_task(task_id):
    if task_id not in dis2_tasks:
        return jsonify({"success": False, "message": "Task không tồn tại!"}), 404
    
    dis2_tasks[task_id]['status'] = 'stopped'
    del dis2_tasks[task_id]
    save_tasks()
    return jsonify({"success": True, "message": "Task deleted!"})

@dis2_bp.route('/get_tasks')
def get_tasks():
    return jsonify(dis2_tasks)
