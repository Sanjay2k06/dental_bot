# Bright Smile Dental Care - Bot & Admin Dashboard

An enterprise-grade clinic receptionist system featuring a Telegram booking bot and a secure FastAPI Web Admin Dashboard, designed to manage patient appointments, track slot occupancy, and log real-time bot interaction telemetry.

---

## 🤖 Telegram Bot Features

The bot acts as a premium clinic receptionist, handling user interactions smoothly without standard form-filling bottlenecks.

* **Global Command Routing**: Support for `/start`, `/menu`, `/cancel`, and `Restart` at any state. Sending these commands immediately resets or aborts the session, redirecting the user back to the appropriate welcome menu.
* **Smart Active Booking Flow**: Automatically scans if a Telegram user has an active booking today or in the future. If yes, it bypasses the 9-option menu and routes them directly to a simplified **Active Booking Menu**:
  1. Reschedule Appointment
  2. Cancel Appointment
  3. Restart (Return to Main Menu)
* **Dynamic Slot Count Metadata**: Offers date selections (`Today`, `Tomorrow`, and the next 5 days) with dynamic slot count remaining appended directly to the buttons (e.g., `Today (8 slots left)`).
* **Smart Time Normalization**: Uses regex to translate unstructured time inputs (e.g. `"5pm"`, `"1030"`, `"09:30 AM"`) to valid clinic time slots.
* **Pre-Booking Confirmation Summary**: Requires an explicit `YES/NO` confirmation from the patient after reviewing their details before writing the booking to the database.
* **Returning Patient Lookup**: Automatically detects past visits using the patient's phone number and displays a welcome back message showing their last visit details (service, date, and time).
* **Timezone-Aligned Reminders**: Sends automated reminders exactly 1 day before the appointment. Calculations are locked to India Standard Time (IST, UTC+5:30) to prevent server-side timezone shifts from causing incorrect or duplicate triggers. Initialized to skip reminders for same-day and next-day bookings to prevent spam.

---

## 📊 Web Admin Dashboard Features

A premium dashboard for receptionist staff, styled using curated colors, Outfit typography, and hover micro-animations.

* **Secure Authentication**: Protected under a beautiful Glassmorphism login screen. Authenticated sessions set a secure, browser-level `HttpOnly` cookie.
  * **Default Credentials**: Username: `taeknibot` / Password: `taeknibot123`
* **Locked API Endpoints**: All background data endpoints (appointments, slots, logs, configurations) require authentication and return `401 Unauthorized` for unsigned visitors.
* **Template Access Security**: The dashboard structure (`index.html`) is located in the `private/` folder. The server only returns this template to validated sessions, ensuring unauthenticated clients can only load the login page.
* **Real-time Overview Analytics**: Visual panels showing cumulative bookings, today's schedule count, and total inquiries.
* **searchable appointments database**: Filters appointments dynamically by patient name, mobile phone, service, or booking reference ID, and includes a **Cancel Slot** action trigger.
* **Interactive Slot occupancy Tracker**: Interactive date picker that displays a detailed visual timeline mapping available vs booked slots for any chosen date.
* **Telemetry & Logs Audit**: Displays real-time inquiries, commands, and errors sent to the bot.
* **Settings Panel Manager**: Edits clinic name, email, website, reception contacts, emergency lines, maps URLs, doctor specialties, and the Telegram `ADMIN_CHAT_ID`.
* **Multi-channel Admin Notifications**: Forwards Telegram alerts to the clinic administrator whenever a booking is created, rescheduled, or cancelled (either from the bot or the dashboard).

---

## 🛠️ Tech Stack & Directory Layout

* **Backend**: FastAPI, Python 3.10+
* **Frontend**: HTML5, Vanilla CSS, Javascript (ES6)
* **Database**: Local JSON structures (`data/`)

```
├── .env                  # Configuration Environment Variables
├── .gitignore            # Git exclusion rules
├── admin_server.py       # FastAPI web server, routing, and background loops
├── appointments.py       # Database querying, slot management, and updates
├── main.py               # Telegram bot polling, states, and scheduling
├── requirements.txt      # Project library dependencies
├── storage.py            # Local JSON read/write operations and IST timezone math
├── private/
│   └── index.html        # Recepetionist Dashboard HTML Template
└── static/
    ├── css/
    │   └── style.css     # Theme design system, layout, and login styling
    ├── js/
    │   └── app.js        # Dashboard state, fetches, filters, and logout events
    └── login.html        # Authentication login screen HTML template
```

---

## 🚀 Setup & Execution

### 1. Requirements
Install dependencies listed in the requirements file:
```bash
pip install -r requirements.txt
```

### 2. Environment Configuration
Create a `.env` file in the root directory:
```env
TELEGRAM_BOT_TOKEN=your_bot_token_here
ADMIN_CHAT_ID=your_chat_id_here
CLINIC_NAME=Bright Smile Dental Care
CLINIC_CONTACT=+91 91234 56789
EMERGENCY_CONTACT=+91 98765 43210
# Additional doctor & landmark configs...
```

### 3. Run Locally
To run both the Telegram Polling Loop and the FastAPI Dashboard in a single container process:
```bash
uvicorn admin_server:app --port 8000
```
Open `http://127.0.0.1:8000` in your web browser. Login using:
* **Username**: `taeknibot`
* **Password**: `taeknibot123`
