#!/bin/bash
# Deploy BuildTrace Frontend to Firebase Hosting or Cloud Run
# Usage: ./deploy-frontend.sh [firebase|cloudrun]

set -e

DEPLOYMENT_METHOD="${1:-firebase}"
PROJECT_ID="${GCP_PROJECT_ID:-buildtrace-dev}"
REGION="${GCP_REGION:-us-central1}"

echo "Deploying frontend using: $DEPLOYMENT_METHOD"

# Get API URL from Terraform output
cd infra/terraform
API_URL=$(terraform output -raw api_url 2>/dev/null || echo "")
cd ../..

if [ -z "$API_URL" ]; then
    echo "Warning: Could not get API URL from Terraform. Please set it manually:"
    read -p "Enter API URL: " API_URL
fi

echo "Using API URL: $API_URL"

cd ../Build-TraceFlow

# Build frontend with production API URL
echo "Building frontend..."
VITE_API_URL="${API_URL}/api" npm run build

if [ "$DEPLOYMENT_METHOD" = "firebase" ]; then
    # Deploy to Firebase Hosting
    echo "Deploying to Firebase Hosting..."
    
    if ! command -v firebase &> /dev/null; then
        echo "Installing Firebase CLI..."
        npm install -g firebase-tools
    fi
    
    # Initialize Firebase if not already done
    if [ ! -f ".firebaserc" ]; then
        echo "Initializing Firebase..."
        firebase init hosting --project "$PROJECT_ID" --public "dist/public" --yes
    fi
    
    firebase deploy --only hosting --project "$PROJECT_ID"
    
    echo "Frontend deployed to Firebase Hosting!"
    echo "URL: https://$PROJECT_ID.web.app"
    
elif [ "$DEPLOYMENT_METHOD" = "cloudrun" ]; then
    # Deploy to Cloud Run
    echo "Deploying to Cloud Run..."
    
    # Create nginx config for SPA
    cat > nginx.conf << 'EOF'
server {
    listen 80;
    server_name _;
    root /usr/share/nginx/html;
    index index.html;

    # SPA routing - serve index.html for all routes
    location / {
        try_files $uri $uri/ /index.html;
    }

    # Cache static assets
    location ~* \.(js|css|png|jpg|jpeg|gif|ico|svg|woff|woff2|ttf|eot)$ {
        expires 1y;
        add_header Cache-Control "public, immutable";
    }
}
EOF
    
    # Create Dockerfile
    cat > Dockerfile.frontend << 'EOF'
FROM nginx:alpine
COPY dist/public /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
EOF
    
    # Build and push image
    echo "Building Docker image..."
    docker build -f Dockerfile.frontend -t ${REGION}-docker.pkg.dev/${PROJECT_ID}/buildtrace/frontend:latest .
    
    echo "Pushing image..."
    gcloud auth configure-docker ${REGION}-docker.pkg.dev
    docker push ${REGION}-docker.pkg.dev/${PROJECT_ID}/buildtrace/frontend:latest
    
    # Deploy to Cloud Run
    echo "Deploying to Cloud Run..."
    gcloud run deploy buildtrace-frontend \
        --image ${REGION}-docker.pkg.dev/${PROJECT_ID}/buildtrace/frontend:latest \
        --region ${REGION} \
        --platform managed \
        --allow-unauthenticated \
        --port 80 \
        --memory 512Mi \
        --cpu 1
    
    FRONTEND_URL=$(gcloud run services describe buildtrace-frontend --region=${REGION} --format="value(status.url)")
    echo "Frontend deployed to Cloud Run!"
    echo "URL: $FRONTEND_URL"
    
    # Cleanup
    rm -f nginx.conf Dockerfile.frontend
else
    echo "Error: Unknown deployment method: $DEPLOYMENT_METHOD"
    echo "Use 'firebase' or 'cloudrun'"
    exit 1
fi

echo "Frontend deployment complete!"
