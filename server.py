from flask import Flask, render_template, request, jsonify, send_file
from flask_socketio import SocketIO, emit
import os
import base64
import uuid
from datetime import datetime

app = Flask(__name__)
app.config['SECRET_KEY'] = 'secret!'
socketio = SocketIO(app, cors_allowed_origins="*")

# Хранилище сообщений и пользователей
messages = []
users = {}
deleted_messages = set()

HTML_TEMPLATE = '''
<!DOCTYPE html>
<html>
<head>
    <title>Messenger</title>
    <meta charset="utf-8">
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { font-family: Arial; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); height: 100vh; display: flex; justify-content: center; align-items: center; }
        .login-container { background: white; border-radius: 10px; padding: 40px; width: 400px; }
        .login-container h1 { margin-bottom: 30px; color: #333; text-align: center; }
        .login-container input { width: 100%; padding: 12px; margin-bottom: 20px; border: 2px solid #ddd; border-radius: 5px; }
        .login-container button { background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; border: none; padding: 12px 30px; border-radius: 5px; cursor: pointer; width: 100%; }
        .chat-container { display: none; width: 1200px; height: 80vh; background: white; border-radius: 10px; overflow: hidden; }
        .sidebar { width: 300px; background: #f5f5f5; border-right: 1px solid #ddd; }
        .main-chat { flex: 1; display: flex; flex-direction: column; }
        .messages { flex: 1; overflow-y: auto; padding: 20px; }
        .message { margin-bottom: 15px; max-width: 70%; }
        .message.own { margin-left: auto; }
        .message-content { background: white; padding: 10px 15px; border-radius: 18px; }
        .message.own .message-content { background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; }
        .message-input { padding: 20px; background: white; border-top: 1px solid #ddd; display: flex; }
        .message-input input { flex: 1; padding: 12px; border: 2px solid #ddd; border-radius: 25px; margin-right: 10px; }
        .message-input button { width: 45px; height: 45px; border-radius: 50%; border: none; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; cursor: pointer; }
        .users-list { padding: 20px; }
        .user-item { display: flex; align-items: center; padding: 10px; background: white; border-radius: 5px; margin-bottom: 10px; }
        .user-avatar { width: 40px; height: 40px; border-radius: 50%; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); display: flex; align-items: center; justify-content: center; color: white; margin-right: 10px; }
        .delete-btn { opacity: 0; cursor: pointer; margin-left: 10px; color: #ff4444; }
        .message:hover .delete-btn { opacity: 1; }
    </style>
</head>
<body>
    <div class="login-container" id="loginContainer">
        <h1>Messenger</h1>
        <input type="text" id="username" placeholder="Ваше имя">
        <button onclick="joinChat()">Войти</button>
    </div>

    <div class="chat-container" id="chatContainer">
        <div class="sidebar">
            <div class="users-list" id="usersList"></div>
        </div>
        <div class="main-chat">
            <div class="messages" id="messages"></div>
            <div class="message-input">
                <input type="text" id="messageInput" placeholder="Напишите сообщение...">
                <button onclick="sendMessage()">➤</button>
            </div>
        </div>
    </div>

    <script src="https://cdn.socket.io/4.5.4/socket.io.min.js"></script>
    <script>
        let socket = io();
        let username = '';
        let currentUserId = '';

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

        socket.on('message-deleted', (data) => {
            const msg = document.querySelector(`[data-id="${data.messageId}"]`);
            if (msg) {
                msg.remove();
            }
        });

        function updateUsersList(users) {
            const list = document.getElementById('usersList');
            list.innerHTML = '<h3>Участники (' + users.length + ')</h3>';
            users.forEach(user => {
                if (user.id !== currentUserId) {
                    list.innerHTML += '<div class="user-item"><div class="user-avatar">' + 
                        user.username[0] + '</div><div>' + user.username + '</div></div>';
                }
            });
        }

        function displayMessage(msg) {
            const div = document.createElement('div');
            div.className = 'message' + (msg.userId === currentUserId ? ' own' : '');
            div.setAttribute('data-id', msg.id);
            
            const time = new Date(msg.timestamp).toLocaleTimeString();
            
            let deleteBtn = '';
            if (msg.userId === currentUserId) {
                deleteBtn = '<button class="delete-btn" onclick="deleteMessage(\'' + msg.id + '\')">✕</button>';
            }
            
            div.innerHTML = '<div class="message-info">' + msg.username + ' ' + time + deleteBtn + '</div>' +
                '<div class="message-content">' + msg.text + '</div>';
            
            document.getElementById('messages').appendChild(div);
            document.getElementById('messages').scrollTop = document.getElementById('messages').scrollHeight;
        }

        function sendMessage() {
            const input = document.getElementById('messageInput');
            if (input.value) {
                socket.emit('send-message', { text: input.value });
                input.value = '';
            }
        }

        function deleteMessage(id) {
            if (confirm('Удалить сообщение?')) {
                socket.emit('delete-message', { messageId: id });
            }
        }
    </script>
</body>
</html>
'''

@app.route('/')
def index():
    return HTML_TEMPLATE

@socketio.on('join')
def handle_join(username):
    user_id = request.sid
    users[user_id] = {'id': user_id, 'username': username}
    emit('message-history', messages[-50:])
    emit('user-joined', {'userId': user_id, 'users': list(users.values())}, broadcast=True)

@socketio.on('send-message')
def handle_message(data):
    msg = {
        'id': str(uuid.uuid4()),
        'userId': request.sid,
        'username': users[request.sid]['username'],
        'text': data['text'],
        'timestamp': datetime.now().isoformat()
    }
    messages.append(msg)
    emit('new-message', msg, broadcast=True)

@socketio.on('delete-message')
def handle_delete_message(data):
    global messages
    messages = [m for m in messages if m['id'] != data['messageId']]
    emit('message-deleted', {'messageId': data['messageId']}, broadcast=True)

@socketio.on('disconnect')
def handle_disconnect():
    if request.sid in users:
        del users[request.sid]
        emit('users-update', list(users.values()), broadcast=True)

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    socketio.run(app, host='0.0.0.0', port=port)