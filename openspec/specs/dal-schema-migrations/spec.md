# dal-schema-migrations

### Requirement: Verificación fail-fast del esquema en arranque (todos los entornos)
El DAL SHALL verificar durante el lifespan de arranque, en todos los entornos (`dev`, `staging`, `prod`), que la revisión registrada en la tabla `alembic_version` de la base de datos coincide con el head de `migrations/versions/`, y SHALL abortar el arranque del proceso (exit code distinto de 0) si la verificación falla. El servicio DAL SHALL NOT ejecutar ninguna operación DDL (incluido `metadata.create_all()`) en ningún entorno.

#### Scenario: Esquema en head — arranque normal
- **WHEN** el DAL arranca y `alembic_version` contiene la revisión head del código
- **THEN** el servicio arranca normalmente y atiende requests

#### Scenario: Base de datos sin migrar — arranque abortado
- **WHEN** el DAL arranca contra una base de datos sin tabla `alembic_version`
- **THEN** el arranque aborta con error que indica que el esquema no está migrado y el comando de migración a ejecutar (`docker compose run --rm dal-migrate`)
- **THEN** no se crea ninguna tabla en la base de datos

#### Scenario: Esquema desfasado — arranque abortado
- **WHEN** el DAL arranca y `alembic_version` contiene una revisión anterior al head del código
- **THEN** el arranque aborta con error que incluye la revisión actual de la BD y la revisión head esperada

#### Scenario: Error de verificación distinguible de error de conexión
- **WHEN** la verificación falla porque la base de datos no es alcanzable
- **THEN** el mensaje de error indica fallo de conexión (no "esquema desfasado") y no incluye credenciales ni DSN con password

### Requirement: create_all confinado a fixtures de tests
`metadata.create_all()` SHALL ejecutarse únicamente dentro de fixtures de tests contra bases de datos efímeras de test. El código del servicio DAL SHALL NOT contener ninguna ruta de ejecución que invoque `create_all`, `drop_all` ni DDL equivalente.

#### Scenario: Fixtures de tests siguen funcionando
- **WHEN** se ejecuta la suite de tests del DAL
- **THEN** los fixtures crean el esquema con `create_all` sobre la base de datos de test y los tests pasan

#### Scenario: Sin DDL en el servicio
- **WHEN** se inspecciona el código del servicio (excluyendo `tests/`)
- **THEN** no existe ruta de ejecución que invoque `create_all`, `drop_all` ni DDL equivalente

### Requirement: Migraciones mediante contenedor efímero como paso de despliegue separado
El sistema SHALL proveer un servicio Docker efímero `dal-migrate` que ejecuta `alembic upgrade head` contra la base de datos y termina. Este servicio SHALL ser el único mecanismo de aplicación de migraciones en todos los entornos, SHALL reutilizar la imagen del DAL y SHALL NOT arrancar como parte del levantamiento normal del stack (`docker compose up`): solo mediante invocación explícita.

#### Scenario: Ejecución explícita de migraciones
- **WHEN** un operador ejecuta `docker compose run --rm dal-migrate`
- **THEN** se aplica `alembic upgrade head` contra la base de datos y el contenedor termina con exit code 0

#### Scenario: El stack normal no migra
- **WHEN** se ejecuta `docker compose up`
- **THEN** el servicio `dal-migrate` no se inicia y no se aplica ninguna migración

#### Scenario: Migración fallida no deja el contenedor vivo
- **WHEN** `alembic upgrade head` falla
- **THEN** el contenedor termina con exit code distinto de 0 y el error queda en los logs del contenedor

### Requirement: Separación estructural de privilegios de base de datos
El servicio DAL SHALL conectarse a PostgreSQL con un rol `vellum_app` sin privilegios DDL (solo `SELECT`/`INSERT`/`UPDATE`/`DELETE` sobre tablas y `USAGE` sobre secuencias del esquema). El contenedor `dal-migrate` SHALL conectarse con un rol `vellum_migrator` con privilegios DDL sobre el esquema. El aprovisionamiento de roles SHALL realizarse mediante un script SQL idempotente (init de PostgreSQL en compose, aplicable manualmente en entornos gestionados) que SHALL incluir `ALTER DEFAULT PRIVILEGES` para que las tablas creadas por `vellum_migrator` queden accesibles a `vellum_app` sin grants manuales.

#### Scenario: El servicio no puede ejecutar DDL
- **WHEN** se intenta ejecutar `CREATE TABLE`, `ALTER TABLE` o `DROP TABLE` con la conexión del rol `vellum_app`
- **THEN** PostgreSQL rechaza la operación con error de permisos

#### Scenario: El migrador aplica DDL y el servicio accede a las tablas nuevas
- **WHEN** `dal-migrate` aplica una migración que crea una tabla nueva
- **THEN** el servicio conectado como `vellum_app` puede leer y escribir en esa tabla sin grants adicionales

#### Scenario: La verificación de arranque funciona con el rol del servicio
- **WHEN** el DAL conectado como `vellum_app` ejecuta `verify_schema_version()`
- **THEN** puede leer `alembic_version` y la verificación se completa

#### Scenario: Script de roles idempotente
- **WHEN** el script de aprovisionamiento de roles se ejecuta sobre una base de datos donde los roles ya existen
- **THEN** termina sin error y sin alterar los privilegios ya correctos

### Requirement: Flujo de despliegue con gate de aprobación humana
La documentación de despliegue del DAL SHALL definir la secuencia obligatoria para staging/prod: (1) aprobación humana de las migraciones pendientes, (2) ejecución del contenedor efímero `dal-migrate`, (3) despliegue o reinicio del servicio DAL. SHALL incluir el procedimiento de rollback mediante `alembic downgrade` y el quickstart de dev (migrar antes de levantar el DAL).

#### Scenario: Runbook documentado
- **WHEN** un operador consulta `docs/DAL-developer-guide.md`
- **THEN** encuentra la secuencia aprobación → migrar → desplegar, los comandos exactos, el procedimiento de rollback con `alembic downgrade`, y el quickstart de dev con el paso de migración inicial
