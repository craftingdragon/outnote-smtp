"""Translate one SMTP submission into a Graph MIME sendMail call."""

import asyncio
import base64
import io
from email import policy
from email.generator import BytesGenerator
from email.parser import BytesParser
from email.utils import getaddresses, parseaddr


def _address(value):
    if not value or "\r" in value or "\n" in value:
        raise ValueError("invalid email address")
    _, address = parseaddr(value)
    if address != value and value.strip() != address:
        raise ValueError("invalid email address")
    if address.count("@") != 1 or not all(address.split("@")):
        raise ValueError("invalid email address")
    return address.casefold()


def prepare_mime(raw, mail_from, rcpt_tos, sender):
    """Keep MIME parts intact while enforcing sender and envelope recipients."""
    if _address(mail_from) != _address(sender):
        raise ValueError("envelope sender differs from signed-in mailbox")
    recipients = {_address(addr): addr for addr in rcpt_tos}
    if not recipients:
        raise ValueError("at least one recipient is required")
    msg = BytesParser(policy=policy.SMTP).parsebytes(raw)
    from_headers = msg.get_all("From", [])
    if len(from_headers) != 1:
        raise ValueError("exactly one From header is required")
    from_addrs = getaddresses(from_headers)
    if len(from_addrs) != 1 or _address(from_addrs[0][1]) != _address(sender):
        raise ValueError("From differs from signed-in mailbox")
    if msg.defects:
        raise ValueError("malformed MIME headers")
    visible = []
    for field in ("To", "Cc", "Bcc"):
        visible.extend(addr for _, addr in getaddresses(msg.get_all(field, [])))
    header_recipients = {_address(addr) for addr in visible}
    if not header_recipients <= recipients.keys():
        raise ValueError("header recipient missing from SMTP envelope")
    hidden = [addr for key, addr in recipients.items() if key not in header_recipients]
    if hidden:
        existing = msg.get_all("Bcc", [])
        if "Bcc" in msg:
            del msg["Bcc"]
        msg["Bcc"] = ", ".join([*existing, *hidden])
    out = io.BytesIO()
    BytesGenerator(out, policy=policy.SMTP).flatten(msg)
    return out.getvalue()


class RelayHandler:
    def __init__(self, note, sender):
        self.note = note
        self.sender = sender

    async def handle_DATA(self, server, session, envelope):
        try:
            mime = prepare_mime(envelope.content, envelope.mail_from, envelope.rcpt_tos, self.sender)
        except ValueError as exc:
            return f"550 5.6.0 {exc}"
        try:
            await asyncio.to_thread(
                self.note.post, "me/sendMail", base64.b64encode(mime), content_type="text/plain"
            )
        except Exception as exc:
            # OutNote's GraphError exposes the upstream HTTP status. Network and
            # authentication failures remain temporary so callers can retry.
            status = getattr(exc, "status", None)
            if status == 400:
                return "550 5.6.0 Microsoft Graph rejected the message"
            return "451 4.3.0 Microsoft Graph submission failed"
        return "250 2.0.0 Accepted by Microsoft Graph"
