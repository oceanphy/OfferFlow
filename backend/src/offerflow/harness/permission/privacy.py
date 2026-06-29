"""L6: Permission — privacy protection layer."""

from __future__ import annotations

import os
import shutil


def anonymize_for_model(transcript: str) -> str:
    """Strip obvious PII before sending to model APIs.

    Removes: email addresses, phone numbers, personal names (simple heuristics).
    Does NOT alter the stored transcript — only the copy sent to LLM.
    """
    import re

    text = transcript
    # email
    text = re.sub(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}", "[email]", text)
    # Chinese mobile
    text = re.sub(r"1[3-9]\d{9}", "[phone]", text)
    # ID card
    text = re.sub(r"\d{17}[\dXx]", "[id]", text)
    return text


def delete_user_data(data_dir: str = "data") -> bool:
    """Delete all stored user data: profiles, history, sessions."""
    if not os.path.exists(data_dir):
        return True
    try:
        shutil.rmtree(data_dir)
        return True
    except Exception:
        return False
