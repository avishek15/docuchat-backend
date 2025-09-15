"""Custom exceptions for the application."""


class DocuChatException(Exception):
    """Base exception for DocuChat application."""

    def __init__(self, message: str, error_code: str = None):
        self.message = message
        self.error_code = error_code
        super().__init__(self.message)


class AuthenticationError(DocuChatException):
    """Authentication related errors."""

    pass


class ExternalAPIError(DocuChatException):
    """External API integration errors."""

    pass


class ValidationError(DocuChatException):
    """Data validation errors."""

    pass


class ConfigurationError(DocuChatException):
    """Configuration related errors."""

    pass
