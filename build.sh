#!/usr/bin/env bash
# Salir inmediatamente si ocurre un error
set -o errexit

# 1. Instalar dependencias
pip install -r requirements.txt

# 2. Recolectar y comprimir archivos estáticos
python manage.py collectstatic --no-input

# 3. Aplicar migraciones a la nueva base de datos PostgreSQL
python manage.py migrate