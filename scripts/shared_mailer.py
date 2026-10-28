from __future__ import annotations

"""Shared SMTP transport for A4 operational email.

Configuration is read from `A4_EMAIL_CONFIG`, then the private per-user
profile, then a permission-checked A3 transition profile. Values are never logged.
"""

import os
import smtplib
import ssl
import time
import mimetypes
from email.message import EmailMessage
from pathlib import Path
from typing import Iterable


def _config_paths() -> list[Path]:
    paths: list[Path] = []
    explicit = os.environ.get("A4_EMAIL_CONFIG", "").strip()
    if explicit:
        paths.append(Path(explicit).expanduser())
    home = Path.home()
    paths.extend([
        home / ".config/a4-mailer/smtp.env",
        home / "agent-coding/agent-system/A3-runtime-standards/local-config/secrets/email/smtp.env",
    ])
    unique: list[Path] = []
    seen: set[Path] = set()
    for path in paths:
        if path not in seen:
            seen.add(path)
            unique.append(path)
    return unique


def load_email_config(environ: dict[str, str] | None = None) -> dict[str, str]:
    values = dict(os.environ if environ is None else environ)
    for path in _config_paths():
        if path.name == "smtp.env" and ("/secrets/email/" in path.as_posix() or path.parent.name == "a4-mailer"):
            try:
                file_mode = path.stat().st_mode & 0o777
                parent_mode = path.parent.stat().st_mode & 0o777
            except OSError:
                continue
            if file_mode & 0o077 or parent_mode & 0o077:
                continue
        try:
            lines = path.read_text(encoding="utf-8").splitlines()
        except OSError:
            continue
        for raw in lines:
            line = raw.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            key = key.strip()
            if key.startswith("export "):
                key = key[7:].strip()
            if key in {"SMTP_HOST", "SMTP_PORT", "SMTP_USER", "SMTP_PASSWORD", "SMTP_STARTTLS", "SMTP_USE_SSL", "SMTP_SSL", "EMAIL_FROM", "MAIL_FROM"}:
                values.setdefault(key, value.strip().strip("\"'"))
    return values


def apply_environment_defaults(environ: dict[str, str] | None = None) -> dict[str, str]:
    """Fill missing SMTP environment variables from the shared profile.

    Existing process/repository settings always win. Recipient routing stays
    repository-local and is deliberately excluded from the shared profile.
    """
    target = os.environ if environ is None else environ
    config = load_email_config(target)
    for key in ("SMTP_HOST", "SMTP_PORT", "SMTP_USER", "SMTP_PASSWORD", "SMTP_STARTTLS", "SMTP_USE_SSL", "SMTP_SSL", "EMAIL_FROM", "MAIL_FROM"):
        if config.get(key):
            target.setdefault(key, config[key])
    return target


def _smtp_client(config: dict[str, str]):
    host = config.get("SMTP_HOST", "smtp.gmail.com")
    port = int(config.get("SMTP_PORT", "587"))
    timeout = float(config.get("SMTP_TIMEOUT", "30"))
    if config.get("SMTP_USE_SSL", "").lower() in {"1", "true", "yes"} or port == 465:
        return smtplib.SMTP_SSL(host, port, timeout=timeout, context=ssl.create_default_context())
    client = smtplib.SMTP(host, port, timeout=timeout)
    if config.get("SMTP_STARTTLS", "1").lower() not in {"0", "false", "no"}:
        client.starttls(context=ssl.create_default_context())
    return client


def verify_smtp_auth(environ: dict[str, str] | None = None) -> tuple[bool, str]:
    config = load_email_config(environ)
    user = config.get("SMTP_USER") or config.get("EMAIL_FROM", "")
    password = config.get("SMTP_PASSWORD", "")
    if not all((config.get("SMTP_HOST", "smtp.gmail.com"), user, password)):
        return False, "smtp_config_incomplete"
    try:
        with _smtp_client(config) as client:
            client.ehlo()
            client.login(user, password)
        return True, "smtp_auth_ok"
    except smtplib.SMTPAuthenticationError:
        return False, "smtp_auth_rejected"
    except Exception as exc:
        return False, f"smtp_unavailable:{type(exc).__name__}"


def send_email(
    subject: str,
    body: str,
    recipients: Iterable[str] | None = None,
    attachments: Iterable[Path] = (),
    environ: dict[str, str] | None = None,
) -> tuple[bool, str]:
    config = load_email_config(environ)
    sender = config.get("EMAIL_FROM") or config.get("SMTP_USER", "")
    to_list = [item.strip() for item in (recipients or config.get("EMAIL_TO", "").split(",")) if item.strip()]
    if not sender or not to_list:
        return False, "smtp_sender_or_recipient_missing"
    user = config.get("SMTP_USER") or sender
    password = config.get("SMTP_PASSWORD", "")
    if not password:
        return False, "smtp_password_missing"

    message = EmailMessage()
    message["From"] = sender
    message["To"] = ", ".join(to_list)
    message["Subject"] = subject
    message.set_content(body)
    for path in attachments:
        file_path = Path(path)
        if not file_path.is_file():
            return False, "attachment_missing"
        if file_path.stat().st_size > 20 * 1024 * 1024:
            return False, "attachment_exceeds_20_mib"
        content_type, _ = mimetypes.guess_type(file_path.name)
        maintype, subtype = (content_type or "application/octet-stream").split("/", 1)
        message.add_attachment(file_path.read_bytes(), maintype=maintype, subtype=subtype, filename=file_path.name)

    for attempt in range(3):
        send_started = False
        try:
            with _smtp_client(config) as client:
                client.ehlo()
                client.login(user, password)
                send_started = True
                refused = client.send_message(message)
            if refused:
                return False, "smtp_recipient_refused"
            return True, "sent"
        except smtplib.SMTPAuthenticationError:
            return False, "smtp_auth_rejected"
        except Exception as exc:
            # If DATA may have reached the server, don't retry or switch
            # transports: that could send a duplicate report.
            if send_started:
                return False, f"smtp_delivery_uncertain:{type(exc).__name__}"
            if attempt == 2:
                return False, f"smtp_connect_failed:{type(exc).__name__}"
            time.sleep(2 ** (attempt + 1))
    return False, "smtp_failed"
