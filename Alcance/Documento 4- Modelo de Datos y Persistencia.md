# Documento 4: Modelo de Datos y Persistencia

**Sistema Corporativo de Gestión de Prompts**

---

## 1. Objetivo del documento

Definir el modelo de datos del sistema, su estructura, relaciones y estrategia de persistencia, garantizando:

* Integridad
* Escalabilidad
* Trazabilidad
* Flexibilidad

---

## 2. Principios de diseño

* Modelo relacional como fuente de verdad
* Normalización controlada (evitar sobre-normalización)
* Separación entre datos operativos y logs
* Versionado explícito
* Auditoría desde el diseño

---

## 3. Tecnología de persistencia

### Base principal

* PostgreSQL

### Complementarios

* Redis (cache + colas)
* Sistema de logs (archivos + futuro ELK)

---

## 4. Entidades principales

* users
* roles
* user_roles
* prompts
* prompt_versions
* transcripts
* transcript_versions
* executions
* connectors
* connector_configs
* system_config

---

## 5. Modelo de datos (tablas)

---

## 5.1 users

```sql id="t1"
users (
  id UUID PRIMARY KEY,
  username VARCHAR(100) UNIQUE,
  email VARCHAR(255) UNIQUE,
  is_active BOOLEAN,
  created_at TIMESTAMP,
  updated_at TIMESTAMP
)
```

---

## 5.2 roles

```sql id="t2"
roles (
  id UUID PRIMARY KEY,
  name VARCHAR(50), -- admin, editor, viewer
  description TEXT
)
```

---

## 5.3 user_roles

```sql id="t3"
user_roles (
  user_id UUID,
  role_id UUID,
  PRIMARY KEY (user_id, role_id)
)
```

---

## 5.4 prompts

Entidad base (no contiene contenido versionado).

```sql id="t4"
prompts (
  id UUID PRIMARY KEY,
  name VARCHAR(255),
  description TEXT,
  owner_id UUID,
  status VARCHAR(50), -- draft, approved, deprecated
  visibility VARCHAR(50),
  created_at TIMESTAMP,
  updated_at TIMESTAMP
)
```

---

## 5.5 prompt_versions

Aquí vive el contenido real.

```sql id="t5"
prompt_versions (
  id UUID PRIMARY KEY,
  prompt_id UUID,
  version_number INTEGER,
  content TEXT,
  change_log TEXT,
  created_by UUID,
  created_at TIMESTAMP,
  is_active BOOLEAN
)
```

---

### Decisión clave:

👉 Nunca se sobrescribe un prompt.
👉 Siempre se crea una nueva versión.

---

## 5.6 executions

Registro de cada ejecución.

```sql id="t6"
executions (
  id UUID PRIMARY KEY,
  prompt_id UUID,
  version_id UUID,
  transcript_id UUID, -- NULL si es texto libre, y UUID si se ejecuta sobre una transcripción gobernada
  executed_by UUID,
  input_data JSONB,
  output_data JSONB,
  status VARCHAR(50), -- queued, running, completed, failed
  model_used VARCHAR(100),
  cost NUMERIC,
  created_at TIMESTAMP,
  completed_at TIMESTAMP
)
```

---

## 5.7 connectors

```sql id="t7"
connectors (
  id UUID PRIMARY KEY,
  type VARCHAR(50), -- confluence, slack, etc.
  name VARCHAR(100),
  is_active BOOLEAN,
  created_at TIMESTAMP
)
```

---

## 5.8 connector_configs

Configuración sensible separada.

```sql id="t8"
connector_configs (
  id UUID PRIMARY KEY,
  connector_id UUID,
  config JSONB,
  encrypted BOOLEAN,
  created_at TIMESTAMP
)
```

---

## 5.9 system_config

Configuración dinámica.

```sql id="t9"
system_config (
  key VARCHAR(100) PRIMARY KEY,
  value JSONB,
  updated_at TIMESTAMP
)
```

---

## 5.10 transcripts

Entidad base para los archivos de audio/video gobernados.

```sql id="t10"
transcripts (
  id UUID PRIMARY KEY,
  name VARCHAR(255),
  media_url VARCHAR(500), -- Referencia al Object Storage (ej. S3)
  owner_id UUID,
  status VARCHAR(50), -- uploading, transcribing, ready, failed
  created_at TIMESTAMP,
  updated_at TIMESTAMP
)
```

---

## 5.11 transcript_versions

Contiene el texto resultante del ASR, con posibles ediciones.

```sql id="t11"
transcript_versions (
  id UUID PRIMARY KEY,
  transcript_id UUID,
  version_number INTEGER,
  content TEXT, -- El texto de la transcripción
  change_log TEXT,
  created_by UUID,
  created_at TIMESTAMP,
  is_active BOOLEAN
)
```

---

## 6. Relaciones clave

* users → prompts (owner)
* prompts → prompt_versions (1:N)
* users → transcripts (owner)
* transcripts → transcript_versions (1:N)
* prompt_versions → executions (1:N)
* transcripts → executions (1:N)
* users → executions
* connectors → connector_configs

---

## 7. Estrategia de versionado

* Campo `version_number` incremental
* Solo una versión activa
* Histórico completo inmutable

---

## 8. Uso de JSONB (PostgreSQL)

Se utiliza en:

* inputs de ejecución
* outputs de ejecución
* configuraciones
* metadatos futuros

---

### Ventajas:

* Flexibilidad
* Evolución sin migraciones constantes

---

## 9. Indexación

Índices críticos:

* prompts(id)
* prompt_versions(prompt_id, version_number)
* executions(prompt_id)
* executions(status)
* executions(created_at)

---

👉 Sin índices, esto muere en producción.

---

## 10. Estrategia de auditoría

Campos obligatorios:

* created_at
* updated_at
* created_by

---

Futuro:

* tabla audit_logs (opcional)

---

## 11. Separación de logs vs datos

IMPORTANTE:

* Logs → archivos / ELK
* Datos → PostgreSQL

👉 Nunca mezclar.

---

## 12. Estrategia de crecimiento

### Horizontal

* Particionado de executions (por fecha)

---

### Vertical

* Escalar DB

---

### Futuro

* Data warehouse para analytics

---

## 13. Gestión de datos sensibles

* Configuraciones cifradas
* Tokens nunca en texto plano
* Uso de KMS o similar

---

## 14. Migraciones

Herramienta recomendada:

* Alembic

---

Buenas prácticas:

* Versionar cambios
* Scripts reversibles
* Entornos separados

---

## 15. Consistencia

* Foreign keys activas
* Transacciones en operaciones críticas

---

## 16. Ejemplo de flujo real en DB

### Crear prompt

1. Insert en prompts
2. Insert en prompt_versions

---

### Ejecutar prompt

1. Insert en executions (status=queued)
2. Update a running
3. Update a completed + output

---

## 17. Riesgos

* Crecimiento excesivo de executions
* Uso abusivo de JSONB sin control
* Falta de indexación

---

## 18. Buenas prácticas

* Limitar tamaño de inputs/outputs
* Limpieza periódica (archivado)
* Monitorización de tablas grandes

---

## 19. Resumen ejecutivo

El modelo de datos está diseñado para:

* Garantizar trazabilidad total
* Soportar versionado real
* Permitir ejecución controlada
* Escalar sin rediseño

---
