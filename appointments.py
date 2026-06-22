from storage import load_data, save_data


def get_available_slots():

    all_slots = [
        "09:00",
        "09:30",
        "10:00",
        "10:30",
        "11:00",
        "11:30",
        "12:00",
        "04:00",
        "04:30",
        "05:00",
        "05:30"
    ]

    data = load_data()

    booked_slots = [
        appointment["time"]
        for appointment in data
    ]

    available = []

    for slot in all_slots:
        if slot not in booked_slots:
            available.append(slot)

    return available


def book_slot(name, phone, slot):

    data = load_data()

    for appointment in data:

        if appointment["time"] == slot:

            return False

    data.append(
        {
            "name": name,
            "phone": phone,
            "time": slot
        }
    )

    save_data(data)

    return True