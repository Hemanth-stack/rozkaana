PYTHONPATH := /opt/hemanth/rozkaana
export PYTHONPATH

API_PORT   := 7078
FRONT_PORT := 7070
FRONT_CTR  := rozkaana_frontend
API_PID    := /tmp/rozkaana-api.pid
WORKER_PID := /tmp/rozkaana-worker.pid
BEAT_PID   := /tmp/rozkaana-beat.pid

.PHONY: host stop restart status \
        restart-api restart-worker \
        logs logs-api logs-worker logs-beat logs-all \
        migrate migrate-gen migrate-down shell-db shell-redis \
        regen-all regen-user trigger-pdf trigger-email admin-login \
        clean-containers help \
        _kill-api _kill-workers

# ── Start everything ──────────────────────────────────────────────────────────
host:
	@echo "── Cleaning up stale containers and processes..."
	@$(MAKE) -s _kill-api _kill-workers
	@# Remove frontend containers by all known names (standalone + compose-suffixed)
	@docker rm -f $(FRONT_CTR) $(FRONT_CTR)_1 rozkaana_frontend_1 2>/dev/null || true
	@# Stop orphaned compose-managed celery/app containers
	@docker rm -f rozkaana_celery_worker_1 rozkaana_celery_beat_1 rozkaana_app_1 2>/dev/null || true
	@sleep 1

	@echo "── Starting infrastructure (postgres / redis / minio)..."
	docker-compose up -d --remove-orphans postgres redis minio

	@echo "── Waiting for postgres..."
	@until docker inspect --format='{{.State.Health.Status}}' rozkaana_postgres_1 2>/dev/null | grep -q healthy; do \
		printf '.'; sleep 2; \
	done
	@echo " ready."

	@echo "── Running migrations..."
	alembic upgrade head

	@echo "── Starting API on :$(API_PORT)..."
	nohup uvicorn app.main:app --host 0.0.0.0 --port $(API_PORT) --workers 1 \
		> /tmp/rozkaana-api.log 2>&1 & echo $$! > $(API_PID)
	@sleep 3

	@echo "── Starting Celery worker..."
	nohup celery -A app.tasks.celery_app.celery_app worker \
		--loglevel=info --concurrency=2 \
		> /tmp/rozkaana-worker.log 2>&1 & echo $$! > $(WORKER_PID)

	@echo "── Starting Celery beat..."
	nohup celery -A app.tasks.celery_app.celery_app beat \
		--loglevel=info \
		> /tmp/rozkaana-beat.log 2>&1 & echo $$! > $(BEAT_PID)

	@echo "── Starting frontend nginx on :$(FRONT_PORT)..."
	@docker run -d \
		--name $(FRONT_CTR) \
		-p $(FRONT_PORT):80 \
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
		-v /opt/hemanth/rozkaana/household.html:/usr/share/nginx/html/household.html:ro \
		-v /opt/hemanth/rozkaana/join.html:/usr/share/nginx/html/join.html:ro \
		-v /opt/hemanth/rozkaana/about.html:/usr/share/nginx/html/about.html:ro \
		-v /opt/hemanth/rozkaana/help.html:/usr/share/nginx/html/help.html:ro \
		-v /opt/hemanth/rozkaana/privacy.html:/usr/share/nginx/html/privacy.html:ro \
		-v /opt/hemanth/rozkaana/terms.html:/usr/share/nginx/html/terms.html:ro \
		-v /opt/hemanth/rozkaana/refund.html:/usr/share/nginx/html/refund.html:ro \
		-v /opt/hemanth/rozkaana/robots.txt:/usr/share/nginx/html/robots.txt:ro \
		-v /opt/hemanth/rozkaana/sitemap.xml:/usr/share/nginx/html/sitemap.xml:ro \
		nginx:alpine
	@sleep 2
	@$(MAKE) -s status

# ── Stop everything ───────────────────────────────────────────────────────────
stop:
	@echo "── Stopping API and workers..."
	@$(MAKE) -s _kill-api _kill-workers
	@echo "── Stopping frontend..."
	@docker rm -f $(FRONT_CTR) $(FRONT_CTR)_1 rozkaana_frontend_1 2>/dev/null || true
	@echo "── Stopping infrastructure..."
	@docker-compose down --remove-orphans
	@echo "All services stopped."

# ── Restart everything ────────────────────────────────────────────────────────
restart:
	@$(MAKE) -s stop
	@sleep 2
	@$(MAKE) host

# ── Restart only the API (fast — no infra restart) ────────────────────────────
restart-api:
	@echo "── Restarting API..."
	@$(MAKE) -s _kill-api
	@sleep 1
	nohup uvicorn app.main:app --host 0.0.0.0 --port $(API_PORT) --workers 1 \
		> /tmp/rozkaana-api.log 2>&1 & echo $$! > $(API_PID)
	@echo "API restarted on :$(API_PORT) (pid $$(cat $(API_PID)))"

# ── Restart only Celery worker ────────────────────────────────────────────────
restart-worker:
	@echo "── Restarting Celery worker..."
	@$(MAKE) -s _kill-workers
	@sleep 1
	nohup celery -A app.tasks.celery_app.celery_app worker \
		--loglevel=info --concurrency=2 \
		> /tmp/rozkaana-worker.log 2>&1 & echo $$! > $(WORKER_PID)
	@echo "Worker restarted (pid $$(cat $(WORKER_PID)))"

# ── Private: kill helpers (use lsof/PID file — never pkill -f to avoid self-match) ──
_kill-api:
	@if [ -f $(API_PID) ]; then kill $$(cat $(API_PID)) 2>/dev/null || true; rm -f $(API_PID); fi
	@PIDS=$$(lsof -ti tcp:$(API_PORT) 2>/dev/null); \
	 if [ -n "$$PIDS" ]; then kill $$PIDS 2>/dev/null || true; fi

_kill-workers:
	@if [ -f $(WORKER_PID) ]; then kill $$(cat $(WORKER_PID)) 2>/dev/null || true; rm -f $(WORKER_PID); fi
	@if [ -f $(BEAT_PID) ]; then kill $$(cat $(BEAT_PID)) 2>/dev/null || true; rm -f $(BEAT_PID); fi
	@# [c]elery bracket trick: grep pattern won't match its own shell subprocess argv
	@PIDS=$$(ps -u $$(id -u) -o pid=,args= 2>/dev/null \
	       | grep '[c]elery.*celery_app' | awk '{print $$1}'); \
	 if [ -n "$$PIDS" ]; then kill $$PIDS 2>/dev/null || true; fi

# ── Status ────────────────────────────────────────────────────────────────────
status:
	@echo ""
	@echo "═══════════════════════════════════════════"
	@echo "        ROZKAANA SERVICE STATUS            "
	@echo "═══════════════════════════════════════════"
	@echo ""
	@echo "── Infrastructure ──"
	@docker ps --format "  {{.Names}}\t{{.Status}}\t{{.Ports}}" \
		| grep -E "postgres|redis|minio|$(FRONT_CTR)" || echo "  (none running)"
	@echo ""
	@echo "── API (port $(API_PORT)) ──"
	@curl -s http://localhost:$(API_PORT)/health 2>/dev/null \
		&& echo "" || echo "  DOWN — check: make logs-api"
	@echo ""
	@echo "── Workers ──"
	@ps aux | grep -E "celery.*(worker|beat)" | grep -v grep \
		| awk '{print "  " $$11, $$12, $$13}' || echo "  (none running)"
	@echo ""
	@echo "── URLs ──"
	@echo "  Landing   : http://localhost:$(FRONT_PORT)"
	@echo "  App       : http://localhost:$(FRONT_PORT)/app"
	@echo "  Admin     : http://localhost:$(FRONT_PORT)/admin"
	@echo "  Dev Chat  : http://localhost:$(FRONT_PORT)/dev"
	@echo "  API Docs  : http://localhost:$(API_PORT)/api/docs"
	@echo "  MinIO UI  : http://localhost:9001"
	@echo "═══════════════════════════════════════════"

# ── Logs ─────────────────────────────────────────────────────────────────────
logs:
	@echo "=== API (last 40) ===" && tail -40 /tmp/rozkaana-api.log
	@echo "" && echo "=== Worker (last 20) ===" && tail -20 /tmp/rozkaana-worker.log
	@echo "" && echo "=== Beat (last 10) ===" && tail -10 /tmp/rozkaana-beat.log

logs-api:
	tail -f /tmp/rozkaana-api.log

logs-worker:
	tail -f /tmp/rozkaana-worker.log

logs-beat:
	tail -f /tmp/rozkaana-beat.log

logs-all:
	tail -f /tmp/rozkaana-api.log /tmp/rozkaana-worker.log /tmp/rozkaana-beat.log

# ── Migrations ────────────────────────────────────────────────────────────────
migrate:
	alembic upgrade head

migrate-gen:
	@test -n "$(msg)" || (echo "Usage: make migrate-gen msg='describe change'"; exit 1)
	alembic revision --autogenerate -m "$(msg)"

migrate-down:
	alembic downgrade -1

# ── DB / Shell ────────────────────────────────────────────────────────────────
shell-db:
	@docker exec -it rozkaana_postgres_1 psql -U rozkaana -d rozkaana

shell-redis:
	@docker exec -it rozkaana_redis_1 redis-cli

# ── Pipeline triggers (requires API to be running) ───────────────────────────
regen-all:
	@echo "Triggering full pipeline for all active users..."
	@curl -s -X POST http://localhost:$(API_PORT)/admin/trigger/full-pipeline \
		-H "Authorization: Bearer $$(cat /tmp/rozkaana-admin-token 2>/dev/null || echo '')" \
		| python3 -m json.tool

regen-user:
	@test -n "$(user_id)" || (echo "Usage: make regen-user user_id=<uuid>"; exit 1)
	@curl -s -X POST "http://localhost:$(API_PORT)/admin/trigger/menu/$(user_id)" \
		-H "Authorization: Bearer $$(cat /tmp/rozkaana-admin-token 2>/dev/null || echo '')" \
		| python3 -m json.tool

trigger-pdf:
	@test -n "$(menu_id)" || (echo "Usage: make trigger-pdf menu_id=<uuid>"; exit 1)
	@curl -s -X POST "http://localhost:$(API_PORT)/admin/trigger/pdf/$(menu_id)" \
		-H "Authorization: Bearer $$(cat /tmp/rozkaana-admin-token 2>/dev/null || echo '')" \
		| python3 -m json.tool

trigger-email:
	@test -n "$(menu_id)" || (echo "Usage: make trigger-email menu_id=<uuid>"; exit 1)
	@curl -s -X POST "http://localhost:$(API_PORT)/admin/menus/$(menu_id)/retry-email" \
		-H "Authorization: Bearer $$(cat /tmp/rozkaana-admin-token 2>/dev/null || echo '')" \
		| python3 -m json.tool

# Save admin JWT for use in pipeline triggers above:
#   make admin-login email=you@example.com password=xxx
admin-login:
	@test -n "$(email)" || (echo "Usage: make admin-login email=<email> password=<pass>"; exit 1)
	@curl -s -X POST http://localhost:$(API_PORT)/admin/login \
		-H "Content-Type: application/json" \
		-d '{"email":"$(email)","password":"$(password)"}' \
		| python3 -c "import sys,json; d=json.load(sys.stdin); open('/tmp/rozkaana-admin-token','w').write(d['access_token']); print('Token saved to /tmp/rozkaana-admin-token')"

# ── Clean up dead Docker containers ──────────────────────────────────────────
clean-containers:
	@echo "Removing stopped/exited containers..."
	@docker container prune -f

# ── Help ─────────────────────────────────────────────────────────────────────
help:
	@echo ""
	@echo "Rozkaana Makefile commands:"
	@echo ""
	@echo "  make host              Start everything (infra + API + workers + frontend)"
	@echo "  make stop              Stop everything"
	@echo "  make restart           Full stop → start"
	@echo "  make restart-api       Restart only the API process"
	@echo "  make restart-worker    Restart only the Celery worker"
	@echo "  make status            Show service health and URLs"
	@echo ""
	@echo "  make logs              Tail all logs (last N lines)"
	@echo "  make logs-api          Follow API log"
	@echo "  make logs-worker       Follow worker log"
	@echo "  make logs-beat         Follow beat scheduler log"
	@echo "  make logs-all          Follow all logs simultaneously"
	@echo ""
	@echo "  make migrate           Run pending migrations"
	@echo "  make migrate-gen msg=  Generate a new migration"
	@echo "  make migrate-down      Roll back one migration"
	@echo ""
	@echo "  make shell-db          psql shell into postgres"
	@echo "  make shell-redis       redis-cli shell"
	@echo ""
	@echo "  make admin-login email= password=   Save admin JWT token"
	@echo "  make regen-all                      Trigger full pipeline for all users"
	@echo "  make regen-user user_id=<uuid>      Regenerate menu for one user"
	@echo "  make trigger-pdf  menu_id=<uuid>    Rebuild PDF for a menu"
	@echo "  make trigger-email menu_id=<uuid>   Retry email for a menu"
	@echo ""
	@echo "  make clean-containers  Prune stopped Docker containers"
	@echo ""
