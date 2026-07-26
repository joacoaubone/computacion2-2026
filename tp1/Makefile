.PHONY: run dev exec stop

run:
	docker compose up --build

dev:
	docker compose run --rm -it monitor tail -f /dev/null

exec:
	docker compose exec monitor bash

stop:
	docker compose down
