import logging
from flask import Flask, render_template, request, jsonify
import threading
import time
import requests
from datetime import datetime, timedelta
import os
from config import API_TOKEN  # Import API_TOKEN from config.py
import pytz  # Add pytz for timezone handling

app = Flask(__name__)

# Configure logging
logging.basicConfig(level=logging.INFO)

send_messages = False
restricted_groups = []
pin_first_message = False
first_message_sent_groups = {}

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/start_bot', methods=['POST'])
def start_bot():
    global send_messages, restricted_groups, pin_first_message, first_message_sent_groups
    send_messages = True
    first_message_sent_groups = {}

    data = request.get_json()
    message = data['message']
    groups = data['groups']
    delay = int(data['delay'])
    restrict_permissions = data['restrict_permissions']
    disable_web_page_preview = data['disable_web_page_preview']
    pin_first_message = data['pin_first_message']
    time_zone = data['time_zone']
    start_time = datetime.strptime(data['start_time'], '%H:%M').time()
    end_time = datetime.strptime(data['end_time'], '%H:%M').time()

    # Convert start and end times to UTC
    tz = pytz.timezone(time_zone)
    start_time = tz.localize(datetime.combine(datetime.today(), start_time)).astimezone(pytz.utc).time()
    end_time = tz.localize(datetime.combine(datetime.today(), end_time)).astimezone(pytz.utc).time()

    restricted_groups = groups if restrict_permissions else []

    logging.info(f"Received start_bot request: message={message}, groups={groups}, delay={delay}, restrict_permissions={restrict_permissions}, disable_web_page_preview={disable_web_page_preview}, pin_first_message={pin_first_message}, start_time={start_time}, end_time={end_time}, time_zone={time_zone}")

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
    logging.info(f"Sending message to {chat_id}: {text}")
    try:
        response = requests.post(url, data=payload)
        response_data = response.json()
        logging.info(f"Response: {response_data}")
        if not response.ok:
            logging.error(f"Error sending message: {response_data}")

        if pin_message:
            message_id = response_data.get('result', {}).get('message_id')
            if message_id:
                pin_message_to_chat(chat_id, message_id)
    except Exception as e:
        logging.error(f"Exception during send_message: {e}", exc_info=True)

def pin_message_to_chat(chat_id, message_id):
    url = f'https://api.telegram.org/bot{API_TOKEN}/pinChatMessage'
    payload = {
        'chat_id': chat_id,
        'message_id': message_id
    }
    logging.info(f"Pinning message {message_id} to chat {chat_id}")
    try:
        response = requests.post(url, data=payload)
        response_data = response.json()
        logging.info(f"Response: {response_data}")
        if not response.ok:
            logging.error(f"Error pinning message: {response_data}")
    except Exception as e:
        logging.error(f"Exception during pin_message_to_chat: {e}", exc_info=True)

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
    logging.info(f"Restricting permissions for chat {chat_id}")
    try:
        response = requests.post(url, json=payload)
        logging.info(f"Response: {response.json()}")
    except Exception as e:
        logging.error(f"Exception during restrict_user_permissions: {e}", exc_info=True)

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
    logging.info(f"Restoring permissions for chat {chat_id}")
    try:
        response = requests.post(url, json=payload)
        logging.info(f"Response: {response.json()}")
    except Exception as e:
        logging.error(f"Exception during restore_user_permissions: {e}", exc_info=True)

def message_scheduler(message, groups, delay, restrict_permissions, disable_web_page_preview, start_time, end_time):
    global send_messages, first_message_sent_groups, pin_first_message

    logging.info(f"Scheduler started: waiting for start time {start_time}")
    while datetime.now(pytz.utc).time() < start_time:
        time.sleep(1)

    if restrict_permissions:
        for group in groups:
            restrict_user_permissions(group)

    logging.info("Starting message sending loop")
    while send_messages and datetime.now(pytz.utc).time() < end_time:
        for group in groups:
            if not send_messages:
                break
            if group not in first_message_sent_groups:
                logging.info(f"Sending first message to group {group}")
                send_message(group, message, disable_web_page_preview, pin_first_message)
                first_message_sent_groups[group] = True
            else:
                logging.info(f"Sending scheduled message to group {group}")
                send_message(group, message, disable_web_page_preview, False)
        time.sleep(delay)

    logging.info("Message sending loop ended")
    send_messages = False
    for group in restricted_groups:
        restore_user_permissions(group)

if __name__ == '__main__':
    app.run(debug=False, port=int(os.environ.get('PORT', 5000)))
