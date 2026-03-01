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
private_messages = {}  # {room_id: [messages]}

# HTML шаблон (встроенный)
HTML_TEMPLATE = '''
<!DOCTYPE html>
<html>
<head>
    <title>Python Messenger</title>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; -webkit-tap-highlight-color: transparent; }
        body { 
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); 
            min-height: 100vh; 
            display: flex; 
            justify-content: center; 
            align-items: center;
        }
        
        /* Мобильная адаптация */
        .login-container { 
            background: white; 
            border-radius: 20px; 
            padding: 30px 20px; 
            width: 90%; 
            max-width: 400px; 
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
            border: 2px solid #ddd; 
            border-radius: 12px; 
            font-size: 16px;
        }
        .login-container button { 
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); 
            color: white; 
            border: none; 
            padding: 15px; 
            border-radius: 12px; 
            cursor: pointer; 
            width: 100%; 
            font-size: 18px;
            font-weight: 600;
        }
        
        /* Чат контейнер - мобильная версия */
        .chat-container { 
            display: none; 
            width: 100%; 
            height: 100vh; 
            background: white; 
            position: relative;
        }
        
        /* Боковое меню (список чатов) */
        .sidebar { 
            position: fixed;
            left: -100%;
            top: 0;
            width: 85%;
            max-width: 350px;
            height: 100vh;
            background: #f8f9fa;
            transition: left 0.3s ease;
            z-index: 1000;
            box-shadow: 2px 0 10px rgba(0,0,0,0.1);
            overflow-y: auto;
        }
        .sidebar.active { left: 0; }
        
        .sidebar-header {
            padding: 20px;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
        }
        .sidebar-header h3 { font-size: 20px; margin-bottom: 5px; }
        .sidebar-header p { font-size: 14px; opacity: 0.9; }
        
        .chats-list { padding: 15px; }
        .chat-item {
            display: flex;
            align-items: center;
            padding: 15px;
            background: white;
            border-radius: 15px;
            margin-bottom: 10px;
            box-shadow: 0 2px 5px rgba(0,0,0,0.05);
            cursor: pointer;
            transition: transform 0.2s;
        }
        .chat-item:active { transform: scale(0.98); }
        .chat-item.active {
            background: linear-gradient(135deg, #667eea20 0%, #764ba220 100%);
            border: 2px solid #667eea;
        }
        .chat-avatar {
            width: 50px;
            height: 50px;
            border-radius: 50%;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            display: flex;
            align-items: center;
            justify-content: center;
            color: white;
            font-size: 20px;
            font-weight: bold;
            margin-right: 15px;
        }
        .chat-info { flex: 1; }
        .chat-name { font-weight: 600; font-size: 16px; margin-bottom: 3px; }
        .chat-last-msg { font-size: 13px; color: #666; }
        .chat-time { font-size: 11px; color: #999; }
        
        .users-section {
            padding: 15px;
            border-top: 1px solid #ddd;
        }
        .users-section h4 { margin-bottom: 15px; color: #333; }
        .user-item {
            display: flex;
            align-items: center;
            padding: 12px;
            background: white;
            border-radius: 12px;
            margin-bottom: 8px;
            cursor: pointer;
        }
        .user-avatar {
            width: 40px;
            height: 40px;
            border-radius: 50%;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            display: flex;
            align-items: center;
            justify-content: center;
            color: white;
            margin-right: 12px;
        }
        .user-status {
            width: 10px;
            height: 10px;
            border-radius: 50%;
            background: #4caf50;
            margin-left: auto;
        }
        
        /* Основной чат */
        .main-chat { 
            display: flex;
            flex-direction: column;
            height: 100vh;
            background: #f5f7fb;
        }
        
        .chat-header { 
            padding: 15px 20px; 
            background: white; 
            border-bottom: 1px solid #eee;
            display: flex;
            align-items: center;
            box-shadow: 0 2px 10px rgba(0,0,0,0.05);
        }
        .menu-btn {
            font-size: 24px;
            background: none;
            border: none;
            margin-right: 15px;
            cursor: pointer;
            padding: 5px 10px;
        }
        .chat-title {
            flex: 1;
            font-size: 18px;
            font-weight: 600;
        }
        .chat-title small {
            font-size: 13px;
            font-weight: normal;
            color: #666;
            margin-left: 5px;
        }
        
        .messages { 
            flex: 1; 
            overflow-y: auto; 
            padding: 20px;
            display: flex;
            flex-direction: column;
        }
        
        .message { 
            margin-bottom: 15px; 
            max-width: 85%;
            animation: fadeIn 0.3s;
        }
        @keyframes fadeIn { from { opacity: 0; transform: translateY(10px); } to { opacity: 1; transform: translateY(0); } }
        
        .message.own { 
            margin-left: auto; 
        }
        
        .message-content { 
            background: white; 
            padding: 12px 16px; 
            border-radius: 20px 20px 20px 5px; 
            box-shadow: 0 1px 3px rgba(0,0,0,0.1);
            word-wrap: break-word;
        }
        .message.own .message-content { 
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); 
            color: white;
            border-radius: 20px 20px 5px 20px;
        }
        
        .message-info { 
            font-size: 11px; 
            color: #666; 
            margin-bottom: 5px;
            padding-left: 5px;
        }
        .message.own .message-info { 
            text-align: right; 
            padding-right: 5px;
        }
        
        .message-input { 
            padding: 15px 20px; 
            background: white; 
            border-top: 1px solid #eee;
            display: flex;
            align-items: center;
            gap: 8px;
        }
        .message-input input { 
            flex: 1; 
            padding: 12px 18px; 
            border: 2px solid #eee; 
            border-radius: 25px; 
            font-size: 16px;
            background: #f8f9fa;
        }
        .message-input input:focus {
            outline: none;
            border-color: #667eea;
        }
        
        .action-btns {
            display: flex;
            gap: 5px;
        }
        .action-btn {
            width: 45px;
            height: 45px;
            border-radius: 50%;
            border: none;
            background: #f0f2f5;
            cursor: pointer;
            font-size: 20px;
            display: flex;
            align-items: center;
            justify-content: center;
        }
        .action-btn:active { background: #e0e2e5; }
        
        .recording-status {
            display: none;
            align-items: center;
            gap: 10px;
            background: #f44336;
            color: white;
            padding: 8px 15px;
            border-radius: 25px;
            font-size: 14px;
        }
        
        /* Модальные окна */
        .modal-overlay {
            position: fixed;
            top: 0;
            left: 0;
            right: 0;
            bottom: 0;
            background: rgba(0,0,0,0.5);
            display: none;
            justify-content: center;
            align-items: center;
            z-index: 2000;
            padding: 20px;
        }
        .modal-content {
            background: white;
            border-radius: 20px;
            padding: 25px;
            width: 100%;
            max-width: 400px;
            max-height: 80vh;
            overflow-y: auto;
        }
        
        .call-modal .modal-content {
            text-align: center;
        }
        .caller-name {
            font-size: 24px;
            margin: 20px 0;
        }
        .call-actions {
            display: flex;
            gap: 20px;
            justify-content: center;
            margin-top: 20px;
        }
        .accept, .reject {
            padding: 15px 30px;
            border: none;
            border-radius: 30px;
            font-size: 18px;
            font-weight: 600;
            cursor: pointer;
        }
        .accept { background: #4caf50; color: white; }
        .reject { background: #f44336; color: white; }
        
        /* Видео контейнер */
        #videoContainer {
            position: fixed;
            bottom: 80px;
            right: 20px;
            width: 120px;
            background: black;
            border-radius: 15px;
            overflow: hidden;
            display: none;
            box-shadow: 0 5px 20px rgba(0,0,0,0.3);
            z-index: 1500;
        }
        #videoContainer video {
            width: 100%;
            display: block;
        }
        #remoteVideo {
            position: fixed;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            object-fit: cover;
            z-index: 1400;
            background: black;
        }
        
        /* Аудио и видео плееры */
        audio, video { max-width: 100%; border-radius: 10px; }
        .video-circle { width: 150px; height: 150px; border-radius: 50%; object-fit: cover; }
        
        /* Оверлей для бокового меню */
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
        .overlay.active { display: block; }
        
        .record-btn { background: #f44336; color: white; animation: pulse 1s infinite; }
        @keyframes pulse { 0% { transform: scale(1); } 50% { transform: scale(1.1); } }
        
        /* Индикатор непрочитанных */
        .unread-badge {
            background: #f44336;
            color: white;
            border-radius: 50%;
            min-width: 20px;
            height: 20px;
            font-size: 12px;
            display: flex;
            align-items: center;
            justify-content: center;
            margin-left: 10px;
        }
    </style>
</head>
<body>
    <div class="login-container" id="loginContainer">
        <h1>Python Messenger</h1>
        <input type="text" id="username" placeholder="Ваше имя" autocomplete="off">
        <button onclick="joinChat()">Войти</button>
    </div>

    <div class="chat-container" id="chatContainer">
        <!-- Оверлей для закрытия меню -->
        <div class="overlay" id="overlay" onclick="toggleSidebar()"></div>
        
        <!-- Боковое меню -->
        <div class="sidebar" id="sidebar">
            <div class="sidebar-header">
                <h3 id="sidebarUsername"></h3>
                <p>Online: <span id="onlineCount">0</span></p>
            </div>
            
            <div class="chats-list" id="chatsList">
                <div class="chat-item active" onclick="switchChat('general')">
                    <div class="chat-avatar">#</div>
                    <div class="chat-info">
                        <div class="chat-name">Общий чат</div>
                        <div class="chat-last-msg" id="generalLastMsg">...</div>
                    </div>
                </div>
            </div>
            
            <div class="users-section">
                <h4>Участники онлайн</h4>
                <div id="usersList"></div>
            </div>
        </div>

        <!-- Основной чат -->
        <div class="main-chat">
            <div class="chat-header">
                <button class="menu-btn" onclick="toggleSidebar()">☰</button>
                <div class="chat-title" id="currentChatTitle">Общий чат</div>
                <div class="call-controls">
                    <button class="action-btn" onclick="startCall()" id="startCallBtn" style="display:none;">📞</button>
                    <button class="action-btn" onclick="endCall()" id="endCallBtn" style="display:none;">🔴</button>
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
                    <button class="action-btn" onclick="stopRecording()" style="background: none; color: white;">⏹️</button>
                </div>
                <input type="text" id="messageInput" placeholder="Сообщение..." onkeypress="if(event.key==='Enter') sendMessage()">
                <button class="action-btn" onclick="sendMessage()">➤</button>
            </div>
        </div>
    </div>

    <!-- Модальное окно звонка -->
    <div class="modal-overlay" id="callModal">
        <div class="modal-content">
            <h3>Входящий звонок</h3>
            <div class="caller-name" id="callerInfo"></div>
            <div class="call-actions">
                <button class="accept" onclick="acceptCall()">Принять</button>
                <button class="reject" onclick="rejectCall()">Отклонить</button>
            </div>
        </div>
    </div>

    <!-- Видео контейнеры -->
    <div id="videoContainer">
        <video id="localVideo" autoplay muted playsinline></video>
    </div>
    <video id="remoteVideo" autoplay playsinline style="display: none;"></video>

    <script src="https://cdn.socket.io/4.5.4/socket.io.min.js"></script>
    <script>
        let socket = io();
        let username = '';
        let currentUserId = '';
        let currentChat = 'general'; // 'general' или userId
        let privateChats = {}; // {userId: {messages: [], unread: 0}}
        
        // Медиа переменные
        let mediaRecorder = null;
        let recordingChunks = [];
        let recordingTimer = null;
        let seconds = 0;
        let localStream = null;
        let peerConnection = null;
        let currentCaller = null;

        function joinChat() {
            username = document.getElementById('username').value.trim();
            if (username) {
                socket.emit('join', username);
                document.getElementById('loginContainer').style.display = 'none';
                document.getElementById('chatContainer').style.display = 'flex';
                document.getElementById('sidebarUsername').textContent = username;
            }
        }

        function toggleSidebar() {
            const sidebar = document.getElementById('sidebar');
            const overlay = document.getElementById('overlay');
            sidebar.classList.toggle('active');
            overlay.classList.toggle('active');
        }

        // Переключение чата
        function switchChat(chatId) {
            currentChat = chatId;
            
            // Обновляем заголовок
            const title = chatId === 'general' ? 'Общий чат' : (privateChats[chatId]?.username || 'Пользователь');
            document.getElementById('currentChatTitle').innerHTML = title + 
                (chatId !== 'general' ? ' <small>Личный чат</small>' : '');
            
            // Очищаем сообщения
            document.getElementById('messages').innerHTML = '';
            
            // Загружаем историю
            if (chatId === 'general') {
                socket.emit('get-history', { room: 'general' });
            } else {
                socket.emit('get-private-history', { userId: chatId });
                // Сбрасываем счетчик непрочитанных
                if (privateChats[chatId]) {
                    privateChats[chatId].unread = 0;
                }
            }
            
            // Обновляем активный чат в списке
            document.querySelectorAll('.chat-item').forEach(item => {
                item.classList.remove('active');
                if (item.dataset.chatId === chatId) {
                    item.classList.add('active');
                }
            });
            
            // Показываем/скрываем кнопку звонка
            document.getElementById('startCallBtn').style.display = chatId !== 'general' ? 'block' : 'none';
            
            toggleSidebar(); // Закрываем меню после выбора
        }

        socket.on('user-joined', (data) => {
            currentUserId = data.userId;
            updateUsersList(data.users);
        });

        socket.on('users-update', (users) => {
            updateUsersList(users);
        });

        function updateUsersList(users) {
            const list = document.getElementById('usersList');
            const onlineCount = document.getElementById('onlineCount');
            onlineCount.textContent = users.length;
            
            list.innerHTML = '';
            users.forEach(user => {
                if (user.id !== currentUserId) {
                    const userDiv = document.createElement('div');
                    userDiv.className = 'user-item';
                    userDiv.onclick = () => startPrivateChat(user);
                    userDiv.innerHTML = `
                        <div class="user-avatar">${user.username[0]}</div>
                        <div style="flex: 1">${user.username}</div>
                        <div class="user-status"></div>
                    `;
                    list.appendChild(userDiv);
                }
            });
        }

        // Начать личный чат
        function startPrivateChat(user) {
            if (!privateChats[user.id]) {
                privateChats[user.id] = {
                    id: user.id,
                    username: user.username,
                    messages: [],
                    unread: 0
                };
                
                // Добавляем в список чатов
                const chatsList = document.getElementById('chatsList');
                const chatItem = document.createElement('div');
                chatItem.className = 'chat-item';
                chatItem.dataset.chatId = user.id;
                chatItem.onclick = () => switchChat(user.id);
                chatItem.innerHTML = `
                    <div class="chat-avatar">${user.username[0]}</div>
                    <div class="chat-info">
                        <div class="chat-name">${user.username}</div>
                        <div class="chat-last-msg" id="lastMsg-${user.id}"></div>
                    </div>
                    <div class="unread-badge" id="unread-${user.id}" style="display: none;">0</div>
                `;
                chatsList.appendChild(chatItem);
            }
            
            switchChat(user.id);
        }

        // Обработка сообщений
        socket.on('new-message', (msg) => {
            if (msg.room === 'general' || !msg.room) {
                if (currentChat === 'general') {
                    displayMessage(msg);
                }
                updateLastMessage('general', msg);
            } else {
                // Личное сообщение
                const otherUserId = msg.from === currentUserId ? msg.to : msg.from;
                
                if (!privateChats[otherUserId]) {
                    // Находим пользователя
                    const user = Object.values(users).find(u => u.id === otherUserId);
                    if (user) {
                        startPrivateChat(user);
                    }
                }
                
                if (privateChats[otherUserId]) {
                    privateChats[otherUserId].messages.push(msg);
                    
                    if (currentChat === otherUserId) {
                        displayMessage(msg);
                    } else {
                        privateChats[otherUserId].unread++;
                        document.getElementById(`unread-${otherUserId}`).style.display = 'flex';
                        document.getElementById(`unread-${otherUserId}`).textContent = 
                            privateChats[otherUserId].unread;
                    }
                    
                    updateLastMessage(otherUserId, msg);
                }
            }
        });

        socket.on('private-history', (data) => {
            data.messages.forEach(msg => {
                if (!privateChats[data.userId]) {
                    const user = Object.values(users).find(u => u.id === data.userId);
                    if (user) startPrivateChat(user);
                }
                displayMessage(msg);
            });
        });

        socket.on('message-history', (history) => {
            history.forEach(msg => displayMessage(msg));
        });

        function updateLastMessage(chatId, msg) {
            const lastMsgEl = document.getElementById(chatId === 'general' ? 'generalLastMsg' : `lastMsg-${chatId}`);
            if (lastMsgEl) {
                let text = msg.type === 'text' ? msg.text : 
                          (msg.type === 'voice' ? '🎤 Голосовое' : '📹 Видео');
                lastMsgEl.textContent = text.substring(0, 20) + (text.length > 20 ? '...' : '');
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
                content = '<audio controls src="' + msg.url + '"></audio>';
            } else if (msg.type === 'video') {
                content = '<video ' + (msg.isCircle ? 'class="video-circle"' : 'controls') + ' src="' + msg.url + '"></video>';
            }
            
            const time = new Date(msg.timestamp).toLocaleTimeString().slice(0,5);
            
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
                if (currentChat === 'general') {
                    socket.emit('send-message', { 
                        text: input.value, 
                        type: 'text',
                        room: 'general'
                    });
                } else {
                    socket.emit('send-private-message', {
                        to: currentChat,
                        text: input.value,
                        type: 'text'
                    });
                }
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

        async function recordVideo() {
            try {
                const stream = await navigator.mediaDevices.getUserMedia({ 
                    video: { facingMode: 'user' }, 
                    audio: true 
                });
                document.getElementById('localVideo').srcObject = stream;
                document.getElementById('videoContainer').style.display = 'block';
                startRecording(stream, 'video');
            } catch (err) {
                alert('Нет доступа к камере');
            }
        }

        function startRecording(stream, type) {
            recordingChunks = [];
            mediaRecorder = new MediaRecorder(stream, {
                mimeType: type === 'voice' ? 'audio/webm' : 'video/webm'
            });
            
            mediaRecorder.ondataavailable = (e) => recordingChunks.push(e.data);
            
            mediaRecorder.onstop = () => {
                const blob = new Blob(recordingChunks, { type: type === 'voice' ? 'audio/webm' : 'video/webm' });
                const reader = new FileReader();
                reader.readAsDataURL(blob);
                reader.onloadend = () => {
                    if (currentChat === 'general') {
                        socket.emit('upload-file', {
                            data: reader.result,
                            type: type,
                            isCircle: type === 'video',
                            room: 'general'
                        });
                    } else {
                        socket.emit('upload-private-file', {
                            to: currentChat,
                            data: reader.result,
                            type: type,
                            isCircle: type === 'video'
                        });
                    }
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
            if (currentChat === 'general') {
                alert('Звонки доступны только в личных чатах');
                return;
            }
            
            try {
                localStream = await navigator.mediaDevices.getUserMedia({ 
                    video: { facingMode: 'user' }, 
                    audio: true 
                });
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
                    document.getElementById('remoteVideo').style.display = 'block';
                };
                
                peerConnection.onicecandidate = (e) => {
                    if (e.candidate) {
                        socket.emit('call-user', {
                            target: currentChat,
                            candidate: e.candidate
                        });
                    }
                };
                
                const offer = await peerConnection.createOffer();
                await peerConnection.setLocalDescription(offer);
                
                socket.emit('call-user', {
                    target: currentChat,
                    offer: offer
                });
                
                document.getElementById('startCallBtn').style.display = 'none';
                document.getElementById('endCallBtn').style.display = 'block';
                
            } catch (err) {
                alert('Ошибка звонка: ' + err.message);
            }
        }

        function endCall() {
            if (peerConnection) peerConnection.close();
            if (localStream) localStream.getTracks().forEach(t => t.stop());
            document.getElementById('videoContainer').style.display = 'none';
            document.getElementById('remoteVideo').style.display = 'none';
            document.getElementById('startCallBtn').style.display = 'block';
            document.getElementById('endCallBtn').style.display = 'none';
            socket.emit('end-call');
        }

        socket.on('incoming-call', async (data) => {
            currentCaller = data.from;
            document.getElementById('callerInfo').textContent = data.fromName;
            document.getElementById('callModal').style.display = 'flex';
            
            if (data.offer) {
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
                    document.getElementById('remoteVideo').style.display = 'block';
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

        socket.on('call-rejected', () => {
            alert('Звонок отклонен');
            endCall();
        });

        function acceptCall() {
            document.getElementById('callModal').style.display = 'none';
            document.getElementById('videoContainer').style.display = 'block';
            document.getElementById('startCallBtn').style.display = 'none';
            document.getElementById('endCallBtn').style.display = 'block';
        }

        function rejectCall() {
            document.getElementById('callModal').style.display = 'none';
            socket.emit('reject-call', { target: currentCaller });
        }

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

        // Обработка свайпов для мобильных
        let touchStartX = 0;
        document.addEventListener('touchstart', (e) => {
            touchStartX = e.touches[0].clientX;
        });

        document.addEventListener('touchend', (e) => {
            const touchEndX = e.changedTouches[0].clientX;
            const sidebar = document.getElementById('sidebar');
            
            if (touchStartX < 30 && touchEndX > 150 && !sidebar.classList.contains('active')) {
                toggleSidebar();
            } else if (touchStartX > window.innerWidth - 30 && touchEndX < window.innerWidth - 150 && sidebar.classList.contains('active')) {
                toggleSidebar();
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
    msg = {
        'id': str(uuid.uuid4()),
        'userId': request.sid,
        'username': users[request.sid]['username'],
        'text': data.get('text', ''),
        'type': data.get('type', 'text'),
        'url': data.get('url'),
        'isCircle': data.get('isCircle', False),
        'room': data.get('room', 'general'),
        'timestamp': datetime.now().isoformat()
    }
    messages.append(msg)
    emit('new-message', msg, broadcast=True)

@socketio.on('send-private-message')
def handle_private_message(data):
    msg = {
        'id': str(uuid.uuid4()),
        'from': request.sid,
        'to': data['to'],
        'username': users[request.sid]['username'],
        'text': data.get('text', ''),
        'type': data.get('type', 'text'),
        'url': data.get('url'),
        'isCircle': data.get('isCircle', False),
        'timestamp': datetime.now().isoformat()
    }
    
    # Сохраняем в приватный чат
    room_id = tuple(sorted([request.sid, data['to']]))
    if room_id not in private_messages:
        private_messages[room_id] = []
    private_messages[room_id].append(msg)
    
    # Отправляем обоим участникам
    emit('new-message', msg, room=request.sid)
    emit('new-message', msg, room=data['to'])

@socketio.on('get-private-history')
def handle_private_history(data):
    room_id = tuple(sorted([request.sid, data['userId']]))
    history = private_messages.get(room_id, [])
    emit('private-history', {
        'userId': data['userId'],
        'messages': history[-50:]
    })

@socketio.on('get-history')
def handle_history(data):
    emit('message-history', messages[-50:])

@socketio.on('upload-file')
def handle_upload(data):
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
        'room': data.get('room', 'general'),
        'timestamp': datetime.now().isoformat()
    }
    messages.append(msg)
    emit('new-message', msg, broadcast=True)

@socketio.on('upload-private-file')
def handle_private_upload(data):
    filename = f"uploads/{uuid.uuid4()}.webm"
    os.makedirs('uploads', exist_ok=True)
    
    file_data = base64.b64decode(data['data'].split(',')[1])
    with open(filename, 'wb') as f:
        f.write(file_data)
    
    msg = {
        'id': str(uuid.uuid4()),
        'from': request.sid,
        'to': data['to'],
        'username': users[request.sid]['username'],
        'type': data['type'],
        'url': '/' + filename,
        'isCircle': data.get('isCircle', False),
        'timestamp': datetime.now().isoformat()
    }
    
    room_id = tuple(sorted([request.sid, data['to']]))
    if room_id not in private_messages:
        private_messages[room_id] = []
    private_messages[room_id].append(msg)
    
    emit('new-message', msg, room=request.sid)
    emit('new-message', msg, room=data['to'])

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
