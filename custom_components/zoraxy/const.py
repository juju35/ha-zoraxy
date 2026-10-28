"""Constants for the Zoraxy integration."""

DOMAIN = "zoraxy"
DEFAULT_SCAN_INTERVAL = 30  # seconds
MIN_SCAN_INTERVAL = 10  # seconds
ACME_POLL_SECONDS = 3600  # the ACME auto-renew settings are re-read at most once an hour
DEFAULT_HOST = "http://zoraxy.local:8000"
DEFAULT_VERIFY_SSL = True

CONF_SCAN_INTERVAL = "scan_interval"
CONF_VERIFY_SSL = "verify_ssl"

SERVICE_TOGGLE_PROXY_RULE = "toggle_proxy_rule"
EXPIRY_WARNING_DAYS = 30  # days before expiry that trigger the warning

DEVICE_INFO_BASE = {
    "name": "Zoraxy Reverse Proxy",
    "manufacturer": "tobychui",
    "model": "Zoraxy",
}


def safe_domain(domain: str) -> str:
    """Turn a domain name into a suffix safe for unique_id."""
    return domain.replace(".", "_").replace("*", "wildcard").replace("-", "_").lower()
