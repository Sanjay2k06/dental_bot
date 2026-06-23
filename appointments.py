import random
from storage import load_data, save_data, get_ist_now

ALL_SLOTS = [
    "09:00 AM",
    "09:30 AM",
    "10:00 AM",
    "10:30 AM",
    "11:00 AM",
    "11:30 AM",
    "12:00 PM",
    "04:00 PM",
    "04:30 PM",
    "05:00 PM",
    "05:30 PM"
]

def get_available_slots(date_str):
    data = load_data()
    
    # Get all slots booked on this specific date
    booked_slots = [
        appointment["time"]
        for appointment in data
        if appointment.get("date") == date_str
    ]
    
    available = []
    for slot in ALL_SLOTS:
        if slot not in booked_slots:
            available.append(slot)
            
    return available

def find_active_booking_by_chat_id(chat_id):
    from datetime import datetime
    today = get_ist_now().date()
    data = load_data()
    for appointment in reversed(data):
        if appointment.get("telegram_chat_id") == chat_id:
            appt_date_str = appointment.get("date")
            if not appt_date_str:
                continue
            try:
                appt_date = datetime.strptime(appt_date_str, "%d/%m/%Y").date()
                if appt_date >= today:
                    return appointment
            except:
                continue
    return None

def book_slot(name, phone, service, date_str, slot_time, telegram_chat_id):
    from datetime import datetime
    data = load_data()
    
    # Double check if slot is already booked on this date
    for appointment in data:
        if appointment.get("date") == date_str and appointment.get("time") == slot_time:
            return None
            
    # Generate unique random 6-digit booking ID: BSD-XXXXXX
    existing_ids = {appt.get("booking_id") for appt in data if appt.get("booking_id")}
    while True:
        rand_num = random.randint(100000, 999999)
        booking_id = f"BSD-{rand_num}"
        if booking_id not in existing_ids:
            break
            
    # Determine initial reminder_sent status
    # If appointment is for Today or Tomorrow, mark reminder_sent as True to prevent immediate spam
    reminder_sent = False
    try:
        today = get_ist_now().date()
        appt_date = datetime.strptime(date_str, "%d/%m/%Y").date()
        if (appt_date - today).days <= 1:
            reminder_sent = True
    except Exception as e:
        print(f"Error calculating reminder status during booking: {e}")
        
    new_booking = {
        "booking_id": booking_id,
        "name": name,
        "phone": phone,
        "service": service,
        "date": date_str,
        "time": slot_time,
        "telegram_chat_id": telegram_chat_id,
        "reminder_sent": reminder_sent,
        "feedback_collected": False
    }
    
    data.append(new_booking)
    save_data(data)
    return new_booking

def find_booking_by_phone(phone):
    data = load_data()
    # Normalize phone for comparison (remove spaces/dashes)
    clean_phone = "".join(filter(str.isdigit, phone))
    
    # Return the latest booking first
    for appointment in reversed(data):
        appt_phone = "".join(filter(str.isdigit, appointment.get("phone", "")))
        if appt_phone == clean_phone:
            return appointment
    return None

def cancel_booking(booking_id):
    data = load_data()
    initial_len = len(data)
    data = [appt for appt in data if appt.get("booking_id") != booking_id]
    if len(data) < initial_len:
        save_data(data)
        return True
    return False

def update_booking(booking_id, new_date=None, new_time=None):
    from datetime import datetime
    data = load_data()
    updated_appt = None
    
    for appointment in data:
        if appointment.get("booking_id") == booking_id:
            if new_date:
                appointment["date"] = new_date
            if new_time:
                appointment["time"] = new_time
                
            # Reset reminder_sent based on new date
            date_str = appointment.get("date")
            reminder_sent = False
            try:
                today = get_ist_now().date()
                appt_date = datetime.strptime(date_str, "%d/%m/%Y").date()
                if (appt_date - today).days <= 1:
                    reminder_sent = True
            except Exception as e:
                print(f"Error calculating reminder status during reschedule: {e}")
            
            appointment["reminder_sent"] = reminder_sent
            appointment["feedback_collected"] = False
            
            updated_appt = appointment
            break
            
    if updated_appt:
        save_data(data)
        
    return updated_appt