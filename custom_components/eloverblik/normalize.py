"""Rensning af config entry-felter (delt af __init__ og config_flow)."""


def _normalize_refresh_token(value: str) -> str:
    """Fjern ledende/hale-mellemrum (almindeligt ved kopiering)."""
    return str(value).strip()


def _normalize_metering_point(value: str) -> str:
    """Fjern alle whitespace — målepunkt-ID kopieres ofte formateret."""
    return "".join(str(value).split())


def normalize_entry_data(data: dict) -> dict:
    """Rens felter før validering og før de gemmes i config entry."""
    return {
        "refresh_token": _normalize_refresh_token(data["refresh_token"]),
        "metering_point": _normalize_metering_point(data["metering_point"]),
    }
