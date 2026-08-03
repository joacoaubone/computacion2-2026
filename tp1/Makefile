.PHONY: run dev exec stop

run:
	docker compose up --build

dev:
	docker compose run --rm -it --name tp1-test monitor bash

exec:
	docker compose exec monitor bash

stop:
	docker compose down
