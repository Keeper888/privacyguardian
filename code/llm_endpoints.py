"""
PrivacyGuardian - LLM Endpoints Registry
=========================================
Configuration for all supported LLM API providers.
"""

from dataclasses import dataclass
from typing import List, Optional, Dict


@dataclass
class LLMProvider:
    """Configuration for an LLM API provider"""
    name: str
    domains: List[str]  # Domains to intercept
    message_paths: List[str]  # JSON paths containing user messages
    api_key_headers: List[str]  # Headers containing API keys to protect
    content_type: str = "application/json"

    def matches_domain(self, domain: str) -> bool:
        """Check if a domain matches this provider"""
        for pattern in self.domains:
            if pattern.startswith("*."):
                # Wildcard match
                suffix = pattern[1:]  # .openai.azure.com
                if domain.endswith(suffix) or domain == pattern[2:]:
                    return True
            elif domain == pattern or domain.endswith("." + pattern):
                return True
        return False


# All supported LLM providers
LLM_PROVIDERS: Dict[str, LLMProvider] = {
    "anthropic": LLMProvider(
        name="Anthropic",
        domains=["api.anthropic.com"],
        message_paths=[
            "messages[*].content",  # Messages API
            "prompt",  # Legacy completion API
        ],
        api_key_headers=["x-api-key", "anthropic-api-key"],
    ),

    "openai": LLMProvider(
        name="OpenAI",
        domains=["api.openai.com"],
        message_paths=[
            "messages[*].content",  # Chat completions
            "prompt",  # Legacy completions
            "input",  # Embeddings
        ],
        api_key_headers=["authorization"],
    ),

    "azure_openai": LLMProvider(
        name="Azure OpenAI",
        domains=["*.openai.azure.com"],
        message_paths=[
            "messages[*].content",
            "prompt",
        ],
        api_key_headers=["api-key", "authorization"],
    ),

    "google": LLMProvider(
        name="Google AI",
        domains=[
            "generativelanguage.googleapis.com",
            "aiplatform.googleapis.com",
        ],
        message_paths=[
            "contents[*].parts[*].text",  # Gemini API
            "instances[*].content",  # Vertex AI
        ],
        api_key_headers=["x-goog-api-key", "authorization"],
    ),

    "mistral": LLMProvider(
        name="Mistral AI",
        domains=["api.mistral.ai"],
        message_paths=[
            "messages[*].content",
            "prompt",
        ],
        api_key_headers=["authorization"],
    ),

    "cohere": LLMProvider(
        name="Cohere",
        domains=["api.cohere.ai", "api.cohere.com"],
        message_paths=[
            "message",  # Chat
            "prompt",  # Generate
            "texts",  # Embed
        ],
        api_key_headers=["authorization"],
    ),

    "groq": LLMProvider(
        name="Groq",
        domains=["api.groq.com"],
        message_paths=[
            "messages[*].content",
        ],
        api_key_headers=["authorization"],
    ),

    "perplexity": LLMProvider(
        name="Perplexity",
        domains=["api.perplexity.ai"],
        message_paths=[
            "messages[*].content",
        ],
        api_key_headers=["authorization"],
    ),

    "together": LLMProvider(
        name="Together AI",
        domains=["api.together.xyz"],
        message_paths=[
            "messages[*].content",
            "prompt",
        ],
        api_key_headers=["authorization"],
    ),

    "fireworks": LLMProvider(
        name="Fireworks AI",
        domains=["api.fireworks.ai"],
        message_paths=[
            "messages[*].content",
            "prompt",
        ],
        api_key_headers=["authorization"],
    ),

    "ollama": LLMProvider(
        name="Ollama (Local)",
        domains=["localhost:11434", "127.0.0.1:11434"],
        message_paths=[
            "messages[*].content",  # Chat API
            "prompt",  # Generate API
        ],
        api_key_headers=[],  # No auth for local
    ),

    "lmstudio": LLMProvider(
        name="LM Studio (Local)",
        domains=["localhost:1234", "127.0.0.1:1234"],
        message_paths=[
            "messages[*].content",
        ],
        api_key_headers=[],
    ),
}


def get_provider_for_domain(domain: str) -> Optional[LLMProvider]:
    """Find the LLM provider for a given domain"""
    # Remove port if present for matching
    domain_no_port = domain.split(":")[0] if ":" in domain else domain

    for provider in LLM_PROVIDERS.values():
        if provider.matches_domain(domain) or provider.matches_domain(domain_no_port):
            return provider
    return None


def get_all_domains() -> List[str]:
    """Get list of all LLM API domains to intercept"""
    domains = []
    for provider in LLM_PROVIDERS.values():
        domains.extend(provider.domains)
    return domains


def get_domains_for_iptables() -> List[str]:
    """Get domains suitable for iptables rules (no wildcards, no ports)"""
    domains = []
    for provider in LLM_PROVIDERS.values():
        for domain in provider.domains:
            # Skip wildcards and localhost
            if domain.startswith("*.") or domain.startswith("localhost") or domain.startswith("127."):
                continue
            # Remove port
            domain_clean = domain.split(":")[0]
            if domain_clean not in domains:
                domains.append(domain_clean)
    return domains


# Quick test
if __name__ == "__main__":
    print("=== Supported LLM Providers ===\n")
    for key, provider in LLM_PROVIDERS.items():
        print(f"{provider.name}:")
        print(f"  Domains: {', '.join(provider.domains)}")
        print(f"  Message paths: {', '.join(provider.message_paths)}")
        print()

    print("=== Domain Matching Test ===\n")
    test_domains = [
        "api.anthropic.com",
        "api.openai.com",
        "mycompany.openai.azure.com",
        "generativelanguage.googleapis.com",
        "api.mistral.ai",
        "localhost:11434",
        "unknown.example.com",
    ]

    for domain in test_domains:
        provider = get_provider_for_domain(domain)
        if provider:
            print(f"✓ {domain} → {provider.name}")
        else:
            print(f"✗ {domain} → Not matched")
