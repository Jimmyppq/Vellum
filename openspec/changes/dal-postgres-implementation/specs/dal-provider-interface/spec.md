## ADDED Requirements

### Requirement: BaseProvider defines the engine contract
The system SHALL define an abstract class `BaseProvider` in `dal/app/providers/base.py` that declares the interface every database engine provider must implement. The class SHALL inherit from `abc.ABC` and declare exactly two abstract methods: `get_engine() -> AsyncEngine` and `health_check() -> bool`. No concrete logic SHALL exist in this class.

#### Scenario: Provider subclass must implement both methods
- **WHEN** a class inherits from `BaseProvider` without implementing `get_engine` or `health_check`
- **THEN** instantiating that class SHALL raise `TypeError`

#### Scenario: Compliant subclass instantiates successfully
- **WHEN** a class inherits from `BaseProvider` and implements both `get_engine` and `health_check`
- **THEN** it SHALL instantiate without errors

### Requirement: Provider selection is delegated to router
The system SHALL provide a `dal/app/providers/router.py` module that reads the `DB_ENGINE` environment variable (default: `postgres`) and returns the corresponding `BaseProvider` implementation. Unknown engine values SHALL raise a `ValueError` with a descriptive message.

#### Scenario: Default engine is postgres
- **WHEN** `DB_ENGINE` is not set
- **THEN** the router SHALL return an instance of `PostgresProvider`

#### Scenario: Unknown engine raises error
- **WHEN** `DB_ENGINE` is set to an unrecognized value (e.g., `sqlite`)
- **THEN** the router SHALL raise `ValueError` containing the invalid value in the message
