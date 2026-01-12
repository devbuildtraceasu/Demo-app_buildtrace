#!/bin/bash
# Setup secrets in Google Cloud Secret Manager
# Usage: ./setup-secrets.sh

set -e

PROJECT_ID="${GCP_PROJECT_ID:-buildtrace-dev}"

echo "Setting up secrets for BuildTrace in project: $PROJECT_ID"

# Check if secrets already exist and prompt for update
create_or_update_secret() {
    local secret_name=$1
    local description=$2
    local prompt_text=$3
    
    if gcloud secrets describe "$secret_name" --project="$PROJECT_ID" &> /dev/null; then
        echo "Secret $secret_name already exists. Update? (y/n)"
        read -r response
        if [[ "$response" =~ ^[Yy]$ ]]; then
            echo "$prompt_text"
            read -s secret_value
            echo -n "$secret_value" | gcloud secrets versions add "$secret_name" --data-file=- --project="$PROJECT_ID"
            echo "Secret $secret_name updated."
        else
            echo "Skipping $secret_name"
        fi
    else
        echo "$prompt_text"
        read -s secret_value
        echo -n "$secret_value" | gcloud secrets create "$secret_name" --data-file=- --replication-policy="automatic" --project="$PROJECT_ID"
        echo "Secret $secret_name created."
    fi
}

# OpenAI API Key
create_or_update_secret "openai-api-key" "OpenAI API Key" "Enter your OpenAI API key:"

# Gemini API Key (optional)
echo "Enter Gemini API key (optional, press Enter to skip):"
read -s gemini_key
if [ -n "$gemini_key" ]; then
    echo -n "$gemini_key" | gcloud secrets create gemini-api-key --data-file=- --replication-policy="automatic" --project="$PROJECT_ID" 2>/dev/null || \
    echo -n "$gemini_key" | gcloud secrets versions add gemini-api-key --data-file=- --project="$PROJECT_ID"
    echo "Gemini API key stored."
fi

# JWT Secret
create_or_update_secret "jwt-secret" "JWT Secret" "Enter a secure JWT secret (min 32 characters):"

# Google OAuth Client ID
create_or_update_secret "google-client-id" "Google OAuth Client ID" "Enter Google OAuth Client ID:"

# Google OAuth Client Secret
create_or_update_secret "google-client-secret" "Google OAuth Client Secret" "Enter Google OAuth Client Secret:"

echo ""
echo "Granting service accounts access to secrets..."

# Get service account emails
API_SA="buildtrace-api@${PROJECT_ID}.iam.gserviceaccount.com"
WORKER_SA="buildtrace-worker@${PROJECT_ID}.iam.gserviceaccount.com"

# Grant access to API service account
for secret in openai-api-key gemini-api-key jwt-secret google-client-id google-client-secret; do
    if gcloud secrets describe "$secret" --project="$PROJECT_ID" &> /dev/null; then
        gcloud secrets add-iam-policy-binding "$secret" \
            --member="serviceAccount:${API_SA}" \
            --role="roles/secretmanager.secretAccessor" \
            --project="$PROJECT_ID" 2>/dev/null || echo "Already has access: $secret"
    fi
done

# Grant access to Worker service account
for secret in openai-api-key gemini-api-key; do
    if gcloud secrets describe "$secret" --project="$PROJECT_ID" &> /dev/null; then
        gcloud secrets add-iam-policy-binding "$secret" \
            --member="serviceAccount:${WORKER_SA}" \
            --role="roles/secretmanager.secretAccessor" \
            --project="$PROJECT_ID" 2>/dev/null || echo "Already has access: $secret"
    fi
done

echo ""
echo "Secrets setup complete!"
