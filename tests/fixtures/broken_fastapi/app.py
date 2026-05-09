from fastapi import FastAPI

app = FastAPI()


@app.get("/")
def read_root():
    raise RuntimeError("deliberately broken")
