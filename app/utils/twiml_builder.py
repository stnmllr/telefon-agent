# ============================================================
# app/utils/twiml_builder.py
# ============================================================


def format_extension_ssml(durchwahl: str) -> str:
    digits = " ".join(list(str(durchwahl).replace("-", "").replace(" ", "").replace(".", "")))
    return f'<say-as interpret-as="characters">{digits}</say-as>'


def build_phonebook_answer_twiml(name: str, durchwahl: str, transcribe_url: str) -> str:
    ext_ssml = format_extension_ssml(durchwahl)
    text = (
        f"{name} erreichen Sie unter Durchwahl {ext_ssml}. "
        f"Ich kann leider keine direkte Weiterleitung vornehmen. "
        f"Kann ich Ihnen sonst noch helfen?"
    )
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
  <Gather input="speech"
          action="{transcribe_url}"
          method="POST"
          language="de-DE"
          speechTimeout="3"
          speechModel="phone_call"
          enhanced="true"
          actionOnEmptyResult="true">
    <Say language="de-DE" voice="Google.de-DE-Neural2-F">{text}</Say>
  </Gather>
  <Say language="de-DE" voice="Google.de-DE-Neural2-F">
    Vielen Dank für Ihren Anruf. Auf Wiederhören.
  </Say>
</Response>"""


def build_welcome_twiml(message: str, transcribe_url: str) -> str:
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
  <Gather input="speech"
          action="{transcribe_url}"
          method="POST"
          language="de-DE"
          speechTimeout="3"
          speechModel="phone_call"
          enhanced="true"
          actionOnEmptyResult="true">
    <Say language="de-DE" voice="Google.de-DE-Neural2-F">{message}</Say>
  </Gather>
  <Say language="de-DE" voice="Google.de-DE-Neural2-F">
    Ich habe leider keine Eingabe erhalten. Auf Wiederhören.
  </Say>
</Response>"""


def build_answer_twiml(answer: str, transcribe_url: str) -> str:
    answer_escaped = (
        answer
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
  <Gather input="speech"
          action="{transcribe_url}"
          method="POST"
          language="de-DE"
          speechTimeout="3"
          speechModel="phone_call"
          enhanced="true"
          actionOnEmptyResult="true">
    <Say language="de-DE" voice="Google.de-DE-Neural2-F">{answer_escaped}</Say>
  </Gather>
  <Say language="de-DE" voice="Google.de-DE-Neural2-F">
    Vielen Dank für Ihren Anruf. Auf Wiederhören.
  </Say>
</Response>"""


def build_farewell_twiml() -> str:
    return """<?xml version="1.0" encoding="UTF-8"?>
<Response>
  <Say language="de-DE" voice="Google.de-DE-Neural2-F">
    Gerne. Auf Wiederhören!
  </Say>
  <Hangup/>
</Response>"""


def build_fallback_twiml(message: str, transcribe_url: str) -> str:
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
  <Gather input="speech"
          action="{transcribe_url}"
          method="POST"
          language="de-DE"
          speechTimeout="3"
          speechModel="phone_call"
          enhanced="true"
          actionOnEmptyResult="true">
    <Say language="de-DE" voice="Google.de-DE-Neural2-F">{message}</Say>
  </Gather>
</Response>"""


# ── Stage-Flow TwiML-Builder ─────────────────────────────────

_VOICE = "Google.de-DE-Neural2-F"

_TEAM_NAMES = {
    "erp":        "dem ERP-Support",
    "evs":        "dem EVS-Support",
    "hr":         "dem HR-Support",
    "it":         "dem IT-Support",
    "verwaltung": "Herrn Müller",
    "nachricht":  "Herrn Müller",
    "phonebook":  "der zuständigen Person",
}

_EMAIL_OFFER_MESSAGES = {
    "erp":        "Soll ich Ihr Anliegen per E-Mail an den ERP-Support weiterleiten?",
    "evs":        "Soll ich Ihr Anliegen per E-Mail an den EVS-Support weiterleiten?",
    "hr":         "Soll ich Ihr Anliegen per E-Mail an den HR-Support weiterleiten?",
    "it":         "Soll ich Ihr Anliegen per E-Mail an den IT-Support weiterleiten?",
    "verwaltung": "Soll ich Ihr Anliegen per E-Mail an Herrn Müller weiterleiten?",
    "nachricht":  "Soll ich Ihre Nachricht per E-Mail an Herrn Müller weiterleiten?",
    "phonebook":  "Soll ich Ihr Anliegen per E-Mail weiterleiten?",
}


def _xml_escape(text: str) -> str:
    return (
        text.replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
            .replace('"', "&quot;")
    )


def _build_gather(msg: str, action: str) -> str:
    safe = _xml_escape(msg)
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
  <Gather input="speech" action="{action}" method="POST"
          language="de-DE" speechTimeout="7">
    <Say language="de-DE" voice="{_VOICE}">{safe}</Say>
  </Gather>
  <Redirect method="POST">{action}</Redirect>
</Response>"""


def build_email_offer_twiml(category: str) -> str:
    msg = _EMAIL_OFFER_MESSAGES.get(category, "Soll ich Ihr Anliegen per E-Mail weiterleiten?")
    return _build_gather(msg, "/call/process")


def build_email_offer_custom_twiml(msg: str) -> str:
    return _build_gather(msg, "/call/process")


def build_addition_ask_twiml() -> str:
    return _build_gather(
        "Möchten Sie noch etwas ergänzen? Wenn nicht, sagen Sie einfach Nein.",
        "/call/process",
    )


def build_callback_offer_twiml(category: str) -> str:
    team = _TEAM_NAMES.get(category, "dem zuständigen Team")
    msg = f"Kein Problem. Möchten Sie stattdessen einen Rückruf von {team}?"
    return _build_gather(msg, "/call/process")


def build_callback_phone_twiml() -> str:
    return _build_gather("Wie lautet Ihre Rückrufnummer?", "/call/process_contact")


def build_goodbye_hangup_twiml() -> str:
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
  <Say language="de-DE" voice="{_VOICE}">
    Kein Problem. Vielen Dank für Ihren Anruf. Ich wünsche Ihnen noch einen schönen Tag. Auf Wiederhören!
  </Say>
  <Hangup/>
</Response>"""
