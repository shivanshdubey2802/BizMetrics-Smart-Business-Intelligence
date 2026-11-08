"""
BizMetrics Communication Integration Engine
Provides WhatsApp message generation, email notifications, invoice sharing,
payment reminders, and order status alerts using configured genuine APIs
(SMTP, Twilio WhatsApp / Meta WhatsApp Cloud API) with graceful fallback
to direct wa.me and mailto URLs.
"""
from __future__ import annotations

import os
import smtplib
import urllib.parse
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.application import MIMEApplication
from typing import Any, Optional


def get_configured_providers() -> dict[str, bool]:
    """Check which genuine external communication APIs are actively configured."""
    smtp_ready = bool(os.getenv("SMTP_HOST") and os.getenv("SMTP_USER") and os.getenv("SMTP_PASSWORD"))
    twilio_ready = bool(os.getenv("TWILIO_ACCOUNT_SID") and os.getenv("TWILIO_AUTH_TOKEN") and os.getenv("TWILIO_WHATSAPP_NUMBER"))
    meta_wa_ready = bool(os.getenv("WHATSAPP_CLOUD_API_TOKEN") and os.getenv("WHATSAPP_PHONE_NUMBER_ID"))

    return {
        "smtp_email": smtp_ready,
        "twilio_whatsapp": twilio_ready,
        "meta_whatsapp": meta_wa_ready,
    }


def format_whatsapp_url(phone: str, message: str) -> str:
    """
    Generates a genuine, direct WhatsApp Click-to-Chat deep link.
    Works natively on Android, iOS, Windows, and WhatsApp Web without API costs.
    """
    clean_phone = "".join(filter(str.isdigit, str(phone)))
    if len(clean_phone) == 10:
        clean_phone = "91" + clean_phone  # Default to India ISD code (+91)
    
    encoded_text = urllib.parse.quote(message)
    return f"https://api.whatsapp.com/send?phone={clean_phone}&text={encoded_text}"


def format_mailto_url(email: str, subject: str, body: str) -> str:
    """Generates a standard mailto: link for desktop/mobile mail clients."""
    clean_email = str(email).strip()
    enc_subj = urllib.parse.quote(subject)
    enc_body = urllib.parse.quote(body)
    return f"mailto:{clean_email}?subject={enc_subj}&body={enc_body}"


def build_invoice_share_message(
    customer_name: str,
    invoice_id: str,
    total_amount: float,
    shop_name: str = "Shivansh Electronics and Hardware",
    payment_mode: str = "Cash",
) -> str:
    """Builds a formatted message for invoice dispatch."""
    return (
        f"Namaste {customer_name}! 🙏\n\n"
        f"Thank you for shopping at *{shop_name}*.\n"
        f"🧾 *Invoice No:* {invoice_id}\n"
        f"💰 *Total Amount:* ₹{total_amount:,.2f}\n"
        f"💳 *Payment Mode:* {payment_mode}\n\n"
        f"You can view and download your full digital receipt in the BizMetrics Customer Portal.\n"
        f"Have a wonderful day!"
    )


def build_payment_reminder_message(
    customer_name: str,
    outstanding_amount: float,
    due_date: str,
    shop_name: str = "Shivansh Electronics and Hardware",
) -> str:
    """Builds a polite, professional payment reminder message."""
    return (
        f"Namaste {customer_name}! 🙏\n\n"
        f"This is a gentle payment reminder from *{shop_name}* regarding your pending ledger balance.\n\n"
        f"📌 *Outstanding Dues:* ₹{outstanding_amount:,.2f}\n"
        f"📅 *Due Date:* {due_date}\n\n"
        f"Kindly settle this at your earliest convenience via UPI or store visit. "
        f"If already paid, please ignore this message. Thank you!"
    )


def build_order_update_message(
    customer_name: str,
    order_id: str,
    status: str,
    product_summary: str,
    shop_name: str = "Shivansh Electronics and Hardware",
) -> str:
    """Builds an order status update message."""
    return (
        f"Namaste {customer_name}! 🙏\n\n"
        f"Your order *{order_id}* at *{shop_name}* is now *{status.upper()}*.\n"
        f"📦 *Items:* {product_summary}\n\n"
        f"Thank you for choosing {shop_name}!"
    )


def send_email_notification(
    to_email: str,
    subject: str,
    body_text: str,
    pdf_attachment_bytes: Optional[bytes] = None,
    attachment_filename: str = "invoice.pdf",
) -> tuple[bool, str]:
    """
    Sends an email using configured SMTP settings.
    If SMTP credentials are not present, returns False with a helpful configuration note.
    """
    smtp_host = os.getenv("SMTP_HOST")
    smtp_port = int(os.getenv("SMTP_PORT", "587"))
    smtp_user = os.getenv("SMTP_USER")
    smtp_pass = os.getenv("SMTP_PASSWORD")

    if not (smtp_host and smtp_user and smtp_pass):
        return False, "SMTP is not configured. Set SMTP_HOST, SMTP_USER, and SMTP_PASSWORD in your environment."

    try:
        msg = MIMEMultipart()
        msg["From"] = smtp_user
        msg["To"] = to_email
        msg["Subject"] = subject
        msg.attach(MIMEText(body_text, "plain", "utf-8"))

        if pdf_attachment_bytes:
            part = MIMEApplication(pdf_attachment_bytes, Name=attachment_filename)
            part["Content-Disposition"] = f'attachment; filename="{attachment_filename}"'
            msg.attach(part)

        with smtplib.SMTP(smtp_host, smtp_port, timeout=15) as server:
            server.starttls()
            server.login(smtp_user, smtp_pass)
            server.send_message(msg)

        return True, f"Email sent successfully to {to_email}."
    except Exception as e:
        return False, f"Failed to send email: {str(e)}"

