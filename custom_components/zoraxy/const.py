"""Constants for the Zoraxy integration."""

DOMAIN = "zoraxy"
DEFAULT_SCAN_INTERVAL = 30  # seconds
EXPIRY_WARNING_DAYS = 30  # days before expiry that trigger the warning

DEVICE_INFO_BASE = {
    "name": "Zoraxy Reverse Proxy",
    "manufacturer": "tobychui",
    "model": "Zoraxy",
}


def safe_domain(domain: str) -> str:
    """Turn a domain name into a suffix safe for unique_id."""
    return domain.replace(".", "_").replace("*", "wildcard").replace("-", "_").lower()
