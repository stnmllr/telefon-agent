# ============================================================
# app/utils/twiml_builder.py
# Hilfsfunktionen für Twilio Markup Language (TwiML)
# Twilio versteht XML-Antworten und steuert damit den Anruf.
# ============================================================


def build_welcome_twiml(message: str, transcribe_url: str) -> str:
    """
    Begrüßt den Anrufer und öffnet <Gather> für Spracheingabe.
    Twilio transkribiert die Sprache und sendet das Ergebnis
    an transcribe_url (POST mit SpeechResult).
    """
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
  <Gather input="speech"
          action="{transcribe_url}"
          method="POST"
          language="de-DE"
          speechTimeout="auto"
          speechModel="phone_call">
    <Say language="de-DE" voice="Polly.Marlene">{message}</Say>
  </Gather>
  <Say language="de-DE" voice="Polly.Marlene">
    Ich habe leider keine Eingabe erhalten. Auf Wiederhören.
  </Say>
</Response>"""


def build_answer_twiml(answer: str, transcribe_url: str) -> str:
    """
    Liest die Antwort vor und wartet direkt auf die nächste Frage.
    Ermöglicht ein mehrstufiges Gespräch.
    """
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
  <Gather input="speech"
          action="{transcribe_url}"
          method="POST"
          language="de-DE"
          speechTimeout="auto"
          speechModel="phone_call">
    <Say language="de-DE" voice="Polly.Marlene">{answer}</Say>
    <Say language="de-DE" voice="Polly.Marlene">
      Haben Sie weitere Fragen?
    </Say>
  </Gather>
  <Say language="de-DE" voice="Polly.Marlene">
    Vielen Dank für Ihren Anruf. Auf Wiederhören.
  </Say>
</Response>"""


def build_fallback_twiml(message: str, transcribe_url: str) -> str:
    """
    Fallback bei schlechter STT-Qualität oder leerer Eingabe.
    """
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
  <Gather input="speech"
          action="{transcribe_url}"
          method="POST"
          language="de-DE"
          speechTimeout="auto">
    <Say language="de-DE" voice="Polly.Marlene">{message}</Say>
  </Gather>
</Response>"""
