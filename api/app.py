import os
import uvicorn
import sys

from pymongo import MongoClient
from fastapi import FastAPI

mongo_uri = os.getenv("MONGO_URI")
api_host = os.getenv("API_HOST")
api_port = os.getenv("API_PORT")
token_pyannote = os.getenv("TOKEN_PYANNOTE")
mongo_database = os.getenv("MONGO_DATABASE")

app = FastAPI()

@app.get("/variables")
def get_varibales():
    print('Type puis value de mongo uri')
    print(type(mongo_uri))
    print(mongo_uri)
    print('Type puis value de api host')
    print(type(api_host))
    print(api_host)
    print('Type puis value de api port')
    print(type(api_port))
    print(api_port)
    print('Type puis value de token pyannote')
    print(type(token_pyannote))
    print(token_pyannote)
    print('Type puis value de mongo database')
    print(type(mongo_database))
    print(mongo_database)

if __name__ == "__main__":
    host1 = os.getenv("API_HOST", "0.0.0.0")
    port1 = int(os.getenv("API_PORT", 5000))
    uvicorn.run(app, host=host1, port=port1)
    print("🚀 FastAPI prêt sur http://localhost:5000")