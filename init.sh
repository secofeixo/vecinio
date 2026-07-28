#!/usr/bin/env bash
# Project scaffold: neighborhood community management
# Usage: bash init.sh (run from the project root)

set -e

mkdir -p src/domain/community
mkdir -p src/domain/owner
mkdir -p src/application/community
mkdir -p src/application/owner
mkdir -p src/infrastructure/persistence
mkdir -p src/infrastructure/outbox
mkdir -p src/interfaces/api/routers
mkdir -p src/interfaces/api/schemas

mkdir -p tests/unit/domain/community
mkdir -p tests/unit/domain/owner
mkdir -p tests/integration/infrastructure
mkdir -p tests/e2e/api

mkdir -p migrations
mkdir -p frontend

for pkg in \
  src/domain src/domain/community src/domain/owner \
  src/application src/application/community src/application/owner \
  src/infrastructure src/infrastructure/persistence src/infrastructure/outbox \
  src/interfaces src/interfaces/api src/interfaces/api/routers src/interfaces/api/schemas
do
  touch "$pkg/__init__.py"
done

touch src/domain/community/community.py
touch src/domain/community/unit.py
touch src/domain/community/value_objects.py
touch src/domain/community/events.py
touch src/domain/community/repository.py

touch src/domain/owner/owner.py
touch src/domain/owner/value_objects.py
touch src/domain/owner/events.py
touch src/domain/owner/repository.py

touch src/application/community/register_community.py
touch src/application/community/assign_owner_to_unit.py
touch src/application/owner/register_owner.py

touch src/infrastructure/persistence/models.py
touch src/infrastructure/persistence/community_repository.py
touch src/infrastructure/persistence/owner_repository.py
touch src/infrastructure/persistence/audit_log.py
touch src/infrastructure/outbox/outbox_repository.py

touch src/interfaces/api/main.py
touch src/interfaces/api/routers/communities.py
touch src/interfaces/api/routers/owners.py
touch src/interfaces/api/schemas/community_schemas.py
touch src/interfaces/api/schemas/owner_schemas.py

echo "Structure created under src/, tests/ and migrations/"
find src tests migrations frontend -type d | sort
