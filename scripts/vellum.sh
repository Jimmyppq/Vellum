#!/usr/bin/env bash
# vellum.sh — Orquestación local de los contenedores de Vellum.
#
# Servicios:        postgres · redis · dal · router  (o "all")
# Composes:         docker-compose.yml (raíz: postgres, redis, dal, dal-migrate)
#                   router-ai/docker-compose.yml (router-ai)
#
# Reglas que el script conoce:
#   - El DAL no arranca sin el esquema migrado (gate de Alembic): "up dal"
#     levanta postgres, ejecuta dal-migrate y después arranca el dal.
#   - dal/.env y router-ai/.env son obligatorios para sus servicios.
#   - "down" detiene sin borrar datos; "destroy" elimina contenedores y volúmenes.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ROOT_COMPOSE=(docker compose -f "$ROOT/docker-compose.yml")
ROUTER_COMPOSE=(docker compose -f "$ROOT/router-ai/docker-compose.yml")

usage() {
  cat <<EOF
Uso: $(basename "$0") <comando> [servicio]

Comandos:
  up       <postgres|redis|dal|router|all>   Inicia el servicio (y sus dependencias)
  down     <postgres|redis|dal|router|all>   Detiene el servicio (conserva datos)
  destroy                                     Elimina TODOS los contenedores y volúmenes (pide confirmación)
  migrate                                     Aplica migraciones del DAL (dal-migrate, efímero)
  status                                      Estado de todos los contenedores
  logs     <postgres|redis|dal|router>        Sigue los logs del servicio (Ctrl-C para salir)

Ejemplos:
  $(basename "$0") up all          # postgres + redis → migraciones → dal → router-ai
  $(basename "$0") up redis        # solo redis
  $(basename "$0") down router     # detiene solo el router-ai
  $(basename "$0") destroy         # borra todo, incluidos los datos de postgres
EOF
  exit 1
}

log()  { printf '\033[1;36m[vellum]\033[0m %s\n' "$*"; }
fail() { printf '\033[1;31m[vellum]\033[0m %s\n' "$*" >&2; exit 1; }

require_env() {
  # $1 = ruta del .env, $2 = servicio al que pertenece
  [ -f "$1" ] || fail "Falta $1 (requerido por '$2'). Crea el archivo a partir de su .env.example o documentación."
}

check_docker() {
  docker info >/dev/null 2>&1 || fail "El daemon de Docker no está corriendo."
}

migrate_dal() {
  require_env "$ROOT/dal/.env" "dal"
  log "Levantando postgres (si no está) y esperando healthcheck…"
  "${ROOT_COMPOSE[@]}" up -d --wait postgres
  log "Aplicando migraciones (dal-migrate, contenedor efímero)…"
  "${ROOT_COMPOSE[@]}" run --rm dal-migrate
}

up_one() {
  case "$1" in
    postgres) "${ROOT_COMPOSE[@]}" up -d --wait postgres ;;
    redis)    "${ROOT_COMPOSE[@]}" up -d --wait redis ;;
    dal)
      migrate_dal
      log "Iniciando dal…"
      "${ROOT_COMPOSE[@]}" up -d dal
      ;;
    router)
      require_env "$ROOT/router-ai/.env" "router"
      log "Iniciando router-ai…"
      "${ROUTER_COMPOSE[@]}" up -d
      ;;
    all)
      up_one postgres
      up_one redis
      up_one dal
      up_one router
      log "Stack completo arriba."
      ;;
    *) usage ;;
  esac
}

down_one() {
  case "$1" in
    postgres) "${ROOT_COMPOSE[@]}" stop postgres ;;
    redis)    "${ROOT_COMPOSE[@]}" stop redis ;;
    dal)      "${ROOT_COMPOSE[@]}" stop dal ;;
    router)   "${ROUTER_COMPOSE[@]}" down ;;
    all)
      log "Deteniendo router-ai…";  "${ROUTER_COMPOSE[@]}" down
      log "Deteniendo stack raíz…"; "${ROOT_COMPOSE[@]}" down
      log "Todo detenido (datos conservados)."
      ;;
    *) usage ;;
  esac
}

destroy_all() {
  printf '\033[1;31m[vellum]\033[0m Esto eliminará contenedores Y VOLÚMENES (datos de postgres incluidos). ¿Seguro? [escribe "si"]: '
  read -r answer
  [ "$answer" = "si" ] || { log "Cancelado."; exit 0; }
  log "Destruyendo router-ai…";  "${ROUTER_COMPOSE[@]}" down -v --remove-orphans
  log "Destruyendo stack raíz…"; "${ROOT_COMPOSE[@]}" down -v --remove-orphans
  log "Todo eliminado."
}

status_all() {
  log "Stack raíz (postgres · redis · dal):"
  "${ROOT_COMPOSE[@]}" ps
  echo
  log "router-ai:"
  "${ROUTER_COMPOSE[@]}" ps
}

logs_one() {
  case "$1" in
    postgres|redis|dal) "${ROOT_COMPOSE[@]}" logs -f "$1" ;;
    router)             "${ROUTER_COMPOSE[@]}" logs -f ;;
    *) usage ;;
  esac
}

[ $# -ge 1 ] || usage
check_docker

case "$1" in
  up)      [ $# -eq 2 ] || usage; up_one "$2" ;;
  down)    [ $# -eq 2 ] || usage; down_one "$2" ;;
  destroy) destroy_all ;;
  migrate) migrate_dal ;;
  status)  status_all ;;
  logs)    [ $# -eq 2 ] || usage; logs_one "$2" ;;
  *) usage ;;
esac
