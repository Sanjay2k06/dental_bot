from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
import os
import json
import threading

from storage import load_data, save_data, load_settings, save_settings
from appointments import ALL_SLOTS, get_available_slots

app = FastAPI()

class SettingsModel(BaseModel):
    CLINIC_NAME: str
    CLINIC_ADDRESS: str
    CLINIC_CONTACT: str
    EMERGENCY_CONTACT: str
    CLINIC_EMAIL: str
    CLINIC_WEBSITE: str
    CLINIC_LANDMARK: str
    CLINIC_GOOGLE_MAPS: str
    DOCTOR_NAME: str
    DOCTOR_QUAL: str
    DOCTOR_EXP: str
    DOCTOR_SPECIALTIES: str
    ADMIN_CHAT_ID: str

@app.on_event("startup")
def startup_event():
    # Import main bot modules inside event to prevent circular dependency imports
    try:
        from main import poll_updates, reminder_scheduler_loop
        print("Starting Telegram Bot polling loop in background thread...")
        threading.Thread(target=poll_updates, daemon=True).start()
        
        print("Starting Reminders and Feedback scheduler loop in background thread...")
        threading.Thread(target=reminder_scheduler_loop, daemon=True).start()
    except Exception as e:
        print(f"Error starting background bot threads: {e}")

@app.get("/api/appointments")
def get_appointments():
    return load_data()

@app.post("/api/appointments/cancel/{booking_id}")
def cancel_appt(booking_id: str):
    from appointments import cancel_booking
    
    # Load booking details to notify admin
    appointments = load_data()
    booking = None
    for appt in appointments:
        if appt.get("booking_id") == booking_id:
            booking = appt
            break
            
    success = cancel_booking(booking_id)
    if not success:
        raise HTTPException(status_code=404, detail="Booking not found")
        
    if booking:
        # Send admin notification
        from storage import get_setting
        admin_id = get_setting("ADMIN_CHAT_ID")
        token = os.getenv("TELEGRAM_BOT_TOKEN")
        if admin_id and token:
            url = f"https://api.telegram.org/bot{token}/sendMessage"
            admin_text = f"""Appointment Cancelled (via Admin Panel)

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
            try:
                import requests
                requests.post(url, json={"chat_id": admin_id, "text": admin_text}, timeout=10)
            except Exception as e:
                print(f"Error sending admin cancel notification: {e}")
                
    return {"status": "success"}

@app.get("/api/inquiries")
def get_inquiries():
    try:
        with open("data/inquiries.json", "r") as f:
            return json.load(f)
    except:
        return []

@app.get("/api/settings")
def get_settings():
    merged = {}
    keys = [
        "CLINIC_NAME", "CLINIC_ADDRESS", "CLINIC_CONTACT", "EMERGENCY_CONTACT",
        "CLINIC_EMAIL", "CLINIC_WEBSITE", "CLINIC_LANDMARK", "CLINIC_GOOGLE_MAPS",
        "DOCTOR_NAME", "DOCTOR_QUAL", "DOCTOR_EXP", "DOCTOR_SPECIALTIES",
        "ADMIN_CHAT_ID"
    ]
    file_settings = load_settings()
    for k in keys:
        merged[k] = file_settings.get(k) or os.getenv(k, "")
    return merged

@app.post("/api/settings")
def update_settings(settings: SettingsModel):
    save_settings(settings.dict())
    for k, v in settings.dict().items():
        os.environ[k] = v
    return {"status": "success"}

@app.get("/api/slots")
def get_slots(date: str):
    appointments = load_data()
    booked_map = {}
    for appt in appointments:
        if appt.get("date") == date:
            booked_map[appt.get("time")] = {
                "booking_id": appt.get("booking_id"),
                "name": appt.get("name"),
                "phone": appt.get("phone"),
                "service": appt.get("service")
            }
            
    slots_status = []
    for slot in ALL_SLOTS:
        if slot in booked_map:
            slots_status.append({
                "time": slot,
                "status": "booked",
                "booking": booked_map[slot]
            })
        else:
            slots_status.append({
                "time": slot,
                "status": "available",
                "booking": None
            })
    return slots_status

# Mount static folder
app.mount("/static", StaticFiles(directory="static"), name="static")

@app.get("/")
def read_index():
    return FileResponse("static/index.html")
