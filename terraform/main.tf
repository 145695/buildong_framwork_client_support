terraform {
  required_providers {
    azurerm = {
      source  = "hashicorp/azurerm"
      version = "~> 3.0"
    }
  }
}

provider "azurerm" {
  features {
    resource_group {
      prevent_deletion_if_contains_resources = false
    }
  }
  subscription_id = "299e067f-d86a-4d63-bc44-b42ed7ecbe2c"
  skip_provider_registration = true
}

resource "azurerm_resource_group" "maces_rg" {
  name     = "maces-rg"
  location = "francecentral"
}

resource "azurerm_container_group" "maces" {
  name                = "maces-app"
  location            = azurerm_resource_group.maces_rg.location
  resource_group_name = azurerm_resource_group.maces_rg.name
  os_type             = "Linux"
  restart_policy      = "Always"

  image_registry_credential {
    username = "mariaboukhelfa2025"
    password = var.docker_password
    server   = "index.docker.io"
  }

  # Container 1: Knowledge Base (START FIRST - 0s)
  container {
    name   = "kb-processor"
    image  = "mariaboukhelfa2025/maces:latest"
    cpu    = "1"
    memory = "2"

    ports {
      port     = 8003
      protocol = "TCP"
    }

    environment_variables = {
      SERVICE_TYPE         = "kb-service"
      PYTHONUNBUFFERED     = "1"
    }

    commands = [
      "sh", "-c",
      "echo '[KB] Waiting 10s before startup...' && sleep 10 && python -m uvicorn app.kb_service:app --host 0.0.0.0 --port 8003 --workers 1"
    ]
  }

  # Container 2: Voice Processing (START AFTER KB - 60s)
  container {
    name   = "voice-processor"
    image  = "mariaboukhelfa2025/maces:latest"
    cpu    = "1.5"
    memory = "3"

    ports {
      port     = 8001
      protocol = "TCP"
    }

    environment_variables = {
      SERVICE_TYPE         = "voice-service"
      PYTHONUNBUFFERED     = "1"
      LOAD_VOICE_MODELS    = "true"
      RIVA_FUNCTION_ID     = "b702f636-f60c-4a3d-a6f4-f3568c13bd7d"
      RIVA_COMMAND_TIMEOUT = "120"
    }

    secure_environment_variables = {
      NVIDIA_API_KEY = var.nvidia_api_key
    }

    commands = [
      "sh", "-c",
      "echo '[Voice] Waiting 60s for KB to stabilize...' && sleep 60 && python -m uvicorn app.voice_service:app --host 0.0.0.0 --port 8001 --workers 1"
    ]
  }

  # Container 3: LLM Processing (START AFTER VOICE - 120s)
  container {
    name   = "llm-processor"
    image  = "mariaboukhelfa2025/maces:latest"
    cpu    = "1"
    memory = "2"

    ports {
      port     = 8002
      protocol = "TCP"
    }

    environment_variables = {
      SERVICE_TYPE     = "llm-service"
      PYTHONUNBUFFERED = "1"
    }

    secure_environment_variables = {
      NVIDIA_API_KEY          = var.nvidia_api_key
      NVIDIA_NEMOTRON_API_KEY = var.nvidia_nemotron_api_key
      NVIDIA_API_KEY_LLAMA    = var.nvidia_api_key_llama
      NVIDIA_API_KEY_MISTRAL  = var.nvidia_api_key_mistral
      MISTRAL_API_KEY         = var.mistral_api_key
      COHERE_API_KEY          = var.cohere_api_key
      GROQ_API_KEY            = var.groq_api_key
      HUGGINGFACE_API_TOKEN   = var.huggingface_api_token
      LANGCHAIN_API_KEY       = var.langchain_api_key
    }

    commands = [
      "sh", "-c",
      "echo '[LLM] Waiting 120s for Voice to stabilize...' && sleep 120 && python -m uvicorn app.llm_service:app --host 0.0.0.0 --port 8002 --workers 1"
    ]
  }

  # Container 4: API Gateway (START LAST - 180s)
  container {
    name   = "api-gateway"
    image  = "mariaboukhelfa2025/maces:latest"
    cpu    = "0.5"
    memory = "1"

    ports {
      port     = 8000
      protocol = "TCP"
    }

    environment_variables = {
      SERVICE_TYPE      = "api-gateway"
      PYTHONUNBUFFERED  = "1"
      VOICE_SERVICE_URL = "http://localhost:8001"
      LLM_SERVICE_URL   = "http://localhost:8002"
      KB_SERVICE_URL    = "http://localhost:8003"
    }

    commands = [
      "sh", "-c",
      "echo '[Gateway] Waiting 180s for all services...' && sleep 180 && python -m uvicorn app.api_gateway:app --host 0.0.0.0 --port 8000 --workers 1"
    ]
  }

  ip_address_type = "Public"
  dns_name_label  = "maces-app"

  tags = {
    project = "MACES"
    env     = "microservices"
  }
}

output "application_url" {
  value       = "http://${azurerm_container_group.maces.fqdn}:8000"
  description = "URL to access the MACES application"
}

output "fqdn" {
  value       = azurerm_container_group.maces.fqdn
  description = "Fully Qualified Domain Name"
}

output "ip_address" {
  value       = azurerm_container_group.maces.ip_address
  description = "Public IP address"
}

output "deployment_summary" {
  value = <<EOF

╔═══════════════════════════════════════════════════════════╗
║     MACES - Microservices (Staggered Startup)             ║
╠═══════════════════════════════════════════════════════════╣
║                                                           ║
║  t+10s   KB Processor      (Port 8003)  1 CPU / 2 GB     ║
║  t+60s   Voice Processor   (Port 8001)  1.5 CPU / 3 GB   ║
║  t+120s  LLM Processor     (Port 8002)  1 CPU / 2 GB     ║
║  t+180s  API Gateway       (Port 8000)  0.5 CPU / 1 GB   ║
║                                                           ║
║  Total: 4 CPUs / 8 GB Memory                             ║
║                                                           ║
║  URL: http://${azurerm_container_group.maces.fqdn}:8000
║  FQDN: ${azurerm_container_group.maces.fqdn}
╚═══════════════════════════════════════════════════════════╝

EOF
  description = "Deployment summary"
}