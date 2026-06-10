class RepositoryError(Exception):
    """Base class for typed repository errors."""


class ExecutionNotFound(RepositoryError):
    def __init__(self, execution_id) -> None:
        self.execution_id = execution_id
        super().__init__(f"Execution {execution_id} not found")


class InvalidStateTransition(RepositoryError):
    def __init__(self, current: str, requested: str) -> None:
        self.current = current
        self.requested = requested
        super().__init__(
            f"Invalid state transition from '{current}' to '{requested}'"
        )


class InvalidPayloadForTransition(RepositoryError):
    def __init__(self, status: str, fields: list[str]) -> None:
        self.status = status
        self.fields = fields
        super().__init__(
            f"Fields {fields} are only accepted on transitions to a terminal "
            f"status, not '{status}'"
        )
