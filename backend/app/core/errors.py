class DomainError(Exception):
    def __init__(self, message: str, *, code: str, status_code: int) -> None:
        super().__init__(message)
        self.message = message
        self.code = code
        self.status_code = status_code


class NotFoundError(DomainError):
    def __init__(self, message: str) -> None:
        super().__init__(message, code="not_found", status_code=404)


class ConflictError(DomainError):
    def __init__(self, message: str) -> None:
        super().__init__(message, code="conflict", status_code=409)


class ConnectorNotConfiguredError(DomainError):
    def __init__(self, message: str) -> None:
        super().__init__(message, code="connector_not_configured", status_code=503)


class UpstreamUnavailableError(DomainError):
    def __init__(self, message: str) -> None:
        super().__init__(message, code="upstream_unavailable", status_code=502)


class UpstreamInvalidResponseError(DomainError):
    def __init__(self, message: str) -> None:
        super().__init__(message, code="upstream_invalid_response", status_code=502)


class InvalidSourceUrlError(DomainError):
    def __init__(self, message: str) -> None:
        super().__init__(message, code="invalid_source_url", status_code=422)
