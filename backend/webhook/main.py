import uvicorn
import os
import sys
import logging
import hmac
import hashlib
import requests
import pandas as pd
import numpy as np

from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse
from typing import Dict, Any

key = os.getenv("PYANNOTEAI_WEBHOOK_SIGNING_SECRET")
api_server_host = os.getenv("API_SERVER_HOST")
api_server_port = os.getenv("API_SERVER_PORT")

api_server_uri = f"http://{api_server_host}:{api_server_port}"

app = FastAPI()
logger = logging.getLogger(__name__)

logger = logging.getLogger(__name__)

logger.setLevel(logging.DEBUG)
    
# create custom handler for INFO msg
stdout_handler = logging.StreamHandler(sys.stdout)
stdout_handler.setLevel(logging.DEBUG)
    
logger.addHandler(stdout_handler)

@app.post("/read")
async def read():
    return {"status": "ok"}

@app.post("/webhook")
async def validate_signature(request: Request):
    body = await request.body()
    headers = request.headers
    timestamp = headers.get("x-request-timestamp")
    received_signature = headers.get("x-signature")

    if not timestamp or not received_signature:
        logger.error(f"Missing headers in webhook endpoint")
        raise HTTPException(status_code=400, detail="Missing headers")

    signed_content = f"v0:{timestamp}:{body.decode('utf-8')}"
    calculated_signature = hmac.new(
        key=key.encode("utf-8"),
        msg=signed_content.encode("utf-8"),
        digestmod=hashlib.sha256,
    ).hexdigest()

    if not hmac.compare_digest(calculated_signature, received_signature):
        logger.error(f"Invalid signature in webhook endpoint")
        raise HTTPException(status_code=403, detail="Invalid signature")

    # Do something with the payload, now that we know it's valid
    logger.info(f"Successful validation, body: {body}")
    
    try:
        data = await request.json()
        result = process_result(data)
        #result.raise_for_status()
        logger.info(f"{result['message']}")
        return JSONResponse(
            status_code=200,
            content={'status': 'received'}
        )
    except Exception as e:
        logger.error(f"Unexpect error: {str(e)}")
        raise HTTPException(status_code=500, detail={str(e)})
    

def process_result(body: Dict[str, Any]) -> Dict[str, str]:
    try:
        job_id = body["jobId"]
        
        df = pd.DataFrame(body["output"]["diarization"])
        diarization = df.drop(['confidence'], axis=1).to_dict(orient="records")
        turn_level_mean_score = np.mean([next(iter(d.values())) for d in df['confidence']])
    
        sample_level_mean_score = np.mean(body["output"]["confidence"]["score"])

        logger.info(f"Type jobid: {type(job_id)}, jobid: {job_id}")
        logger.info(f"Type diarization: {type(diarization)}, jobid: {diarization}")
        logger.info(f"Type turn_level_mean_score: {type(turn_level_mean_score)}, jobid: {turn_level_mean_score}")
        logger.info(f"Type sample_level_mean_score: {type(sample_level_mean_score)}, jobid: {sample_level_mean_score}")
        
        data = {
            "job_id": job_id,
            "diarization": diarization,
            "turn_level_mean_score": turn_level_mean_score,
            "sample_level_mean_score": sample_level_mean_score
        }

        url_to_use = f"{api_server_uri}/update_diarization_result"
        
        response = requests.post(url_to_use, json=data)
        response.raise_for_status()
        logger.info(f"Diarization result successfully updated: {response}")
        return {"status": "success", "message": "Success to diarize"}
    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}")
        raise HTTPException(status_code=500, detail={str(e)})
    # Faire request post sur api server avec
    # - sample level mean score
    # - turn level mean score
    # - diarization result
    # - job id --> nécessaire pour enregistrer le résultat à la bonne donnée

if __name__ == "__main__":
    host = os.getenv("API_HOST", "0.0.0.0")
    port = int(os.getenv("API_PORT", 5003))
    uvicorn.run(app, host=host, port=port)