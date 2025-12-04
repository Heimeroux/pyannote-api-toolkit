import requests
import os
import uvicorn
import sys
import logging

from fastapi import FastAPI, UploadFile, Form, File, HTTPException, status
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from typing import Optional, Dict

pyannote_wrapper_host = os.getenv("PYANNOTE_WRAPPER_HOST")
pyannote_wrapper_port = os.getenv("PYANNOTE_WRAPPER_PORT")
mongo_gateway_host = os.getenv("MONGO_GATEWAY_HOST")
mongo_gateway_port = os.getenv("MONGO_GATEWAY_PORT")

pyannote_wrapper_uri = f"http://{pyannote_wrapper_host}:{pyannote_wrapper_port}"
mongo_gateway_uri = f"http://{mongo_gateway_host}:{mongo_gateway_port}"

app = FastAPI()
logger = logging.getLogger(__name__)

"""
origins = [
    "http://localhost:8080"
]

# TO DO : To limit properties setted up
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
"""

def call_external_service(
    url: str,
    files: Optional[dict] = None,
    data: Optional[dict] = None
) -> dict:
    try:
        response = requests.post(url, files=files, data=data)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.HTTPError as e:
        logger.error(f"HTTP Error: {e.response.text}")
        raise HTTPException(status_code=e.response.status_code, detail=f"Service error: {e.response.text}")
    except requests.exceptions.RequestException as e:
        logger.error(f"Request Error: {str(e)}")
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="Service unavailable")

@app.post("/upload")
#async def upload_file(filename: str = Form(...), file: UploadFile = File(...)):
async def upload_file(
    storage_type: str = Form(...),
    filename: str = Form(...),
    file_id: str = Form(...),
    content_type: str = Form(...),
    file: UploadFile = File(...)
) -> Dict[str, str]:
    
    try:
        audio = await file.read()
        files = {'file': (filename, audio, content_type)}

        url_to_use = f'{pyannote_wrapper_uri}/upload_file'

        data = {
            "filename": filename,
            "file_id": file_id
        }
        
        result = call_external_service(
            url_to_use,
            files=files,
            data=data
        )
        
        logger.info(f"PyAnnote wrapper response: {result}")

        url_to_use = f"{mongo_gateway_uri}/register_add_file"
        data = {
            "filename": filename,
            "file_id": file_id,
            "storage_type": storage_type,
            "content_type": content_type
        }
        
        result = call_external_service(
            url_to_use,
            files=files,
            data=data
        )
        logger.info(f"Mongo gateway response: {result}")
        
        return {"status": "success", "message": "File successfully registered in PyAnnote and local."}
    except HTTPException as e:
        return JSONResponse(
            status_code=e.status_code,
            content={"message": "error", "details": str(e.detail)}
        )
    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}")
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"message": "error", "details": "Internal server error"}
        )


if __name__ == '__main__':
    host = os.getenv("API_HOST", "0.0.0.0")
    port = int(os.getenv("API_PORT", 5000))
    uvicorn.run(app, host=host, port=port)
