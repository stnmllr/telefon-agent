"""Ticket-ID-Formatierung (Pure-Core)."""


def format_ticket_id(year: int, seq: int) -> str:
    return f"SOF-{year}-{seq:06d}"
