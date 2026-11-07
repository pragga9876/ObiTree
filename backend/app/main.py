from fastapi import FastAPI

app = FastAPI(title="PaperRoots API")

@app.get("/health")
def health():
    return {"status": "ok"}