# FastAPI Cloud Run Demo with Workload Identity Federation

This repository contains a simple FastAPI application that is deployed to Google Cloud Run using GitHub Actions and Workload Identity Federation.

## Project URL

It's live: https://fastapi-demo-957176400089.us-central1.run.app

FastAPI swagger UI: https://fastapi-demo-957176400089.us-central1.run.app/docs

## Setup Instructions


### 1. Create a Google Cloud Project
If you haven't already, create a new Google Cloud Project and enable the necessary APIs:
```bash
# Enable required APIs
gcloud services enable \
  artifactregistry.googleapis.com \
  containerregistry.googleapis.com \
  run.googleapis.com \
  iam.googleapis.com \
  iamcredentials.googleapis.com
```

### 2. Set up Workload Identity Federation

1. Create a Workload Identity Pool:
```bash
gcloud iam workload-identity-pools create "github-pool" \
  --project="${PROJECT_ID}" \
  --location="global" \
  --display-name="GitHub Actions Pool"
```

2. Create a Workload Identity Provider:
```bash
gcloud iam workload-identity-pools providers create-oidc "github-provider" \
  --project="${PROJECT_ID}" \
  --location="global" \
  --workload-identity-pool="github-pool" \
  --display-name="GitHub Actions Provider" \
  --attribute-mapping="google.subject=assertion.sub,attribute.actor=assertion.actor,attribute.repository=assertion.repository" \
  --issuer-uri="https://token.actions.githubusercontent.com"
```

3. Create a Service Account:
```bash
gcloud iam service-accounts create "github-actions-sa" \
  --project="${PROJECT_ID}" \
  --display-name="GitHub Actions Service Account"
```

4. Grant the necessary roles to the service account:
```bash
gcloud projects add-iam-policy-binding "${PROJECT_ID}" \
  --member="serviceAccount:github-actions-sa@${PROJECT_ID}.iam.gserviceaccount.com" \
  --role="roles/run.admin"

gcloud projects add-iam-policy-binding "${PROJECT_ID}" \
  --member="serviceAccount:github-actions-sa@${PROJECT_ID}.iam.gserviceaccount.com" \
  --role="roles/storage.admin"

gcloud projects add-iam-policy-binding "${PROJECT_ID}" \
  --member="serviceAccount:github-actions-sa@${PROJECT_ID}.iam.gserviceaccount.com" \
  --role="roles/iam.serviceAccountUser"
```

5. Allow the GitHub Actions workflow to impersonate the service account:
```bash
gcloud iam service-accounts add-iam-policy-binding "github-actions-sa@${PROJECT_ID}.iam.gserviceaccount.com" \
  --project="${PROJECT_ID}" \
  --role="roles/iam.workloadIdentityUser" \
  --member="principalSet://iam.googleapis.com/projects/${PROJECT_NUMBER}/locations/global/workloadIdentityPools/github-pool/attribute.repository/${GITHUB_REPO}"
```

### 3. Update GitHub Actions Workflow

Update the following values in `.github/workflows/deploy.yml`:

- `PROJECT_ID`: Your Google Cloud Project ID
- `WORKLOAD_IDENTITY_PROVIDER`: The full identifier of your Workload Identity Provider (format: `projects/PROJECT_NUMBER/locations/global/workloadIdentityPools/github-pool/providers/github-provider`)
- `SERVICE_ACCOUNT_EMAIL`: Your service account email (format: `github-actions-sa@PROJECT_ID.iam.gserviceaccount.com`)

## Local Development

1. Install dependencies:
```bash
pip install -r requirements.txt
```

2. Run the application:
```bash
uvicorn main:app --reload
```

The application will be available at `http://localhost:8000`

## API Endpoints

- `GET /`: Returns a "Hello World" message
- `GET /health`: Returns the health status of the application 
