"""Constantes pour l'intégration Zoraxy."""

DOMAIN = "zoraxy"
DEFAULT_SCAN_INTERVAL = 30  # secondes
EXPIRY_WARNING_DAYS = 30    # jours avant expiration pour l'alerte

DEVICE_INFO_BASE = {
    "name": "Zoraxy Reverse Proxy",
    "manufacturer": "tobychui",
    "model": "Zoraxy",
}


def safe_domain(domain: str) -> str:
    """Convertit un nom de domaine en suffixe safe pour unique_id."""
    return domain.replace(".", "_").replace("*", "wildcard").replace("-", "_").lower()
