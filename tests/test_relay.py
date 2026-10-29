import asyncio
import base64
from email import policy
from email.message import EmailMessage
from email.parser import BytesParser
from types import SimpleNamespace

import pytest

from outnote_smtp.relay import RelayHandler, prepare_mime


SENDER = "sender@example.com"


def message():
    msg = EmailMessage()
    msg["From"] = SENDER
    msg["To"] = "alice@example.net"
    msg["Subject"] = "Example"
    msg.set_content("Plain body")
    msg.add_alternative("<p>HTML body</p>", subtype="html")
    msg.add_attachment(b"binary\x00data", maintype="application", subtype="octet-stream", filename="data.bin")
    return msg.as_bytes(policy=policy.SMTP)


def test_multipart_and_envelope_bcc():
    result = prepare_mime(message(), SENDER, ["alice@example.net", "hidden@example.net"], SENDER)
    parsed = BytesParser(policy=policy.SMTP).parsebytes(result)
    assert parsed["Bcc"] == "hidden@example.net"
    assert parsed["To"] == "alice@example.net"
    assert parsed.get_body(preferencelist=("html",)).get_content().strip() == "<p>HTML body</p>"
    attachments = list(parsed.iter_attachments())
    assert len(attachments) == 1
    assert attachments[0].get_payload(decode=True) == b"binary\x00data"


def test_rejects_sender_mismatch():
    with pytest.raises(ValueError, match="envelope sender"):
        prepare_mime(message(), "other@example.com", ["alice@example.net"], SENDER)


def test_rejects_header_recipient_outside_envelope():
    with pytest.raises(ValueError, match="header recipient"):
        prepare_mime(message(), SENDER, ["other@example.net"], SENDER)


def test_rejects_empty_recipient_list():
    with pytest.raises(ValueError, match="recipient"):
        prepare_mime(message(), SENDER, [], SENDER)


def test_posts_base64_mime_and_returns_success(monkeypatch):
    async def direct(fn, *args, **kwargs):
        return fn(*args, **kwargs)

    monkeypatch.setattr("outnote_smtp.relay.asyncio.to_thread", direct)
    calls = []

    class Note:
        def post(self, *args, **kwargs):
            calls.append((args, kwargs))

    envelope = SimpleNamespace(content=message(), mail_from=SENDER, rcpt_tos=["alice@example.net"])
    reply = asyncio.run(RelayHandler(Note(), SENDER).handle_DATA(None, None, envelope))
    assert reply.startswith("250 ")
    assert calls[0][0][0] == "me/sendMail"
    assert calls[0][1]["content_type"] == "text/plain"
    assert b"Subject: Example" in base64.b64decode(calls[0][0][1])


@pytest.mark.parametrize("status,expected", [(400, "550"), (429, "451"), (503, "451")])
def test_graph_errors(status, expected, monkeypatch):
    async def direct(fn, *args, **kwargs):
        return fn(*args, **kwargs)

    monkeypatch.setattr("outnote_smtp.relay.asyncio.to_thread", direct)
    class Note:
        def post(self, *args, **kwargs):
            error = RuntimeError("upstream failure")
            error.status = status
            raise error

    envelope = SimpleNamespace(content=message(), mail_from=SENDER, rcpt_tos=["alice@example.net"])
    reply = asyncio.run(RelayHandler(Note(), SENDER).handle_DATA(None, None, envelope))
    assert reply.startswith(expected + " ")
