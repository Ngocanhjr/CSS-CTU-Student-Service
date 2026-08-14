class ApplicationError(Exception):
    """Base exception for errors that may cross an application boundary."""


class NotFoundError(LookupError, ApplicationError):
    pass


class InvalidRequestError(ValueError, ApplicationError):
    pass


class ConflictError(ValueError, ApplicationError):
    pass


class ExternalServiceError(RuntimeError, ApplicationError):
    pass
