"""
notifier.py — WhatsApp notification dispatcher via Meta WhatsApp Business Cloud API.

The Meta WhatsApp Cloud API is completely free up to 1,000 conversations/month.
No third-party relay (like CallMeBot) is needed — messages go directly through
Meta's official infrastructure.

Setup (one-time, ~10 minutes):
  1. Go to https://developers.facebook.com → My Apps → Create App (Business type).
  2. Add Product → WhatsApp → Set up.
  3. Under "API Setup" copy your:
       • Phone Number ID  →  WA_PHONE_NUMBER_ID  (env var)
       • Temporary access token  →  WA_ACCESS_TOKEN  (env var)
  4. Under "Recipient phone numbers", click "Add phone number" and verify
     your WhatsApp number with an OTP. This allows the sandbox to message you.
  5. Add the two env vars to your .env file (locally) or GitHub Secrets (CI).

API reference:
  POST https://graph.facebook.com/v20.0/{PHONE_NUMBER_ID}/messages
  Headers:
    Authorization: Bearer {ACCESS_TOKEN}
    Content-Type: application/json
  Body (text message):
    {
      "messaging_product": "whatsapp",
      "to": "<RECIPIENT_NUMBER_E164>",
      "type": "text",
      "text": {"body": "<MESSAGE>"}
    }
"""

import time
import requests

from config import WHATSAPP_PHONE, WA_PHONE_NUMBER_ID, WA_ACCESS_TOKEN


def _graph_url() -> str:
    return f"https://graph.facebook.com/v20.0/{WA_PHONE_NUMBER_ID}/messages"


def send_whatsapp(message: str, retries: int = 3, delay: float = 5.0) -> bool:
    """
    Send *message* to the configured WhatsApp number via Meta's Cloud API.

    Parameters
    ----------
    message : str
        Plain text message to send (up to 4096 characters).
    retries : int
        Number of total attempts before giving up (default 3).
    delay : float
        Seconds to wait between retry attempts (default 5 s).

    Returns
    -------
    bool
        True if the message was dispatched successfully, False otherwise.
    """
    headers = {
        "Authorization": f"Bearer {WA_ACCESS_TOKEN}",
        "Content-Type": "application/json",
    }
    payload = {
        "messaging_product": "whatsapp",
        "to": WHATSAPP_PHONE,
        "type": "text",
        "text": {"body": message},
    }

    for attempt in range(1, retries + 1):
        try:
            response = requests.post(
                _graph_url(), headers=headers, json=payload, timeout=15
            )

            if response.status_code == 200:
                data   = response.json()
                msg_id = (
                    data.get("messages", [{}])[0].get("id", "unknown")
                    if data.get("messages")
                    else "unknown"
                )
                print(
                    f"✅ WhatsApp message dispatched successfully "
                    f"(attempt {attempt}, message_id: {msg_id})."
                )
                return True

            # Non-200: parse the Meta error for a helpful message
            error_info = response.json().get("error", {})
            error_msg  = error_info.get("message", response.text[:200])
            error_code = error_info.get("code", response.status_code)
            print(
                f"⚠️  Attempt {attempt}/{retries} — Meta API error "
                f"[code {error_code}]: {error_msg}"
            )

        except requests.exceptions.RequestException as exc:
            print(f"⚠️  Attempt {attempt}/{retries} — Network error: {exc}")

        if attempt < retries:
            print(f"   Retrying in {delay}s …")
            time.sleep(delay)

    print("❌ Failed to send WhatsApp message after all retries.")
    print(
        "   Common fixes:\n"
        "   • Verify your WA_ACCESS_TOKEN is valid (not expired).\n"
        "   • Make sure WHATSAPP_PHONE is in E.164 format (e.g. +919876543210).\n"
        "   • Confirm your recipient number is added to the Meta sandbox allowlist.\n"
        "   • Check https://developers.facebook.com/docs/whatsapp/cloud-api/support"
    )
    return False
