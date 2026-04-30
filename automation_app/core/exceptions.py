class AutomationError(Exception):
    """Base exception for automation runtime failures."""


class ConfigurationError(AutomationError):
    """Raised when required runtime configuration is invalid."""


class QuizParsingError(AutomationError):
    """Raised when question extraction fails."""
