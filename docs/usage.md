# Usage tutorial

This walkthrough runs OutNote SMTP on your computer and sends one test message through your Microsoft 365 mailbox. You need Python 3.10 or newer, an account that OutNote can sign into, and permission to send mail from that account.

## 1. Install the bridge

From the `outnote-smtp` directory, create a virtual environment and install the project:

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -e .
```

On Windows, activate it with `.venv\Scripts\activate` instead. Keep this environment active for the remaining commands.

To use a development checkout of OutNote in the adjacent `../OutNote` directory, install it into the same environment after the bridge:

```bash
python -m pip install --no-deps -e ../OutNote
```

An editable install uses changes from that checkout without reinstalling the package.

## 2. Sign in

```bash
outnote-smtp login
```

Enter your Microsoft 365 email and password when prompted. For MFA, enter either your Base32 TOTP secret or a current one-time code; leave the prompt blank if your account does not use TOTP. The bridge calls OutNote's `authenticate(...)` without a browser and stores the refresh token and cookies under `$XDG_STATE_HOME/outnote-smtp`, or `~/.local/state/outnote-smtp` if `XDG_STATE_HOME` is unset. Use the same user account and state directory when running the server later. Treat these files like passwords; do not copy them into the repository.

## 3. Start the server

```bash
outnote-smtp serve
```

The startup line shows the mailbox address to use as the sender. Leave this terminal running. By default the server listens only on `127.0.0.1:1025`. Press Ctrl+C to stop it.

If port 1025 is occupied, choose another port and use that same port in your mail client:

```bash
outnote-smtp serve --port 2525
```

For submission details, run `outnote-smtp serve --verbose`. It prints a startup confirmation, then logs `description` (the subject), `from`, and `to` (all To/Cc/Bcc addresses) from each converted message when mail is submitted. It does not log message bodies or attachments.

## 4. Configure a local mail client

| Client setting | Enter |
| --- | --- |
| Outgoing SMTP server | `127.0.0.1` |
| Port | `1025`, or your chosen `--port` |
| Connection security | None |
| SMTP authentication | None |
| Sender / From address | The mailbox printed when the server starts |

Use these settings only for an application running on the same computer. The bridge has no TLS listener or SMTP login and cannot accept connections from other machines.

## 5. Send a test message

Replace both addresses below. Set `From` to the exact mailbox printed by the server, and `To` to a mailbox you can check.

```python
import smtplib
from email.message import EmailMessage

sender = "you@example.com"
recipient = "friend@example.net"

message = EmailMessage()
message["From"] = sender
message["To"] = recipient
message["Subject"] = "OutNote SMTP test"
message.set_content("This message was submitted through OutNote SMTP.")

with smtplib.SMTP("127.0.0.1", 1025, timeout=60) as smtp:
    smtp.send_message(message)

print("Microsoft Graph accepted the submission")
```

Save this as `send_test.py` and run `python send_test.py` in another terminal with the virtual environment active. If you changed the server port, change `1025` in the script too. A successful SMTP response means Microsoft Graph accepted the request; it does not guarantee delivery to the destination inbox.

To send an attachment, add it before calling `send_message`:

```python
from pathlib import Path

path = Path("report.pdf")
message.add_attachment(
    path.read_bytes(),
    maintype="application",
    subtype="pdf",
    filename=path.name,
)
```

## Common problems

| Symptom | What to check |
| --- | --- |
| `no saved sign-in` | Run `outnote-smtp login` as the same user, with the same `XDG_STATE_HOME`. |
| Connection refused | Start `outnote-smtp serve`; check the host and port. |
| `550` sender mismatch | Set both the SMTP envelope sender and `From` header to the mailbox printed at startup. |
| `550` recipient mismatch | Ensure every To, Cc, and Bcc address is included in the SMTP envelope. Standard `smtplib.send_message` handles this. |
| `552` message too large | Reduce the message size or restart with a larger `--max-size` value in bytes. The default is 10 MiB. |
| `451` Graph submission failed | Check the account sign-in and Microsoft 365 availability, then retry. The bridge does not queue mail. |

Only local applications you trust should use this listener. Any local process able to reach its port can submit mail as the signed-in account.
