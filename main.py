import os
import time
import re
import random
import threading
from datetime import datetime, timedelta, date
import requests

from storage import load_data, save_data, get_setting, log_inquiry, get_ist_now
from appointments import (
    ALL_SLOTS,
    get_available_slots,
    book_slot,
    find_booking_by_phone,
    cancel_booking,
    update_booking,
    find_active_booking_by_chat_id
)

# Global session storage
user_sessions = {}

# Parse .env manually to avoid extra dependencies
def load_env():
    if os.path.exists(".env"):
        with open(".env", "r") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#"):
                    parts = line.split("=", 1)
                    if len(parts) == 2:
                        key, val = parts
                        os.environ[key.strip()] = val.strip()

load_env()

TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
if not TOKEN:
    raise ValueError("TELEGRAM_BOT_TOKEN not found in .env file.")

API_URL = f"https://api.telegram.org/bot{TOKEN}"

# Keyboards
MAIN_MENU_KEYBOARD = {
    "keyboard": [
        [{"text": "1. Book Appointment"}],
        [{"text": "2. Dental Services"}, {"text": "3. Clinic Location"}],
        [{"text": "4. Contact Doctor"}, {"text": "5. Working Hours"}],
        [{"text": "6. Frequently Asked Questions"}, {"text": "7. Emergency Support"}],
        [{"text": "8. Reschedule Appointment"}, {"text": "9. Cancel Appointment"}]
    ],
    "resize_keyboard": True,
    "one_time_keyboard": True
}

SERVICES_KEYBOARD = {
    "keyboard": [
        [{"text": "1. General Checkup"}, {"text": "2. Teeth Cleaning"}],
        [{"text": "3. Root Canal Treatment"}, {"text": "4. Tooth Extraction"}],
        [{"text": "5. Teeth Whitening"}, {"text": "6. Braces Consultation"}],
        [{"text": "7. Dental Implants"}, {"text": "8. Other"}],
        [{"text": "Cancel and Restart"}]
    ],
    "resize_keyboard": True,
    "one_time_keyboard": True
}

YES_NO_KEYBOARD = {
    "keyboard": [
        [{"text": "YES"}, {"text": "NO"}],
        [{"text": "Cancel and Restart"}]
    ],
    "resize_keyboard": True,
    "one_time_keyboard": True
}

RESCHEDULE_OPTIONS_KEYBOARD = {
    "keyboard": [
        [{"text": "1. Change Date"}, {"text": "2. Change Time"}],
        [{"text": "Cancel Rescheduling"}]
    ],
    "resize_keyboard": True,
    "one_time_keyboard": True
}

REMOVE_KEYBOARD = {
    "remove_keyboard": True
}

def get_next_5_dates():
    dates = []
    current = get_ist_now() + timedelta(days=2)
    while len(dates) < 5:
        if current.weekday() != 6: # Skip Sundays (closed)
            dates.append(current)
        current += timedelta(days=1)
    return dates

def get_date_selection_keyboard():
    today_str = get_ist_now().strftime("%d/%m/%Y")
    tomorrow_str = (get_ist_now() + timedelta(days=1)).strftime("%d/%m/%Y")
    
    today_count = len(get_available_slots(today_str))
    tomorrow_count = len(get_available_slots(tomorrow_str))
    
    if is_sunday(today_str):
        today_text = "1. Today (Closed)"
    else:
        today_text = f"1. Today ({today_count} slots left)"
        
    if is_sunday(tomorrow_str):
        tomorrow_text = "2. Tomorrow (Closed)"
    else:
        tomorrow_text = f"2. Tomorrow ({tomorrow_count} slots left)"
        
    return {
        "keyboard": [
            [{"text": today_text}, {"text": tomorrow_text}],
            [{"text": "3. Select Another Date"}],
            [{"text": "Cancel and Restart"}]
        ],
        "resize_keyboard": True,
        "one_time_keyboard": True
    }

def get_date_keyboard():
    dates = get_next_5_dates()
    keyboard = []
    row = []
    for d in dates:
        date_str = d.strftime("%d/%m/%Y")
        day_name = d.strftime("%A")
        count = len(get_available_slots(date_str))
        button_text = f"{date_str} ({day_name}) - {count} slots left"
        row.append({"text": button_text})
        if len(row) == 2:
            keyboard.append(row)
            row = []
    if row:
        keyboard.append(row)
    keyboard.append([{"text": "Cancel and Restart"}])
    return {
        "keyboard": keyboard,
        "resize_keyboard": True,
        "one_time_keyboard": True
    }

def get_slots_keyboard(slots):
    keyboard = []
    row = []
    for slot in slots:
        row.append({"text": slot})
        if len(row) == 3:
            keyboard.append(row)
            row = []
    if row:
        keyboard.append(row)
    keyboard.append([{"text": "Cancel and Restart"}])
    return {
        "keyboard": keyboard,
        "resize_keyboard": True,
        "one_time_keyboard": True
    }

def send_message(chat_id, text, reply_markup=None):
    url = f"{API_URL}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": text
    }
    if reply_markup:
        payload["reply_markup"] = reply_markup
    try:
        response = requests.post(url, json=payload, timeout=10)
        if response.status_code != 200:
            print(f"Failed to send message: {response.text}")
    except Exception as e:
        print(f"Error sending message to chat {chat_id}: {e}")

def resolve_menu_option(text):
    text = text.strip().lower()
    
    # Check leading digit first (handles "3", "3.", "3. Clinic Location")
    m = re.match(r'^(\d)', text)
    if m:
        opt = m.group(1)
        if opt in ["1", "2", "3", "4", "5", "6", "7", "8", "9"]:
            return opt
            
    # Fuzzy match text keywords
    if "book appointment" in text:
        return "1"
    elif "dental services" in text:
        return "2"
    elif "clinic location" in text:
        return "3"
    elif "contact doctor" in text:
        return "4"
    elif "working hours" in text:
        return "5"
    elif "frequently asked" in text or "faq" in text:
        return "6"
    elif "emergency support" in text:
        return "7"
    elif "reschedule appointment" in text:
        return "8"
    elif "cancel appointment" in text:
        return "9"
    return None

def normalize_time_input(text):
    text = text.strip().lower()
    cleaned = re.sub(r'[^a-z0-9]', '', text)
    
    # Try direct match
    for s in ALL_SLOTS:
        cleaned_s = re.sub(r'[^a-z0-9]', '', s.lower())
        if cleaned == cleaned_s:
            return s
            
    # Pattern: hour and minute (with or without am/pm)
    m = re.match(r'^(\d{1,2})(\d{2})\s*(am|pm)?$', cleaned)
    if m:
        hours = int(m.group(1))
        minutes = int(m.group(2))
        ampm = m.group(3)
        return resolve_ampm(hours, minutes, ampm)
        
    # Pattern: just hour (with or without am/pm)
    m = re.match(r'^(\d{1,2})\s*(am|pm)?$', cleaned)
    if m:
        hours = int(m.group(1))
        minutes = 0
        ampm = m.group(2)
        return resolve_ampm(hours, minutes, ampm)
        
    return None

def resolve_ampm(hours, minutes, ampm):
    if hours >= 24 or minutes >= 60:
        return None
    if not ampm:
        if hours in [9, 10, 11]:
            ampm = "am"
        elif hours in [12, 1, 2, 3, 4, 5, 6]:
            ampm = "pm"
        elif hours >= 13 and hours <= 23:
            hours -= 12
            ampm = "pm"
        else:
            return None
            
    if ampm == "am" and hours == 12:
        hours = 0
        
    slot_str = f"{hours:02d}:{minutes:02d} {ampm.upper()}"
    for slot in ALL_SLOTS:
        if slot == slot_str:
            return slot
    return None

def is_sunday(date_str):
    try:
        dt = datetime.strptime(date_str, "%d/%m/%Y")
        return dt.weekday() == 6
    except:
        return False

def clean_phone_number(text):
    cleaned = "".join(filter(str.isdigit, text))
    if len(cleaned) >= 10:
        return cleaned[-10:]
    return None

def check_reminders_and_feedback():
    data = load_data()
    today = get_ist_now().date()
    updated = False
    
    for appointment in data:
        appt_date_str = appointment.get("date")
        chat_id = appointment.get("telegram_chat_id")
        if not appt_date_str or not chat_id:
            continue
            
        try:
            appt_date = datetime.strptime(appt_date_str, "%d/%m/%Y").date()
        except:
            continue
            
        clinic_name = get_setting("CLINIC_NAME", "Bright Smile Dental Care")
        clinic_contact = get_setting("CLINIC_CONTACT", "+91 91234 56789")

        # Reminder: 24h (1 day) before appointment
        if (appt_date - today).days == 1 and not appointment.get("reminder_sent"):
            reminder_text = f"""Reminder

Dear {appointment['name']},

This is a reminder that your dental appointment is scheduled for tomorrow.

Date:
{appointment['date']}

Time:
{appointment['time']}

Clinic:
{clinic_name}

For assistance, contact:
{clinic_contact}"""
            send_message(chat_id, reminder_text)
            appointment["reminder_sent"] = True
            updated = True
            
    if updated:
        save_data(data)

def send_admin_notification(booking):
    admin_id = get_setting("ADMIN_CHAT_ID")
    if not admin_id:
        return
    admin_text = f"""New Appointment Booking

Patient:
{booking['name']}

Phone:
{booking['phone']}

Service:
{booking['service']}

Date:
{booking['date']}

Time:
{booking['time']}

Booking ID:
{booking['booking_id']}"""
    send_message(admin_id, admin_text)

def send_admin_cancel_notification(booking):
    admin_id = get_setting("ADMIN_CHAT_ID")
    if not admin_id:
        return
    admin_text = f"""Appointment Cancelled

Patient:
{booking['name']}

Phone:
{booking['phone']}

Service:
{booking['service']}

Date:
{booking['date']}

Time:
{booking['time']}

Booking ID:
{booking['booking_id']}"""
    send_message(admin_id, admin_text)

def send_admin_reschedule_notification(booking, old_date, old_time):
    admin_id = get_setting("ADMIN_CHAT_ID")
    if not admin_id:
        return
    admin_text = f"""Appointment Rescheduled

Patient:
{booking['name']}

Phone:
{booking['phone']}

Service:
{booking['service']}

Date:
{booking['date']} (was {old_date})

Time:
{booking['time']} (was {old_time})

Booking ID:
{booking['booking_id']}"""
    send_message(admin_id, admin_text)

def handle_text_message(chat_id, text, username):
    msg = text.strip()
    
    # Global commands interceptor
    msg_lower = msg.lower()
    if msg_lower in ["/start", "/menu", "restart", "/restart", "cancel and restart", "cancel rescheduling"]:
        user_sessions.pop(chat_id, None)
        msg = "/start"
    elif msg_lower in ["/cancel", "cancel"]:
        user_sessions.pop(chat_id, None)
        send_message(chat_id, "Operation cancelled. Returning to main menu...", reply_markup=REMOVE_KEYBOARD)
        time.sleep(1)
        msg = "/start"

    clinic_name = get_setting("CLINIC_NAME", "Bright Smile Dental Care")

    # Start Session if /start or not existing
    if chat_id not in user_sessions or msg == "/start":
        bypass = False
        if chat_id in user_sessions:
            bypass = user_sessions[chat_id].get("bypass_active_check", False)
            
        active_booking = None
        if not bypass:
            active_booking = find_active_booking_by_chat_id(chat_id)
            
        if active_booking:
            user_sessions[chat_id] = {
                "step": "active_booking_menu",
                "book_data": {},
                "reschedule_data": {},
                "cancel_data": {},
                "active_booking": active_booking
            }
            
            welcome_text = (
                f"Welcome back to {clinic_name}!\n\n"
                f"You have an active appointment booked with us:\n"
                f"Date: {active_booking['date']}\n"
                f"Time: {active_booking['time']}\n"
                f"Service: {active_booking['service']}\n"
                f"Reference: {active_booking['booking_id']}\n\n"
                "How would you like to proceed?\n\n"
                "1. Reschedule Appointment\n"
                "2. Cancel Appointment\n"
                "3. Restart (Return to Main Menu)"
            )
            
            ACTIVE_BOOKING_KEYBOARD = {
                "keyboard": [
                    [{"text": "1. Reschedule Appointment"}],
                    [{"text": "2. Cancel Appointment"}],
                    [{"text": "3. Restart (Main Menu)"}]
                ],
                "resize_keyboard": True,
                "one_time_keyboard": True
            }
            send_message(chat_id, welcome_text, reply_markup=ACTIVE_BOOKING_KEYBOARD)
            return
        else:
            user_sessions[chat_id] = {
                "step": "menu",
                "book_data": {},
                "reschedule_data": {},
                "cancel_data": {}
            }
            
            welcome_text = (
                f"Welcome to {clinic_name}\n\n"
                "\"Your Smile, Our Priority\"\n\n"
                "How may we assist you today?\n\n"
                "1. Book Appointment\n"
                "2. Dental Services\n"
                "3. Clinic Location\n"
                "4. Contact Doctor\n"
                "5. Working Hours\n"
                "6. Frequently Asked Questions\n"
                "7. Emergency Support\n"
                "8. Reschedule Appointment\n"
                "9. Cancel Appointment\n\n"
                "Please select an option by replying with a number."
            )
            send_message(chat_id, welcome_text, reply_markup=MAIN_MENU_KEYBOARD)
            return

    session = user_sessions[chat_id]
    step = session["step"]

    # --- ACTIVE BOOKING MENU STEP ---
    if step == "active_booking_menu":
        msg_clean = msg.strip().lower()
        if "reschedule" in msg_clean or "1" in msg_clean:
            log_inquiry(chat_id, username, "Initiated Reschedule Flow (from Active Menu)")
            session["step"] = "reschedule_select"
            session["reschedule_data"] = {
                "phone": session["active_booking"]["phone"],
                "booking": session["active_booking"]
            }
            
            appt_info = (
                "I found your appointment:\n\n"
                f"Patient: {session['active_booking']['name']}\n"
                f"Service: {session['active_booking']['service']}\n"
                f"Date: {session['active_booking']['date']}\n"
                f"Time: {session['active_booking']['time']}\n\n"
                "What would you like to change?"
            )
            send_message(chat_id, appt_info, reply_markup=RESCHEDULE_OPTIONS_KEYBOARD)
            
        elif "cancel" in msg_clean or "2" in msg_clean:
            log_inquiry(chat_id, username, "Initiated Cancel Flow (from Active Menu)")
            session["step"] = "cancel_confirm"
            session["cancel_data"] = {
                "booking": session["active_booking"]
            }
            
            appt_info = (
                "I found your appointment:\n\n"
                f"Patient: {session['active_booking']['name']}\n"
                f"Service: {session['active_booking']['service']}\n"
                f"Date: {session['active_booking']['date']}\n"
                f"Time: {session['active_booking']['time']}\n\n"
                "Are you sure you want to cancel this appointment?"
            )
            send_message(chat_id, appt_info, reply_markup=YES_NO_KEYBOARD)
            
        elif "restart" in msg_clean or "3" in msg_clean:
            user_sessions[chat_id] = {
                "step": "menu",
                "book_data": {},
                "reschedule_data": {},
                "cancel_data": {},
                "bypass_active_check": True
            }
            welcome_text = (
                f"Welcome to {clinic_name}\n\n"
                "\"Your Smile, Our Priority\"\n\n"
                "How may we assist you today?\n\n"
                "1. Book Appointment\n"
                "2. Dental Services\n"
                "3. Clinic Location\n"
                "4. Contact Doctor\n"
                "5. Working Hours\n"
                "6. Frequently Asked Questions\n"
                "7. Emergency Support\n"
                "8. Reschedule Appointment\n"
                "9. Cancel Appointment\n\n"
                "Please select an option by replying with a number."
            )
            send_message(chat_id, welcome_text, reply_markup=MAIN_MENU_KEYBOARD)
        else:
            ACTIVE_BOOKING_KEYBOARD = {
                "keyboard": [
                    [{"text": "1. Reschedule Appointment"}],
                    [{"text": "2. Cancel Appointment"}],
                    [{"text": "3. Restart (Main Menu)"}]
                ],
                "resize_keyboard": True,
                "one_time_keyboard": True
            }
            send_message(chat_id, "Please select a valid option from the menu:", reply_markup=ACTIVE_BOOKING_KEYBOARD)
        return

    # --- MENU STEP ---
    if step == "menu":
        opt = resolve_menu_option(msg)
        if opt == "1":
            log_inquiry(chat_id, username, "Initiated Booking Flow")
            session["step"] = "book_name"
            send_message(chat_id, "To schedule your appointment, may I know your full name?", reply_markup=REMOVE_KEYBOARD)
        elif opt == "2":
            log_inquiry(chat_id, username, "Viewed Dental Services")
            services_text = (
                "Available Dental Services\n\n"
                "1. General Dental Checkup\n"
                "Comprehensive evaluation of your teeth, gums, and overall oral health.\n\n"
                "2. Teeth Cleaning & Scaling\n"
                "Removes plaque, tartar, and stains to improve oral hygiene and prevent gum disease.\n\n"
                "3. Root Canal Treatment\n"
                "Saves and restores infected or damaged teeth, relieving severe toothaches.\n\n"
                "4. Tooth Extraction\n"
                "Safe and painless removal of non-restorable or wisdom teeth.\n\n"
                "5. Dental Fillings\n"
                "Restores decayed teeth using composite materials.\n\n"
                "6. Teeth Whitening\n"
                "Brightens your smile by removing deep stains and discoloration.\n\n"
                "7. Braces Consultation\n"
                "Evaluation for correcting misaligned teeth using modern braces.\n\n"
                "8. Dental Implants\n"
                "Permanent replacement for missing teeth.\n\n"
                "9. Gum Treatment\n"
                "Treats gum bleeding and infections.\n\n"
                "10. Pediatric Dentistry\n"
                "Specialized, friendly oral care for children.\n\n"
                "11. Smile Design Consultation\n"
                "Cosmetic planning to completely transform your smile.\n\n"
                "12. Emergency Dental Care\n"
                "Immediate relief for severe tooth pain or trauma.\n\n"
                "You can select an option from the menu below or type /restart."
            )
            send_message(chat_id, services_text, reply_markup=MAIN_MENU_KEYBOARD)
        elif opt == "3":
            log_inquiry(chat_id, username, "Viewed Clinic Location")
            clinic_address = get_setting("CLINIC_ADDRESS", "No. 45, Anna Nagar Main Road, Anna Nagar West, Chennai, Tamil Nadu 600040")
            clinic_landmark = get_setting("CLINIC_LANDMARK", "Near Anna Nagar Tower Metro Station")
            clinic_maps = get_setting("CLINIC_GOOGLE_MAPS", "https://maps.google.com/?q=Bright+Smile+Dental+Care+Anna+Nagar+Chennai")
            location_text = (
                f"{clinic_name}\n\n"
                f"{clinic_address}\n\n"
                f"Landmark:\n"
                f"{clinic_landmark}\n\n"
                f"Google Maps:\n"
                f"{clinic_maps}"
            )
            send_message(chat_id, location_text, reply_markup=MAIN_MENU_KEYBOARD)
        elif opt == "4":
            log_inquiry(chat_id, username, "Viewed Contact Doctor Info")
            doctor_name = get_setting("DOCTOR_NAME", "Dr. Arjun Kumar")
            doctor_qual = get_setting("DOCTOR_QUAL", "BDS, MDS (Conservative Dentistry)")
            doctor_exp = get_setting("DOCTOR_EXP", "12 Years")
            doctor_specialties = get_setting("DOCTOR_SPECIALTIES", "General & Cosmetic Dentistry")
            clinic_contact = get_setting("CLINIC_CONTACT", "+91 91234 56789")
            clinic_email = get_setting("CLINIC_EMAIL", "doctor@brightsmilecare.in")
            doctor_text = (
                f"{doctor_name}\n\n"
                f"{doctor_qual}\n"
                f"Experience: {doctor_exp}\n\n"
                f"Specialization:\n"
                f"{doctor_specialties}\n\n"
                f"Phone:\n"
                f"{clinic_contact}\n"
                f"Email:\n"
                f"{clinic_email}"
            )
            send_message(chat_id, doctor_text, reply_markup=MAIN_MENU_KEYBOARD)
        elif opt == "5":
            log_inquiry(chat_id, username, "Viewed Working Hours")
            hours_text = (
                "Clinic Working Hours\n\n"
                "Monday - Saturday\n"
                "09:00 AM - 01:00 PM\n"
                "04:00 PM - 06:00 PM\n\n"
                "Sunday\n"
                "Closed"
            )
            send_message(chat_id, hours_text, reply_markup=MAIN_MENU_KEYBOARD)
        elif opt == "6":
            log_inquiry(chat_id, username, "Viewed FAQs")
            faq_text = (
                "Frequently Asked Questions (FAQ)\n\n"
                "Q: What is the consultation fee?\n"
                "A: The standard consultation fee is ₹500.\n\n"
                "Q: Do you accept walk-in patients?\n"
                "A: Yes. However, appointments are recommended to reduce waiting time.\n\n"
                "Q: What payment methods are accepted?\n"
                "A: UPI, Cash, Debit Card, Credit Card, and Net Banking.\n\n"
                "Q: Do you provide emergency treatment?\n"
                "A: Yes. Emergency dental care is available during clinic hours.\n\n"
                "Q: Can I reschedule my appointment?\n"
                "A: Yes. You can choose the Reschedule Appointment option from the main menu."
            )
            send_message(chat_id, faq_text, reply_markup=MAIN_MENU_KEYBOARD)
        elif opt == "7":
            log_inquiry(chat_id, username, "Viewed Emergency Support Info")
            emergency_contact = get_setting("EMERGENCY_CONTACT", "+91 98765 43210")
            emergency_text = (
                "Emergency Dental Support\n\n"
                "If you are experiencing:\n"
                "• Severe Tooth Pain\n"
                "• Bleeding\n"
                "• Facial Swelling\n"
                "• Dental Trauma\n"
                "• Broken Tooth\n\n"
                f"Please contact immediately:\n"
                f"Emergency Helpline: {emergency_contact}"
            )
            send_message(chat_id, emergency_text, reply_markup=MAIN_MENU_KEYBOARD)
        elif opt == "8":
            log_inquiry(chat_id, username, "Initiated Reschedule Flow")
            session["step"] = "reschedule_phone"
            send_message(chat_id, "Please enter your registered mobile number.", reply_markup=REMOVE_KEYBOARD)
        elif opt == "9":
            log_inquiry(chat_id, username, "Initiated Cancellation Flow")
            session["step"] = "cancel_phone"
            send_message(chat_id, "Please enter your registered mobile number.", reply_markup=REMOVE_KEYBOARD)
        else:
            send_message(chat_id, "Please select a valid option from the menu.", reply_markup=MAIN_MENU_KEYBOARD)
        return

    # --- BOOKING FLOW ---
    if step == "book_name":
        session["book_data"]["name"] = msg
        session["step"] = "book_phone"
        send_message(chat_id, "Please enter your mobile number.")
        return

    if step == "book_phone":
        formatted_phone = clean_phone_number(msg)
        if formatted_phone:
            session["book_data"]["phone"] = formatted_phone
            
            # Lookup past booking for returning patient
            past_booking = find_booking_by_phone(formatted_phone)
            if past_booking:
                past_service = past_booking.get("service", "Dental Visit")
                past_date = past_booking.get("date", "Previous Date")
                past_time = past_booking.get("time", "Previous Time")
                
                welcome_back_text = (
                    f"Welcome back, {session['book_data']['name']}!\n\n"
                    f"I found your previous booking history with us:\n"
                    f"Last Visit: {past_service} on {past_date} at {past_time}.\n\n"
                    f"We look forward to serving you again."
                )
                send_message(chat_id, welcome_back_text)
                time.sleep(1)
                
            session["step"] = "book_service"
            send_message(chat_id, "What service would you like to book?", reply_markup=SERVICES_KEYBOARD)
        else:
            send_message(chat_id, "Please enter a valid 10-digit mobile number.")
        return

    if step == "book_service":
        service_map = {
            "1": "General Checkup",
            "2": "Teeth Cleaning",
            "3": "Root Canal Treatment",
            "4": "Tooth Extraction",
            "5": "Teeth Whitening",
            "6": "Braces Consultation",
            "7": "Dental Implants",
            "8": "Other"
        }
        
        resolved = None
        for key, val in service_map.items():
            if msg.lower().startswith(key) or val.lower() in msg.lower():
                resolved = val
                break
                
        if resolved:
            session["book_data"]["service"] = resolved
            session["step"] = "book_date"
            send_message(chat_id, "Please choose an appointment date.", reply_markup=get_date_selection_keyboard())
        else:
            send_message(chat_id, "Please select a valid service from the options below:", reply_markup=SERVICES_KEYBOARD)
        return

    if step == "book_date":
        selected_date = None
        
        if "1" in msg or msg.lower() == "today":
            selected_date = get_ist_now().strftime("%d/%m/%Y")
        elif "2" in msg or msg.lower() == "tomorrow":
            selected_date = (get_ist_now() + timedelta(days=1)).strftime("%d/%m/%Y")
        elif "3" in msg or msg.lower() == "select another date":
            send_message(chat_id, "Please select a date from the options below:", reply_markup=get_date_keyboard())
            return
        else:
            match = re.search(r'(\d{2}/\d{2}/\d{4})', msg)
            if match:
                selected_date = match.group(1)
                
        if selected_date:
            if is_sunday(selected_date):
                send_message(
                    chat_id, 
                    "We are closed on Sundays. Please select a weekday (Monday to Saturday).", 
                    reply_markup=get_date_selection_keyboard()
                )
            else:
                session["book_data"]["date"] = selected_date
                session["step"] = "book_time"
                slots = get_available_slots(selected_date)
                if slots:
                    send_message(
                        chat_id,
                        f"Available Appointment Slots ({len(slots)} slots remaining):\n\nPlease choose your preferred slot.",
                        reply_markup=get_slots_keyboard(slots)
                    )
                else:
                    send_message(
                        chat_id,
                        "Unfortunately, there are no available slots for this date. Please choose another date.",
                        reply_markup=get_date_selection_keyboard()
                    )
        else:
            send_message(chat_id, "Please select a valid date from the options.", reply_markup=get_date_selection_keyboard())
        return

    if step == "book_time":
        date_str = session["book_data"]["date"]
        slots = get_available_slots(date_str)
        
        selected_slot = None
        for s in slots:
            if s.lower() == msg.lower():
                selected_slot = s
                break
                
        if selected_slot:
            session["book_data"]["time"] = selected_slot
            session["step"] = "book_confirm_final"
            
            summary_text = f"""Please review and confirm your booking:

Patient: {session['book_data']['name']}
Mobile: {session['book_data']['phone']}
Service: {session['book_data']['service']}
Date: {session['book_data']['date']}
Time: {session['book_data']['time']}
Clinic: {clinic_name}

Reply YES to confirm and book your appointment, or NO to cancel and restart."""
            send_message(chat_id, summary_text, reply_markup=YES_NO_KEYBOARD)
        else:
            parsed = normalize_time_input(msg)
            if parsed:
                if parsed in slots:
                    session["book_data"]["parsed_time"] = parsed
                    session["step"] = "book_confirm_time"
                    send_message(
                        chat_id,
                        f"I found your preferred slot as {parsed}.\n\nReply YES to confirm or NO to select another slot.",
                        reply_markup=YES_NO_KEYBOARD
                    )
                else:
                    send_message(
                        chat_id,
                        f"I recognized '{parsed}' but it is already booked. Please choose from the available slots:",
                        reply_markup=get_slots_keyboard(slots)
                    )
            else:
                send_message(
                    chat_id,
                    "I couldn't understand your response. Please choose one of the available options:",
                    reply_markup=get_slots_keyboard(slots)
                )
        return

    if step == "book_confirm_time":
        date_str = session["book_data"]["date"]
        slots = get_available_slots(date_str)
        
        if msg.lower() == "yes":
            parsed_time = session["book_data"]["parsed_time"]
            if parsed_time in slots:
                session["book_data"]["time"] = parsed_time
                session["step"] = "book_confirm_final"
                
                summary_text = f"""Please review and confirm your booking:

Patient: {session['book_data']['name']}
Mobile: {session['book_data']['phone']}
Service: {session['book_data']['service']}
Date: {session['book_data']['date']}
Time: {session['book_data']['time']}
Clinic: {clinic_name}

Reply YES to confirm and book your appointment, or NO to cancel and restart."""
                send_message(chat_id, summary_text, reply_markup=YES_NO_KEYBOARD)
            else:
                send_message(
                    chat_id,
                    "Unfortunately, that slot was just taken. Please choose another slot:",
                    reply_markup=get_slots_keyboard(slots)
                )
                session["step"] = "book_time"
        elif msg.lower() == "no":
            session["step"] = "book_time"
            send_message(
                chat_id,
                "Please choose your preferred slot:",
                reply_markup=get_slots_keyboard(slots)
            )
        else:
            send_message(chat_id, "Please reply with YES or NO.", reply_markup=YES_NO_KEYBOARD)
        return

    if step == "book_confirm_final":
        if msg.lower() == "yes":
            booking = book_slot(
                session["book_data"]["name"],
                session["book_data"]["phone"],
                session["book_data"]["service"],
                session["book_data"]["date"],
                session["book_data"]["time"],
                chat_id
            )
            confirm_text = f"""Appointment Confirmed

Patient:
{booking['name']}

Mobile:
{booking['phone']}

Service:
{booking['service']}

Date:
{booking['date']}

Time:
{booking['time']}

Clinic:
{clinic_name}

Reference Number:
{booking['booking_id']}

Please arrive 10 minutes before your appointment.

Thank you for choosing {clinic_name}.
We look forward to seeing you."""
            send_message(chat_id, confirm_text, reply_markup=REMOVE_KEYBOARD)
            send_admin_notification(booking)
            log_inquiry(chat_id, username, f"Successfully Booked Appointment (ID: {booking['booking_id']})")
            user_sessions.pop(chat_id, None)
            time.sleep(1.5)
            handle_text_message(chat_id, "/start", username)
        elif msg.lower() == "no":
            send_message(chat_id, "Booking cancelled. Returning to main menu...", reply_markup=REMOVE_KEYBOARD)
            user_sessions.pop(chat_id, None)
            time.sleep(1.5)
            handle_text_message(chat_id, "/start", username)
        else:
            send_message(chat_id, "Please reply with YES or NO to confirm your booking.", reply_markup=YES_NO_KEYBOARD)
        return

    # --- RESCHEDULE FLOW ---
    if step == "reschedule_phone":
        formatted_phone = clean_phone_number(msg)
        booking = find_booking_by_phone(formatted_phone) if formatted_phone else None
        
        if booking:
            session["reschedule_data"]["phone"] = formatted_phone
            session["reschedule_data"]["booking"] = booking
            session["step"] = "reschedule_select"
            
            appt_info = (
                "I found your appointment:\n\n"
                f"Patient: {booking['name']}\n"
                f"Service: {booking['service']}\n"
                f"Date: {booking['date']}\n"
                f"Time: {booking['time']}\n\n"
                "What would you like to change?"
            )
            send_message(chat_id, appt_info, reply_markup=RESCHEDULE_OPTIONS_KEYBOARD)
        else:
            send_message(
                chat_id,
                "I couldn't find any active appointment for this mobile number. Returning to main menu...",
                reply_markup=REMOVE_KEYBOARD
            )
            user_sessions.pop(chat_id, None)
            time.sleep(1.5)
            handle_text_message(chat_id, "/start", username)
        return

    if step == "reschedule_select":
        booking = session["reschedule_data"]["booking"]
        if "change date" in msg.lower() or "1" in msg:
            session["reschedule_data"]["choice"] = "date"
            session["step"] = "reschedule_date"
            send_message(chat_id, "Please choose a new appointment date.", reply_markup=get_date_selection_keyboard())
        elif "change time" in msg.lower() or "2" in msg:
            session["reschedule_data"]["choice"] = "time"
            session["step"] = "reschedule_time"
            slots = get_available_slots(booking["date"])
            send_message(
                chat_id,
                "Please choose a new preferred time slot:",
                reply_markup=get_slots_keyboard(slots)
            )
        else:
            send_message(chat_id, "Please select an option from the menu.", reply_markup=RESCHEDULE_OPTIONS_KEYBOARD)
        return

    if step == "reschedule_date":
        selected_date = None
        if "1" in msg or msg.lower() == "today":
            selected_date = get_ist_now().strftime("%d/%m/%Y")
        elif "2" in msg or msg.lower() == "tomorrow":
            selected_date = (get_ist_now() + timedelta(days=1)).strftime("%d/%m/%Y")
        elif "3" in msg or msg.lower() == "select another date":
            send_message(chat_id, "Please select a date from the options below:", reply_markup=get_date_keyboard())
            return
        else:
            match = re.search(r'(\d{2}/\d{2}/\d{4})', msg)
            if match:
                selected_date = match.group(1)
                
        if selected_date:
            if is_sunday(selected_date):
                send_message(
                    chat_id, 
                    "We are closed on Sundays. Please select a weekday (Monday to Saturday).", 
                    reply_markup=get_date_selection_keyboard()
                )
            else:
                session["reschedule_data"]["new_date"] = selected_date
                session["step"] = "reschedule_time"
                slots = get_available_slots(selected_date)
                if slots:
                    send_message(
                        chat_id,
                        f"Available Appointment Slots ({len(slots)} slots remaining):\n\nPlease choose a new preferred slot.",
                        reply_markup=get_slots_keyboard(slots)
                    )
                else:
                    send_message(
                        chat_id,
                        "Unfortunately, there are no available slots for this date. Please choose another date.",
                        reply_markup=get_date_selection_keyboard()
                    )
        else:
            send_message(chat_id, "Please select a valid date from the options.", reply_markup=get_date_selection_keyboard())
        return

    if step == "reschedule_time":
        booking = session["reschedule_data"]["booking"]
        target_date = session["reschedule_data"].get("new_date") or booking["date"]
        slots = get_available_slots(target_date)
        
        selected_slot = None
        for s in slots:
            if s.lower() == msg.lower():
                selected_slot = s
                break
                
        if selected_slot:
            old_date = booking["date"]
            old_time = booking["time"]
            updated = update_booking(
                booking["booking_id"],
                new_date=target_date,
                new_time=selected_slot
            )
            confirm_text = f"""Appointment Rescheduled Successfully

Patient:
{updated['name']}

Mobile:
{updated['phone']}

Service:
{updated['service']}

Date:
{updated['date']}

Time:
{updated['time']}

Reference Number:
{updated['booking_id']}"""
            send_message(chat_id, confirm_text, reply_markup=REMOVE_KEYBOARD)
            send_admin_reschedule_notification(updated, old_date, old_time)
            log_inquiry(chat_id, username, f"Successfully Rescheduled Appointment (ID: {updated['booking_id']})")
            user_sessions.pop(chat_id, None)
            time.sleep(1.5)
            handle_text_message(chat_id, "/start", username)
        else:
            parsed = normalize_time_input(msg)
            if parsed:
                if parsed in slots:
                    session["reschedule_data"]["parsed_time"] = parsed
                    session["step"] = "reschedule_confirm_time"
                    send_message(
                        chat_id,
                        f"I found your preferred slot as {parsed}.\n\nReply YES to confirm or NO to select another slot.",
                        reply_markup=YES_NO_KEYBOARD
                    )
                else:
                    send_message(
                        chat_id,
                        f"I recognized '{parsed}' but it is already booked. Please choose from the available slots:",
                        reply_markup=get_slots_keyboard(slots)
                    )
            else:
                send_message(
                    chat_id,
                    "I couldn't understand your response. Please choose one of the available options:",
                    reply_markup=get_slots_keyboard(slots)
                )
        return

    if step == "reschedule_confirm_time":
        booking = session["reschedule_data"]["booking"]
        target_date = session["reschedule_data"].get("new_date") or booking["date"]
        slots = get_available_slots(target_date)
        
        if msg.lower() == "yes":
            parsed_time = session["reschedule_data"]["parsed_time"]
            if parsed_time in slots:
                old_date = booking["date"]
                old_time = booking["time"]
                updated = update_booking(
                    booking["booking_id"],
                    new_date=target_date,
                    new_time=parsed_time
                )
                confirm_text = f"""Appointment Rescheduled Successfully

Patient:
{updated['name']}

Mobile:
{updated['phone']}

Service:
{updated['service']}

Date:
{updated['date']}

Time:
{updated['time']}

Reference Number:
{updated['booking_id']}"""
                send_message(chat_id, confirm_text, reply_markup=REMOVE_KEYBOARD)
                send_admin_reschedule_notification(updated, old_date, old_time)
                log_inquiry(chat_id, username, f"Successfully Rescheduled Appointment via Smart Time (ID: {updated['booking_id']})")
                user_sessions.pop(chat_id, None)
                time.sleep(1.5)
                handle_text_message(chat_id, "/start", username)
            else:
                send_message(
                    chat_id,
                    "Unfortunately, that slot was just taken. Please choose another slot:",
                    reply_markup=get_slots_keyboard(slots)
                )
                session["step"] = "reschedule_time"
        elif msg.lower() == "no":
            session["step"] = "reschedule_time"
            send_message(
                chat_id,
                "Please choose a preferred slot:",
                reply_markup=get_slots_keyboard(slots)
            )
        else:
            send_message(chat_id, "Please reply with YES or NO.", reply_markup=YES_NO_KEYBOARD)
        return

    # --- CANCEL FLOW ---
    if step == "cancel_phone":
        formatted_phone = clean_phone_number(msg)
        booking = find_booking_by_phone(formatted_phone) if formatted_phone else None
        
        if booking:
            session["cancel_data"]["booking"] = booking
            session["step"] = "cancel_confirm"
            
            appt_info = (
                "I found your appointment:\n\n"
                f"Patient: {booking['name']}\n"
                f"Service: {booking['service']}\n"
                f"Date: {booking['date']}\n"
                f"Time: {booking['time']}\n\n"
                "Are you sure you want to cancel this appointment?"
            )
            send_message(chat_id, appt_info, reply_markup=YES_NO_KEYBOARD)
        else:
            send_message(
                chat_id,
                "I couldn't find any active appointment for this mobile number. Returning to main menu...",
                reply_markup=REMOVE_KEYBOARD
            )
            user_sessions.pop(chat_id, None)
            time.sleep(1.5)
            handle_text_message(chat_id, "/start", username)
        return

    if step == "cancel_confirm":
        booking = session["cancel_data"]["booking"]
        if msg.lower() == "yes":
            success = cancel_booking(booking["booking_id"])
            if success:
                cancel_text = f"""Appointment Cancelled Successfully

Reference Number:
{booking['booking_id']}

We hope to serve you again."""
                send_message(chat_id, cancel_text, reply_markup=REMOVE_KEYBOARD)
                send_admin_cancel_notification(booking)
                log_inquiry(chat_id, username, f"Successfully Cancelled Appointment (ID: {booking['booking_id']})")
            else:
                send_message(chat_id, "Failed to cancel booking. It may have already been cancelled.", reply_markup=REMOVE_KEYBOARD)
            user_sessions.pop(chat_id, None)
            time.sleep(1.5)
            handle_text_message(chat_id, "/start", username)
        elif msg.lower() == "no":
            send_message(chat_id, "Cancellation aborted. Returning to main menu...", reply_markup=REMOVE_KEYBOARD)
            user_sessions.pop(chat_id, None)
            time.sleep(1.5)
            handle_text_message(chat_id, "/start", username)
        else:
            send_message(chat_id, "Please reply with YES or NO.", reply_markup=YES_NO_KEYBOARD)
        return

def poll_updates():
    offset = None
    print("Bot @tg_intel_search_bot is running and polling updates...")
    while True:
        url = f"{API_URL}/getUpdates"
        params = {"timeout": 30}
        if offset:
            params["offset"] = offset

        try:
            response = requests.get(url, params=params, timeout=35)
            if response.status_code == 200:
                data = response.json()
                if data.get("ok"):
                    for update in data.get("result", []):
                        offset = update["update_id"] + 1
                        message = update.get("message")
                        if not message:
                            continue
                        
                        chat = message.get("chat")
                        if not chat:
                            continue
                        
                        chat_id = chat["id"]
                        from_user = message.get("from", {})
                        username = from_user.get("username")
                        first_name = from_user.get("first_name", "")
                        last_name = from_user.get("last_name", "")
                        display_name = username or f"{first_name} {last_name}".strip() or str(chat_id)
                        
                        text = message.get("text")
                        if text:
                            printable_name = display_name.encode('ascii', errors='ignore').decode('ascii')
                            printable_text = text.encode('ascii', errors='ignore').decode('ascii')
                            print(f"Received message from {printable_name}: {printable_text}")
                            handle_text_message(chat_id, text, display_name)
                        else:
                            send_message(chat_id, "Please reply with a valid option or text message.")
            else:
                print(f"Error from getUpdates API: Status code {response.status_code}, Response: {response.text}")
                time.sleep(5)
        except requests.exceptions.RequestException as e:
            print(f"Network error in polling updates: {e}")
            time.sleep(5)
        except Exception as e:
            print(f"Unexpected error: {e}")
            time.sleep(5)

# Background scheduler loop to run check_reminders_and_feedback
def reminder_scheduler_loop():
    while True:
        try:
            check_reminders_and_feedback()
        except Exception as e:
            print(f"Error in scheduler loop: {e}")
        time.sleep(60) # check every minute

if __name__ == "__main__":
    # Start reminders & feedback daemon thread
    threading.Thread(target=reminder_scheduler_loop, daemon=True).start()
    
    try:
        poll_updates()
    except KeyboardInterrupt:
        print("Bot stopped by user.")