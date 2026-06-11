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

  # Container 1: Voice Processing (STT + Translation + TTS)
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
      SERVICE_TYPE              = "voice-service"
      PYTHONUNBUFFERED          = "1"
      AUDIO_SAMPLE_RATE         = "16000"
      AUDIO_CHUNK_SIZE          = "256"
      SILENCE_DURATION_SEC      = "0.8"
      VAD_AGGRESSIVENESS        = "3"
      LOAD_VOICE_MODELS         = "true"
      RIVA_FUNCTION_ID          = "b702f636-f60c-4a3d-a6f4-f3568c13bd7d"
      RIVA_COMMAND_TIMEOUT      = "120"
    }

    secure_environment_variables = {
      NVIDIA_API_KEY = var.nvidia_api_key
    }

    commands = [
      "python", "-m", "uvicorn", "app.voice_service:app",
      "--host", "0.0.0.0", "--port", "8001", "--workers", "1"
    ]
  }

  # Container 2: LLM & Security Processing
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
      SERVICE_TYPE              = "llm-service"
      PYTHONUNBUFFERED          = "1"
      RIVA_FUNCTION_ID          = "b702f636-f60c-4a3d-a6f4-f3568c13bd7d"
      RIVA_COMMAND_TIMEOUT      = "120"
      LANGCHAIN_TRACING_V2      = "true"
      LANGCHAIN_PROJECT         = "maces-multi-agent"
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
      "python", "-m", "uvicorn", "app.llm_service:app",
      "--host", "0.0.0.0", "--port", "8002", "--workers", "1"
    ]
  }

  # Container 3: Knowledge Base Search
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
      SERVICE_TYPE              = "kb-service"
      PYTHONUNBUFFERED          = "1"
      LANGCHAIN_TRACING_V2      = "true"
      LANGCHAIN_PROJECT         = "maces-multi-agent"
      MISTRAL_API_KEY           = var.mistral_api_key
    }

    commands = [
      "python", "-m", "uvicorn", "app.kb_service:app",
      "--host", "0.0.0.0", "--port", "8003", "--workers", "1"
    ]
  }

  # Container 4: Main API Gateway
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
      SERVICE_TYPE              = "api-gateway"
      PYTHONUNBUFFERED          = "1"
      VOICE_SERVICE_URL         = "http://localhost:8001"
      LLM_SERVICE_URL           = "http://localhost:8002"
      KB_SERVICE_URL            = "http://localhost:8003"
    }

    commands = [
      "python", "-m", "uvicorn", "app.api_gateway:app",
      "--host", "0.0.0.0", "--port", "8000", "--workers", "1"
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
  description = "Full URL to access the MACES application"
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
║     MACES - Microservices Architecture                    ║
╠═══════════════════════════════════════════════════════════╣
║ Total: 4 CPUs / 8 GB Memory                              ║
║                                                           ║
║ Voice Processor (Port 8001): 1.5 CPU / 3 GB               ║
║   → STT, Translation, TTS (Kokoro)                        ║
║                                                           ║
║ LLM Processor (Port 8002): 1 CPU / 2 GB                   ║
║   → Security, Agents, NVIDIA API                          ║
║                                                           ║
║ KB Processor (Port 8003): 1 CPU / 2 GB                    ║
║   → Document search, embeddings                           ║
║                                                           ║
║ API Gateway (Port 8000): 0.5 CPU / 1 GB                   ║
║   → WebSocket, HTTP routing                               ║
║                                                           ║
║ URL: http://${azurerm_container_group.maces.fqdn}:8000
║ FQDN: ${azurerm_container_group.maces.fqdn}
║ IP:   ${azurerm_container_group.maces.ip_address}
╚═══════════════════════════════════════════════════════════╝

Check services:
  curl http://localhost:8000/health

Monitor logs:
  az container logs -g maces-rg -n maces-app --container-name api-gateway
  az container logs -g maces-rg -n maces-app --container-name voice-processor
  az container logs -g maces-rg -n maces-app --container-name llm-processor
  az container logs -g maces-rg -n maces-app --container-name kb-processor

Destroy:
  terraform destroy

EOF
  description = "Complete deployment summary"
}