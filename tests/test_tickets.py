from app.tools.tickets import format_ticket_id


def test_zero_padding():
    assert format_ticket_id(2026, 123) == "SOF-2026-000123"


def test_large_seq():
    assert format_ticket_id(2026, 1000000) == "SOF-2026-1000000"


def test_first_ticket():
    assert format_ticket_id(2026, 1) == "SOF-2026-000001"
