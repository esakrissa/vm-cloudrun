# Deploying to Cloud Run using Workload Identity Federation

This guide provides step-by-step instructions for deploying applications to Google Cloud Run using GitHub Actions with Workload Identity Federation and Artifact Registry.

## Prerequisites

- Google Cloud account with billing enabled
- GitHub repository
- Basic knowledge of Docker and containerization
- `gcloud` CLI installed and configured

## Step 1: Set up Google Cloud Project

1. Create or select a Google Cloud project:
   ```bash
   gcloud config set project YOUR_PROJECT_ID
   ```

2. Enable the required APIs:
   ```bash
   gcloud services enable \
     artifactregistry.googleapis.com \
     containerregistry.googleapis.com \
     run.googleapis.com \
     iam.googleapis.com \
     iamcredentials.googleapis.com
   ```

## Step 2: Create an Artifact Registry Repository

1. Create a Docker repository in Artifact Registry:
   ```bash
   gcloud artifacts repositories create YOUR_REPO_NAME \
     --repository-format=docker \
     --location=REGION \
     --description="Docker repository for your application"
   ```

   Replace:
   - `YOUR_REPO_NAME` with your desired repository name
   - `REGION` with your preferred region (e.g., `us-central1`)

## Step 3: Set up Workload Identity Federation

1. Create a Workload Identity Pool:
   ```bash
   gcloud iam workload-identity-pools create github-actions \
     --location=global \
     --display-name="GitHub Actions" \
     --description="Identity pool for GitHub Actions"
   ```

2. Create a Workload Identity Provider:
   ```bash
   gcloud iam workload-identity-pools providers create-oidc github \
     --workload-identity-pool=github-actions \
     --location=global \
     --display-name="GitHub Actions OIDC" \
     --issuer-uri="https://token.actions.githubusercontent.com" \
     --attribute-mapping="google.subject=assertion.sub,attribute.repository=assertion.repository" \
     --attribute-condition="assertion.repository=='GITHUB_USERNAME/REPO_NAME'"
   ```

   Replace `GITHUB_USERNAME/REPO_NAME` with your GitHub username and repository name.

3. Get the Workload Identity Provider resource name:
   ```bash
   gcloud iam workload-identity-pools providers describe github \
     --location=global \
     --workload-identity-pool=github-actions \
     --format="value(name)"
   ```

   Save this value for your GitHub Actions workflow.

## Step 4: Create and Configure a Service Account

1. Create a service account:
   ```bash
   gcloud iam service-accounts create github-actions-sa \
     --display-name="GitHub Actions Service Account"
   ```

2. Grant the necessary roles to the service account:
   ```bash
   # Cloud Run Admin role
   gcloud projects add-iam-policy-binding YOUR_PROJECT_ID \
     --member="serviceAccount:github-actions-sa@YOUR_PROJECT_ID.iam.gserviceaccount.com" \
     --role="roles/run.admin"

   # Artifact Registry Writer role
   gcloud projects add-iam-policy-binding YOUR_PROJECT_ID \
     --member="serviceAccount:github-actions-sa@YOUR_PROJECT_ID.iam.gserviceaccount.com" \
     --role="roles/artifactregistry.writer"

   # Service Account User role
   gcloud projects add-iam-policy-binding YOUR_PROJECT_ID \
     --member="serviceAccount:github-actions-sa@YOUR_PROJECT_ID.iam.gserviceaccount.com" \
     --role="roles/iam.serviceAccountUser"

   # Storage Admin role (for container storage)
   gcloud projects add-iam-policy-binding YOUR_PROJECT_ID \
     --member="serviceAccount:github-actions-sa@YOUR_PROJECT_ID.iam.gserviceaccount.com" \
     --role="roles/storage.admin"
   ```

   Replace `YOUR_PROJECT_ID` with your Google Cloud project ID.

3. Allow the GitHub Actions workflow to impersonate the service account:
   ```bash
   gcloud iam service-accounts add-iam-policy-binding github-actions-sa@YOUR_PROJECT_ID.iam.gserviceaccount.com \
     --member="principalSet://iam.googleapis.com/projects/PROJECT_NUMBER/locations/global/workloadIdentityPools/github-actions/attribute.repository/GITHUB_USERNAME/REPO_NAME" \
     --role="roles/iam.workloadIdentityUser"
   ```

   Replace:
   - `YOUR_PROJECT_ID` with your Google Cloud project ID
   - `PROJECT_NUMBER` with your Google Cloud project number
   - `GITHUB_USERNAME/REPO_NAME` with your GitHub username and repository name

4. Grant token creator permissions:
   ```bash
   gcloud iam service-accounts add-iam-policy-binding github-actions-sa@YOUR_PROJECT_ID.iam.gserviceaccount.com \
     --member="principalSet://iam.googleapis.com/projects/PROJECT_NUMBER/locations/global/workloadIdentityPools/github-actions/*" \
     --role="roles/iam.serviceAccountTokenCreator"
   ```

## Step 5: Create GitHub Actions Workflow

Create a `.github/workflows/deploy.yml` file in your repository:

```yaml
name: Deploy to Cloud Run

on:
  push:
    branches:
      - main
  workflow_dispatch:

env:
  PROJECT_ID: YOUR_PROJECT_ID
  REGION: YOUR_REGION
  SERVICE_NAME: YOUR_SERVICE_NAME
  REGISTRY: YOUR_REGION-docker.pkg.dev

permissions:
  contents: read
  id-token: write

jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - id: auth
        name: Authenticate with Google Cloud
        uses: google-github-actions/auth@v2
        with:
          workload_identity_provider: WORKLOAD_IDENTITY_PROVIDER_ID
          service_account: github-actions-sa@YOUR_PROJECT_ID.iam.gserviceaccount.com
          create_credentials_file: true

      - name: Set up Cloud SDK
        uses: google-github-actions/setup-gcloud@v2
        with:
          project_id: ${{ env.PROJECT_ID }}
          install_components: "beta,docker-credential-gcr"

      - name: Configure Docker authentication
        run: |-
          gcloud auth configure-docker ${{ env.REGISTRY }} --quiet

      - name: Build and Push Container
        run: |-
          docker build -t ${{ env.REGISTRY }}/${{ env.PROJECT_ID }}/${{ env.SERVICE_NAME }}/${{ env.SERVICE_NAME }}:${{ github.sha }} .
          docker push ${{ env.REGISTRY }}/${{ env.PROJECT_ID }}/${{ env.SERVICE_NAME }}/${{ env.SERVICE_NAME }}:${{ github.sha }}

      - name: Deploy to Cloud Run
        run: |-
          gcloud run deploy ${{ env.SERVICE_NAME }} \
            --image ${{ env.REGISTRY }}/${{ env.PROJECT_ID }}/${{ env.SERVICE_NAME }}/${{ env.SERVICE_NAME }}:${{ github.sha }} \
            --region ${{ env.REGION }} \
            --platform managed \
            --allow-unauthenticated
```

Replace:
- `YOUR_PROJECT_ID` with your Google Cloud project ID
- `YOUR_REGION` with your preferred region (e.g., `us-central1`)
- `YOUR_SERVICE_NAME` with your desired service name
- `WORKLOAD_IDENTITY_PROVIDER_ID` with the provider resource name from Step 3.3

## Step 6: Prepare Your Application

1. Create a `Dockerfile` for your application:
   ```dockerfile
   FROM python:3.11-slim

   WORKDIR /app

   COPY requirements.txt .
   RUN pip install --no-cache-dir -r requirements.txt

   COPY . .

   EXPOSE 8080

   CMD ["gunicorn", "main:app", "--workers", "2", "--worker-class", "uvicorn.workers.UvicornWorker", "--bind", "0.0.0.0:8080"]
   ```

2. Ensure your application listens on port 8080 (Cloud Run default)

3. Commit and push your code to GitHub:
   ```bash
   git add .
   git commit -m "Set up Cloud Run deployment"
   git push
   ```

## Step 7: Monitor Deployment

1. Go to your GitHub repository
2. Click on the "Actions" tab
3. Monitor the workflow execution
4. Once completed, find your Cloud Run service URL in the GitHub Actions logs or in the Google Cloud Console

## Troubleshooting

If you encounter authentication issues:

1. Verify the Workload Identity Pool and Provider are correctly configured
2. Check that the service account has the necessary permissions
3. Ensure the attribute condition in the provider matches your GitHub repository exactly
4. Verify that the service account has token creator permissions

## Additional Resources

- [Workload Identity Federation documentation](https://cloud.google.com/iam/docs/workload-identity-federation)
- [Cloud Run documentation](https://cloud.google.com/run/docs)
- [Artifact Registry documentation](https://cloud.google.com/artifact-registry/docs)
- [GitHub Actions for Google Cloud](https://github.com/google-github-actions) 