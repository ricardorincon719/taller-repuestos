from decimal import Decimal, InvalidOperation


CURRENCY_SYMBOLS = {
    "ARS": "$",
    "BOB": "Bs",
    "BRL": "R$",
    "CLP": "$",
    "COP": "$",
    "CRC": "₡",
    "DOP": "RD$",
    "GTQ": "Q",
    "HNL": "L",
    "MXN": "$",
    "NIO": "C$",
    "PAB": "B/.",
    "PEN": "S/",
    "PYG": "₲",
    "USD": "US$",
    "UYU": "$U",
    "VES": "Bs",
}


def format_money(value, currency="BRL"):
    try:
        amount = Decimal(value or 0)
    except (InvalidOperation, TypeError, ValueError):
        amount = Decimal("0.00")
    code = currency or "BRL"
    symbol = CURRENCY_SYMBOLS.get(code, code)
    whole = code in {"CLP", "PYG"}
    formatted = f"{amount:,.0f}" if whole else f"{amount:,.2f}"
    formatted = formatted.replace(",", "_").replace(".", ",").replace("_", ".")
    return f"{symbol} {formatted}"
