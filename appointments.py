import random
from storage import load_data, save_data

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

def book_slot(name, phone, service, date_str, slot_time, telegram_chat_id):
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
            
    new_booking = {
        "booking_id": booking_id,
        "name": name,
        "phone": phone,
        "service": service,
        "date": date_str,
        "time": slot_time,
        "telegram_chat_id": telegram_chat_id
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
    data = load_data()
    updated_appt = None
    
    for appointment in data:
        if appointment.get("booking_id") == booking_id:
            if new_date:
                appointment["date"] = new_date
            if new_time:
                appointment["time"] = new_time
            updated_appt = appointment
            break
            
    if updated_appt:
        save_data(data)
        
    return updated_appt