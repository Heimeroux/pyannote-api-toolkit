import requests
import os
import uvicorn
import sys
import logging

from fastapi import FastAPI, UploadFile, Form, File, HTTPException, status, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from typing import Optional, Dict, Union

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
    method: str,  # Méthode HTTP par défaut : GET
    files: Optional[dict] = None,
    data: Optional[dict] = None,
    params: Optional[dict] = None,
    json: Optional[dict] = None,
    headers: Optional[dict] = None
) -> Union[dict, str]:
    """
    Appelle un service externe avec la méthode HTTP spécifiée.

    Args:
        url: URL du service externe.
        method: Méthode HTTP ("GET", "POST", "PUT", etc.).
        files: Fichiers à envoyer (pour multipart/form-data).
        data: Données de formulaire (pour application/x-www-form-urlencoded).
        params: Paramètres de requête (pour GET ou query string).
        json: Données JSON à envoyer dans le corps.
        headers: En-têtes personnalisés.

    Returns:
        Réponse JSON ou texte du service externe.

    Raises:
        HTTPException: En cas d'erreur HTTP ou de requête.
    """
    try:
        if method.upper() == "GET":
            response = requests.get(url, params=params, headers=headers)
        elif method.upper() == "POST":
            response = requests.post(url, files=files, data=data, json=json, headers=headers)
        else:
            raise ValueError(f"Méthode HTTP non supportée : {method}")

        response.raise_for_status()  # Lève une exception pour les codes d'erreur HTTP
        return response.json() if response.content else {"status": "success"}    
    except requests.exceptions.HTTPError as e:
        logger.error(f"HTTP Error: {e.response.text}")
        raise HTTPException(status_code=e.response.status_code, detail=f"Service error: {e.response.text}")
    
    except requests.exceptions.RequestException as e:
        logger.error(f"Request Error: {str(e)}")
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=f"Erreur de requête : {str(e)}")

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
            method="POST",
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
            method="POST",
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

@app.post("/diarise")
async def diarise(request: Request) -> Dict[str, str]:
    
    try:
        data = await request.json()
        filename = data.get("filename")
    
        # Get file_id from mongo db
        # POST ?
        url_to_use = f"{mongo_gateway_uri}/get_file_id"
        data = {
            "filename": filename
        }
        result = call_external_service(url_to_use, method="GET", params=data)
        logger.info(f"Mongo gateway response: {result}")
        file_id = result["file_id"]
    
        # Send file_id for diarisation
        url_to_use = f"{pyannote_wrapper_uri}/diarise"
        data = {
            "file_id": file_id 
        }
        result = call_external_service(url_to_use, method="POST", json=data)
        logger.info(f"PyAnnote wrapper response: {result}")
        job_id = result["job_id"]
    
        # Update file whose filename job_id
        url_to_use = f"{mongo_gateway_uri}/update_job_id"
        data = {
            "filename": filename,
            "job_id": job_id
        }
        result = call_external_service(url_to_use, method="POST", json=data)
        logger.info(f"Mongo gateway response: {result}")
        
        return {"status": "success", "message": "File successfully sent for diarisation on PyAnnote API. MongoDB successfully updated."}
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
