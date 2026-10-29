"""Command line entry point for sign-in and the local SMTP listener."""

import argparse
import getpass
import logging
import os
import re
import subprocess
from pathlib import Path

from .carddav import start_carddav, sync_directory
from .relay import RelayHandler, log


def _state_dir():
    root = Path(os.environ.get("XDG_STATE_HOME", Path.home() / ".local" / "state"))
    return root / "outnote-smtp"


def _login(note_auth, token, cookies):
    username = input("Microsoft 365 email: ").strip()
    password = getpass.getpass("Password: ")
    factor = getpass.getpass("TOTP secret or one-time code (blank if none): ").strip()
    if not username or not password:
        raise ValueError("email and password are required")
    kwargs = {"frt_store": str(token), "cookies": str(cookies), "interactive": False}
    if factor:
        kwargs["totp_code" if re.fullmatch(r"\d{6}|\d{8}", factor) else "totp_secret"] = factor
    return note_auth(username, password, **kwargs)


def _enable_verbose_logging():
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s", "%H:%M:%S"))
    log.addHandler(handler)
    log.setLevel(logging.INFO)
    log.propagate = False


def main(argv=None):
    parser = argparse.ArgumentParser(description="Local SMTP submission through OutNote")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("login", help="Sign in with OutNote using credentials and TOTP")
    serve = sub.add_parser("serve", help="Start the loopback SMTP server")
    serve.add_argument("--port", type=int, default=1025)
    serve.add_argument("--max-size", type=int, default=10 * 1024 * 1024)
    serve.add_argument("--carddav-port", type=int, default=5232)
    serve.add_argument("--no-carddav", action="store_true", help="Disable the local CardDAV address book")
    serve.add_argument("--verbose", action="store_true", help="Log subject and converted addresses")
    args = parser.parse_args(argv)

    from outnote import authenticate

    state = _state_dir()
    state.mkdir(mode=0o700, parents=True, exist_ok=True)
    token = state / "refresh.token"
    cookies = state / "cookies.json"
    if args.command == "serve" and not token.exists():
        parser.error("no saved sign-in; run 'outnote-smtp login' first")
    if args.command == "login":
        try:
            _login(authenticate, token, cookies)
        except ValueError as exc:
            parser.error(str(exc))
        print("Sign-in saved.")
        return 0
    if args.verbose:
        _enable_verbose_logging()
        log.info("Loading saved OutNote session; Microsoft 365 authentication may take a while")
    else:
        print("Loading saved OutNote session...", flush=True)
    note = authenticate(frt_store=str(token), cookies=str(cookies), interactive=False)
    if args.verbose:
        log.info("Session ready; checking mailbox address")
    if not 1 <= args.port <= 65535 or not 1 <= args.carddav_port <= 65535 or args.max_size < 1:
        parser.error("ports must be 1-65535 and max-size must be positive")
    if args.port == args.carddav_port and not args.no_carddav:
        parser.error("SMTP and CardDAV ports must differ")
    profile = note.get("me", {"$select": "mail,userPrincipalName"})
    sender = profile.get("mail") or profile.get("userPrincipalName")
    if not sender:
        parser.error("Microsoft 365 profile has no mailbox address")
    from aiosmtpd.controller import Controller

    if args.verbose:
        log.info("Mailbox %s ready; starting SMTP listener", sender)
    controller = Controller(
        RelayHandler(note, sender, verbose=args.verbose), hostname="127.0.0.1", port=args.port,
        data_size_limit=args.max_size,
    )
    controller.start()
    print(f"SMTP listening on 127.0.0.1:{args.port} for {sender}", flush=True)
    carddav = None
    if args.verbose:
        log.info("Verbose logging enabled; waiting for SMTP submissions")
    try:
        if not args.no_carddav:
            print("Loading Microsoft 365 directory for CardDAV...", flush=True)
            try:
                count, rights = sync_directory(note, state)
                carddav = start_carddav(state, rights, args.carddav_port)
                try:
                    exit_code = carddav.wait(timeout=0.5)
                except subprocess.TimeoutExpired:
                    pass
                else:
                    carddav = None
                    raise RuntimeError(f"CardDAV server exited with code {exit_code}")
                print(
                    f"CardDAV serving {count} directory contacts at "
                    f"http://127.0.0.1:{args.carddav_port}/local/directory/",
                    flush=True,
                )
            except Exception as exc:
                print(f"CardDAV unavailable: {exc}", flush=True)
        import time

        while True:
            time.sleep(3600)
    except KeyboardInterrupt:
        pass
    finally:
        controller.stop()
        if carddav is not None:
            carddav.terminate()
            try:
                carddav.wait(timeout=5)
            except subprocess.TimeoutExpired:
                carddav.kill()
                carddav.wait()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
