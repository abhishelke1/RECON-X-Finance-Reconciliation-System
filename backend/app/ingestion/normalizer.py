from decimal import Decimal
from datetime import datetime, timezone
from typing import Any

def normalize_razorpay_amount(amount_paise: int | float | Decimal | str | None) -> Decimal | None:
    """Convert Razorpay amounts in paise to INR Decimal."""
    if amount_paise is None:
        return None
    try:
        return Decimal(str(amount_paise)) / Decimal("100")
    except (ValueError, TypeError):
        return None

def normalize_string(value: str | None) -> str | None:
    """Strip whitespace and lowercase."""
    if value is None:
        return None
    val_str = str(value).strip()
    return val_str.lower() if val_str else None

def normalize_currency(currency: str | None) -> str:
    """Standardize currency to uppercase, defaults to INR."""
    if currency is None:
        return "INR"
    val = str(currency).strip().upper()
    return val if val else "INR"

def normalize_timestamp(ts: int | float | str | datetime | None) -> datetime | None:
    """Normalize various timestamp formats to UTC datetime."""
    if ts is None:
        return None
    try:
        if isinstance(ts, (int, float)):
            return datetime.fromtimestamp(ts, tz=timezone.utc)
        elif isinstance(ts, str):
            if ts.isdigit():
                return datetime.fromtimestamp(int(ts), tz=timezone.utc)
            else:
                dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=timezone.utc)
                return dt
        elif isinstance(ts, datetime):
            if ts.tzinfo is None:
                return ts.replace(tzinfo=timezone.utc)
            return ts
    except (ValueError, TypeError, OSError):
        return None
    return None

def normalize_razorpay_payment(raw_data: dict[str, Any]) -> dict[str, Any]:
    """Normalize a raw Razorpay payment dict into format expected by validators."""
    return {
        "source_id": raw_data.get("id"),
        "source_system": "razorpay",
        "amount": normalize_razorpay_amount(raw_data.get("amount")),
        "currency": normalize_currency(raw_data.get("currency")),
        "status": normalize_string(raw_data.get("status")),
        "method": normalize_string(raw_data.get("method")),
        "customer_email": normalize_string(raw_data.get("email")),
        "customer_phone": normalize_string(raw_data.get("contact")),
        "payment_timestamp": normalize_timestamp(raw_data.get("created_at")),
        "order_source_id": raw_data.get("order_id"),
        "fee": normalize_razorpay_amount(raw_data.get("fee")),
        "tax": normalize_razorpay_amount(raw_data.get("tax")),
        "raw_data": raw_data
    }
