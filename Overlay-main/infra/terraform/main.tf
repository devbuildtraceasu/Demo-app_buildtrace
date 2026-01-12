# BuildTrace GCP Infrastructure
# Terraform configuration for Cloud Run, Cloud SQL, Cloud Storage, and Pub/Sub

terraform {
  required_version = ">= 1.5.0"

  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 5.0"
    }
    google-beta = {
      source  = "hashicorp/google-beta"
      version = "~> 5.0"
    }
  }

  backend "gcs" {
    bucket = "buildtrace-terraform-state"
    prefix = "terraform/state"
  }
}

provider "google" {
  project = var.project_id
  region  = var.region
}

provider "google-beta" {
  project = var.project_id
  region  = var.region
}

# Enable required APIs
resource "google_project_service" "apis" {
  for_each = toset([
    "run.googleapis.com",
    "sqladmin.googleapis.com",
    "storage.googleapis.com",
    "pubsub.googleapis.com",
    "artifactregistry.googleapis.com",
    "secretmanager.googleapis.com",
    "compute.googleapis.com",
    "servicenetworking.googleapis.com",
    "cloudresourcemanager.googleapis.com",
  ])

  service            = each.key
  disable_on_destroy = false
}

# VPC for private services
resource "google_compute_network" "main" {
  name                    = "buildtrace-vpc"
  auto_create_subnetworks = false

  depends_on = [google_project_service.apis]
}

resource "google_compute_subnetwork" "main" {
  name          = "buildtrace-subnet"
  ip_cidr_range = "10.0.0.0/24"
  region        = var.region
  network       = google_compute_network.main.id
}

# Cloud SQL PostgreSQL Instance
resource "google_sql_database_instance" "main" {
  name             = "buildtrace-db"
  database_version = "POSTGRES_15"
  region           = var.region

  deletion_protection = var.environment == "production"

  settings {
    tier      = var.db_tier
    disk_size = var.db_disk_size
    disk_type = "PD_SSD"

    ip_configuration {
      ipv4_enabled    = false
      private_network = google_compute_network.main.id
    }

    backup_configuration {
      enabled                        = true
      start_time                     = "02:00"
      point_in_time_recovery_enabled = true
      transaction_log_retention_days = 7

      backup_retention_settings {
        retained_backups = 7
      }
    }

    database_flags {
      name  = "max_connections"
      value = "100"
    }

    insights_config {
      query_insights_enabled  = true
      query_plans_per_minute  = 5
      query_string_length     = 1024
      record_application_tags = true
      record_client_address   = true
    }
  }

  depends_on = [google_project_service.apis]
}

resource "google_sql_database" "main" {
  name     = "buildtrace"
  instance = google_sql_database_instance.main.name
}

resource "google_sql_user" "main" {
  name     = "buildtrace"
  instance = google_sql_database_instance.main.name
  password = random_password.db_password.result
}

resource "random_password" "db_password" {
  length  = 32
  special = false
}

# Store database password in Secret Manager
resource "google_secret_manager_secret" "db_password" {
  secret_id = "buildtrace-db-password"

  replication {
    auto {}
  }

  depends_on = [google_project_service.apis]
}

resource "google_secret_manager_secret_version" "db_password" {
  secret      = google_secret_manager_secret.db_password.id
  secret_data = random_password.db_password.result
}

# Cloud Storage Buckets
resource "google_storage_bucket" "uploads" {
  name          = "${var.project_id}-uploads"
  location      = var.region
  storage_class = "STANDARD"

  uniform_bucket_level_access = true

  versioning {
    enabled = true
  }

  lifecycle_rule {
    condition {
      age = 90
    }
    action {
      type          = "SetStorageClass"
      storage_class = "NEARLINE"
    }
  }

  cors {
    origin          = var.cors_origins
    method          = ["GET", "PUT", "POST"]
    response_header = ["Content-Type", "Content-Length"]
    max_age_seconds = 3600
  }

  depends_on = [google_project_service.apis]
}

resource "google_storage_bucket" "overlays" {
  name          = "${var.project_id}-overlays"
  location      = var.region
  storage_class = "STANDARD"

  uniform_bucket_level_access = true

  lifecycle_rule {
    condition {
      age = 180
    }
    action {
      type          = "SetStorageClass"
      storage_class = "COLDLINE"
    }
  }

  depends_on = [google_project_service.apis]
}

# Pub/Sub Topics and Subscriptions
resource "google_pubsub_topic" "vision" {
  name = "vision"

  message_retention_duration = "86400s" # 1 day

  depends_on = [google_project_service.apis]
}

resource "google_pubsub_subscription" "vision_worker" {
  name  = "vision-worker-subscription"
  topic = google_pubsub_topic.vision.name

  ack_deadline_seconds = 600 # 10 minutes for long-running jobs

  retry_policy {
    minimum_backoff = "10s"
    maximum_backoff = "600s"
  }

  dead_letter_policy {
    dead_letter_topic     = google_pubsub_topic.vision_dlq.id
    max_delivery_attempts = 5
  }
}

resource "google_pubsub_topic" "vision_dlq" {
  name = "vision-dlq"

  depends_on = [google_project_service.apis]
}

# Artifact Registry for Docker images
resource "google_artifact_registry_repository" "main" {
  location      = var.region
  repository_id = "buildtrace"
  format        = "DOCKER"
  description   = "Docker images for BuildTrace services"

  depends_on = [google_project_service.apis]
}

# Service Account for Cloud Run services
resource "google_service_account" "api" {
  account_id   = "buildtrace-api"
  display_name = "BuildTrace API Service Account"
}

resource "google_service_account" "worker" {
  account_id   = "buildtrace-worker"
  display_name = "BuildTrace Worker Service Account"
}

# IAM bindings
resource "google_project_iam_member" "api_storage" {
  project = var.project_id
  role    = "roles/storage.objectAdmin"
  member  = "serviceAccount:${google_service_account.api.email}"
}

resource "google_project_iam_member" "api_sql" {
  project = var.project_id
  role    = "roles/cloudsql.client"
  member  = "serviceAccount:${google_service_account.api.email}"
}

resource "google_project_iam_member" "api_pubsub" {
  project = var.project_id
  role    = "roles/pubsub.publisher"
  member  = "serviceAccount:${google_service_account.api.email}"
}

resource "google_project_iam_member" "worker_storage" {
  project = var.project_id
  role    = "roles/storage.objectAdmin"
  member  = "serviceAccount:${google_service_account.worker.email}"
}

resource "google_project_iam_member" "worker_sql" {
  project = var.project_id
  role    = "roles/cloudsql.client"
  member  = "serviceAccount:${google_service_account.worker.email}"
}

resource "google_project_iam_member" "worker_pubsub" {
  project = var.project_id
  role    = "roles/pubsub.subscriber"
  member  = "serviceAccount:${google_service_account.worker.email}"
}

resource "google_secret_manager_secret_iam_member" "api_db_password" {
  secret_id = google_secret_manager_secret.db_password.id
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:${google_service_account.api.email}"
}

resource "google_secret_manager_secret_iam_member" "worker_db_password" {
  secret_id = google_secret_manager_secret.db_password.id
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:${google_service_account.worker.email}"
}

# Cloud Run - API Service
resource "google_cloud_run_v2_service" "api" {
  name     = "buildtrace-api"
  location = var.region
  ingress  = "INGRESS_TRAFFIC_ALL"

  template {
    service_account = google_service_account.api.email

    containers {
      image = "${var.region}-docker.pkg.dev/${var.project_id}/buildtrace/api:${var.api_image_tag}"

      resources {
        limits = {
          cpu    = "2"
          memory = "2Gi"
        }
      }

      env {
        name  = "DATABASE_URL"
        value = "postgresql://buildtrace:${random_password.db_password.result}@/buildtrace?host=/cloudsql/${google_sql_database_instance.main.connection_name}"
      }

      env {
        name  = "STORAGE_BACKEND"
        value = "gcs"
      }

      env {
        name  = "STORAGE_BUCKET"
        value = google_storage_bucket.uploads.name
      }

      env {
        name  = "PUBSUB_PROJECT_ID"
        value = var.project_id
      }

      env {
        name  = "VISION_TOPIC"
        value = google_pubsub_topic.vision.name
      }

      volume_mounts {
        name       = "cloudsql"
        mount_path = "/cloudsql"
      }
    }

    volumes {
      name = "cloudsql"
      cloud_sql_instance {
        instances = [google_sql_database_instance.main.connection_name]
      }
    }

    scaling {
      min_instance_count = 0
      max_instance_count = 10
    }
  }

  traffic {
    type    = "TRAFFIC_TARGET_ALLOCATION_TYPE_LATEST"
    percent = 100
  }

  depends_on = [
    google_project_service.apis,
    google_sql_database_instance.main,
  ]
}

# Cloud Run - Overlay Worker
resource "google_cloud_run_v2_service" "overlay_worker" {
  name     = "buildtrace-overlay-worker"
  location = var.region
  ingress  = "INGRESS_TRAFFIC_INTERNAL_ONLY"

  template {
    service_account = google_service_account.worker.email

    containers {
      image = "${var.region}-docker.pkg.dev/${var.project_id}/buildtrace/overlay-worker:${var.worker_image_tag}"

      resources {
        limits = {
          cpu    = "8"
          memory = "16Gi"
        }
      }

      env {
        name  = "DATABASE_URL"
        value = "postgresql://buildtrace:${random_password.db_password.result}@/buildtrace?host=/cloudsql/${google_sql_database_instance.main.connection_name}"
      }

      env {
        name  = "STORAGE_BACKEND"
        value = "gcs"
      }

      env {
        name  = "STORAGE_BUCKET"
        value = google_storage_bucket.overlays.name
      }

      env {
        name  = "PUBSUB_PROJECT_ID"
        value = var.project_id
      }

      env {
        name  = "VISION_SUBSCRIPTION"
        value = google_pubsub_subscription.vision_worker.name
      }

      volume_mounts {
        name       = "cloudsql"
        mount_path = "/cloudsql"
      }
    }

    volumes {
      name = "cloudsql"
      cloud_sql_instance {
        instances = [google_sql_database_instance.main.connection_name]
      }
    }

    scaling {
      min_instance_count = 0
      max_instance_count = 5
    }

    timeout = "900s" # 15 minutes for long-running jobs
  }

  traffic {
    type    = "TRAFFIC_TARGET_ALLOCATION_TYPE_LATEST"
    percent = 100
  }

  depends_on = [
    google_project_service.apis,
    google_sql_database_instance.main,
  ]
}

# Allow unauthenticated access to API
resource "google_cloud_run_v2_service_iam_member" "api_public" {
  name     = google_cloud_run_v2_service.api.name
  location = var.region
  role     = "roles/run.invoker"
  member   = "allUsers"
}

# Outputs
output "api_url" {
  value       = google_cloud_run_v2_service.api.uri
  description = "BuildTrace API URL"
}

output "db_connection_name" {
  value       = google_sql_database_instance.main.connection_name
  description = "Cloud SQL connection name"
}

output "uploads_bucket" {
  value       = google_storage_bucket.uploads.name
  description = "Uploads storage bucket"
}

output "overlays_bucket" {
  value       = google_storage_bucket.overlays.name
  description = "Overlays storage bucket"
}

output "vision_topic" {
  value       = google_pubsub_topic.vision.name
  description = "Vision Pub/Sub topic"
}

output "artifact_registry" {
  value       = google_artifact_registry_repository.main.name
  description = "Artifact Registry repository"
}

