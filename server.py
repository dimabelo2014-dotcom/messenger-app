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

# HTML шаблон для мобильной версии
HTML_TEMPLATE = '''
<!DOCTYPE html>
<html>
<head>
    <title>Mobile Messenger</title>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
    <style>
        * { 
            margin: 0; 
            padding: 0; 
            box-sizing: border-box; 
            -webkit-tap-highlight-color: transparent;
        }
        
        body { 
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; 
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); 
            height: 100vh; 
            display: flex; 
            justify-content: center; 
            align-items: center; 
        }
        
        /* Логин экран */
        .login-container { 
            background: white; 
            border-radius: 20px; 
            padding: 30px 20px; 
            width: 90%; 
            max-width: 350px; 
            margin: 20px;
            box-shadow: 0 10px 40px rgba(0,0,0,0.2);
        }
        
        .login-container h1 { 
            margin-bottom: 30px; 
            color: #333; 
            font-size: 28px;
            text-align: center;
        }
        
        .login-container input { 
            width: 100%; 
            padding: 15px; 
            margin-bottom: 20px; 
            border: 2px solid #eee; 
            border-radius: 30px; 
            font-size: 16px;
            outline: none;
            transition: border-color 0.3s;
        }
        
        .login-container input:focus {
            border-color: #667eea;
        }
        
        .login-container button { 
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); 
            color: white; 
            border: none; 
            padding: 15px 30px; 
            border-radius: 30px; 
            cursor: pointer; 
            width: 100%; 
            font-size: 16px;
            font-weight: 600;
            box-shadow: 0 5px 15px rgba(102, 126, 234, 0.4);
        }
        
        /* Чат контейнер */
        .chat-container { 
            display: none; 
            width: 100%; 
            height: 100vh; 
            background: white; 
            overflow: hidden;
            position: relative;
        }
        
        /* Верхняя панель */
        .chat-header { 
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 15px 20px;
            display: flex;
            align-items: center;
            justify-content: space-between;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
            position: fixed;
            top: 0;
            left: 0;
            right: 0;
            z-index: 100;
        }
        
        .header-left {
            display: flex;
            align-items: center;
            gap: 15px;
        }
        
        .menu-btn {
            background: none;
            border: none;
            color: white;
            font-size: 24px;
            cursor: pointer;
            width: 40px;
            height: 40px;
            display: flex;
            align-items: center;
            justify-content: center;
            border-radius: 50%;
            background: rgba(255,255,255,0.2);
        }
        
        .chat-header h2 { 
            font-size: 18px;
            font-weight: 600;
        }
        
        .call-controls {
            display: flex;
            gap: 10px;
        }
        
        .call-btn { 
            width: 45px; 
            height: 45px; 
            border-radius: 50%; 
            border: none; 
            background: rgba(255,255,255,0.2); 
            color: white;
            font-size: 20px;
            cursor: pointer;
            display: flex;
            align-items: center;
            justify-content: center;
        }
        
        /* Боковое меню */
        .sidebar { 
            position: fixed;
            top: 0;
            left: -300px;
            width: 85%;
            max-width: 300px;
            height: 100vh;
            background: #f8f9fa;
            transition: left 0.3s ease;
            z-index: 1000;
            box-shadow: 2px 0 10px rgba(0,0,0,0.1);
            overflow-y: auto;
        }
        
        .sidebar.active {
            left: 0;
        }
        
        .sidebar-header {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 60px 20px 30px;
        }
        
        .sidebar-header h3 {
            font-size: 24px;
            margin-bottom: 10px;
        }
        
        .users-list { 
            padding: 20px; 
        }
        
        .user-item { 
            display: flex; 
            align-items: center; 
            padding: 15px; 
            background: white; 
            border-radius: 15px; 
            margin-bottom: 10px; 
            box-shadow: 0 2px 5px rgba(0,0,0,0.05);
        }
        
        .user-avatar { 
            width: 50px; 
            height: 50px; 
            border-radius: 50%; 
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); 
            display: flex; 
            align-items: center; 
            justify-content: center; 
            color: white; 
            margin-right: 15px; 
            font-size: 20px;
            font-weight: 600;
        }
        
        /* Область сообщений */
        .messages { 
            padding: 20px;
            padding-top: 80px;
            padding-bottom: 100px;
            height: 100vh;
            overflow-y: auto;
            background: #f5f7fb;
        }
        
        .message { 
            margin-bottom: 15px; 
            max-width: 85%; 
            animation: fadeIn 0.3s;
        }
        
        @keyframes fadeIn {
            from { opacity: 0; transform: translateY(10px); }
            to { opacity: 1; transform: translateY(0); }
        }
        
        .message.own { 
            margin-left: auto; 
        }
        
        .message-content { 
            background: white; 
            padding: 12px 16px; 
            border-radius: 20px; 
            box-shadow: 0 2px 5px rgba(0,0,0,0.05);
            font-size: 16px;
            word-break: break-word;
        }
        
        .message.own .message-content { 
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); 
            color: white; 
        }
        
        .message-info { 
            font-size: 12px; 
            color: #999; 
            margin-bottom: 5px;
            margin-left: 5px;
        }
        
        .message.own .message-info { 
            text-align: right; 
            color: #667eea;
        }
        
        /* Нижняя панель */
        .message-input-container {
            position: fixed;
            bottom: 0;
            left: 0;
            right: 0;
            background: white;
            padding: 15px 20px;
            box-shadow: 0 -2px 10px rgba(0,0,0,0.05);
            z-index: 100;
        }
        
        .message-input-wrapper {
            display: flex;
            align-items: center;
            gap: 10px;
            background: #f0f2f5;
            border-radius: 30px;
            padding: 5px;
        }
        
        .message-input { 
            flex: 1;
            padding: 12px 15px;
            border: none;
            background: transparent;
            font-size: 16px;
            outline: none;
        }
        
        .action-btn { 
            width: 45px;
            height: 45px;
            border-radius: 50%;
            border: none;
            background: transparent;
            font-size: 20px;
            cursor: pointer;
            display: flex;
            align-items: center;
            justify-content: center;
            color: #667eea;
        }
        
        .send-btn {
            width: 45px;
            height: 45px;
            border-radius: 50%;
            border: none;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            font-size: 18px;
            cursor: pointer;
            display: flex;
            align-items: center;
            justify-content: center;
            box-shadow: 0 5px 15px rgba(102, 126, 234, 0.4);
        }
        
        /* Медиа файлы */
        audio, video { 
            max-width: 100%; 
            border-radius: 15px; 
        }
        
        .video-circle { 
            width: 150px; 
            height: 150px; 
            border-radius: 50%; 
            object-fit: cover; 
        }
        
        /* Статус записи */
        .recording-status { 
            display: none; 
            align-items: center; 
            gap: 10px; 
            background: #f44336; 
            color: white; 
            padding: 8px 20px; 
            border-radius: 30px; 
            position: fixed;
            top: 80px;
            left: 50%;
            transform: translateX(-50%);
            z-index: 1000;
            box-shadow: 0 5px 15px rgba(244, 67, 54, 0.4);
            animation: slideDown 0.3s;
        }
        
        @keyframes slideDown {
            from { top: 60px; opacity: 0; }
            to { top: 80px; opacity: 1; }
        }
        
        .recording-status button {
            background: white;
            border: none;
            width: 35px;
            height: 35px;
            border-radius: 50%;
            cursor: pointer;
            font-size: 16px;
        }
        
        /* Модальное окно звонка */
        .call-modal { 
            position: fixed; 
            top: 0; 
            left: 0; 
            right: 0; 
            bottom: 0; 
            background: rgba(0,0,0,0.8); 
            display: none; 
            justify-content: center; 
            align-items: center; 
            z-index: 2000;
        }
        
        .call-content { 
            background: white; 
            padding: 40px 30px; 
            border-radius: 30px; 
            text-align: center; 
            width: 90%;
            max-width: 350px;
            animation: popIn 0.3s;
        }
        
        @keyframes popIn {
            from { transform: scale(0.8); opacity: 0; }
            to { transform: scale(1); opacity: 1; }
        }
        
        .call-content h3 {
            font-size: 24px;
            margin-bottom: 30px;
            color: #333;
        }
        
        .call-actions { 
            display: flex; 
            gap: 20px; 
            justify-content: center;
        }
        
        .accept, .reject {
            width: 70px;
            height: 70px;
            border-radius: 50%;
            border: none;
            font-size: 30px;
            cursor: pointer;
            display: flex;
            align-items: center;
            justify-content: center;
            transition: transform 0.2s;
        }
        
        .accept:active, .reject:active {
            transform: scale(0.95);
        }
        
        .accept { 
            background: #4caf50; 
            color: white; 
        }
        
        .reject { 
            background: #f44336; 
            color: white; 
        }
        
        /* Видео контейнер */
        #videoContainer { 
            position: fixed; 
            bottom: 20px; 
            right: 20px; 
            width: 120px; 
            background: black; 
            border-radius: 20px; 
            overflow: hidden; 
            display: none; 
            z-index: 1500;
            box-shadow: 0 5px 20px rgba(0,0,0,0.3);
        }
        
        #videoContainer video { 
            width: 100%; 
            height: auto;
        }
        
        #remoteVideo {
            position: fixed;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            object-fit: cover;
            z-index: 1400;
        }
        
        .record-btn { 
            background: #f44336 !important; 
            color: white;
            animation: pulse 1s infinite;
        }
        
        @keyframes pulse { 
            0% { transform: scale(1); } 
            50% { transform: scale(1.1); } 
        }
        
        .overlay {
            position: fixed;
            top: 0;
            left: 0;
            right: 0;
            bottom: 0;
            background: rgba(0,0,0,0.5);
            display: none;
            z-index: 999;
        }
        
        .overlay.active {
            display: block;
        }
    </style>
</head>
<body>
    <div class="login-container" id="loginContainer">
        <h1>Mobile Chat</h1>
        <input type="text" id="username" placeholder="Ваше имя" autocomplete="off">
        <button onclick="joinChat()">Войти</button>
    </div>

    <div class="chat-container" id="chatContainer">
        <div class="chat-header">
            <div class="header-left">
                <button class="menu-btn" onclick="toggleMenu()">☰</button>
                <h2>Общий чат</h2>
            </div>
            <div class="call-controls">
                <button class="call-btn" onclick="startCall()" id="startCallBtn">📞</button>
                <button class="call-btn" onclick="endCall()" id="endCallBtn" style="display:none;">🔴</button>
            </div>
        </div>
        
        <div class="overlay" id="overlay" onclick="toggleMenu()"></div>
        
        <div class="sidebar" id="sidebar">
            <div class="sidebar-header">
                <h3>Участники</h3>
                <p id="usersCount">0 онлайн</p>
            </div>
            <div class="users-list" id="usersList"></div>
        </div>

        <div class="messages" id="messages"></div>
        
        <div class="message-input-container">
            <div class="recording-status" id="recordingStatus">
                <span>🔴</span>
                <span id="recordingTimer">00:00</span>
                <button onclick="stopRecording()">⏹️</button>
            </div>
            
            <div class="message-input-wrapper">
                <button class="action-btn" onclick="recordVoice()" id="voiceBtn">🎤</button>
                <button class="action-btn" onclick="recordVideo()" id="videoBtn">📹</button>
                <input type="text" class="message-input" id="messageInput" placeholder="Сообщение..." 
                       onkeypress="if(event.key==='Enter') sendMessage()">
                <button class="send-btn" onclick="sendMessage()">➤</button>
            </div>
        </div>
    </div>

    <div class="call-modal" id="callModal">
        <div class="call-content">
            <h3 id="callerInfo">Входящий звонок</h3>
            <div class="call-actions">
                <button class="accept" onclick="acceptCall()">📞</button>
                <button class="reject" onclick="rejectCall()">❌</button>
            </div>
        </div>
    </div>

    <div id="videoContainer">
        <video id="localVideo" autoplay muted playsinline></video>
        <video id="remoteVideo" autoplay playsinline></video>
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
        let peerConnection = null;
        let currentCaller = null;

        function toggleMenu() {
            document.getElementById('sidebar').classList.toggle('active');
            document.getElementById('overlay').classList.toggle('active');
        }

        function joinChat() {
            username = document.getElementById('username').value.trim();
            if (username) {
                socket.emit('join', username);
                document.getElementById('loginContainer').style.display = 'none';
                document.getElementById('chatContainer').style.display = 'block';
            } else {
                alert('Введите имя');
            }
        }

        socket.on('user-joined', (data) => {
            currentUserId = data.userId;
            updateUsersList(data.users);
        });

        socket.on('users-update', (users) => {
            updateUsersList(users);
            document.getElementById('usersCount').textContent = users.length + ' онлайн';
        });

        socket.on('new-message', (msg) => {
            displayMessage(msg);
            vibrate();
        });

        socket.on('message-history', (history) => {
            history.forEach(msg => displayMessage(msg));
        });

        function vibrate() {
            if (window.navigator.vibrate) {
                window.navigator.vibrate(50);
            }
        }

        function updateUsersList(users) {
            const list = document.getElementById('usersList');
            list.innerHTML = '';
            users.forEach(user => {
                if (user.id !== currentUserId) {
                    list.innerHTML += `
                        <div class="user-item" onclick="showUserOptions('${user.id}', '${user.username}')">
                            <div class="user-avatar">${user.username[0].toUpperCase()}</div>
                            <div style="flex:1">
                                <div style="font-weight:600">${user.username}</div>
                                <div style="font-size:12px; color:#999">онлайн</div>
                            </div>
                        </div>
                    `;
                }
            });
        }

        function showUserOptions(userId, username) {
            if (confirm('Позвонить пользователю ' + username + '?')) {
                startCallTo(userId);
            }
        }

        function displayMessage(msg) {
            const messagesDiv = document.getElementById('messages');
            const messageDiv = document.createElement('div');
            messageDiv.className = 'message' + (msg.userId === currentUserId ? ' own' : '');
            
            let content = '';
            if (msg.type === 'text') {
                content = msg.text;
            } else if (msg.type === 'voice') {
                content = '<audio controls src="' + msg.url + '" style="max-width:200px"></audio>';
            } else if (msg.type === 'video') {
                content = '<video ' + (msg.isCircle ? 'class="video-circle"' : '') + ' controls src="' + msg.url + '" style="max-width:200px"></video>';
            }
            
            const time = new Date(msg.timestamp).toLocaleTimeString('ru-RU', {hour: '2-digit', minute:'2-digit'});
            
            messageDiv.innerHTML = `
                <div class="message-info">${msg.username} ${time}</div>
                <div class="message-content">${content}</div>
            `;
            messagesDiv.appendChild(messageDiv);
            messagesDiv.scrollTop = messagesDiv.scrollHeight;
        }

        function sendMessage() {
            const input = document.getElementById('messageInput');
            if (input.value.trim()) {
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
                const stream = await navigator.mediaDevices.getUserMedia({ 
                    video: { facingMode: 'user' }, 
                    audio: true 
                });
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
            
            mediaRecorder.ondataavailable = (e) => {
                if (e.data.size > 0) {
                    recordingChunks.push(e.data);
                }
            };
            
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
                document.getElementById('videoBtn').classList.remove('record-btn');
                document.getElementById('videoContainer').style.display = 'none';
                stream.getTracks().forEach(t => t.stop());
            };
            
            mediaRecorder.start();
            
            if (type === 'voice') {
                document.getElementById('voiceBtn').classList.add('record-btn');
            } else {
                document.getElementById('videoBtn').classList.add('record-btn');
            }
            
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
            const targetId = prompt('Введите ID пользователя для звонка:');
            if (targetId) {
                startCallTo(targetId);
            }
        }

        async function startCallTo(targetId) {
            try {
                localStream = await navigator.mediaDevices.getUserMedia({ 
                    video: { facingMode: 'user' }, 
                    audio: true 
                });
                
                document.getElementById('remoteVideo').style.display = 'block';
                document.getElementById('localVideo').style.display = 'block';
                document.getElementById('localVideo').srcObject = localStream;
                
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
                            target: targetId,
                            candidate: e.candidate
                        });
                    }
                };
                
                const offer = await peerConnection.createOffer();
                await peerConnection.setLocalDescription(offer);
                
                socket.emit('call-user', {
                    target: targetId,
                    offer: offer
                });
                
                document.getElementById('startCallBtn').style.display = 'none';
                document.getElementById('endCallBtn').style.display = 'inline-block';
                document.getElementById('videoContainer').style.display = 'block';
                
            } catch (err) {
                alert('Ошибка звонка: ' + err.message);
            }
        }

        function endCall() {
            if (peerConnection) {
                peerConnection.close();
                peerConnection = null;
            }
            if (localStream) {
                localStream.getTracks().forEach(t => t.stop());
                localStream = null;
            }
            document.getElementById('remoteVideo').style.display = 'none';
            document.getElementById('videoContainer').style.display = 'none';
            document.getElementById('startCallBtn').style.display = 'inline-block';
            document.getElementById('endCallBtn').style.display = 'none';
            socket.emit('end-call');
        }

        socket.on('incoming-call', async (data) => {
            currentCaller = data.from;
            document.getElementById('callerInfo').textContent = `Звонок от ${data.fromName}`;
            document.getElementById('callModal').style.display = 'flex';
            vibrate();
            
            if (data.offer) {
                try {
                    peerConnection = new RTCPeerConnection({
                        iceServers: [{ urls: 'stun:stun.l.google.com:19302' }]
                    });
                    
                    localStream = await navigator.mediaDevices.getUserMedia({ 
                        video: { facingMode: 'user' }, 
                        audio: true 
                    });
                    
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
                } catch (err) {
                    console.error('Error handling call:', err);
                }
            }
        });

        socket.on('call-answered', async (data) => {
            try {
                if (data.answer) {
                    await peerConnection.setRemoteDescription(new RTCSessionDescription(data.answer));
                }
                if (data.candidate) {
                    await peerConnection.addIceCandidate(new RTCIceCandidate(data.candidate));
                }
            } catch (err) {
                console.error('Error answering call:', err);
            }
        });

        socket.on('call-ended', () => {
            endCall();
        });

        function acceptCall() {
            document.getElementById('callModal').style.display = 'none';
            document.getElementById('remoteVideo').style.display = 'block';
            document.getElementById('videoContainer').style.display = 'block';
            document.getElementById('startCallBtn').style.display = 'none';
            document.getElementById('endCallBtn').style.display = 'inline-block';
        }

        function rejectCall() {
            document.getElementById('callModal').style.display = 'none';
            if (currentCaller) {
                socket.emit('reject-call', { target: currentCaller });
            }
            endCall();
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

        // Закрытие меню свайпом
        let touchStartX = 0;
        document.addEventListener('touchstart', (e) => {
            touchStartX = e.touches[0].clientX;
        });

        document.addEventListener('touchend', (e) => {
            const touchEndX = e.changedTouches[0].clientX;
            const sidebar = document.getElementById('sidebar');
            
            if (sidebar.classList.contains('active') && touchEndX - touchStartX < -50) {
                toggleMenu();
            }
        });

        // Обработка кнопки назад на Android
        window.addEventListener('popstate', () => {
            if (document.getElementById('sidebar').classList.contains('active')) {
                toggleMenu();
            }
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
        filename = f"uploads/{uuid.uuid4()}.{data['type']}"
        os.makedirs('uploads', exist_ok=True)
        
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
    
    emit('message-history', messages[-50:])
    
    emit('user-joined', {
        'userId': user_id,
        'users': list(users.values())
    }, broadcast=True)

@socketio.on('send-message')
def handle_message(data):
    if request.sid in users:
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
    if request.sid in users:
        filename = f"uploads/{uuid.uuid4()}.webm"
        os.makedirs('uploads', exist_ok=True)
        
        file_data = base64.b64decode(data['data'].split(',')[1])
        with open(filename, 'wb') as f:
            f.write(file_data)
        
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
    if data['target'] in users:
        emit('incoming-call', {
            'from': request.sid,
            'fromName': users[request.sid]['username'],
            'offer': data.get('offer'),
            'candidate': data.get('candidate')
        }, room=data['target'])

@socketio.on('call-answer')
def handle_answer(data):
    if data['target'] in users:
        emit('call-answered', {
            'answer': data.get('answer'),
            'candidate': data.get('candidate')
        }, room=data['target'])

@socketio.on('reject-call')
def handle_reject(data):
    if data['target'] in users:
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
    socketio.run(app, host='0.0.0.0', port=5000, debug=True)from flask import Flask, render_template, request, jsonify, send_file
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

# HTML шаблон для мобильной версии
HTML_TEMPLATE = '''
<!DOCTYPE html>
<html>
<head>
    <title>Mobile Messenger</title>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
    <style>
        * { 
            margin: 0; 
            padding: 0; 
            box-sizing: border-box; 
            -webkit-tap-highlight-color: transparent;
        }
        
        body { 
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; 
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); 
            height: 100vh; 
            display: flex; 
            justify-content: center; 
            align-items: center; 
        }
        
        /* Логин экран */
        .login-container { 
            background: white; 
            border-radius: 20px; 
            padding: 30px 20px; 
            width: 90%; 
            max-width: 350px; 
            margin: 20px;
            box-shadow: 0 10px 40px rgba(0,0,0,0.2);
        }
        
        .login-container h1 { 
            margin-bottom: 30px; 
            color: #333; 
            font-size: 28px;
            text-align: center;
        }
        
        .login-container input { 
            width: 100%; 
            padding: 15px; 
            margin-bottom: 20px; 
            border: 2px solid #eee; 
            border-radius: 30px; 
            font-size: 16px;
            outline: none;
            transition: border-color 0.3s;
        }
        
        .login-container input:focus {
            border-color: #667eea;
        }
        
        .login-container button { 
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); 
            color: white; 
            border: none; 
            padding: 15px 30px; 
            border-radius: 30px; 
            cursor: pointer; 
            width: 100%; 
            font-size: 16px;
            font-weight: 600;
            box-shadow: 0 5px 15px rgba(102, 126, 234, 0.4);
        }
        
        /* Чат контейнер */
        .chat-container { 
            display: none; 
            width: 100%; 
            height: 100vh; 
            background: white; 
            overflow: hidden;
            position: relative;
        }
        
        /* Верхняя панель */
        .chat-header { 
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 15px 20px;
            display: flex;
            align-items: center;
            justify-content: space-between;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
            position: fixed;
            top: 0;
            left: 0;
            right: 0;
            z-index: 100;
        }
        
        .header-left {
            display: flex;
            align-items: center;
            gap: 15px;
        }
        
        .menu-btn {
            background: none;
            border: none;
            color: white;
            font-size: 24px;
            cursor: pointer;
            width: 40px;
            height: 40px;
            display: flex;
            align-items: center;
            justify-content: center;
            border-radius: 50%;
            background: rgba(255,255,255,0.2);
        }
        
        .chat-header h2 { 
            font-size: 18px;
            font-weight: 600;
        }
        
        .call-controls {
            display: flex;
            gap: 10px;
        }
        
        .call-btn { 
            width: 45px; 
            height: 45px; 
            border-radius: 50%; 
            border: none; 
            background: rgba(255,255,255,0.2); 
            color: white;
            font-size: 20px;
            cursor: pointer;
            display: flex;
            align-items: center;
            justify-content: center;
        }
        
        /* Боковое меню */
        .sidebar { 
            position: fixed;
            top: 0;
            left: -300px;
            width: 85%;
            max-width: 300px;
            height: 100vh;
            background: #f8f9fa;
            transition: left 0.3s ease;
            z-index: 1000;
            box-shadow: 2px 0 10px rgba(0,0,0,0.1);
            overflow-y: auto;
        }
        
        .sidebar.active {
            left: 0;
        }
        
        .sidebar-header {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 60px 20px 30px;
        }
        
        .sidebar-header h3 {
            font-size: 24px;
            margin-bottom: 10px;
        }
        
        .users-list { 
            padding: 20px; 
        }
        
        .user-item { 
            display: flex; 
            align-items: center; 
            padding: 15px; 
            background: white; 
            border-radius: 15px; 
            margin-bottom: 10px; 
            box-shadow: 0 2px 5px rgba(0,0,0,0.05);
        }
        
        .user-avatar { 
            width: 50px; 
            height: 50px; 
            border-radius: 50%; 
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); 
            display: flex; 
            align-items: center; 
            justify-content: center; 
            color: white; 
            margin-right: 15px; 
            font-size: 20px;
            font-weight: 600;
        }
        
        /* Область сообщений */
        .messages { 
            padding: 20px;
            padding-top: 80px;
            padding-bottom: 100px;
            height: 100vh;
            overflow-y: auto;
            background: #f5f7fb;
        }
        
        .message { 
            margin-bottom: 15px; 
            max-width: 85%; 
            animation: fadeIn 0.3s;
        }
        
        @keyframes fadeIn {
            from { opacity: 0; transform: translateY(10px); }
            to { opacity: 1; transform: translateY(0); }
        }
        
        .message.own { 
            margin-left: auto; 
        }
        
        .message-content { 
            background: white; 
            padding: 12px 16px; 
            border-radius: 20px; 
            box-shadow: 0 2px 5px rgba(0,0,0,0.05);
            font-size: 16px;
            word-break: break-word;
        }
        
        .message.own .message-content { 
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); 
            color: white; 
        }
        
        .message-info { 
            font-size: 12px; 
            color: #999; 
            margin-bottom: 5px;
            margin-left: 5px;
        }
        
        .message.own .message-info { 
            text-align: right; 
            color: #667eea;
        }
        
        /* Нижняя панель */
        .message-input-container {
            position: fixed;
            bottom: 0;
            left: 0;
            right: 0;
            background: white;
            padding: 15px 20px;
            box-shadow: 0 -2px 10px rgba(0,0,0,0.05);
            z-index: 100;
        }
        
        .message-input-wrapper {
            display: flex;
            align-items: center;
            gap: 10px;
            background: #f0f2f5;
            border-radius: 30px;
            padding: 5px;
        }
        
        .message-input { 
            flex: 1;
            padding: 12px 15px;
            border: none;
            background: transparent;
            font-size: 16px;
            outline: none;
        }
        
        .action-btn { 
            width: 45px;
            height: 45px;
            border-radius: 50%;
            border: none;
            background: transparent;
            font-size: 20px;
            cursor: pointer;
            display: flex;
            align-items: center;
            justify-content: center;
            color: #667eea;
        }
        
        .send-btn {
            width: 45px;
            height: 45px;
            border-radius: 50%;
            border: none;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            font-size: 18px;
            cursor: pointer;
            display: flex;
            align-items: center;
            justify-content: center;
            box-shadow: 0 5px 15px rgba(102, 126, 234, 0.4);
        }
        
        /* Медиа файлы */
        audio, video { 
            max-width: 100%; 
            border-radius: 15px; 
        }
        
        .video-circle { 
            width: 150px; 
            height: 150px; 
            border-radius: 50%; 
            object-fit: cover; 
        }
        
        /* Статус записи */
        .recording-status { 
            display: none; 
            align-items: center; 
            gap: 10px; 
            background: #f44336; 
            color: white; 
            padding: 8px 20px; 
            border-radius: 30px; 
            position: fixed;
            top: 80px;
            left: 50%;
            transform: translateX(-50%);
            z-index: 1000;
            box-shadow: 0 5px 15px rgba(244, 67, 54, 0.4);
            animation: slideDown 0.3s;
        }
        
        @keyframes slideDown {
            from { top: 60px; opacity: 0; }
            to { top: 80px; opacity: 1; }
        }
        
        .recording-status button {
            background: white;
            border: none;
            width: 35px;
            height: 35px;
            border-radius: 50%;
            cursor: pointer;
            font-size: 16px;
        }
        
        /* Модальное окно звонка */
        .call-modal { 
            position: fixed; 
            top: 0; 
            left: 0; 
            right: 0; 
            bottom: 0; 
            background: rgba(0,0,0,0.8); 
            display: none; 
            justify-content: center; 
            align-items: center; 
            z-index: 2000;
        }
        
        .call-content { 
            background: white; 
            padding: 40px 30px; 
            border-radius: 30px; 
            text-align: center; 
            width: 90%;
            max-width: 350px;
            animation: popIn 0.3s;
        }
        
        @keyframes popIn {
            from { transform: scale(0.8); opacity: 0; }
            to { transform: scale(1); opacity: 1; }
        }
        
        .call-content h3 {
            font-size: 24px;
            margin-bottom: 30px;
            color: #333;
        }
        
        .call-actions { 
            display: flex; 
            gap: 20px; 
            justify-content: center;
        }
        
        .accept, .reject {
            width: 70px;
            height: 70px;
            border-radius: 50%;
            border: none;
            font-size: 30px;
            cursor: pointer;
            display: flex;
            align-items: center;
            justify-content: center;
            transition: transform 0.2s;
        }
        
        .accept:active, .reject:active {
            transform: scale(0.95);
        }
        
        .accept { 
            background: #4caf50; 
            color: white; 
        }
        
        .reject { 
            background: #f44336; 
            color: white; 
        }
        
        /* Видео контейнер */
        #videoContainer { 
            position: fixed; 
            bottom: 20px; 
            right: 20px; 
            width: 120px; 
            background: black; 
            border-radius: 20px; 
            overflow: hidden; 
            display: none; 
            z-index: 1500;
            box-shadow: 0 5px 20px rgba(0,0,0,0.3);
        }
        
        #videoContainer video { 
            width: 100%; 
            height: auto;
        }
        
        #remoteVideo {
            position: fixed;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            object-fit: cover;
            z-index: 1400;
        }
        
        .record-btn { 
            background: #f44336 !important; 
            color: white;
            animation: pulse 1s infinite;
        }
        
        @keyframes pulse { 
            0% { transform: scale(1); } 
            50% { transform: scale(1.1); } 
        }
        
        .overlay {
            position: fixed;
            top: 0;
            left: 0;
            right: 0;
            bottom: 0;
            background: rgba(0,0,0,0.5);
            display: none;
            z-index: 999;
        }
        
        .overlay.active {
            display: block;
        }
    </style>
</head>
<body>
    <div class="login-container" id="loginContainer">
        <h1>Mobile Chat</h1>
        <input type="text" id="username" placeholder="Ваше имя" autocomplete="off">
        <button onclick="joinChat()">Войти</button>
    </div>

    <div class="chat-container" id="chatContainer">
        <div class="chat-header">
            <div class="header-left">
                <button class="menu-btn" onclick="toggleMenu()">☰</button>
                <h2>Общий чат</h2>
            </div>
            <div class="call-controls">
                <button class="call-btn" onclick="startCall()" id="startCallBtn">📞</button>
                <button class="call-btn" onclick="endCall()" id="endCallBtn" style="display:none;">🔴</button>
            </div>
        </div>
        
        <div class="overlay" id="overlay" onclick="toggleMenu()"></div>
        
        <div class="sidebar" id="sidebar">
            <div class="sidebar-header">
                <h3>Участники</h3>
                <p id="usersCount">0 онлайн</p>
            </div>
            <div class="users-list" id="usersList"></div>
        </div>

        <div class="messages" id="messages"></div>
        
        <div class="message-input-container">
            <div class="recording-status" id="recordingStatus">
                <span>🔴</span>
                <span id="recordingTimer">00:00</span>
                <button onclick="stopRecording()">⏹️</button>
            </div>
            
            <div class="message-input-wrapper">
                <button class="action-btn" onclick="recordVoice()" id="voiceBtn">🎤</button>
                <button class="action-btn" onclick="recordVideo()" id="videoBtn">📹</button>
                <input type="text" class="message-input" id="messageInput" placeholder="Сообщение..." 
                       onkeypress="if(event.key==='Enter') sendMessage()">
                <button class="send-btn" onclick="sendMessage()">➤</button>
            </div>
        </div>
    </div>

    <div class="call-modal" id="callModal">
        <div class="call-content">
            <h3 id="callerInfo">Входящий звонок</h3>
            <div class="call-actions">
                <button class="accept" onclick="acceptCall()">📞</button>
                <button class="reject" onclick="rejectCall()">❌</button>
            </div>
        </div>
    </div>

    <div id="videoContainer">
        <video id="localVideo" autoplay muted playsinline></video>
        <video id="remoteVideo" autoplay playsinline></video>
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
        let peerConnection = null;
        let currentCaller = null;

        function toggleMenu() {
            document.getElementById('sidebar').classList.toggle('active');
            document.getElementById('overlay').classList.toggle('active');
        }

        function joinChat() {
            username = document.getElementById('username').value.trim();
            if (username) {
                socket.emit('join', username);
                document.getElementById('loginContainer').style.display = 'none';
                document.getElementById('chatContainer').style.display = 'block';
            } else {
                alert('Введите имя');
            }
        }

        socket.on('user-joined', (data) => {
            currentUserId = data.userId;
            updateUsersList(data.users);
        });

        socket.on('users-update', (users) => {
            updateUsersList(users);
            document.getElementById('usersCount').textContent = users.length + ' онлайн';
        });

        socket.on('new-message', (msg) => {
            displayMessage(msg);
            vibrate();
        });

        socket.on('message-history', (history) => {
            history.forEach(msg => displayMessage(msg));
        });

        function vibrate() {
            if (window.navigator.vibrate) {
                window.navigator.vibrate(50);
            }
        }

        function updateUsersList(users) {
            const list = document.getElementById('usersList');
            list.innerHTML = '';
            users.forEach(user => {
                if (user.id !== currentUserId) {
                    list.innerHTML += `
                        <div class="user-item" onclick="showUserOptions('${user.id}', '${user.username}')">
                            <div class="user-avatar">${user.username[0].toUpperCase()}</div>
                            <div style="flex:1">
                                <div style="font-weight:600">${user.username}</div>
                                <div style="font-size:12px; color:#999">онлайн</div>
                            </div>
                        </div>
                    `;
                }
            });
        }

        function showUserOptions(userId, username) {
            if (confirm('Позвонить пользователю ' + username + '?')) {
                startCallTo(userId);
            }
        }

        function displayMessage(msg) {
            const messagesDiv = document.getElementById('messages');
            const messageDiv = document.createElement('div');
            messageDiv.className = 'message' + (msg.userId === currentUserId ? ' own' : '');
            
            let content = '';
            if (msg.type === 'text') {
                content = msg.text;
            } else if (msg.type === 'voice') {
                content = '<audio controls src="' + msg.url + '" style="max-width:200px"></audio>';
            } else if (msg.type === 'video') {
                content = '<video ' + (msg.isCircle ? 'class="video-circle"' : '') + ' controls src="' + msg.url + '" style="max-width:200px"></video>';
            }
            
            const time = new Date(msg.timestamp).toLocaleTimeString('ru-RU', {hour: '2-digit', minute:'2-digit'});
            
            messageDiv.innerHTML = `
                <div class="message-info">${msg.username} ${time}</div>
                <div class="message-content">${content}</div>
            `;
            messagesDiv.appendChild(messageDiv);
            messagesDiv.scrollTop = messagesDiv.scrollHeight;
        }

        function sendMessage() {
            const input = document.getElementById('messageInput');
            if (input.value.trim()) {
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
                const stream = await navigator.mediaDevices.getUserMedia({ 
                    video: { facingMode: 'user' }, 
                    audio: true 
                });
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
            
            mediaRecorder.ondataavailable = (e) => {
                if (e.data.size > 0) {
                    recordingChunks.push(e.data);
                }
            };
            
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
                document.getElementById('videoBtn').classList.remove('record-btn');
                document.getElementById('videoContainer').style.display = 'none';
                stream.getTracks().forEach(t => t.stop());
            };
            
            mediaRecorder.start();
            
            if (type === 'voice') {
                document.getElementById('voiceBtn').classList.add('record-btn');
            } else {
                document.getElementById('videoBtn').classList.add('record-btn');
            }
            
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
            const targetId = prompt('Введите ID пользователя для звонка:');
            if (targetId) {
                startCallTo(targetId);
            }
        }

        async function startCallTo(targetId) {
            try {
                localStream = await navigator.mediaDevices.getUserMedia({ 
                    video: { facingMode: 'user' }, 
                    audio: true 
                });
                
                document.getElementById('remoteVideo').style.display = 'block';
                document.getElementById('localVideo').style.display = 'block';
                document.getElementById('localVideo').srcObject = localStream;
                
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
                            target: targetId,
                            candidate: e.candidate
                        });
                    }
                };
                
                const offer = await peerConnection.createOffer();
                await peerConnection.setLocalDescription(offer);
                
                socket.emit('call-user', {
                    target: targetId,
                    offer: offer
                });
                
                document.getElementById('startCallBtn').style.display = 'none';
                document.getElementById('endCallBtn').style.display = 'inline-block';
                document.getElementById('videoContainer').style.display = 'block';
                
            } catch (err) {
                alert('Ошибка звонка: ' + err.message);
            }
        }

        function endCall() {
            if (peerConnection) {
                peerConnection.close();
                peerConnection = null;
            }
            if (localStream) {
                localStream.getTracks().forEach(t => t.stop());
                localStream = null;
            }
            document.getElementById('remoteVideo').style.display = 'none';
            document.getElementById('videoContainer').style.display = 'none';
            document.getElementById('startCallBtn').style.display = 'inline-block';
            document.getElementById('endCallBtn').style.display = 'none';
            socket.emit('end-call');
        }

        socket.on('incoming-call', async (data) => {
            currentCaller = data.from;
            document.getElementById('callerInfo').textContent = `Звонок от ${data.fromName}`;
            document.getElementById('callModal').style.display = 'flex';
            vibrate();
            
            if (data.offer) {
                try {
                    peerConnection = new RTCPeerConnection({
                        iceServers: [{ urls: 'stun:stun.l.google.com:19302' }]
                    });
                    
                    localStream = await navigator.mediaDevices.getUserMedia({ 
                        video: { facingMode: 'user' }, 
                        audio: true 
                    });
                    
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
                } catch (err) {
                    console.error('Error handling call:', err);
                }
            }
        });

        socket.on('call-answered', async (data) => {
            try {
                if (data.answer) {
                    await peerConnection.setRemoteDescription(new RTCSessionDescription(data.answer));
                }
                if (data.candidate) {
                    await peerConnection.addIceCandidate(new RTCIceCandidate(data.candidate));
                }
            } catch (err) {
                console.error('Error answering call:', err);
            }
        });

        socket.on('call-ended', () => {
            endCall();
        });

        function acceptCall() {
            document.getElementById('callModal').style.display = 'none';
            document.getElementById('remoteVideo').style.display = 'block';
            document.getElementById('videoContainer').style.display = 'block';
            document.getElementById('startCallBtn').style.display = 'none';
            document.getElementById('endCallBtn').style.display = 'inline-block';
        }

        function rejectCall() {
            document.getElementById('callModal').style.display = 'none';
            if (currentCaller) {
                socket.emit('reject-call', { target: currentCaller });
            }
            endCall();
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

        // Закрытие меню свайпом
        let touchStartX = 0;
        document.addEventListener('touchstart', (e) => {
            touchStartX = e.touches[0].clientX;
        });

        document.addEventListener('touchend', (e) => {
            const touchEndX = e.changedTouches[0].clientX;
            const sidebar = document.getElementById('sidebar');
            
            if (sidebar.classList.contains('active') && touchEndX - touchStartX < -50) {
                toggleMenu();
            }
        });

        // Обработка кнопки назад на Android
        window.addEventListener('popstate', () => {
            if (document.getElementById('sidebar').classList.contains('active')) {
                toggleMenu();
            }
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
        filename = f"uploads/{uuid.uuid4()}.{data['type']}"
        os.makedirs('uploads', exist_ok=True)
        
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
    
    emit('message-history', messages[-50:])
    
    emit('user-joined', {
        'userId': user_id,
        'users': list(users.values())
    }, broadcast=True)

@socketio.on('send-message')
def handle_message(data):
    if request.sid in users:
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
    if request.sid in users:
        filename = f"uploads/{uuid.uuid4()}.webm"
        os.makedirs('uploads', exist_ok=True)
        
        file_data = base64.b64decode(data['data'].split(',')[1])
        with open(filename, 'wb') as f:
            f.write(file_data)
        
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
    if data['target'] in users:
        emit('incoming-call', {
            'from': request.sid,
            'fromName': users[request.sid]['username'],
            'offer': data.get('offer'),
            'candidate': data.get('candidate')
        }, room=data['target'])

@socketio.on('call-answer')
def handle_answer(data):
    if data['target'] in users:
        emit('call-answered', {
            'answer': data.get('answer'),
            'candidate': data.get('candidate')
        }, room=data['target'])

@socketio.on('reject-call')
def handle_reject(data):
    if data['target'] in users:
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
