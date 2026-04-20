@echo off
set BASE_URL=https://telefon-agent-1051648887841.europe-west3.run.app

echo ========================================
echo SZENARIO 1: syska ProFI - Buchung erfassen
echo ========================================
curl -s -X POST %BASE_URL%/call/process -d "SpeechResult=Wie erfasse ich eine Buchung?" -d "Confidence=0.9" -d "CallSid=test-s1"

echo.
echo ========================================
echo SZENARIO 2: syska ProFI - Steuerkonto Differenz
echo ========================================
curl -s -X POST %BASE_URL%/call/process -d "SpeechResult=Ich habe eine Differenz zwischen meinem Steuerkonto und der theoretischen Steuer" -d "Confidence=0.9" -d "CallSid=test-s2"
echo.
echo ========================================
echo SZENARIO 3: Telefonbuch - Person suchen
echo ========================================
curl -s -X POST %BASE_URL%/call/process -d "SpeechResult=Ich moechte Herrn Schindler sprechen" -d "Confidence=0.9" -d "CallSid=test-s3"
echo.
echo ========================================
echo SZENARIO 4: ERP Support
echo ========================================
curl -s -X POST %BASE_URL%/call/process -d "SpeechResult=Ich habe ein Problem mit meinem ERP System" -d "Confidence=0.9" -d "CallSid=test-s4"
echo.
echo ========================================
echo SZENARIO 5: EVS Support
echo ========================================
curl -s -X POST %BASE_URL%/call/process -d "SpeechResult=Ich brauche Hilfe mit EVS" -d "Confidence=0.9" -d "CallSid=test-s5"
echo.
echo ========================================
echo SZENARIO 6: IT Problem
echo ========================================
curl -s -X POST %BASE_URL%/call/process -d "SpeechResult=Mein Computer startet nicht mehr" -d "Confidence=0.9" -d "CallSid=test-s6"
echo.
echo ========================================
echo SZENARIO 7: Verwaltung / Rechnung
echo ========================================
curl -s -X POST %BASE_URL%/call/process -d "SpeechResult=Ich habe eine Frage zu meiner Rechnung" -d "Confidence=0.9" -d "CallSid=test-s7"
echo.
echo ========================================
echo SZENARIO 8: Verabschiedung
echo ========================================
curl -s -X POST %BASE_URL%/call/process -d "SpeechResult=Nein danke tschuess" -d "Confidence=0.9" -d "CallSid=test-s8"
echo.
echo ========================================
echo SZENARIO 9a: Verwaltung - Kontaktdaten-Rueckfrage ausloesen
echo ========================================
curl -s -X POST %BASE_URL%/call/process -d "SpeechResult=Mein Name ist Einmueller, ich habe eine Frage zu meinem Vertrag. Welche Module haben wir in der Fibu im Einsatz?" -d "Confidence=0.9" -d "CallSid=test-s9" -d "From=%%2B4989123456"
echo.
echo ========================================
echo SZENARIO 9b: Kontaktdaten nennen und E-Mail ausloesen
echo ========================================
curl -s -X POST %BASE_URL%/call/process_contact -d "SpeechResult=Meine Nummer ist 089 12345 und meine Email ist einmueller at test punkt de" -d "CallSid=test-s9"
echo.
echo ========================================
echo ALLE TESTS ABGESCHLOSSEN
echo ========================================
pause
