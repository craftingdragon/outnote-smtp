# OutNote SMTP

A local SMTP submission server that sends mail through [OutNote](https://github.com/PianoNic/OutNote) and Microsoft 365. It accepts messages from applications on your computer and forwards their MIME content, including multipart bodies and attachments, through Microsoft Graph.

For a complete first-run walkthrough, see the [usage tutorial](docs/usage.md).

## Install

Requires Python 3.10 or newer.

```bash
pip install -e .
outnote-smtp login
outnote-smtp serve
```

Run the install command from this repository. Once the package is published, `pip install outnote-smtp` will also work.

`login` prompts for your Microsoft 365 email, password, and optional TOTP secret or one-time code, then calls OutNote's `authenticate(...)` directly. It does not open a browser. The refresh token and sign-in cookies are saved in `$XDG_STATE_HOME/outnote-smtp` (or `~/.local/state/outnote-smtp`). Keep that directory private and do not commit its contents. The server loads this sign-in on startup.

To use an adjacent development checkout of OutNote, install this package first, then replace its OutNote dependency with the editable checkout:

```bash
pip install -e '.[test]'
pip install --no-deps -e ../OutNote
```

## Configure an application

| Setting | Value |
| --- | --- |
| SMTP host | `127.0.0.1` |
| SMTP port | `1025` |
| Encryption | None (loopback only) |
| SMTP authentication | None |
| From address | The signed-in Microsoft 365 mailbox |

Run `outnote-smtp serve --port 2525` to use a different port. The server always binds to loopback. Its default message limit is 10 MiB; use `--max-size BYTES` to change it.

Add `--verbose` to print a startup confirmation and log each submitted message's subject (shown as `description`), From address, and all To/Cc/Bcc recipient addresses after MIME conversion. Message details appear when mail is submitted; bodies and attachments are not logged.

For example, Python's standard library can submit a message:

```python
import smtplib
from email.message import EmailMessage

msg = EmailMessage()
msg["From"] = "you@example.com"
msg["To"] = "friend@example.net"
msg["Subject"] = "Hello"
msg.set_content("Hello from OutNote SMTP")

with smtplib.SMTP("127.0.0.1", 1025) as smtp:
    smtp.send_message(msg)
```

The SMTP envelope sender and `From` header must match the signed-in mailbox. Every visible To, Cc, or Bcc recipient must appear in the SMTP envelope. Envelope recipients absent from the headers are added as Bcc. A `250` response means Microsoft Graph accepted the submission; final delivery is handled by Microsoft 365.

This is a local submission bridge, not an inbound mailbox server. It has no queue, SMTP authentication, or TLS listener. Run it only on a computer whose local applications you trust.

## Development

```bash
pip install -e '.[test]'
pytest
python -m build
```

Tests use a fake OutNote client and do not send mail.

## License

MIT. See [LICENSE](LICENSE).
