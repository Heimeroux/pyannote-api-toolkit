import os
import uvicorn
import sys
import pandas as pd
import numpy as np
import requests
import logging

from fastapi import FastAPI, Request, UploadFile, Form, File, status
from fastapi import HTTPException
from typing import Dict

api_host = os.getenv("API_HOST")
api_port = os.getenv("API_PORT")
token_pyannote = os.getenv("TOKEN_PYANNOTE")


app = FastAPI()
logger = logging.getLogger(__name__)


@app.post("/upload_file")
async def upload_file(
    filename: str = Form(...),
    file_id: str = Form(...),
    file: UploadFile = File(...)
) -> Dict[str, str]:
    try:
        data = await file.read()

        response = requests.post(
            "https://api.pyannote.ai/v1/media/input",
            json={"url": f"media://{file_id}"},
            headers={
                "Authorization": f"Bearer {token_pyannote}",
                "Content-Type": "application/json"
            }
        )
        response.raise_for_status()
        presigned_url = response.json()["url"]

        requests.put(presigned_url, data=data)

        logger.info(f"File {filename} successfully uploaded to PyAnnote.")
        return {"status": "success", "message": "File successfully sent to PyAnnote"}
    except requests.exceptions.HTTPError as e:
        logger.error(f"PyAnnote API error: {e.response.text}")
        raise HTTPException(status_code=e.response.status_code, detail=f"PyAnnote API error: {e.response.text}")
    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Internal server error")


# TO DO
@app.get("/diarize_file/{filename}")
def diarize_file(object_key: str, job_id: str, filename: str):
    """
    Étape 1 Diarization du fichier
    Étape 2 Ajout du job_id
    """
    # Étape 1
    try:
        response = requests.post(
            "https://api.pyannote.ai/v1/diarize",
            json={
                "url": f"media://{object_key}",
                "webhook": "http://0.0.0.0:5000/webhook",
                "confidence": True,
                "turnLevelConfidence": True
            },
            headers={
               "Authorization": f"Bearer {token_pyannote}",
               "Content-Type": "application/json"
            }
        )
        response.raise_for_status()
    except e:
        print("Error:", e)

    job_id = response.json()['jobId']

    # Étape 2
    #file_infos.update_job_id(job_id, filename)

# TO DO
@app.post("/webhook")
def process_results(request: Request):
    """
    Étape 1 Récupérer résultat
    Étape 2 Nettoyer le JSON et calculer le score moyen sur les turns
    Étape 3 Calculer le score moyen au sample level
    Étape 4 Ajouter les résultats dans la BD
    """

    # Étape 1
    data = request.json()  #"""==> à adapter car disponile que sous flask"""
    job_id = data["jobId"]
    
    # Étape 2
    df = pd.DataFrame(data["output"]["diarization"])
    result_diarization = df.drop(['confidence'], axis=1).to_dict(orient="records")
    turn_level_mean_score = np.mean([next(iter(d.values())) for d in df['confidence']])
    
    # Étape 3
    sample_level_mean_score = np.mean(data["output"]["confidence"]["score"])

    # Étape 4
    #file_infos.update_diarization_infos(sample_level_mean_score, turn_level_mean_score, diarization_result, job_id)

if __name__ == "__main__":
    host = os.getenv("API_HOST", "0.0.0.0")
    port = int(os.getenv("API_PORT", 5001))
    uvicorn.run(app, host=host, port=port)