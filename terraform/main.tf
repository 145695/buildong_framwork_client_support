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

# ========================================
# DNS Labels (computed manually to avoid cycle)
# ========================================
locals {
  voice_dns = "maces-voice.francecentral.azurecontainer.io"
  loan_dns  = "maces-loan.francecentral.azurecontainer.io"
}

# ========================================
# VOICE ASSISTANT - Container Instance
# ========================================
resource "azurerm_container_group" "voice_assistant" {
  name                = "maces-voice-assistant"
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
    name   = "voice-assistant"
    image  = "mariaboukhelfa2025/maces:voice-assistant-latest"
    cpu    = "4"
    memory = "16"

    ports {
      port     = 8000
      protocol = "TCP"
    }

    environment_variables = {
      LOAN_AGENT_URL = "http://${local.loan_dns}:5000"
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
  dns_name_label  = "maces-voice"

  tags = {
    project = "MACES"
    service = "voice-assistant"
    env     = "production"
  }
}

# ========================================
# LOAN AGENT - Container Instance
# ========================================
resource "azurerm_container_group" "loan_agent" {
  name                = "maces-loan-agent"
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
    name   = "loan-agent"
    image  = "mariaboukhelfa2025/maces:loan-agent-latest"
    cpu    = "1"
    memory = "8"

    ports {
      port     = 5000
      protocol = "TCP"
    }

    environment_variables = {
      PROCEED_URL = "http://${local.voice_dns}:8000/maces_interface.html"
      RETURN_URL  = "http://${local.voice_dns}:8000/"
      PORT        = "5000"
    }
  }

  ip_address_type = "Public"
  dns_name_label  = "maces-loan"

  tags = {
    project = "MACES"
    service = "loan-agent"
    env     = "production"
  }
}

# ========================================
# OUTPUTS
# ========================================
output "voice_assistant_url" {
  value       = "http://${azurerm_container_group.voice_assistant.fqdn}:8000"
  description = "URL to access the Voice Assistant"
}

output "voice_assistant_fqdn" {
  value       = azurerm_container_group.voice_assistant.fqdn
  description = "Voice Assistant Fully Qualified Domain Name"
}

output "loan_agent_url" {
  value       = "http://${azurerm_container_group.loan_agent.fqdn}:5000"
  description = "URL to access the Loan Agent"
}

output "loan_agent_fqdn" {
  value       = azurerm_container_group.loan_agent.fqdn
  description = "Loan Agent Fully Qualified Domain Name"
}