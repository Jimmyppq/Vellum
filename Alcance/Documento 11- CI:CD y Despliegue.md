# Documento 11: CI/CD y Despliegue

**Sistema Corporativo de Gestión de Prompts**

---

## 1. Objetivo del documento

Definir la estrategia de integración continua (CI) y despliegue continuo (CD), garantizando:

* Calidad del software
* Automatización de procesos
* Despliegues seguros y repetibles
* Control de versiones

---

## 2. Principios clave

* **Automatización total**
* **Pipeline como código**
* **Fail fast** (fallar rápido)
* **Despliegues reproducibles**
* **Rollback sencillo**

---

## 3. Flujo general

```id="ci1"
[ Developer ]
     │
     ▼
[ Git Push ]
     │
     ▼
[ CI Pipeline ]
     │
     ├── Build
     ├── Test
     ├── Security Scan
     └── Package (Docker)
     │
     ▼
[ CD Pipeline ]
     │
     ├── Deploy Staging
     ├── Tests
     └── Deploy Prod
```

---

## 4. Estrategia de ramas

---

### 4.1 Ramas principales

* `main` → producción
* `develop` → integración
* `feature/*` → desarrollo
* `hotfix/*` → correcciones urgentes

---

### 4.2 Flujo

* Feature → develop
* Release → main
* Hotfix → main + develop

---

## 5. Pipeline de CI

---

## 5.1 Etapas

---

### 1. Checkout

```id="ci2"
git clone repo
```

---

### 2. Validación

* Linting
* Formato de código

---

### 3. Build

* Backend
* Frontend

---

### 4. Tests

* Unitarios
* Integración

---

### 5. Security Scan

* Dependencias
* Vulnerabilidades

---

### 6. Build de contenedores

```id="ci3"
docker build -t backend:1.2.0 .
docker build -t frontend:1.2.0 .
```

---

### 7. Push a registry

* Docker Hub / ECR / GCR

---

## 6. Pipeline de CD

---

## 6.1 Staging

* Deploy automático
* Tests de integración

---

## 6.2 Producción

Opciones:

* Manual approval (recomendado)
* Automático (si muy maduro)

---

## 7. Estrategias de despliegue

---

### 7.1 Rolling update (recomendado)

* Sin downtime
* Reemplazo gradual

---

### 7.2 Blue/Green

* Dos entornos
* Switch controlado

---

### 7.3 Canary

* Despliegue parcial
* Validación progresiva

---

## 8. Versionado en CI/CD

---

### 8.1 Fuente

* Archivo `VERSION`

---

### 8.2 Uso

* Tags Docker
* Releases
* Logs

---

### 8.3 Ejemplo

```id="ci4"
backend:1.2.0
frontend:1.2.0
```

---

## 9. Gestión de entornos

---

Variables separadas:

* dev
* staging
* prod

---

Nunca mezclar:

* credenciales
* endpoints

---

## 10. Secretos en CI/CD

---

* Variables seguras del pipeline
* Nunca en repositorio

---

Ejemplos:

* DB password
* API tokens
* claves

---

## 11. Testing

---

### 11.1 Tipos

* Unit tests
* Integration tests
* API tests

---

### 11.2 Reglas

* Tests obligatorios para merge
* Coverage mínimo

---

## 12. Validación de API

---

* Tests automáticos sobre endpoints
* Validación de contratos

---

## 13. Rollback

---

Debe ser inmediato:

```id="ci5"
deploy previous version
```

---

### Opciones:

* Revert Docker tag
* Revert release

---

## 14. Automatización del versionado

---

Opcional:

* Auto incremento PATCH
* Generación de changelog

---

## 15. Monitoreo post-deploy

---

Tras cada deploy:

* Verificar logs
* Validar métricas
* Revisar errores

---

## 16. Integración con Git

---

### Buenas prácticas:

* Commits claros
* PR obligatorios
* Code review

---

## 17. Pipeline como código

---

Herramientas:

* GitHub Actions
* GitLab CI
* Jenkins

---

Ejemplo básico:

```yaml id="ci6"
name: CI

on: [push]

jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      - name: Build
        run: docker build .
```

---

## 18. Riesgos

---

* Deploy manual
* Falta de tests
* Versionado inconsistente
* Exposición de secretos

---

## 19. Buenas prácticas

---

* Automatizar todo
* Validar antes de deploy
* Mantener pipelines simples
* Monitorear siempre

---

## 20. Resumen ejecutivo

El CI/CD permite:

* Entregar cambios rápidamente
* Reducir errores humanos
* Mantener calidad constante
* Escalar el desarrollo

---

👉 Sin CI/CD: caos
👉 Con CI/CD: sistema controlado y predecible

---