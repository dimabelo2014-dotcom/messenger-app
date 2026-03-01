from flask import Flask, render_template, request, jsonify, send_file, session, redirect, url_for
from flask_socketio import SocketIO, emit, join_room, leave_room
import os
import json
import base64
import time
import uuid
from datetime import datetime
import threading
import hashlib
import sqlite3

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your-secret-key-here'
app.config['SESSION_TYPE'] = 'filesystem'
socketio = SocketIO(app, cors_allowed_origins="*")

# Инициализация базы данных
def init_db():
    conn = sqlite3.connect('chat.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS users
                 (id TEXT PRIMARY KEY, username TEXT UNIQUE, password TEXT, avatar TEXT, created_at TIMESTAMP)''')
    c.execute('''CREATE TABLE IF NOT EXISTS messages
                 (id TEXT PRIMARY KEY, from_user TEXT, to_user TEXT, content TEXT, type TEXT, 
                  file_url TEXT, timestamp TIMESTAMP, is_read BOOLEAN)''')
    conn.commit()
    conn.close()

init_db()

# Временное хранилище онлайн пользователей
online_users = {}

# Множество для отслеживания обработанных сообщений
processed_messages = set()

# HTML шаблон
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
        
        /* Аутентификация */
        .auth-container { 
            background: white; 
            border-radius: 20px; 
            padding: 30px 20px; 
            width: 90%; 
            max-width: 350px; 
            margin: 20px;
            box-shadow: 0 10px 40px rgba(0,0,0,0.2);
        }
        
        .auth-tabs {
            display: flex;
            margin-bottom: 30px;
            border-bottom: 2px solid #eee;
        }
        
        .auth-tab {
            flex: 1;
            text-align: center;
            padding: 10px;
            cursor: pointer;
            color: #999;
            font-weight: 600;
        }
        
        .auth-tab.active {
            color: #667eea;
            border-bottom: 2px solid #667eea;
        }
        
        .auth-form { 
            display: none;
        }
        
        .auth-form.active {
            display: block;
        }
        
        .auth-form h1 { 
            margin-bottom: 30px; 
            color: #333; 
            font-size: 28px;
            text-align: center;
        }
        
        .auth-form input { 
            width: 100%; 
            padding: 15px; 
            margin-bottom: 15px; 
            border: 2px solid #eee; 
            border-radius: 30px; 
            font-size: 16px;
            outline: none;
            transition: border-color 0.3s;
        }
        
        .auth-form input:focus {
            border-color: #667eea;
        }
        
        .auth-form button { 
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); 
            color: white; 
            border: none; 
            padding: 15px 30px; 
            border-radius: 30px; 
            cursor: pointer; 
            width: 100%; 
            font-size: 16px;
            font-weight: 600;
            margin-top: 10px;
            box-shadow: 0 5px 15px rgba(102, 126, 234, 0.4);
        }
        
        .error-message {
            color: #f44336;
            font-size: 14px;
            margin-top: 10px;
            text-align: center;
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
        
        .current-chat-info {
            display: flex;
            flex-direction: column;
        }
        
        .current-chat-name {
            font-size: 16px;
            font-weight: 600;
        }
        
        .current-chat-status {
            font-size: 12px;
            opacity: 0.8;
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
        
        .call-btn.active {
            background: #f44336;
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
            margin-bottom: 5px;
        }
        
        .sidebar-header p {
            font-size: 14px;
            opacity: 0.9;
        }
        
        .logout-btn {
            position: absolute;
            top: 20px;
            right: 20px;
            background: rgba(255,255,255,0.2);
            border: none;
            color: white;
            padding: 8px 15px;
            border-radius: 20px;
            cursor: pointer;
            font-size: 14px;
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
            cursor: pointer;
            transition: transform 0.2s;
        }
        
        .user-item:active {
            transform: scale(0.98);
        }
        
        .user-item.selected {
            border: 2px solid #667eea;
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
        
        .user-info {
            flex: 1;
        }
        
        .user-name {
            font-weight: 600;
            margin-bottom: 5px;
        }
        
        .user-status {
            font-size: 12px;
            color: #4caf50;
        }
        
        .user-status.offline {
            color: #999;
        }
        
        .unread-badge {
            background: #f44336;
            color: white;
            border-radius: 50%;
            width: 20px;
            height: 20px;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 12px;
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
        
        .empty-chat {
            text-align: center;
            color: #999;
            margin-top: 50px;
            font-style: italic;
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
        
        .message-time {
            font-size: 10px;
            opacity: 0.7;
            margin-top: 5px;
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
        
        /* Аудио сообщения */
        audio { 
            max-width: 200px; 
            height: 40px;
            border-radius: 20px;
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
            background: rgba(0,0,0,0.9); 
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
        
        .call-avatar {
            width: 100px;
            height: 100px;
            border-radius: 50%;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            margin: 0 auto 20px;
            display: flex;
            align-items: center;
            justify-content: center;
            color: white;
            font-size: 40px;
        }
        
        .call-content h3 {
            font-size: 24px;
            margin-bottom: 10px;
            color: #333;
        }
        
        .call-status {
            color: #666;
            margin-bottom: 30px;
            font-size: 16px;
        }
        
        .call-actions { 
            display: flex; 
            gap: 30px; 
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
            transition: transform 0.2s, box-shadow 0.2s;
        }
        
        .accept:active, .reject:active {
            transform: scale(0.95);
        }
        
        .accept { 
            background: #4caf50; 
            color: white; 
            box-shadow: 0 5px 15px rgba(76, 175, 80, 0.4);
        }
        
        .reject { 
            background: #f44336; 
            color: white;
            box-shadow: 0 5px 15px rgba(244, 67, 54, 0.4);
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
        
        /* Адаптация для iPhone */
        @supports (padding: max(0px)) {
            .chat-header {
                padding-top: max(15px, env(safe-area-inset-top));
            }
            
            .messages {
                padding-top: max(80px, calc(env(safe-area-inset-top) + 60px));
                padding-bottom: max(100px, calc(env(safe-area-inset-bottom) + 80px));
            }
            
            .message-input-container {
                padding-bottom: max(15px, env(safe-area-inset-bottom));
            }
        }
    </style>
</head>
<body>
    <div class="auth-container" id="authContainer">
        <div class="auth-tabs">
            <div class="auth-tab active" onclick="switchTab('login')">Вход</div>
            <div class="auth-tab" onclick="switchTab('register')">Регистрация</div>
        </div>
        
        <div class="auth-form active" id="loginForm">
            <h1>Вход</h1>
            <input type="text" id="loginUsername" placeholder="Имя пользователя" autocomplete="off">
            <input type="password" id="loginPassword" placeholder="Пароль">
            <button onclick="login()">Войти</button>
            <div class="error-message" id="loginError"></div>
        </div>
        
        <div class="auth-form" id="registerForm">
            <h1>Регистрация</h1>
            <input type="text" id="regUsername" placeholder="Имя пользователя" autocomplete="off">
            <input type="password" id="regPassword" placeholder="Пароль">
            <input type="password" id="regConfirmPassword" placeholder="Подтвердите пароль">
            <button onclick="register()">Зарегистрироваться</button>
            <div class="error-message" id="registerError"></div>
        </div>
    </div>

    <div class="chat-container" id="chatContainer">
        <div class="chat-header">
            <div class="header-left">
                <button class="menu-btn" onclick="toggleMenu()">☰</button>
                <div class="current-chat-info">
                    <span class="current-chat-name" id="currentChatName">Выберите чат</span>
                    <span class="current-chat-status" id="currentChatStatus"></span>
                </div>
            </div>
            <div class="call-controls">
                <button class="call-btn" onclick="startAudioCall()" id="startCallBtn" style="display:none;">📞</button>
                <button class="call-btn active" onclick="endCall()" id="endCallBtn" style="display:none;">🔴</button>
            </div>
        </div>
        
        <div class="overlay" id="overlay" onclick="toggleMenu()"></div>
        
        <div class="sidebar" id="sidebar">
            <div class="sidebar-header">
                <h3 id="currentUsername"></h3>
                <p id="usersCount">0 пользователей</p>
                <button class="logout-btn" onclick="logout()">Выйти</button>
            </div>
            <div class="users-list" id="usersList"></div>
        </div>

        <div class="messages" id="messages">
            <div class="empty-chat">Выберите пользователя для начала общения</div>
        </div>
        
        <div class="message-input-container">
            <div class="recording-status" id="recordingStatus">
                <span>🔴</span>
                <span id="recordingTimer">00:00</span>
                <button onclick="stopRecording()">⏹️</button>
            </div>
            
            <div class="message-input-wrapper">
                <button class="action-btn" onclick="recordVoice()" id="voiceBtn">🎤</button>
                <input type="text" class="message-input" id="messageInput" placeholder="Сообщение..." 
                       onkeypress="if(event.key==='Enter') sendMessage()" disabled>
                <button class="send-btn" onclick="sendMessage()">➤</button>
            </div>
        </div>
    </div>

    <div class="call-modal" id="callModal">
        <div class="call-content">
            <div class="call-avatar" id="callerAvatar"></div>
            <h3 id="callerInfo">Входящий звонок</h3>
            <div class="call-status" id="callStatus">Ожидание...</div>
            <div class="call-actions" id="callActions">
                <button class="accept" onclick="acceptCall()">📞</button>
                <button class="reject" onclick="rejectCall()">❌</button>
            </div>
        </div>
    </div>

    <script src="https://cdn.socket.io/4.5.4/socket.io.min.js"></script>
    <script>
        let socket = null;
        let currentUser = null;
        let selectedUser = null;
        let mediaRecorder = null;
        let recordingChunks = [];
        let recordingTimer = null;
        let seconds = 0;
        let currentCall = null;
        let peerConnection = null;
        let localStream = null;
        let remoteAudio = null;
        
        // Множество для отслеживания отображенных сообщений
        let displayedMessageIds = new Set();

        function switchTab(tab) {
            document.querySelectorAll('.auth-tab').forEach(t => t.classList.remove('active'));
            document.querySelectorAll('.auth-form').forEach(f => f.classList.remove('active'));
            
            if (tab === 'login') {
                document.querySelector('.auth-tab').classList.add('active');
                document.getElementById('loginForm').classList.add('active');
            } else {
                document.querySelectorAll('.auth-tab')[1].classList.add('active');
                document.getElementById('registerForm').classList.add('active');
            }
        }

        async function register() {
            const username = document.getElementById('regUsername').value.trim();
            const password = document.getElementById('regPassword').value;
            const confirm = document.getElementById('regConfirmPassword').value;
            
            if (!username || !password) {
                showError('register', 'Заполните все поля');
                return;
            }
            
            if (password !== confirm) {
                showError('register', 'Пароли не совпадают');
                return;
            }
            
            try {
                const response = await fetch('/register', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({username, password})
                });
                
                const data = await response.json();
                if (response.ok) {
                    alert('Регистрация успешна! Теперь войдите.');
                    switchTab('login');
                    document.getElementById('loginUsername').value = username;
                } else {
                    showError('register', data.error);
                }
            } catch (err) {
                showError('register', 'Ошибка соединения');
            }
        }

        async function login() {
            const username = document.getElementById('loginUsername').value.trim();
            const password = document.getElementById('loginPassword').value;
            
            if (!username || !password) {
                showError('login', 'Заполните все поля');
                return;
            }
            
            try {
                const response = await fetch('/login', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({username, password})
                });
                
                const data = await response.json();
                if (response.ok) {
                    currentUser = data.user;
                    document.getElementById('currentUsername').textContent = currentUser.username;
                    document.getElementById('authContainer').style.display = 'none';
                    document.getElementById('chatContainer').style.display = 'block';
                    
                    // Очищаем множество сообщений при входе
                    displayedMessageIds.clear();
                    
                    // Инициализируем socket после логина
                    socket = io();
                    setupSocketListeners();
                    
                    // Отправляем событие о том, что пользователь онлайн
                    socket.emit('user-online', currentUser);
                    
                    // Загружаем список пользователей
                    loadUsers();
                } else {
                    showError('login', data.error);
                }
            } catch (err) {
                showError('login', 'Ошибка соединения');
            }
        }

        function showError(form, message) {
            document.getElementById(form + 'Error').textContent = message;
        }

        function setupSocketListeners() {
            socket.on('connect', () => {
                console.log('Socket connected');
            });

            socket.on('users-online', (users) => {
                updateUsersList(users);
            });

            socket.on('private-message', (msg) => {
                console.log('Received message:', msg);
                
                // Проверяем, не было ли это сообщение уже отображено
                if (!displayedMessageIds.has(msg.id)) {
                    // Проверяем, относится ли сообщение к текущему чату
                    if (selectedUser && (msg.from === selectedUser.id || msg.from === currentUser.id)) {
                        displayMessage(msg);
                        displayedMessageIds.add(msg.id);
                    }
                    
                    // Обновляем счетчик непрочитанных, если сообщение от другого пользователя
                    if (msg.from !== currentUser.id && (!selectedUser || selectedUser.id !== msg.from)) {
                        updateUnreadCount(msg.from);
                    }
                }
            });

            socket.on('message-history', (messages) => {
                document.getElementById('messages').innerHTML = '';
                displayedMessageIds.clear();
                
                if (messages.length === 0) {
                    document.getElementById('messages').innerHTML = '<div class="empty-chat">Нет сообщений</div>';
                } else {
                    messages.forEach(msg => {
                        displayMessage(msg);
                        displayedMessageIds.add(msg.id);
                    });
                }
            });

            socket.on('incoming-call', (data) => {
                console.log('Incoming call:', data);
                showIncomingCall(data);
            });

            socket.on('call-accepted', (data) => {
                console.log('Call accepted');
                if (data.answer) {
                    peerConnection.setRemoteDescription(new RTCSessionDescription(data.answer));
                }
                startCall();
            });

            socket.on('call-rejected', () => {
                console.log('Call rejected');
                hideCallModal();
                alert('Звонок отклонен');
                endCall();
            });

            socket.on('call-ended', () => {
                console.log('Call ended');
                endCall();
            });

            socket.on('call-signal', async (data) => {
                console.log('Call signal:', data);
                if (data.candidate && peerConnection) {
                    try {
                        await peerConnection.addIceCandidate(new RTCIceCandidate(data.candidate));
                    } catch (e) {
                        console.error('Error adding ice candidate', e);
                    }
                }
            });
        }

        function toggleMenu() {
            document.getElementById('sidebar').classList.toggle('active');
            document.getElementById('overlay').classList.toggle('active');
        }

        async function loadUsers() {
            try {
                const response = await fetch('/users');
                const users = await response.json();
                updateUsersList(users);
            } catch (err) {
                console.error('Error loading users:', err);
            }
        }

        function updateUsersList(users) {
            const list = document.getElementById('usersList');
            const onlineUsers = users.filter(u => u.online && u.id !== currentUser.id);
            const offlineUsers = users.filter(u => !u.online && u.id !== currentUser.id);
            
            document.getElementById('usersCount').textContent = onlineUsers.length + ' онлайн, ' + offlineUsers.length + ' офлайн';
            
            list.innerHTML = '<div style="padding:10px; color:#999; font-weight:600;">ОНЛАЙН</div>';
            
            if (onlineUsers.length === 0) {
                list.innerHTML += '<div style="padding:10px; color:#999; text-align:center;">Нет пользователей онлайн</div>';
            } else {
                onlineUsers.forEach(user => {
                    list.innerHTML += createUserItem(user, true);
                });
            }
            
            if (offlineUsers.length > 0) {
                list.innerHTML += '<div style="padding:10px; color:#999; margin-top:10px; font-weight:600;">ОФЛАЙН</div>';
                offlineUsers.forEach(user => {
                    list.innerHTML += createUserItem(user, false);
                });
            }
        }

        function createUserItem(user, online) {
            const isSelected = selectedUser && selectedUser.id === user.id;
            return `
                <div class="user-item ${isSelected ? 'selected' : ''}" onclick="selectUser('${user.id}', '${user.username}')">
                    <div class="user-avatar">${user.username[0].toUpperCase()}</div>
                    <div class="user-info">
                        <div class="user-name">${user.username}</div>
                        <div class="user-status ${online ? '' : 'offline'}">${online ? 'онлайн' : 'офлайн'}</div>
                    </div>
                    <div class="unread-badge" id="unread-${user.id}" style="display:none;">0</div>
                </div>
            `;
        }

        function selectUser(userId, username) {
            selectedUser = {id: userId, username: username};
            document.getElementById('currentChatName').textContent = username;
            document.getElementById('currentChatStatus').textContent = 'онлайн';
            document.getElementById('startCallBtn').style.display = 'inline-block';
            document.getElementById('messageInput').disabled = false;
            document.getElementById('messageInput').focus();
            
            loadChatHistory(userId);
            toggleMenu();
            
            // Скрываем непрочитанные для этого пользователя
            document.getElementById(`unread-${userId}`).style.display = 'none';
        }

        async function loadChatHistory(userId) {
            try {
                const response = await fetch(`/messages/${userId}?user_id=${currentUser.id}`);
                const messages = await response.json();
                document.getElementById('messages').innerHTML = '';
                displayedMessageIds.clear();
                
                if (messages.length === 0) {
                    document.getElementById('messages').innerHTML = '<div class="empty-chat">Нет сообщений</div>';
                } else {
                    messages.forEach(msg => {
                        displayMessage(msg);
                        displayedMessageIds.add(msg.id);
                    });
                }
            } catch (err) {
                console.error('Error loading history:', err);
            }
        }

        function displayMessage(msg) {
            const messagesDiv = document.getElementById('messages');
            
            // Проверяем, не было ли это сообщение уже отображено
            if (displayedMessageIds.has(msg.id)) {
                return;
            }
            
            // Определяем, наше это сообщение или нет
            const isOwn = msg.from === currentUser.id;
            
            // Убираем сообщение о пустом чате если оно есть
            const emptyChat = messagesDiv.querySelector('.empty-chat');
            if (emptyChat) {
                emptyChat.remove();
            }
            
            const messageDiv = document.createElement('div');
            messageDiv.className = 'message' + (isOwn ? ' own' : '');
            messageDiv.setAttribute('data-message-id', msg.id);
            
            let content = '';
            if (msg.type === 'text') {
                content = msg.content;
            } else if (msg.type === 'voice') {
                content = '<audio controls src="' + msg.file_url + '"></audio>';
            }
            
            const time = new Date(msg.timestamp).toLocaleTimeString('ru-RU', {hour: '2-digit', minute:'2-digit'});
            const senderName = isOwn ? 'Вы' : msg.from_name;
            
            messageDiv.innerHTML = `
                <div class="message-info">${senderName}</div>
                <div class="message-content">${content}</div>
                <div class="message-time">${time}</div>
            `;
            
            messagesDiv.appendChild(messageDiv);
            messagesDiv.scrollTop = messagesDiv.scrollHeight;
            
            // Добавляем ID в множество отображенных сообщений
            displayedMessageIds.add(msg.id);
        }

        function updateUnreadCount(fromUserId) {
            if (!selectedUser || selectedUser.id !== fromUserId) {
                const badge = document.getElementById(`unread-${fromUserId}`);
                if (badge) {
                    const current = parseInt(badge.textContent) || 0;
                    badge.textContent = current + 1;
                    badge.style.display = 'flex';
                }
            }
        }

        function sendMessage() {
            const input = document.getElementById('messageInput');
            if (input.value.trim() && selectedUser && currentUser) {
                // Создаем временный ID для сообщения
                const tempId = 'temp_' + Date.now() + '_' + Math.random();
                
                const messageData = {
                    id: tempId,  // Временный ID
                    to: selectedUser.id,
                    content: input.value,
                    type: 'text',
                    from: currentUser.id,
                    from_name: currentUser.username,
                    timestamp: new Date().toISOString()
                };
                
                // Отображаем сообщение сразу (оптимистичный интерфейс)
                displayMessage(messageData);
                
                // Отправляем на сервер
                socket.emit('private-message', messageData);
                
                input.value = '';
            }
        }

        async function recordVoice() {
            if (!selectedUser) {
                alert('Сначала выберите пользователя');
                return;
            }
            
            try {
                const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
                startRecording(stream, 'voice');
            } catch (err) {
                alert('Нет доступа к микрофону: ' + err.message);
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
            
            mediaRecorder.onstop = async () => {
                const blob = new Blob(recordingChunks, { type: 'audio/webm' });
                const reader = new FileReader();
                reader.readAsDataURL(blob);
                reader.onloadend = async () => {
                    try {
                        const response = await fetch('/upload', {
                            method: 'POST',
                            headers: {'Content-Type': 'application/json'},
                            body: JSON.stringify({
                                file: reader.result,
                                type: 'voice'
                            })
                        });
                        
                        const data = await response.json();
                        if (data.url) {
                            const tempId = 'temp_voice_' + Date.now() + '_' + Math.random();
                            
                            const messageData = {
                                id: tempId,
                                to: selectedUser.id,
                                type: 'voice',
                                file_url: data.url,
                                from: currentUser.id,
                                from_name: currentUser.username,
                                timestamp: new Date().toISOString()
                            };
                            
                            // Отображаем голосовое сообщение сразу
                            displayMessage(messageData);
                            
                            // Отправляем на сервер
                            socket.emit('private-message', messageData);
                        }
                    } catch (err) {
                        console.error('Error uploading voice:', err);
                    }
                };
                
                document.getElementById('voiceBtn').classList.remove('record-btn');
                document.getElementById('recordingStatus').style.display = 'none';
                stream.getTracks().forEach(t => t.stop());
            };
            
            mediaRecorder.start();
            document.getElementById('voiceBtn').classList.add('record-btn');
            document.getElementById('recordingStatus').style.display = 'flex';
            
            seconds = 0;
            if (recordingTimer) clearInterval(recordingTimer);
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
            }
        }

        // Аудио звонки
        async function startAudioCall() {
            if (!selectedUser) {
                alert('Сначала выберите пользователя');
                return;
            }
            
            try {
                console.log('Starting call to:', selectedUser);
                
                localStream = await navigator.mediaDevices.getUserMedia({ audio: true });
                
                peerConnection = new RTCPeerConnection({
                    iceServers: [
                        { urls: 'stun:stun.l.google.com:19302' },
                        { urls: 'stun:stun1.l.google.com:19302' }
                    ]
                });
                
                localStream.getTracks().forEach(track => 
                    peerConnection.addTrack(track, localStream)
                );
                
                // Создаем аудио элемент для удаленного потока
                if (!remoteAudio) {
                    remoteAudio = new Audio();
                    remoteAudio.autoplay = true;
                }
                
                peerConnection.ontrack = (e) => {
                    console.log('Received remote track');
                    remoteAudio.srcObject = e.streams[0];
                };
                
                peerConnection.onicecandidate = (e) => {
                    if (e.candidate) {
                        console.log('Sending ICE candidate');
                        socket.emit('call-signal', {
                            to: selectedUser.id,
                            candidate: e.candidate
                        });
                    }
                };
                
                peerConnection.oniceconnectionstatechange = () => {
                    console.log('ICE connection state:', peerConnection.iceConnectionState);
                };
                
                const offer = await peerConnection.createOffer();
                await peerConnection.setLocalDescription(offer);
                
                console.log('Sending call offer');
                socket.emit('start-call', {
                    to: selectedUser.id,
                    offer: offer,
                    fromName: currentUser.username,
                    fromId: currentUser.id
                });
                
                showCallModal('Исходящий звонок', selectedUser.username, 'Звоним...');
                document.getElementById('callActions').innerHTML = '<button class="reject" onclick="endCall()">❌</button>';
                
            } catch (err) {
                console.error('Error starting call:', err);
                alert('Ошибка при звонке: ' + err.message);
            }
        }

        function showIncomingCall(data) {
            currentCall = data;
            showCallModal('Входящий звонок', data.fromName, '');
            document.getElementById('callActions').innerHTML = `
                <button class="accept" onclick="acceptCall('${data.fromId}')">📞</button>
                <button class="reject" onclick="rejectCall('${data.fromId}')">❌</button>
            `;
        }

        async function acceptCall(fromUserId) {
            try {
                console.log('Accepting call from:', fromUserId);
                
                localStream = await navigator.mediaDevices.getUserMedia({ audio: true });
                
                peerConnection = new RTCPeerConnection({
                    iceServers: [
                        { urls: 'stun:stun.l.google.com:19302' },
                        { urls: 'stun:stun1.l.google.com:19302' }
                    ]
                });
                
                localStream.getTracks().forEach(track => 
                    peerConnection.addTrack(track, localStream)
                );
                
                if (!remoteAudio) {
                    remoteAudio = new Audio();
                    remoteAudio.autoplay = true;
                }
                
                peerConnection.ontrack = (e) => {
                    console.log('Received remote track');
                    remoteAudio.srcObject = e.streams[0];
                };
                
                peerConnection.onicecandidate = (e) => {
                    if (e.candidate) {
                        console.log('Sending ICE candidate');
                        socket.emit('call-signal', {
                            to: fromUserId,
                            candidate: e.candidate
                        });
                    }
                };
                
                if (currentCall && currentCall.offer) {
                    await peerConnection.setRemoteDescription(new RTCSessionDescription(currentCall.offer));
                    const answer = await peerConnection.createAnswer();
                    await peerConnection.setLocalDescription(answer);
                    
                    console.log('Sending call answer');
                    socket.emit('accept-call', {
                        to: fromUserId,
                        answer: answer
                    });
                }
                
                hideCallModal();
                document.getElementById('startCallBtn').style.display = 'none';
                document.getElementById('endCallBtn').style.display = 'inline-block';
                
            } catch (err) {
                console.error('Error accepting call:', err);
            }
        }

        function rejectCall(fromUserId) {
            console.log('Rejecting call from:', fromUserId);
            socket.emit('reject-call', { to: fromUserId });
            hideCallModal();
            endCall();
        }

        function startCall() {
            hideCallModal();
            document.getElementById('startCallBtn').style.display = 'none';
            document.getElementById('endCallBtn').style.display = 'inline-block';
        }

        function endCall() {
            console.log('Ending call');
            
            if (peerConnection) {
                peerConnection.close();
                peerConnection = null;
            }
            
            if (localStream) {
                localStream.getTracks().forEach(t => t.stop());
                localStream = null;
            }
            
            if (remoteAudio) {
                remoteAudio.srcObject = null;
            }
            
            if (selectedUser) {
                socket.emit('end-call', { to: selectedUser.id });
            }
            
            document.getElementById('startCallBtn').style.display = 'inline-block';
            document.getElementById('endCallBtn').style.display = 'none';
            hideCallModal();
        }

        function showCallModal(title, name, status) {
            document.getElementById('callerAvatar').textContent = name ? name[0].toUpperCase() : '?';
            document.getElementById('callerInfo').textContent = title;
            document.getElementById('callStatus').textContent = status;
            document.getElementById('callModal').style.display = 'flex';
        }

        function hideCallModal() {
            document.getElementById('callModal').style.display = 'none';
        }

        function logout() {
            if (socket) {
                socket.disconnect();
            }
            document.getElementById('authContainer').style.display = 'block';
            document.getElementById('chatContainer').style.display = 'none';
            selectedUser = null;
            currentUser = null;
            displayedMessageIds.clear();
            
            // Очищаем поля ввода
            document.getElementById('loginUsername').value = '';
            document.getElementById('loginPassword').value = '';
            document.getElementById('regUsername').value = '';
            document.getElementById('regPassword').value = '';
            document.getElementById('regConfirmPassword').value = '';
        }

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

@socketio.on('private-message')
def handle_private_message(data):
    # Находим отправителя
    from_user = None
    for user in online_users.values():
        if user['sid'] == request.sid:
            from_user = user
            break
    
    if from_user and data.get('to'):
        # Генерируем уникальный ID для сообщения
        message_id = str(uuid.uuid4())
        
        msg = {
            'id': message_id,
            'from': from_user['id'],
            'to': data['to'],
            'content': data.get('content', ''),
            'type': data.get('type', 'text'),
            'file_url': data.get('file_url'),
            'timestamp': datetime.now().isoformat(),
            'is_read': False,
            'from_name': from_user['username']
        }
        
        # Сохраняем в базу
        conn = sqlite3.connect('chat.db')
        c = conn.cursor()
        c.execute('''INSERT INTO messages 
                    (id, from_user, to_user, content, type, file_url, timestamp, is_read)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)''',
                  (msg['id'], msg['from'], msg['to'], msg['content'], 
                   msg['type'], msg['file_url'], msg['timestamp'], msg['is_read']))
        conn.commit()
        conn.close()
        
        # Отправляем получателю, если он онлайн
        if data['to'] in online_users:
            emit('private-message', msg, room=online_users[data['to']]['sid'])
        
        # Не отправляем обратно отправителю, так как он уже отобразил сообщение оптимистично
        # Вместо этого можно отправить подтверждение, но не нужно

# Остальные маршруты остаются без изменений
@app.route('/')
def index():
    return HTML_TEMPLATE

@app.route('/register', methods=['POST'])
def register():
    data = request.json
    username = data.get('username')
    password = data.get('password')
    
    if not username or not password:
        return jsonify({'error': 'Заполните все поля'}), 400
    
    conn = sqlite3.connect('chat.db')
    c = conn.cursor()
    
    # Проверяем, существует ли пользователь
    c.execute('SELECT id FROM users WHERE username = ?', (username,))
    if c.fetchone():
        conn.close()
        return jsonify({'error': 'Пользователь уже существует'}), 400
    
    # Создаем нового пользователя
    user_id = str(uuid.uuid4())
    hashed_password = hashlib.sha256(password.encode()).hexdigest()
    
    c.execute('INSERT INTO users (id, username, password, created_at) VALUES (?, ?, ?, ?)',
              (user_id, username, hashed_password, datetime.now()))
    conn.commit()
    conn.close()
    
    return jsonify({'success': True})

@app.route('/login', methods=['POST'])
def login():
    data = request.json
    username = data.get('username')
    password = data.get('password')
    
    conn = sqlite3.connect('chat.db')
    c = conn.cursor()
    
    hashed_password = hashlib.sha256(password.encode()).hexdigest()
    c.execute('SELECT id, username FROM users WHERE username = ? AND password = ?',
              (username, hashed_password))
    
    user = c.fetchone()
    conn.close()
    
    if user:
        return jsonify({'success': True, 'user': {'id': user[0], 'username': user[1]}})
    else:
        return jsonify({'error': 'Неверное имя или пароль'}), 401

@app.route('/users')
def get_users():
    conn = sqlite3.connect('chat.db')
    c = conn.cursor()
    c.execute('SELECT id, username FROM users')
    users = []
    for user in c.fetchall():
        users.append({
            'id': user[0],
            'username': user[1],
            'online': user[0] in online_users
        })
    conn.close()
    return jsonify(users)

@app.route('/messages/<user_id>')
def get_messages(user_id):
    current_user_id = request.args.get('user_id')
    
    if not current_user_id:
        return jsonify([])
    
    conn = sqlite3.connect('chat.db')
    c = conn.cursor()
    
    c.execute('''SELECT m.*, u.username as from_name 
                 FROM messages m 
                 JOIN users u ON m.from_user = u.id
                 WHERE (m.from_user = ? AND m.to_user = ?) 
                    OR (m.from_user = ? AND m.to_user = ?)
                 ORDER BY m.timestamp ASC''',
              (current_user_id, user_id, user_id, current_user_id))
    
    messages = []
    for msg in c.fetchall():
        messages.append({
            'id': msg[0],
            'from': msg[1],
            'to': msg[2],
            'content': msg[3],
            'type': msg[4],
            'file_url': msg[5],
            'timestamp': msg[6],
            'is_read': bool(msg[7]),
            'from_name': msg[8]
        })
    
    conn.close()
    return jsonify(messages)

@app.route('/upload', methods=['POST'])
def upload():
    data = request.json
    if data and 'file' in data:
        filename = f"uploads/{uuid.uuid4()}.webm"
        os.makedirs('uploads', exist_ok=True)
        
        try:
            file_data = base64.b64decode(data['file'].split(',')[1])
            with open(filename, 'wb') as f:
                f.write(file_data)
            
            return jsonify({'url': '/uploads/' + os.path.basename(filename)})
        except Exception as e:
            return jsonify({'error': str(e)}), 500
    return jsonify({'error': 'No file'}), 400

@app.route('/uploads/<filename>')
def get_file(filename):
    return send_file(os.path.join('uploads', filename))

@socketio.on('user-online')
def handle_online(user):
    online_users[user['id']] = {
        'id': user['id'],
        'username': user['username'],
        'sid': request.sid
    }
    emit('users-online', list(online_users.values()), broadcast=True)

@socketio.on('start-call')
def handle_start_call(data):
    print(f"Start call to {data['to']}")
    if data['to'] in online_users:
        emit('incoming-call', {
            'fromId': data['fromId'],
            'fromName': data['fromName'],
            'offer': data.get('offer')
        }, room=online_users[data['to']]['sid'])

@socketio.on('accept-call')
def handle_accept_call(data):
    print(f"Accept call from {data['to']}")
    if data['to'] in online_users:
        emit('call-accepted', {
            'answer': data.get('answer')
        }, room=online_users[data['to']]['sid'])

@socketio.on('reject-call')
def handle_reject_call(data):
    print(f"Reject call from {data['to']}")
    if data['to'] in online_users:
        emit('call-rejected', {}, room=online_users[data['to']]['sid'])

@socketio.on('call-signal')
def handle_call_signal(data):
    if data['to'] in online_users:
        emit('call-signal', {
            'candidate': data.get('candidate')
        }, room=online_users[data['to']]['sid'])

@socketio.on('end-call')
def handle_end_call(data):
    if data.get('to') and data['to'] in online_users:
        emit('call-ended', {}, room=online_users[data['to']]['sid'])

@socketio.on('disconnect')
def handle_disconnect():
    # Удаляем пользователя из онлайн
    to_remove = None
    for user_id, user in online_users.items():
        if user['sid'] == request.sid:
            to_remove = user_id
            break
    
    if to_remove:
        del online_users[to_remove]
        emit('users-online', list(online_users.values()), broadcast=True)

if __name__ == '__main__':
    os.makedirs('uploads', exist_ok=True)
    socketio.run(app, host='0.0.0.0', port=5000, debug=True)
