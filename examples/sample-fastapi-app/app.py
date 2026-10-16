from fastapi import FastAPI

app = FastAPI(title="sample-fastapi-app")


@app.get("/")
def root():
    return {"app": "sample-fastapi-app"}


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/version")
def version():
    return {"version": "0.1.0"}
