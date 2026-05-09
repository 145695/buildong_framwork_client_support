from app.main import DEVICE, WHISPER_MODEL, app, ml_models


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)