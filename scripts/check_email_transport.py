from __future__ import annotations

import argparse
import time

from shared_mailer import load_email_config, send_email, verify_smtp_auth


def main() -> int:
    parser = argparse.ArgumentParser(description="Check the shared A4 SMTP transport without exposing credentials.")
    parser.add_argument("--send-test", action="store_true", help="send one clearly labeled test email after SMTP auth succeeds")
    parser.add_argument("--to", help="optional test recipient; otherwise use configured EMAIL_TO")
    args = parser.parse_args()

    ok, detail = verify_smtp_auth()
    print(f"SMTP authentication: {'OK' if ok else 'FAILED'} ({detail})")
    if not ok or not args.send_test:
        return 0 if ok else 1

    config = load_email_config()
    recipients = [x.strip() for x in args.to.split(",") if x.strip()] if args.to else None
    sent, result = send_email(
        "[A4 mail transport] SMTP delivery check",
        f"SMTP mail transport check completed at {time.strftime('%Y-%m-%d %H:%M %Z')}.",
        recipients=recipients,
        environ=config,
    )
    print(f"SMTP delivery: {'SENT' if sent else 'FAILED'} ({result})")
    return 0 if sent else 1


if __name__ == "__main__":
    raise SystemExit(main())
