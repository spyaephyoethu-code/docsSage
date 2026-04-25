class DocsSageError(Exception):
    pass


class KBLimitExceeded(DocsSageError):
    pass


class KBNotFound(DocsSageError):
    pass


class SourceLimitExceeded(DocsSageError):
    pass


class SourceNotFound(DocsSageError):
    pass


class ChunkLimitExceeded(DocsSageError):
    pass


class DailyLimitExceeded(DocsSageError):
    pass


class BudgetExceeded(DocsSageError):
    pass
