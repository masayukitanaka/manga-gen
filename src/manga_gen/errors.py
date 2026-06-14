"""MangaDSL exception types."""


class MangaDSLError(Exception):
    """Base class for all MangaDSL exceptions."""
    pass


class ParseError(MangaDSLError):
    """Raised when DSL source code has syntax errors."""
    pass


class ValidationError(MangaDSLError):
    """Raised when semantic validation fails."""
    pass


class LayoutError(MangaDSLError):
    """Raised when layout computation fails (e.g., size constraints violated)."""
    pass


class RenderError(MangaDSLError):
    """Raised when rendering fails."""
    pass
