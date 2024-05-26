from flask import Flask, render_template, request, jsonify
import threading
import time
import requests
from datetime import datetime
import os
from config import API_TOKEN  # Import API_TOKEN from config.py

app = Flask(__name__)

send_messages = False
restricted_groups = []
pin_first_message = False
first_message_sent = False

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/start_bot', methods=['POST'])
def start_bot():
    global send_messages, restricted_groups, pin_first_message, first_message_sent
    send_messages = True
    first_message_sent = False

    data = request.get_json()
    message = data['message']
    groups = data['groups']
    delay = int(data['delay'])
    restrict_permissions = data['restrict_permissions']
    disable_web_page_preview = data['disable_web_page_preview']
    pin_first_message = data['pin_first_message']
    start_time = datetime.strptime(data['start_time'], '%H:%M').time()
    end_time = datetime.strptime(data['end_time'], '%H:%M').time()

    restricted_groups = groups if restrict_permissions else []

    threading.Thread(target=message_scheduler, args=(message, groups, delay, restrict_permissions, disable_web_page_preview, start_time, end_time)).start()

    return jsonify(status="Bot started")

@app.route('/stop_bot', methods=['POST'])
def stop_bot():
    global send_messages
    send_messages = False
    for group in restricted_groups:
        restore_user_permissions(group)
    return jsonify(status="Bot stopped")

@app.route('/restore_permissions', methods=['POST'])
def restore_permissions():
    global restricted_groups
    for group in restricted_groups:
        restore_user_permissions(group)
    return jsonify(status="Permissions restored")

def send_message(chat_id, text, disable_web_page_preview=False, pin_message=False):
    url = f'https://api.telegram.org/bot{API_TOKEN}/sendMessage'
    payload = {
        'chat_id': chat_id,
        'text': text,
        'disable_web_page_preview': disable_web_page_preview
    }
    response = requests.post(url, data=payload)
    if pin_message:
        message_id = response.json().get('result', {}).get('message_id')
        if message_id:
            pin_message_to_chat(chat_id, message_id)

def pin_message_to_chat(chat_id, message_id):
    url = f'https://api.telegram.org/bot{API_TOKEN}/pinChatMessage'
    payload = {
        'chat_id': chat_id,
        'message_id': message_id
    }
    requests.post(url, data=payload)

def restrict_user_permissions(chat_id):
    url = f'https://api.telegram.org/bot{API_TOKEN}/setChatPermissions'
    payload = {
        'chat_id': chat_id,
        'permissions': {
            'can_send_messages': False,
            'can_send_media_messages': False,
            'can_send_polls': False,
            'can_send_other_messages': False,
            'can_add_web_page_previews': False,
            'can_change_info': False,
            'can_invite_users': True,
            'can_pin_messages': False
        }
    }
    requests.post(url, json=payload)

def restore_user_permissions(chat_id):
    url = f'https://api.telegram.org/bot{API_TOKEN}/setChatPermissions'
    payload = {
        'chat_id': chat_id,
        'permissions': {
            'can_send_messages': True,
            'can_send_media_messages': False,
            'can_send_polls': False,
            'can_send_other_messages': False,
            'can_add_web_page_previews': False,
            'can_change_info': False,
            'can_invite_users': True,
            'can_pin_messages': False
        }
    }
    requests.post(url, json=payload)

def message_scheduler(message, groups, delay, restrict_permissions, disable_web_page_preview, start_time, end_time):
    global send_messages, first_message_sent, pin_first_message

    while datetime.now().time() < start_time:
        time.sleep(1)

    if restrict_permissions:
        for group in groups:
            restrict_user_permissions(group)

    while send_messages and datetime.now().time() < end_time:
        for group in groups:
            if not send_messages:
                break
            send_message(group, message, disable_web_page_preview, pin_first_message and not first_message_sent)
            if pin_first_message and not first_message_sent:
                first_message_sent = True
        time.sleep(delay)

    send_messages = False
    for group in restricted_groups:
        restore_user_permissions(group)

if __name__ == '__main__':
    app.run(debug=False, port=int(os.environ.get('PORT', 5000)))
