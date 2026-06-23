import json
import os
from datetime import datetime, timezone, timedelta

FILE_PATH = "data/appointments.json"
SETTINGS_FILE = "data/settings.json"
INQUIRIES_FILE = "data/inquiries.json"

def get_ist_now():
    return datetime.now(timezone.utc) + timedelta(hours=5, minutes=30)

def load_data():
    try:
        with open(FILE_PATH, "r") as file:
            return json.load(file)
    except:
        return []

def save_data(data):
    with open(FILE_PATH, "w") as file:
        json.dump(data, file, indent=4)

def load_settings():
    try:
        with open(SETTINGS_FILE, "r") as file:
            return json.load(file)
    except:
        return {}

def save_settings(settings):
    try:
        os.makedirs(os.path.dirname(SETTINGS_FILE), exist_ok=True)
        with open(SETTINGS_FILE, "w") as file:
            json.dump(settings, file, indent=4)
    except Exception as e:
        print(f"Error saving settings: {e}")

def get_setting(key, default=None):
    settings = load_settings()
    if key in settings and settings[key]:
        return settings[key]
    return os.getenv(key, default)

def log_inquiry(chat_id, username, action):
    try:
        try:
            with open(INQUIRIES_FILE, "r") as file:
                data = json.load(file)
        except:
            data = []
            
        data.append({
            "chat_id": chat_id,
            "username": username,
            "action": action,
            "timestamp": get_ist_now().strftime("%d/%m/%Y %I:%M %p")
        })
        
        # Keep last 500 inquiries
        if len(data) > 500:
            data = data[-500:]
            
        os.makedirs(os.path.dirname(INQUIRIES_FILE), exist_ok=True)
        with open(INQUIRIES_FILE, "w") as file:
            json.dump(data, file, indent=4)
    except Exception as e:
        print(f"Error logging inquiry: {e}")