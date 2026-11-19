"""Keep one-time tokens out of application logs."""

import logging
import re


TOKEN_PATHS = re.compile(
    r"(/(?:confirmar|baja)/|/confirm-email/|/password/reset/key/|/login/code/confirm/)[^/\s\"'?]+"
)


def redact(text):
    return TOKEN_PATHS.sub(r"\1[redacted]", text)


class RedactTokensFilter(logging.Filter):
    def filter(self, record):
        message = record.getMessage()
        cleaned = redact(message)
        if cleaned != message:
            record.msg, record.args = cleaned, None
        # Request objects attached by django.request may be rendered by formatters.
        if hasattr(record, "request"):
            record.request = None
        return True
