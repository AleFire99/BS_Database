"""Parser errors."""


class ParseError(ValueError):
    """Raised when a page does not have the expected structure."""


class NoCardList(ParseError):
    """A set page with a title but no card list (events and books): valid, zero cards."""
