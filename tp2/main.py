"""Punto de entrada local para ejecutar la API del TP2."""

if __package__:
    from .app.application import app
else:
    from app.application import app


def main() -> None:
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)


if __name__ == "__main__":
    main()
