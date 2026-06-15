./scripts/vellum.sh up <postgres|redis|dal|router|all>
./scripts/vellum.sh down <postgres|redis|dal|router|all>   # conserva datos
./scripts/vellum.sh destroy                                # borra todo + volúmenes (pide confirmación)
./scripts/vellum.sh migrate                                # solo migraciones del DAL
./scripts/vellum.sh status
./scripts/vellum.sh logs <servicio>
