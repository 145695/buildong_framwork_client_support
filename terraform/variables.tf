variable "nvidia_api_key" {
  description = "NVIDIA API Key for Whisper STT"
  sensitive   = true
}

variable "nvidia_nemotron_api_key" {
  description = "NVIDIA API Key for Nemotron Translation"
  sensitive   = true
}

variable "nvidia_api_key_llama" {
  description = "NVIDIA API Key for Llama"
  sensitive   = true
}

variable "nvidia_api_key_mistral" {
  description = "NVIDIA API Key for Mistral"
  sensitive   = true
}

variable "mistral_api_key" {
  description = "Mistral API Key for RAG"
  sensitive   = true
}

variable "cohere_api_key" {
  description = "Cohere API Key"
  sensitive   = true
}

variable "langchain_api_key" {
  description = "LangSmith API Key"
  sensitive   = true
}

variable "groq_api_key" {
  description = "Groq API Key"
  sensitive   = true
}

variable "huggingface_api_token" {
  description = "HuggingFace API Token"
  sensitive   = true
}
variable "docker_password" {
  description = "Docker Hub password or access token"
  type        = string
  sensitive   = true
}
