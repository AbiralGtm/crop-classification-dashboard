"""Google Earth Engine authentication / initialization.

GEE requires a registered Google Cloud project (mandatory since mid-2024) and,
for noncommercial use, a selected quota tier. See:
https://developers.google.com/earth-engine/guides/auth

Local dev: run `earthengine authenticate` once, or let ee.Authenticate() open
a browser login flow on first call.

Server deployment: set GEE_SERVICE_ACCOUNT_JSON to a service account key file
and this module will use ee.ServiceAccountCredentials instead.
"""
import ee

from app.config import get_settings

_initialized = False


def init_earth_engine() -> None:
    """Idempotently authenticate + initialize the Earth Engine client."""
    global _initialized
    if _initialized:
        return

    settings = get_settings()

    if settings.gee_service_account_json:
        credentials = ee.ServiceAccountCredentials(
            email=None, key_file=settings.gee_service_account_json
        )
        ee.Initialize(credentials, project=settings.gee_project_id)
    else:
        try:
            ee.Initialize(project=settings.gee_project_id)
        except Exception:
            ee.Authenticate()
            ee.Initialize(project=settings.gee_project_id)

    _initialized = True
