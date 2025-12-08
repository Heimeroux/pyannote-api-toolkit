# PyAnnote-Api-Toolkit

## Goal
The **PyAnnote-Api-Toolkit** application is designed to help users identify audio recordings or segments where the **pyannote** diarization system struggles to achieve high confidence. The application allows users to upload an audio recording, which is then diarized. Users can visualize the diarization results through a diagram, listen to the audio, and provide an overall appreciation score. The tool also enables analysis through configurable thresholds, including:

- **Mean score** across all samples (combined with human scores).
- **Turn-level confidence score thresholds**.
- **Sample-level confidence score thresholds**.

## Author
This project is developed by **Alex CHOUX**, who holds a **Master's Degree in Computer Science**, with a specialization in **Data Science and AI for NLP**.

---

## Application Structure
The application consists of **6 distinct services**, orchestrated using **Docker Compose**:
   Service               | Description                                                                 |
 |------------------------|-----------------------------------------------------------------------------|
 | **HTML Page**          | Dockerized using **Nginx**, serving as the client interface.               |
 | **Python Server**      | Manages requests between the HTML page and other services.                 |
 | **Webhook + Ngrok**    | Handles diarization jobs and sends results to the server.                  |
 | **PyAnnote Wrapper**   | Interface with the **PyAnnote API**.                                        |
 | **Mongo Gateway**      | Interface for interacting with the **MongoDB** database.                    |
 | **MongoDB**            | Database for storing application data.                                      |

**Note:** Only the **webhook** is exposed to the internet via **Ngrok**. The **HTML page** is the only other service with a publicly accessible port for user interaction.

---

## Prerequisites
To run the application, you need:
- **Docker Compose** (to build and launch the services).
- A `.env` file containing the required environment variables.

### `.env` File Structure
```ini
NGROK_SUBDOMAIN=your_ngrok_subdomain
NGROK_AUTH_TOKEN=your_ngrok_auth_token
TOKEN_PYANNOTE=your_pyannote_api_token
PYANNOTEAI_WEBHOOK_SIGNING_SECRET=your_pyannote_webhook_signing_secret
```

---

## Forwards
Right now, the application is not designed to use speaker identification. It would be the further step in the development of the application. Moreover, some minor considerations must be addressed, such as:
- The expiration management of the uploaded audio files.
- The `job_id` expiration.
- Allowing the user to use recordings stored on a web storage like **S3**.
