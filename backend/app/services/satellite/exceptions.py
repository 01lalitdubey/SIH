"""Structured errors for the satellite-data layer.

Every message here is written assuming it may be shown directly to an API
client (surfaced as ProcessingJob.error_message) — never include a token,
client secret, or raw provider response body in one of these messages.
"""


class SatelliteError(Exception):
    """Base class for all satellite-layer errors."""


class InvalidAOIError(SatelliteError):
    """The AOI geometry is missing, malformed, or out of valid lat/lon range."""


class InvalidDateRangeError(SatelliteError):
    """The requested search date range is missing or logically invalid."""


class InvalidCloudCoverError(SatelliteError):
    """The requested max cloud cover is out of the valid 0-100 range."""


class MissingCredentialsError(SatelliteError):
    """COPERNICUS_CLIENT_ID / COPERNICUS_CLIENT_SECRET are not configured."""


class AuthenticationError(SatelliteError):
    """The configured credentials were rejected by the provider."""


class ProviderUnavailableError(SatelliteError):
    """A timeout, connection failure, or 5xx from the provider's API."""


class NoScenesFoundError(SatelliteError):
    """The search succeeded but returned zero matching scenes."""


class SceneDownloadError(SatelliteError):
    """A scene was selected but its data could not be retrieved."""
