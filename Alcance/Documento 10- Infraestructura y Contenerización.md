# Documento 10: Infraestructura y Contenerización

**Sistema Corporativo de Gestión de Prompts**

---

## 1. Objetivo del documento

Definir la infraestructura base del sistema utilizando contenedores, garantizando:

* Portabilidad
* Reproducibilidad
* Aislamiento de servicios
* Escalabilidad futura

---

## 2. Principios de infraestructura

* **Container-first** desde el inicio
* **Entornos consistentes (dev = prod lo más posible)**
* **Configuración externa (no hardcodeada)**
* **Desacoplamiento de servicios**
* **Preparado para Kubernetes**

---

## 3. Componentes a contenerizar

Cada uno como contenedor independiente:

* frontend (Angular)
* backend (FastAPI)
* database (PostgreSQL)
* cache/queue (Redis)
* api-gateway (Nginx o similar)
* worker (procesamiento async)

---

## 4. Estructura de repositorio

```id="i1"
project-root/
 ├── backend/
 ├── frontend/
 ├── infra/
 │    ├── docker/
 │    └── docker-compose.yml
 ├── VERSION
 └── .env
```

---

## 5. Dockerfiles

---

## 5.1 Backend (FastAPI)

```dockerfile id="i2"
FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
```

---

## 5.2 Frontend (Angular)

```dockerfile id="i3"
FROM node:18 as build

WORKDIR /app
COPY . .
RUN npm install && npm run build

FROM nginx:alpine
COPY --from=build /app/dist /usr/share/nginx/html
```

---

## 5.3 Worker

Similar al backend, pero ejecutando worker:

```dockerfile id="i4"
CMD ["celery", "-A", "app.worker", "worker", "--loglevel=info"]
```

---

## 6. Docker Compose (desarrollo)

---

```yaml id="i5"
version: "3.9"

services:

  backend:
    build: ./backend
    ports:
      - "8000:8000"
    env_file: .env
    depends_on:
      - db
      - redis

  frontend:
    build: ./frontend
    ports:
      - "4200:80"

  db:
    image: postgres:15
    environment:
      POSTGRES_DB: prompts
      POSTGRES_USER: user
      POSTGRES_PASSWORD: password
    volumes:
      - db_data:/var/lib/postgresql/data

  redis:
    image: redis:7

  worker:
    build: ./backend
    command: celery -A app.worker worker
    depends_on:
      - backend
      - redis

  gateway:
    image: nginx:alpine
    volumes:
      - ./infra/nginx.conf:/etc/nginx/nginx.conf
    ports:
      - "80:80"

volumes:
  db_data:
```

---

## 7. Redes

---

* Red interna Docker
* Servicios comunicándose por nombre

Ejemplo:

```id="i6"
backend → db:5432
backend → redis:6379
```

---

## 8. Volúmenes persistentes

---

### Necesarios:

* Base de datos
* Logs (opcional)

---

Ejemplo:

```id="i7"
db_data:/var/lib/postgresql/data
```

---

## 9. Variables de entorno

---

Archivo `.env`:

```id="i8"
DB_HOST=db
DB_USER=user
DB_PASSWORD=password
REDIS_HOST=redis
ENV=dev
```

---

## 10. Configuración por entorno

---

### Dev

* docker-compose
* logs verbose

---

### Staging

* configuración similar a prod
* pruebas

---

### Prod

* sin puertos expuestos innecesarios
* seguridad reforzada

---

## 11. API Gateway (Nginx)

---

Responsabilidades:

* routing
* TLS
* seguridad básica

---

Ejemplo config:

```nginx id="i9"
server {
    listen 80;

    location /api/ {
        proxy_pass http://backend:8000/;
    }

    location / {
        root /usr/share/nginx/html;
    }
}
```

---

## 12. Escalabilidad

---

### Horizontal

* múltiples instancias backend
* múltiples workers

---

### Vertical

* más CPU / RAM

---

## 13. Preparación para Kubernetes

---

Aunque se empiece con Docker:

* separar servicios
* evitar estado en contenedores
* usar variables de entorno

---

Futuro:

* Deploy con Kubernetes
* Autoescalado

---

## 14. Seguridad en contenedores

---

* Imágenes oficiales
* No usar root
* Escaneo de vulnerabilidades
* Secrets fuera de imagen

---

## 15. Gestión de logs en contenedores

---

Opciones:

* stdout (recomendado)
* archivos montados

---

## 16. Health checks

---

Cada servicio debe exponer:

```id="i10"
/health
```

---

Permite:

* monitoreo
* reinicios automáticos

---

## 17. Arranque del sistema

---

```id="i11"
docker-compose up --build
```

---

## 18. Parada

```id="i12"
docker-compose down
```

---

## 19. Riesgos

---

* mala gestión de volúmenes
* dependencia de configuración local
* falta de aislamiento

---

## 20. Buenas prácticas

---

* no hardcodear nada
* separar entornos
* versionar imágenes
* usar .env correctamente

---

## 21. Resumen ejecutivo

La infraestructura:

* Permite levantar el sistema completo en minutos
* Asegura consistencia entre entornos
* Facilita escalado futuro
* Reduce fricción en desarrollo

---

👉 Docker aquí no es opcional, es la base operativa del sistema.

---
