#!/bin/bash
# ============================================================
# deploy.sh – Cloud Run Deployment
# Aufruf: ./deploy.sh
# Voraussetzung: gcloud auth login && gcloud config set project PROJECT_ID
# ============================================================

set -e

PROJECT_ID=$(gcloud config get-value project)
REGION="europe-west3"
SERVICE_NAME="telefon-agent"
IMAGE="gcr.io/${PROJECT_ID}/${SERVICE_NAME}:latest"

echo "▸ Baue Docker-Image: ${IMAGE}"
gcloud builds submit --tag "${IMAGE}" .

echo "▸ Deploye auf Cloud Run (Region: ${REGION})"
gcloud run deploy "${SERVICE_NAME}" \
  --image "${IMAGE}" \
  --region "${REGION}" \
  --platform managed \
  --allow-unauthenticated \
  --min-instances 1 \
  --max-instances 10 \
  --memory 2Gi \
  --cpu 2 \
  --timeout 30 \
  --set-env-vars "ENVIRONMENT=production,GCP_PROJECT_ID=${PROJECT_ID},GCP_LOCATION=${REGION}" \
  --set-secrets "TWILIO_AUTH_TOKEN=twilio-auth-token:latest,TWILIO_ACCOUNT_SID=twilio-account-sid:latest"

echo ""
echo "✅ Deployment abgeschlossen!"
echo "▸ Service URL:"
gcloud run services describe "${SERVICE_NAME}" \
  --region "${REGION}" \
  --format "value(status.url)"

echo ""
echo "▸ Nächster Schritt: Twilio Webhook setzen auf:"
echo "  https://<SERVICE_URL>/call/incoming"
