"""Publish a snapshot of the Microsoft 365 directory through local CardDAV."""

import json
import subprocess
import sys
from pathlib import Path


def _vcard_text(value):
    return str(value).replace("\\", "\\\\").replace("\n", "\\n").replace(";", "\\;").replace(",", "\\,")


def sync_directory(note, state):
    """Write directory users as vCards in Radicale's filesystem storage."""
    users = note.list(
        "users",
        {"$top": 999, "$select": "id,displayName,mail,userPrincipalName"},
    )
    book = Path(state) / "carddav" / "collection-root" / "local" / "directory"
    book.mkdir(mode=0o700, parents=True, exist_ok=True)
    (book / ".Radicale.props").write_text(json.dumps({"tag": "VADDRESSBOOK"}), encoding="utf-8")
    expected = set()
    for user in users:
        uid = user.get("id")
        address = user.get("mail")
        if not uid or not address:
            continue
        # Graph IDs are UUIDs; keep all storage names under our own directory.
        filename = "".join(c for c in uid if c.isascii() and (c.isalnum() or c == "-")) + ".vcf"
        if filename == ".vcf":
            continue
        expected.add(filename)
        name = user.get("displayName") or address
        card = (
            "BEGIN:VCARD\r\nVERSION:3.0\r\n"
            f"UID:{_vcard_text(uid)}\r\n"
            f"FN:{_vcard_text(name)}\r\n"
            f"EMAIL:{_vcard_text(address)}\r\n"
            "END:VCARD\r\n"
        )
        (book / filename).write_text(card, encoding="utf-8")
    for old in book.glob("*.vcf"):
        if old.name not in expected:
            old.unlink()
    rights = Path(state) / "carddav-rights"
    rights.write_text("[read-only]\nuser: .*\ncollection: .*\npermissions: Rr\n", encoding="utf-8")
    return len(expected), rights


def start_carddav(state, rights, port):
    """Launch Radicale on loopback with anonymous read-only access."""
    return subprocess.Popen(
        [
            sys.executable, "-m", "radicale", "-C", "",
            "--server-hosts", f"127.0.0.1:{port}",
            "--storage-filesystem-folder", str(Path(state) / "carddav"),
            "--auth-type", "none",
            "--rights-type", "from_file",
            "--rights-file", str(rights),
            "--logging-level", "warning",
        ],
        stdout=subprocess.DEVNULL,
    )
