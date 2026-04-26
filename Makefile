.PHONY: host stop

host:
	docker-compose up -d landing-page

stop:
	docker-compose down