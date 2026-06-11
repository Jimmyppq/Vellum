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


class PromptNotFound(RepositoryError):
    def __init__(self, prompt_id) -> None:
        self.prompt_id = prompt_id
        super().__init__(f"Prompt {prompt_id} not found")


class TranscriptNotFound(RepositoryError):
    def __init__(self, transcript_id) -> None:
        self.transcript_id = transcript_id
        super().__init__(f"Transcript {transcript_id} not found")


class PromptHasExecutions(RepositoryError):
    def __init__(self, prompt_id) -> None:
        self.prompt_id = prompt_id
        super().__init__(
            f"Prompt {prompt_id} has executions and cannot be deleted; "
            f"deprecate it instead (PATCH /v1/prompts/{prompt_id}/status)"
        )


class TranscriptHasExecutions(RepositoryError):
    def __init__(self, transcript_id) -> None:
        self.transcript_id = transcript_id
        super().__init__(
            f"Transcript {transcript_id} is referenced by executions and cannot be deleted"
        )


class InvalidPayloadForTransition(RepositoryError):
    def __init__(self, status: str, fields: list[str]) -> None:
        self.status = status
        self.fields = fields
        super().__init__(
            f"Fields {fields} are only accepted on transitions to a terminal "
            f"status, not '{status}'"
        )
