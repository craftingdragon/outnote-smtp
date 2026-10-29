import sys
import logging
from types import SimpleNamespace

import pytest

from outnote_smtp.cli import _enable_verbose_logging, main
from outnote_smtp.relay import log


@pytest.mark.parametrize(
    "factor,field",
    [("JBSWY3DPEHPK3PXP", "totp_secret"), ("123456", "totp_code")],
)
def test_login_uses_outnote_credentials(monkeypatch, tmp_path, factor, field):
    calls = []
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path))
    monkeypatch.setattr("builtins.input", lambda prompt: "you@school.ch")
    answers = iter(["password", factor])
    monkeypatch.setattr("outnote_smtp.cli.getpass.getpass", lambda prompt: next(answers))
    monkeypatch.setitem(
        sys.modules,
        "outnote",
        SimpleNamespace(authenticate=lambda *args, **kwargs: calls.append((args, kwargs)) or object()),
    )

    assert main(["login"]) == 0
    assert len(calls) == 1
    args, kwargs = calls[0]
    assert args == ("you@school.ch", "password")
    assert kwargs[field] == factor
    assert kwargs["interactive"] is False
    assert "device" not in kwargs
    assert kwargs["frt_store"] == str(tmp_path / "outnote-smtp" / "refresh.token")


def test_verbose_logger_prints_even_when_root_is_configured(capsys):
    old_handlers = log.handlers[:]
    old_level = log.level
    old_propagate = log.propagate
    root = logging.getLogger()
    old_root_level = root.level
    root.setLevel(logging.ERROR)
    try:
        _enable_verbose_logging()
        log.info("Verbose logging enabled; waiting for SMTP submissions")
        assert "Verbose logging enabled" in capsys.readouterr().err
    finally:
        for handler in log.handlers:
            if handler not in old_handlers:
                log.removeHandler(handler)
                handler.close()
        log.setLevel(old_level)
        log.propagate = old_propagate
        root.setLevel(old_root_level)
