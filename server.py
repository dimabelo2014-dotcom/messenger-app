from flask import Flask, render_template, request, jsonify, send_file
from flask_socketio import SocketIO, emit, join_room, leave_room
import os
import json
import base64
import time
import uuid
from datetime import datetime
import threading

app = Flask(__name__)
app.config['SECRET_KEY'] = 'secret!'
socketio = SocketIO(app, cors_allowed_origins="*")

# Хранилище сообщений и пользователей
messages = []
users = {}
active_calls = {}

# HTML шаблон (встроенный)
HTML_TEMPLATE = '''
<!DOCTYPE html>
<html>
<head>
    <title>Python Messenger</title>
    <meta charset="utf-8">
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { font-family: Arial; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); height: 100vh; display: flex; justify-content: center; align-items: center; }
        .login-container { background: white; border-radius: 10px; padding: 40px; width: 400px; }
        .login-container h1 { margin-bottom: 30px; color: #333; }
        .login-container input { width: 100%; padding: 12px; margin-bottom: 20px; border: 2px solid #ddd; border-radius: 5px; }
        .login-container button { background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; border: none; padding: 12px 30px; border-radius: 5px; cursor: pointer; width: 100%; }
        .chat-container { display: none; width: 1200px; height: 80vh; background: white; border-radius: 10px; overflow: hidden; }
        .sidebar { width: 300px; background: #f5f5f5; border-right: 1px solid #ddd; }
        .main-chat { flex: 1; display: flex; flex-direction: column; }
        .chat-header { padding: 20px; background: white; border-bottom: 1px solid #ddd; }
        .messages { flex: 1; overflow-y: auto; padding: 20px; }
        .message { margin-bottom: 15px; max-width: 70%; }
        .message.own { margin-left: auto; }
        .message-content { background: white; padding: 10px 15px; border-radius: 18px; box-shadow: 0 1px 2px rgba(0,0,0,0.1); }
        .message.own .message-content { background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; }
        .message-info { font-size: 12px; color: #666; margin-bottom: 5px; }
        .message.own .message-info { text-align: right; color: #ddd; }
        .message-input { padding: 20px; background: white; border-top: 1px solid #ddd; display: flex; }
        .message-input input { flex: 1; padding: 12px; border: 2px solid #ddd; border-radius: 25px; margin-right: 10px; }
        .message-input button { width: 45px; height: 45px; border-radius: 50%; border: none; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; cursor: pointer; }
        .users-list { padding: 20px; }
        .user-item { display: flex; align-items: center; padding: 10px; background: white; border-radius: 5px; margin-bottom: 10px; }
        .user-avatar { width: 40px; height: 40px; border-radius: 50%; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); display: flex; align-items: center; justify-content: center; color: white; margin-right: 10px; }
        .call-controls { display: flex; gap: 10px; }
        .call-btn { width: 40px; height: 40px; border-radius: 50%; border: none; background: #f0f0f0; cursor: pointer; }
        .call-modal { position: fixed; top: 0; left: 0; right: 0; bottom: 0; background: rgba(0,0,0,0.7); display: none; justify-content: center; align-items: center; }
        .call-content { background: white; padding: 30px; border-radius: 10px; text-align: center; }
        .call-actions { display: flex; gap: 20px; margin-top: 20px; }
        .accept { background: #4caf50; color: white; border: none; padding: 10px 20px; border-radius: 5px; cursor: pointer; }
        .reject { background: #f44336; color: white; border: none; padding: 10px 20px; border-radius: 5px; cursor: pointer; }
        .record-btn { background: #f44336; color: white; animation: pulse 1s infinite; }
        @keyframes pulse { 0% { transform: scale(1); } 50% { transform: scale(1.1); } }
        .recording-status { display: none; align-items: center; gap: 10px; background: #f44336; color: white; padding: 5px 15px; border-radius: 20px; }
        audio, video { max-width: 100%; border-radius: 10px; }
        .video-circle { width: 150px; height: 150px; border-radius: 50%; object-fit: cover; }
        .action-btns { display: flex; gap: 5px; margin-right: 10px; }
        .action-btn { width: 40px; height: 40px; border-radius: 50%; border: none; background: #f0f0f0; cursor: pointer; }
        #videoContainer { position: fixed; bottom: 20px; right: 20px; width: 200px; background: black; border-radius: 10px; overflow: hidden; display: none; }
        #videoContainer video { width: 100%; }
    </style>
</head>
<body>
    <div class="login-container" id="loginContainer">
        <h1>Python Messenger</h1>
        <input type="text" id="username" placeholder="Ваше имя">
        <button onclick="joinChat()">Войти</button>
    </div>

    <div class="chat-container" id="chatContainer">
        <div class="sidebar">
            <div class="users-list" id="usersList"></div>
        </div>
        <div class="main-chat">
            <div class="chat-header">
                <h2>Общий чат</h2>
                <div class="call-controls">
                    <button class="call-btn" onclick="startCall()" id="startCallBtn">📞</button>
                    <button class="call-btn" onclick="endCall()" id="endCallBtn" style="display:none;">🔴</button>
                </div>
            </div>
            <div class="messages" id="messages"></div>
            <div class="message-input">
                <div class="action-btns">
                    <button class="action-btn" onclick="recordVoice()" id="voiceBtn">🎤</button>
                    <button class="action-btn" onclick="recordVideo()" id="videoBtn">📹</button>
                </div>
                <div class="recording-status" id="recordingStatus">
                    <span>🔴</span>
                    <span id="recordingTimer">00:00</span>
                    <button onclick="stopRecording()">⏹️</button>
                </div>
                <input type="text" id="messageInput" placeholder="Напишите сообщение..." onkeypress="if(event.key==='Enter') sendMessage()">
                <button onclick="sendMessage()">➤</button>
            </div>
        </div>
    </div>

    <div class="call-modal" id="callModal">
        <div class="call-content">
            <h3 id="callerInfo">Входящий звонок</h3>
            <div class="call-actions">
                <button class="accept" onclick="acceptCall()">Принять</button>
                <button class="reject" onclick="rejectCall()">Отклонить</button>
            </div>
        </div>
    </div>

    <div id="videoContainer">
        <video id="localVideo" autoplay muted></video>
        <video id="remoteVideo" autoplay></video>
    </div>

    <script src="https://cdn.socket.io/4.5.4/socket.io.min.js"></script>
    <script>
        let socket = io();
        let username = '';
        let currentUserId = '';
        let mediaRecorder = null;
        let recordingChunks = [];
        let recordingTimer = null;
        let seconds = 0;
        let localStream = null;
        let remoteStream = null;
        let peerConnection = null;
        let currentCaller = null;

        function joinChat() {
            username = document.getElementById('username').value;
            if (username) {
                socket.emit('join', username);
                document.getElementById('loginContainer').style.display = 'none';
                document.getElementById('chatContainer').style.display = 'flex';
            }
        }

        socket.on('user-joined', (data) => {
            currentUserId = data.userId;
            updateUsersList(data.users);
        });

        socket.on('users-update', (users) => {
            updateUsersList(users);
        });

        socket.on('new-message', (msg) => {
            displayMessage(msg);
        });

        socket.on('message-history', (history) => {
            history.forEach(msg => displayMessage(msg));
        });

        function updateUsersList(users) {
            const list = document.getElementById('usersList');
            list.innerHTML = '<h3>Участники (' + users.length + ')</h3>';
            users.forEach(user => {
                if (user.id !== currentUserId) {
                    list.innerHTML += `
                        <div class="user-item">
                            <div class="user-avatar">${user.username[0]}</div>
                            <div>${user.username}</div>
                        </div>
                    `;
                }
            });
        }

        function displayMessage(msg) {
            const messagesDiv = document.getElementById('messages');
            const messageDiv = document.createElement('div');
            messageDiv.className = 'message' + (msg.userId === currentUserId ? ' own' : '');
            
            let content = '';
            if (msg.type === 'text') {
                content = msg.text;
            } else if (msg.type === 'voice') {
                content = '<audio controls src="' + msg.url + '"></audio>';
            } else if (msg.type === 'video') {
                content = '<video ' + (msg.isCircle ? 'class="video-circle"' : '') + ' controls src="' + msg.url + '"></video>';
            }
            
            messageDiv.innerHTML = `
                <div class="message-info">${msg.username} ${new Date(msg.timestamp).toLocaleTimeString()}</div>
                <div class="message-content">${content}</div>
            `;
            messagesDiv.appendChild(messageDiv);
            messagesDiv.scrollTop = messagesDiv.scrollHeight;
        }

        function sendMessage() {
            const input = document.getElementById('messageInput');
            if (input.value) {
                socket.emit('send-message', { text: input.value, type: 'text' });
                input.value = '';
            }
        }

        // Запись голоса
        async function recordVoice() {
            try {
                const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
                startRecording(stream, 'voice');
            } catch (err) {
                alert('Нет доступа к микрофону');
            }
        }

        // Запись видео
        async function recordVideo() {
            try {
                const stream = await navigator.mediaDevices.getUserMedia({ video: true, audio: true });
                document.getElementById('videoContainer').style.display = 'block';
                document.getElementById('localVideo').srcObject = stream;
                startRecording(stream, 'video');
            } catch (err) {
                alert('Нет доступа к камере');
            }
        }

        function startRecording(stream, type) {
            recordingChunks = [];
            mediaRecorder = new MediaRecorder(stream);
            
            mediaRecorder.ondataavailable = (e) => recordingChunks.push(e.data);
            
            mediaRecorder.onstop = () => {
                const blob = new Blob(recordingChunks, { type: type === 'voice' ? 'audio/webm' : 'video/webm' });
                const reader = new FileReader();
                reader.readAsDataURL(blob);
                reader.onloadend = () => {
                    socket.emit('upload-file', {
                        data: reader.result,
                        type: type,
                        isCircle: type === 'video'
                    });
                };
                
                document.getElementById('voiceBtn').classList.remove('record-btn');
                document.getElementById('videoContainer').style.display = 'none';
                stream.getTracks().forEach(t => t.stop());
            };
            
            mediaRecorder.start();
            
            document.getElementById('voiceBtn').classList.add('record-btn');
            document.getElementById('recordingStatus').style.display = 'flex';
            
            seconds = 0;
            recordingTimer = setInterval(() => {
                seconds++;
                const mins = Math.floor(seconds / 60);
                const secs = seconds % 60;
                document.getElementById('recordingTimer').textContent = 
                    `${mins.toString().padStart(2,'0')}:${secs.toString().padStart(2,'0')}`;
            }, 1000);
        }

        function stopRecording() {
            if (mediaRecorder && mediaRecorder.state !== 'inactive') {
                mediaRecorder.stop();
                clearInterval(recordingTimer);
                document.getElementById('recordingStatus').style.display = 'none';
            }
        }

        // WebRTC звонки
        async function startCall() {
            try {
                localStream = await navigator.mediaDevices.getUserMedia({ video: true, audio: true });
                document.getElementById('localVideo').srcObject = localStream;
                document.getElementById('videoContainer').style.display = 'block';
                
                peerConnection = new RTCPeerConnection({
                    iceServers: [{ urls: 'stun:stun.l.google.com:19302' }]
                });
                
                localStream.getTracks().forEach(track => 
                    peerConnection.addTrack(track, localStream)
                );
                
                peerConnection.ontrack = (e) => {
                    document.getElementById('remoteVideo').srcObject = e.streams[0];
                };
                
                peerConnection.onicecandidate = (e) => {
                    if (e.candidate) {
                        socket.emit('call-user', {
                            target: prompt('Введите ID пользователя для звонка:'),
                            candidate: e.candidate
                        });
                    }
                };
                
                const offer = await peerConnection.createOffer();
                await peerConnection.setLocalDescription(offer);
                
                socket.emit('call-user', {
                    target: prompt('Введите ID пользователя для звонка:'),
                    offer: offer
                });
                
                document.getElementById('startCallBtn').style.display = 'none';
                document.getElementById('endCallBtn').style.display = 'inline-block';
                
            } catch (err) {
                alert('Ошибка звонка: ' + err.message);
            }
        }

        function endCall() {
            if (peerConnection) peerConnection.close();
            if (localStream) localStream.getTracks().forEach(t => t.stop());
            document.getElementById('videoContainer').style.display = 'none';
            document.getElementById('startCallBtn').style.display = 'inline-block';
            document.getElementById('endCallBtn').style.display = 'none';
            socket.emit('end-call');
        }

        socket.on('incoming-call', async (data) => {
            currentCaller = data.from;
            document.getElementById('callerInfo').textContent = `Звонок от ${data.fromName}`;
            document.getElementById('callModal').style.display = 'flex';
            
            if (data.offer) {
                peerConnection = new RTCPeerConnection({
                    iceServers: [{ urls: 'stun:stun.l.google.com:19302' }]
                });
                
                localStream = await navigator.mediaDevices.getUserMedia({ video: true, audio: true });
                document.getElementById('localVideo').srcObject = localStream;
                
                localStream.getTracks().forEach(track => 
                    peerConnection.addTrack(track, localStream)
                );
                
                peerConnection.ontrack = (e) => {
                    document.getElementById('remoteVideo').srcObject = e.streams[0];
                };
                
                peerConnection.onicecandidate = (e) => {
                    if (e.candidate) {
                        socket.emit('call-answer', {
                            target: data.from,
                            candidate: e.candidate
                        });
                    }
                };
                
                await peerConnection.setRemoteDescription(new RTCSessionDescription(data.offer));
                const answer = await peerConnection.createAnswer();
                await peerConnection.setLocalDescription(answer);
                
                socket.emit('call-answer', {
                    target: data.from,
                    answer: answer
                });
            }
        });

        socket.on('call-answered', async (data) => {
            if (data.answer) {
                await peerConnection.setRemoteDescription(new RTCSessionDescription(data.answer));
            }
            if (data.candidate) {
                await peerConnection.addIceCandidate(new RTCIceCandidate(data.candidate));
            }
        });

        socket.on('call-ended', () => {
            endCall();
        });

        function acceptCall() {
            document.getElementById('callModal').style.display = 'none';
            document.getElementById('videoContainer').style.display = 'block';
            document.getElementById('startCallBtn').style.display = 'none';
            document.getElementById('endCallBtn').style.display = 'inline-block';
        }

        function rejectCall() {
            document.getElementById('callModal').style.display = 'none';
            socket.emit('reject-call', { target: currentCaller });
        }

        socket.on('call-rejected', () => {
            alert('Звонок отклонен');
            endCall();
        });

        socket.on('file-uploaded', (data) => {
            displayMessage({
                userId: currentUserId,
                username: username,
                type: data.type,
                url: data.url,
                isCircle: data.isCircle,
                timestamp: new Date()
            });
        });
    </script>
</body>
</html>
'''

@app.route('/')
def index():
    return HTML_TEMPLATE

@app.route('/upload', methods=['POST'])
def upload():
    data = request.json
    if data and 'file' in data:
        # Сохраняем файл
        filename = f"uploads/{uuid.uuid4()}.{data['type']}"
        os.makedirs('uploads', exist_ok=True)
        
        # Декодируем base64
        file_data = base64.b64decode(data['file'].split(',')[1])
        with open(filename, 'wb') as f:
            f.write(file_data)
        
        return jsonify({'url': '/' + filename})
    return jsonify({'error': 'No file'}), 400

@app.route('/uploads/<filename>')
def get_file(filename):
    return send_file(f'uploads/{filename}')

@socketio.on('join')
def handle_join(username):
    user_id = request.sid
    users[user_id] = {
        'id': user_id,
        'username': username,
        'online': True
    }
    
    # Отправляем историю сообщений
    emit('message-history', messages[-50:])  # последние 50 сообщений
    
    # Уведомляем всех
    emit('user-joined', {
        'userId': user_id,
        'users': list(users.values())
    }, broadcast=True)

@socketio.on('send-message')
def handle_message(data):
    msg = {
        'id': str(uuid.uuid4()),
        'userId': request.sid,
        'username': users[request.sid]['username'],
        'text': data.get('text', ''),
        'type': data.get('type', 'text'),
        'url': data.get('url'),
        'isCircle': data.get('isCircle', False),
        'timestamp': datetime.now().isoformat()
    }
    messages.append(msg)
    emit('new-message', msg, broadcast=True)

@socketio.on('upload-file')
def handle_upload(data):
    # Сохраняем файл
    filename = f"uploads/{uuid.uuid4()}.webm"
    os.makedirs('uploads', exist_ok=True)
    
    # Декодируем base64
    file_data = base64.b64decode(data['data'].split(',')[1])
    with open(filename, 'wb') as f:
        f.write(file_data)
    
    # Отправляем как сообщение
    msg = {
        'id': str(uuid.uuid4()),
        'userId': request.sid,
        'username': users[request.sid]['username'],
        'type': data['type'],
        'url': '/' + filename,
        'isCircle': data.get('isCircle', False),
        'timestamp': datetime.now().isoformat()
    }
    messages.append(msg)
    emit('new-message', msg, broadcast=True)

@socketio.on('call-user')
def handle_call(data):
    emit('incoming-call', {
        'from': request.sid,
        'fromName': users[request.sid]['username'],
        'offer': data.get('offer'),
        'candidate': data.get('candidate')
    }, room=data['target'])

@socketio.on('call-answer')
def handle_answer(data):
    emit('call-answered', {
        'answer': data.get('answer'),
        'candidate': data.get('candidate')
    }, room=data['target'])

@socketio.on('reject-call')
def handle_reject(data):
    emit('call-rejected', {}, room=data['target'])

@socketio.on('end-call')
def handle_end_call():
    emit('call-ended', {}, broadcast=True)

@socketio.on('disconnect')
def handle_disconnect():
    if request.sid in users:
        del users[request.sid]
        emit('users-update', list(users.values()), broadcast=True)

if __name__ == '__main__':
    os.makedirs('uploads', exist_ok=True)
    socketio.run(app, host='0.0.0.0', port=5000, debug=True)
