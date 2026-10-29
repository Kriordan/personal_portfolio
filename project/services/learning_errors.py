"""Learning service exceptions, in a module with no imports.

learning_service re-exports these, so `learning_service.NotFoundError` and friends are
unchanged. practice_service imports them from here: importing learning_service itself
during app start-up would be circular (it loads the project.learning package, whose
views import practice_service).
"""


class LearningServiceError(Exception):
    """Base learning service exception."""


class NotFoundError(LearningServiceError):
    """Raised when requested learning content does not exist."""


class ValidationError(LearningServiceError):
    """Raised when service input fails validation."""


class InvalidRatingError(ValidationError):
    """Raised when a review rating is outside the supported range."""


class InvalidCardIdError(ValidationError):
    """Raised when a review card ID does not use the expected format."""


class ConflictError(LearningServiceError):
    """Raised when a resource conflict occurs."""


class StaleReviewError(ConflictError):
    """Another client changed this card after the queue was loaded."""
