# ============================================================
# app/utils/twiml_builder.py
# ============================================================

def build_welcome_twiml(message: str, transcribe_url: str) -> str:
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
  <Gather input="speech"
          action="{transcribe_url}"
          method="POST"
          language="de-DE"
          speechTimeout="10"
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
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
  <Gather input="speech"
          action="{transcribe_url}"
          method="POST"
          language="de-DE"
          speechTimeout="10"
          speechModel="phone_call"
          enhanced="true"
          actionOnEmptyResult="true">
    <Say language="de-DE" voice="Google.de-DE-Neural2-F">{answer}</Say>
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
          speechTimeout="10"
          speechModel="phone_call"
          enhanced="true"
          actionOnEmptyResult="true">
    <Say language="de-DE" voice="Google.de-DE-Neural2-F">{message}</Say>
  </Gather>
</Response>"""
