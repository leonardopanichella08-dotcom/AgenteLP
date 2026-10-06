"""Invia l'email della Rassegna tramite l'API di Resend (immagini incluse).

Uso:  python3 send_resend.py "<oggetto>" [cartella]   (default /tmp/rassegna)
Legge email.html ed email.txt. Richiede la variabile RESEND_API_KEY e
api.resend.com tra i domini consentiti dell'ambiente.
Esce con codice 2 se la chiave manca, 1 se l'invio fallisce, 0 se va a buon fine.
"""
import json
import os
import sys
import urllib.request

TO = "leonardopanichella08@gmail.com"


def main():
    key = os.environ.get("RESEND_API_KEY")
    if not key:
        print("MISSING_RESEND_API_KEY")
        sys.exit(2)
    subject = sys.argv[1]
    folder = sys.argv[2] if len(sys.argv) > 2 else "/tmp/rassegna"
    payload = {
        "from": os.environ.get("RESEND_FROM", "La Rassegna <onboarding@resend.dev>"),
        "to": [TO],
        "subject": subject,
        "html": open(os.path.join(folder, "email.html"), encoding="utf-8").read(),
        "text": open(os.path.join(folder, "email.txt"), encoding="utf-8").read(),
    }
    req = urllib.request.Request(
        "https://api.resend.com/emails",
        data=json.dumps(payload).encode(),
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            print("SENT", r.read().decode())
    except Exception as e:
        body = getattr(e, "read", lambda: b"")().decode(errors="ignore")
        print("FAILED", e, body[:300])
        sys.exit(1)


if __name__ == "__main__":
    main()
