.PHONY: host stop restart status logs

PYTHONPATH := /opt/hemanth/rozkaana
export PYTHONPATH

# ── Start everything ─────────────────────────────────────────────────────────
host:
	@echo "Starting infrastructure..."
	docker-compose up -d postgres redis minio
	@echo "Waiting for postgres to be healthy..."
	@until docker inspect --format='{{.State.Health.Status}}' rozkaana_postgres_1 2>/dev/null | grep -q healthy; do sleep 2; done
	@echo "Starting API on :7078..."
	nohup uvicorn app.main:app --host 0.0.0.0 --port 7078 --workers 1 \
		> /tmp/rozkaana-api.log 2>&1 &
	@sleep 3
	@echo "Starting Celery worker..."
	nohup celery -A app.tasks.celery_app.celery_app worker \
		--loglevel=info --concurrency=2 -f /tmp/rozkaana-worker.log > /dev/null 2>&1 &
	@echo "Starting Celery beat..."
	nohup celery -A app.tasks.celery_app.celery_app beat \
		--loglevel=info > /tmp/rozkaana-beat.log 2>&1 &
	@echo "Starting frontend nginx on :7070..."
	@docker rm -f rozkaana_frontend 2>/dev/null || true
	docker run -d \
		--name rozkaana_frontend \
		-p 7070:80 \
		-v /opt/hemanth/rozkaana/nginx.conf:/etc/nginx/conf.d/default.conf:ro \
		-v /opt/hemanth/rozkaana/index.html:/usr/share/nginx/html/index.html:ro \
		-v /opt/hemanth/rozkaana/admin.html:/usr/share/nginx/html/admin.html:ro \
		-v /opt/hemanth/rozkaana/dev.html:/usr/share/nginx/html/dev.html:ro \
		-v /opt/hemanth/rozkaana/auth-success.html:/usr/share/nginx/html/auth-success.html:ro \
		-v /opt/hemanth/rozkaana/onboard.html:/usr/share/nginx/html/onboard.html:ro \
		-v /opt/hemanth/rozkaana/app.html:/usr/share/nginx/html/app.html:ro \
		-v /opt/hemanth/rozkaana/settings.html:/usr/share/nginx/html/settings.html:ro \
		-v /opt/hemanth/rozkaana/billing.html:/usr/share/nginx/html/billing.html:ro \
		-v /opt/hemanth/rozkaana/history.html:/usr/share/nginx/html/history.html:ro \
		nginx:alpine
	@sleep 2
	@$(MAKE) status

# ── Stop everything ───────────────────────────────────────────────────────────
stop:
	@echo "Stopping API and workers..."
	@fuser -k 7078/tcp 2>/dev/null || true
	@pkill -f "celery.*rozkaana" 2>/dev/null || true
	@docker rm -f rozkaana_frontend 2>/dev/null || true
	@echo "Stopping infrastructure..."
	docker-compose down
	@echo "All services stopped."

# ── Restart ───────────────────────────────────────────────────────────────────
restart:
	@$(MAKE) stop
	@sleep 2
	@$(MAKE) host

# ── Status ────────────────────────────────────────────────────────────────────
status:
	@echo ""
	@echo "═══════════════════════════════════════════"
	@echo "          ROZKAANA SERVICE STATUS           "
	@echo "═══════════════════════════════════════════"
	@echo ""
	@echo "── Infrastructure ──"
	@docker ps --format "  {{.Names}}\t{{.Status}}" | grep -E "postgres|redis|minio|frontend" || echo "  (none running)"
	@echo ""
	@echo "── API ──"
	@curl -s http://localhost:7078/health 2>/dev/null && echo "" || echo "  API: DOWN"
	@echo ""
	@echo "── Workers ──"
	@ps aux | grep -E "celery.*(worker|beat)" | grep -v grep | awk '{print "  " $$11, $$12, $$13}' || echo "  (none running)"
	@echo ""
	@echo "── URLs ──"
	@echo "  Landing   : http://localhost:7070"
	@echo "  Admin     : http://localhost:7070/admin"
	@echo "  Dev Chat  : http://localhost:7070/dev"
	@echo "  API Docs  : http://localhost:7078/api/docs"
	@echo "═══════════════════════════════════════════"

# ── Logs ─────────────────────────────────────────────────────────────────────
logs:
	@echo "=== API ===" && tail -30 /tmp/rozkaana-api.log
	@echo "" && echo "=== Worker ===" && tail -20 /tmp/rozkaana-worker.log

logs-api:
	tail -f /tmp/rozkaana-api.log

logs-worker:
	tail -f /tmp/rozkaana-worker.log

# ── Migrations ────────────────────────────────────────────────────────────────
migrate:
	alembic upgrade head

migrate-gen:
	alembic revision --autogenerate -m "$(msg)"
