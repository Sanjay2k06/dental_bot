from fastapi import FastAPI, Form, Response
from twilio.twiml.messaging_response import MessagingResponse

from appointments import (
    get_available_slots,
    book_slot
)

app = FastAPI()

user_sessions = {}


@app.post("/whatsapp")
async def whatsapp(

    Body: str = Form(...),
    From: str = Form(...)
):

    msg = Body.strip()

    response = MessagingResponse()

    reply = response.message()

    if msg.lower() in ["hi", "hello", "menu", "start", "reset"]:
        user_sessions.pop(From, None)

    if From not in user_sessions:

        user_sessions[From] = {
            "step": "menu"
        }

        reply.body(
            """
Welcome to Smile Dental Clinic.

How may we assist you today?

1. Book Appointment

2. Clinic Location

3. Contact Doctor
"""
        )

        return Response(content=str(response), media_type="application/xml")

    session = user_sessions[From]

    if session["step"] == "menu":

        if msg == "1":

            session["step"] = "name"

            reply.body(
                """
Certainly.

May I know your full name?
"""
            )

            return Response(content=str(response), media_type="application/xml")

    if session["step"] == "name":

        session["name"] = msg

        session["step"] = "slot"

        slots = get_available_slots()

        slot_text = "\n".join(slots)

        reply.body(
            f"""
Thank you, {msg}.

The following appointment times are currently available:

{slot_text}

Please type your preferred time.
"""
        )

        return Response(content=str(response), media_type="application/xml")

    if session["step"] == "slot":

        success = book_slot(
            session["name"],
            From,
            msg
        )

        if success:

            reply.body(
                f"""
Your appointment has been successfully confirmed.

Patient:
{session['name']}

Time:
{msg}

Thank you for choosing Smile Dental Clinic.

We look forward to seeing you.
"""
            )

        else:

            reply.body(
                """
Unfortunately that time has just been reserved.

Please choose another available slot.
"""
            )

        user_sessions.pop(From)

        return Response(content=str(response), media_type="application/xml")

    return Response(content=str(response), media_type="application/xml")