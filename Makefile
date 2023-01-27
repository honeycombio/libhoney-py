
smoke:
	@echo ""
	@echo "+++ Running example app in docker"
	@echo ""
	docker-compose up --build

unsmoke:
	@echo ""
	@echo "+++ Spinning down example app in docker"
	@echo ""
	docker-compose down