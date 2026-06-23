document.addEventListener('DOMContentLoaded', () => {
    // Current state variables
    let appointmentsData = [];
    let inquiriesData = [];
    let settingsData = {};

    // DOM Elements
    const navItems = document.querySelectorAll('.nav-item');
    const tabPanels = document.querySelectorAll('.tab-panel');
    const currentTabTitle = document.getElementById('current-tab-title');
    const currentTabDesc = document.getElementById('current-tab-desc');
    const clinicNameHeader = document.getElementById('clinic-name-header');

    // Date Format Helper (DD/MM/YYYY)
    function getTodayString() {
        const today = new Date();
        const yyyy = today.getFullYear();
        let mm = today.getMonth() + 1; // Months start at 0
        let dd = today.getDate();
        if (dd < 10) dd = '0' + dd;
        if (mm < 10) mm = '0' + mm;
        return dd + '/' + mm + '/' + yyyy;
    }

    // Convert Date Picker Value (YYYY-MM-DD) to Bot Format (DD/MM/YYYY)
    function formatDatePickerToBot(dateVal) {
        if (!dateVal) return '';
        const parts = dateVal.split('-');
        return `${parts[2]}/${parts[1]}/${parts[0]}`;
    }

    // Set Date Picker default to Today's date
    const slotPicker = document.getElementById('slot-picker-date');
    const today = new Date();
    const yyyy = today.getFullYear();
    const mm = String(today.getMonth() + 1).padStart(2, '0');
    const dd = String(today.getDate()).padStart(2, '0');
    slotPicker.value = `${yyyy}-${mm}-${dd}`;

    // --- TAB SYSTEM NAVIGATION ---
    const tabMetaData = {
        overview: { title: 'Overview', desc: 'Welcome to the clinic management panel.' },
        appointments: { title: 'Appointments Database', desc: 'View and manage scheduled dental bookings.' },
        slots: { title: 'Slots Occupancy Tracker', desc: 'Monitor slot allocations and check available times.' },
        inquiries: { title: 'Telemetry & Inquiries', desc: 'View real-time logs of patient interactions with the Telegram bot.' },
        settings: { title: 'Configurations Settings', desc: 'Update Doctor bio, specialties, clinic address and contact details.' }
    };

    navItems.forEach(item => {
        item.addEventListener('click', () => {
            const targetTab = item.getAttribute('data-tab');

            // Toggle active menu items
            navItems.forEach(nav => nav.classList.remove('active'));
            item.classList.add('active');

            // Toggle active tabs
            tabPanels.forEach(panel => panel.classList.remove('active'));
            document.getElementById(`tab-${targetTab}`).classList.add('active');

            // Update Titles
            currentTabTitle.textContent = tabMetaData[targetTab].title;
            currentTabDesc.textContent = tabMetaData[targetTab].desc;

            // Trigger specific tab loads
            if (targetTab === 'overview') {
                loadDashboardData();
            } else if (targetTab === 'appointments') {
                loadAppointmentsTab();
            } else if (targetTab === 'slots') {
                loadSlotsTrackerTab();
            } else if (targetTab === 'inquiries') {
                loadInquiriesTab();
            } else if (targetTab === 'settings') {
                loadSettingsTab();
            }
        });
    });

    // --- API DATA SERVICE HANDLERS ---

    // 1. Load Dashboard Data (Overview Tab)
    async function loadDashboardData() {
        try {
            // Load Settings (to update header clinic name)
            const settingsRes = await fetch('/api/settings');
            settingsData = await settingsRes.json();
            clinicNameHeader.textContent = settingsData.CLINIC_NAME || 'Bright Smile Dental Care';

            // Load Appointments
            const apptRes = await fetch('/api/appointments');
            appointmentsData = await apptRes.json();

            // Load Inquiries
            const inqRes = await fetch('/api/inquiries');
            inquiriesData = await inqRes.json();

            // Filter appointments scheduled for today
            const todayStr = getTodayString();
            document.getElementById('stat-today-date').textContent = `Date: ${todayStr}`;
            
            const todayAppts = appointmentsData.filter(appt => appt.date === todayStr);

            // Populate Overview Card Values
            document.getElementById('stat-total-bookings').textContent = appointmentsData.length;
            document.getElementById('stat-today-bookings').textContent = todayAppts.length;
            document.getElementById('stat-total-inquiries').textContent = inquiriesData.length;

            // Render Recent Bookings Table
            const tbody = document.getElementById('recent-bookings-table');
            tbody.innerHTML = '';

            // Get last 5 bookings (newest first)
            const recentBookings = [...appointmentsData].reverse().slice(0, 5);

            if (recentBookings.length === 0) {
                tbody.innerHTML = `<tr><td colspan="6" class="loading-text">No bookings found in the database.</td></tr>`;
                return;
            }

            recentBookings.forEach(appt => {
                const tr = document.createElement('tr');
                tr.innerHTML = `
                    <td><strong>${escapeHtml(appt.name)}</strong></td>
                    <td>${escapeHtml(appt.phone)}</td>
                    <td><span class="badge badge-success">${escapeHtml(appt.service)}</span></td>
                    <td>${escapeHtml(appt.date)}</td>
                    <td>${escapeHtml(appt.time)}</td>
                    <td><code>${escapeHtml(appt.booking_id)}</code></td>
                `;
                tbody.appendChild(tr);
            });

        } catch (err) {
            console.error('Error loading dashboard data:', err);
        }
    }

    // 2. Load Appointments Tab Table
    async function loadAppointmentsTab() {
        try {
            const res = await fetch('/api/appointments');
            appointmentsData = await res.json();
            renderAppointmentsTable(appointmentsData);
        } catch (err) {
            console.error('Error loading appointments:', err);
        }
    }

    function renderAppointmentsTable(data) {
        const tbody = document.getElementById('all-bookings-table');
        tbody.innerHTML = '';

        if (data.length === 0) {
            tbody.innerHTML = `<tr><td colspan="7" class="loading-text">No scheduled appointments found.</td></tr>`;
            return;
        }

        // Show newest first
        [...data].reverse().forEach(appt => {
            const tr = document.createElement('tr');
            tr.innerHTML = `
                <td><strong>${escapeHtml(appt.name)}</strong></td>
                <td>${escapeHtml(appt.phone)}</td>
                <td><span class="badge badge-success">${escapeHtml(appt.service)}</span></td>
                <td>${escapeHtml(appt.date)}</td>
                <td>${escapeHtml(appt.time)}</td>
                <td><code>${escapeHtml(appt.booking_id)}</code></td>
                <td style="text-align: center;">
                    <button class="btn btn-danger btn-sm cancel-btn" data-id="${appt.booking_id}">Cancel Slot</button>
                </td>
            `;
            tbody.appendChild(tr);
        });

        // Add event listeners to cancel buttons
        document.querySelectorAll('.cancel-btn').forEach(btn => {
            btn.addEventListener('click', async (e) => {
                const bookingId = e.target.getAttribute('data-id');
                if (confirm(`Are you sure you want to cancel appointment reference: ${bookingId}?`)) {
                    await cancelAppointment(bookingId);
                }
            });
        });
    }

    async function cancelAppointment(bookingId) {
        try {
            const res = await fetch(`/api/appointments/cancel/${bookingId}`, {
                method: 'POST'
            });
            if (res.ok) {
                // Refresh table
                await loadAppointmentsTab();
            } else {
                alert('Failed to cancel the appointment.');
            }
        } catch (err) {
            console.error('Error cancelling appointment:', err);
        }
    }

    // Appointments Search Handler
    document.getElementById('appt-search').addEventListener('input', (e) => {
        const query = e.target.value.toLowerCase().trim();
        const filtered = appointmentsData.filter(appt => {
            return (
                appt.name.toLowerCase().includes(query) ||
                appt.phone.toLowerCase().includes(query) ||
                appt.service.toLowerCase().includes(query) ||
                appt.booking_id.toLowerCase().includes(query)
            );
        });
        renderAppointmentsTable(filtered);
    });

    // 3. Load Slots Tracker Tab
    slotPicker.addEventListener('change', loadSlotsTrackerTab);

    async function loadSlotsTrackerTab() {
        const dateVal = slotPicker.value;
        if (!dateVal) return;

        const dateStr = formatDatePickerToBot(dateVal);
        document.getElementById('slots-view-title').textContent = `Slot allocations for ${dateStr}`;

        try {
            const res = await fetch(`/api/slots?date=${encodeURIComponent(dateStr)}`);
            const slots = await res.json();

            const grid = document.getElementById('slots-grid-display');
            grid.innerHTML = '';

            slots.forEach(slot => {
                const card = document.createElement('div');
                card.className = `slot-tile ${slot.status}`;

                if (slot.status === 'booked') {
                    card.innerHTML = `
                        <div class="slot-time-header">
                            <span>${slot.time}</span>
                            <span class="badge badge-danger slot-status-indicator">Booked</span>
                        </div>
                        <div class="slot-patient-info">
                            <span class="slot-patient-name">${escapeHtml(slot.booking.name)}</span>
                            <span class="slot-patient-phone">${escapeHtml(slot.booking.phone)}</span>
                            <span class="slot-patient-service">${escapeHtml(slot.booking.service)}</span>
                            <small style="display:block; margin-top: 4px; color: var(--text-muted);">Ref: ${escapeHtml(slot.booking.booking_id)}</small>
                        </div>
                    `;
                } else {
                    card.innerHTML = `
                        <div class="slot-time-header">
                            <span>${slot.time}</span>
                            <span class="badge badge-success slot-status-indicator">Available</span>
                        </div>
                        <div class="slot-patient-info" style="color: var(--text-muted); font-style: italic; font-size: 13px; margin-top: 6px;">
                            Ready for bookings
                        </div>
                    `;
                }
                grid.appendChild(card);
            });

        } catch (err) {
            console.error('Error fetching slots:', err);
        }
    }

    // 4. Load Telemetry & Inquiries Tab
    async function loadInquiriesTab() {
        try {
            const res = await fetch('/api/inquiries');
            inquiriesData = await res.json();

            const tbody = document.getElementById('inquiries-table');
            tbody.innerHTML = '';

            if (inquiriesData.length === 0) {
                tbody.innerHTML = `<tr><td colspan="4" class="loading-text">No telemetry queries logged yet.</td></tr>`;
                return;
            }

            // Show newest first
            [...inquiriesData].reverse().forEach(inq => {
                const tr = document.createElement('tr');
                tr.innerHTML = `
                    <td><strong>${escapeHtml(inq.username)}</strong></td>
                    <td><code>${escapeHtml(inq.chat_id)}</code></td>
                    <td><span class="badge ${inq.action.includes('Success') ? 'badge-success' : 'badge-danger'}" style="background-color: #f1f5f9; color: var(--text-color); font-weight: 500;">${escapeHtml(inq.action)}</span></td>
                    <td>${escapeHtml(inq.timestamp)}</td>
                `;
                tbody.appendChild(tr);
            });

        } catch (err) {
            console.error('Error loading inquiries:', err);
        }
    }

    // 5. Load Settings Tab
    async function loadSettingsTab() {
        try {
            const res = await fetch('/api/settings');
            settingsData = await res.json();

            // Pre-fill form fields
            Object.keys(settingsData).forEach(key => {
                const input = document.getElementById(key);
                if (input) {
                    input.value = settingsData[key];
                }
            });
        } catch (err) {
            console.error('Error loading settings:', err);
        }
    }

    // Submit Settings Form
    const settingsForm = document.getElementById('settings-form');
    const saveBtn = document.getElementById('save-settings-btn');
    const statusMsg = document.getElementById('settings-status-msg');

    settingsForm.addEventListener('submit', async (e) => {
        e.preventDefault();
        saveBtn.disabled = true;
        saveBtn.textContent = 'Saving Configurations...';

        // Gather form data
        const formData = {};
        new FormData(settingsForm).forEach((value, key) => {
            formData[key] = value;
        });

        try {
            const res = await fetch('/api/settings', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify(formData)
            });

            if (res.ok) {
                statusMsg.textContent = 'Configurations saved successfully!';
                statusMsg.className = 'status-msg success';
                clinicNameHeader.textContent = formData.CLINIC_NAME;
                // Fade out message after 3 seconds
                setTimeout(() => {
                    statusMsg.textContent = '';
                }, 3000);
            } else {
                statusMsg.textContent = 'Error saving configurations.';
                statusMsg.className = 'status-msg error';
            }
        } catch (err) {
            console.error('Error saving settings:', err);
            statusMsg.textContent = 'Network error saving configurations.';
            statusMsg.className = 'status-msg error';
        } finally {
            saveBtn.disabled = false;
            saveBtn.textContent = 'Save Configurations';
        }
    });

    // Helper: Escape HTML string
    function escapeHtml(str) {
        if (!str) return '';
        return String(str)
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;')
            .replace(/'/g, '&#039;');
    }

    // Initial Dashboard Data Load
    loadDashboardData();
});
