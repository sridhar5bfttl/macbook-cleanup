# macbook-cleanup

A lightweight Flask web app that scans your macOS Trash folder and returns a list of files with their sizes. It can run locally for personal use or be deployed to Google Cloud Run for remote access.

---

## 📋 Project Overview

- **Language**: Python 3.12
- **Framework**: Flask
- **Key Features**:
  - Scan macOS Trash and report file details.
  - Optional `CLOUD_MODE` environment variable to disable local‑only AppleScript calls when running in the cloud.
  - Dockerized for easy deployment.

---

## 🛠 Prerequisites

- Python 3.12+ (if running locally)
- `uv` or `pip` for dependency installation
- Docker Desktop (or Docker Engine) for container builds
- Google Cloud SDK (`gcloud`) logged in to your GCP project
- A GCP project with **Artifact Registry** and **Cloud Run** enabled

---

## ⚙️ Local Development

```bash
# Clone the repo (if you haven't already)
git clone https://github.com/sridhar5bfttl/macbook-cleanup.git
cd macbook-cleanup

# Create a virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Install dependencies
uv pip install -r requirements.txt   # or: pip install -r requirements.txt

# Run the app
export CLOUD_MODE=0   # optional – default is local mode
python app.py
```

Visit `http://127.0.0.1:5000/` in your browser and use the endpoint:
`GET /api/category-files/trash` to see the JSON list of files in your Trash.

---

## 📦 Docker Build & Run

```bash
# Build the image (replace <PROJECT_ID> with your GCP project ID)
export PROJECT_ID=$(gcloud config get-value project)
docker build -t $PROJECT_ID/macbook-cleanup:latest .

# Test locally
docker run -e CLOUD_MODE=0 -p 8080:8080 $PROJECT_ID/macbook-cleanup:latest
# Open http://localhost:8080/ in the browser

# To run on a different port: 
CLOUD_MODE=0 flask --app app run --host 0.0.0.0 --port 5005
# Open http://localhost:5005/ in the browser
```

The Dockerfile is set up to use `gunicorn` and respects the `$PORT` environment variable that Cloud Run provides.

---

## 🚀 Deploy to Google Cloud Run

```bash
# Authenticate Docker to push to Artifact Registry
gcloud auth configure-docker us-central1-docker.pkg.dev

# Tag and push the image to Artifact Registry
docker tag $PROJECT_ID/macbook-cleanup:latest us-central1-docker.pkg.dev/$PROJECT_ID/macbook-cleanup-repo/macbook-cleanup:latest
docker push us-central1-docker.pkg.dev/$PROJECT_ID/macbook-cleanup-repo/macbook-cleanup:latest

# Deploy the container to Cloud Run
gcloud run deploy macbook-cleanup \
  --image us-central1-docker.pkg.dev/$PROJECT_ID/macbook-cleanup-repo/macbook-cleanup:latest \
  --platform managed \
  --region us-central1 \
  --allow-unauthenticated \
  --set-env-vars CLOUD_MODE=1
```

After deployment, Cloud Run will give you a URL (e.g., `https://macbook-cleanup-xxxxx-uc.a.run.app`). Use the same `/api/category-files/trash` endpoint to query the service.

---

## 🔄 Updating Code & Redeploying

1. Make changes locally (e.g., add new endpoints or tweak the UI).
2. Test the changes:
   ```bash
   python app.py   # or run the Docker container locally
   ```
3. Re‑build and push the image:
   ```bash
   docker build -t $PROJECT_ID/macbook-cleanup:latest .
   docker push us-central1-docker.pkg.dev/$PROJECT_ID/macbook-cleanup-repo/macbook-cleanup:latest
   ```
4. Deploy the new image:
   ```bash
   gcloud run deploy macbook-cleanup \
     --image us-central1-docker.pkg.dev/$PROJECT_ID/macbook-cleanup-repo/macbook-cleanup:latest \
     --platform managed --region us-central1 --allow-unauthenticated
   ```

Cloud Run will spin up the new revision instantly; the old revision remains available for rollback.

---

## 🔐 Secrets & .env

- The `.env` file is **git‑ignored** (see `.gitignore`).
- Store any API keys or secrets in Cloud Run’s **environment variables** or use **Secret Manager** and reference them with `--set-secrets` during deployment.

---

## 📜 License

This project is licensed under the MIT License – see the LICENSE file for details.

---

*Happy cleaning!*
