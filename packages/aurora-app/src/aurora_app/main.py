import uvicorn

from aurora_serve.server import create_app

app = create_app()


def main():
    uvicorn.run("aurora_app.main:app", host="0.0.0.0", port=8888, reload=True)


if __name__ == "__main__":
    main()
