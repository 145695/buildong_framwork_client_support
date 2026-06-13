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

  container {
    name   = "maces"
    image  = "mariaboukhelfa2025/maces:latest"
    cpu    = "2"
    memory = "8"

    ports {
      port     = 8000
      protocol = "TCP"
    }

    environment_variables = {
      AUDIO_SAMPLE_RATE          = "16000"
      AUDIO_CHUNK_SIZE           = "256"
      SILENCE_DURATION_SEC       = "0.8"
      VAD_AGGRESSIVENESS         = "3"
      WS_BUFFER_MAX_SIZE         = "5242880"
      AUDIO_PROCESSING_TIMEOUT   = "15"
      RESPONSE_STREAMING_TIMEOUT = "60"
      RIVA_COMMAND_TIMEOUT       = "120"
      LANGCHAIN_TRACING_V2       = "true"
      LANGCHAIN_PROJECT          = "maces-multi-agent"
      RIVA_FUNCTION_ID           = "b702f636-f60c-4a3d-a6f4-f3568c13bd7d"
      LOAD_VOICE_MODELS          = "true"
    }

    secure_environment_variables = {
      NVIDIA_API_KEY          = var.nvidia_api_key
      NVIDIA_NEMOTRON_API_KEY = var.nvidia_nemotron_api_key
      NVIDIA_API_KEY_LLAMA    = var.nvidia_api_key_llama
      NVIDIA_API_KEY_MISTRAL  = var.nvidia_api_key_mistral
      MISTRAL_API_KEY         = var.mistral_api_key
      COHERE_API_KEY          = var.cohere_api_key
      LANGCHAIN_API_KEY       = var.langchain_api_key
      GROQ_API_KEY            = var.groq_api_key
      HUGGINGFACE_API_TOKEN   = var.huggingface_api_token
    }
  }

  ip_address_type = "Public"
  dns_name_label  = "maces-app"

  tags = {
    project = "MACES"
    env     = "optimized"
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