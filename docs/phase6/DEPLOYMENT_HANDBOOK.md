# DOIP Deployment Handbook
## Defense Operations Intelligence Platform — Production Infrastructure & Deployment
### Phase 6 Production Hardening & Operational Deployment

---

## 1. Deployment Models & System Profiles

DOIP is engineered to run seamlessly across two primary deployment archetypes:

```text
┌───────────────────────────────────────────────┬───────────────────────────────────────────────┐
│        PROFILE A: ENTERPRISE COMMAND          │          PROFILE B: TACTICAL EDGE FOB         │
├───────────────────────────────────────────────┼───────────────────────────────────────────────┤
│ • Primary Host: Headquarters / Data Center    │ • Primary Host: Ruggedized Laptop / Vehicle   │
│ • Database: PostgreSQL 16 + PostGIS + pgvector│ • Database: Embedded SQLite 3.40+ (WAL Mode)  │
│ • LLM/Vision: vLLM or Ollama on dedicated GPU │ • LLM/Vision: CPU Rule-Grounded Fallback      │
│ • Networking: Multi-user LAN / SIPRNet / WAN  │ • Networking: Air-gapped / Degraded Tactical  │
│ • Ingestion: Real-time sensor feeds (ADS-B)   │ • Ingestion: Local sensor relays / Manual     │
└───────────────────────────────────────────────┴───────────────────────────────────────────────┘
```

---

## 2. Hardware & Infrastructure Sizing

### 2.1 Profile A — Enterprise Command Center (Per Node)
- **CPU**: 16 physical cores (x86_64 or ARM64)
- **RAM**: 64 GB DDR4/DDR5 ECC
- **GPU**: NVIDIA RTX 4090 / A5000 / A100 (24GB+ VRAM for concurrent LLM & vision inference)
- **Storage**: 1 TB NVMe SSD (PCIe 4.0)
- **Network**: 10 GbE NIC with redundant interfaces

### 2.2 Profile B — Tactical Edge / Forward Operating Base (FOB)
- **CPU**: 4 to 8 cores (e.g., Intel i7/Xeon-D or AMD Ryzen Mobile)
- **RAM**: 16 GB to 32 GB
- **GPU**: Integrated or NVIDIA T1000 / RTX 2000 Ada Mobile (optional; CPU inference supported)
- **Storage**: 256 GB NVMe SSD
- **Network**: Air-gapped, isolated 1 GbE or tactical mesh radio (PACE)

---

## 3. Environment Variable Configuration Reference

| Variable | Default Value | Description |
|---|---|---|
| `APP_ENV` | `production` | Operational environment mode (`development`, `staging`, `production`). |
| `DATABASE_URL` | `sqlite:///./doip.db` | Persistence connection string. Use `postgresql://user:pass@host:5432/doip` for PostGIS. |
| `DB_POOL_SIZE` | `20` | Database connection pool size (PostgreSQL). |
| `DB_MAX_OVERFLOW`| `10` | Max overflow connections beyond pool size. |
| `OLLAMA_HOST` | `http://127.0.0.1:11434` | Endpoint for local Ollama LLM provider. |
| `OPENAI_API_BASE`| `http://127.0.0.1:8000/v1` | OpenAI-compatible endpoint (vLLM or LiteLLM). |
| `JWT_SECRET_KEY` | *(Generated random 32-byte)*| Shared secret for HMAC-SHA256 authentication tokens. |
| `ALLOWED_ORIGINS`| `*` | Comma-separated list of CORS origin headers. |
| `LOG_LEVEL` | `INFO` | Application log verbosity (`DEBUG`, `INFO`, `WARNING`, `ERROR`). |
| `CACHE_DEFAULT_TTL`| `300` | Default time-to-live for cached responses in seconds. |

---

## 4. Docker Compose Deployment (Profile A)

Below is the standard production `docker-compose.yml` configuration:

```yaml
version: '3.8'

services:
  db:
    image: postgis/postgis:16-3.4
    restart: always
    environment:
      POSTGRES_DB: doip
      POSTGRES_USER: doip_admin
      POSTGRES_PASSWORD: ${DB_PASSWORD:-OperationalSecret2026!}
    volumes:
      - postgres_data:/var/lib/postgresql/data
    ports:
      - "5432:5432"
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U doip_admin -d doip"]
      interval: 10s
      timeout: 5s
      retries: 5

  backend:
    build:
      context: ./backend
      dockerfile: Dockerfile
    restart: always
    depends_on:
      db:
        condition: service_healthy
    environment:
      APP_ENV: production
      DATABASE_URL: postgresql://doip_admin:${DB_PASSWORD:-OperationalSecret2026!}@db:5432/doip
      OLLAMA_HOST: http://host.docker.internal:11434
      JWT_SECRET_KEY: ${JWT_SECRET_KEY:-ChangeThisInProductionKey12345}
    ports:
      - "8000:8000"
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/api/health"]
      interval: 15s
      timeout: 5s
      retries: 3

  frontend:
    build:
      context: ./frontend
      dockerfile: Dockerfile
    restart: always
    depends_on:
      - backend
    ports:
      - "80:80"

volumes:
  postgres_data:
```

### Launch Commands
```bash
# Validate configuration and start containers
docker compose up -d

# Verify service logs
docker compose logs -f backend

# Run initial database migration
docker compose exec backend alembic upgrade head
```

---

## 5. Air-Gapped Deployment Procedures

For classified or isolated networks without public internet egress:

### 5.1 Artifact Staging (On Internet-Connected Machine)
```bash
# 1. Export container images
docker save -o doip_stack.tar postgis/postgis:16-3.4 doip-backend:latest doip-frontend:latest

# 2. Pull model weights for local inference
ollama pull nomic-embed-text
ollama pull llama3:8b
# Tar ~/.ollama/models directory
tar -czvf ollama_models.tar.gz ~/.ollama/models

# 3. Export python wheels if deploying bare metal
pip download -r backend/requirements.txt -d ./wheels/
```

### 5.2 Destination Loading (Air-Gapped Node)
```bash
# 1. Load container images
docker load -i doip_stack.tar

# 2. Unpack model cache
tar -xzvf ollama_models.tar.gz -C ~/.ollama/

# 3. Initialize DOIP in offline mode
docker compose up -d
```

---

## 6. Backup & Disaster Recovery

### 6.1 Database Backup
```bash
# PostgreSQL Automated Dump
pg_dump -U doip_admin -h localhost -Fc doip > /backup/doip_$(date +%Y%m%d_%H%M%S).dump

# SQLite Snapshot
sqlite3 doip.db ".backup '/backup/doip_snapshot_$(date +%Y%m%d_%H%M%S).db'"
```

### 6.2 Restoration
```bash
# PostgreSQL Restore
pg_restore -U doip_admin -d doip --clean --if-exists /backup/doip_target.dump

# SQLite Restore
cp /backup/doip_snapshot_target.db ./doip.db
```
