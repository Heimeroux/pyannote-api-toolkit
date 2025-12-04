import uvicorn
import os
import logging

from fastapi import FastAPI

app = FastAPI()
logger = logging.getLogger(__name__)

@app.post("/read")
async def read():
    return {"status": "ok"}

if __name__ == "__main__":
    host = os.getenv("API_HOST", "0.0.0.0")
    port = int(os.getenv("API_PORT", 5003))
    uvicorn.run(app, host=host, port=port)