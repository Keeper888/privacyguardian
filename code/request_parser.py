"""
PrivacyGuardian - Request Parser
================================
Parses and modifies LLM API requests/responses for different providers.
Extracts message content from various JSON structures.
"""

import json
import re
from typing import Any, Dict, List, Tuple, Callable, Optional
from llm_endpoints import LLMProvider, get_provider_for_domain


class RequestParser:
    """
    Parse and modify LLM API requests/responses.
    Handles different JSON structures for each provider.
    """

    def __init__(self, pii_protector: Callable[[str], str], pii_unprotector: Callable[[str], str]):
        """
        Args:
            pii_protector: Function to encrypt PII in text
            pii_unprotector: Function to decrypt tokens in text
        """
        self.protect = pii_protector
        self.unprotect = pii_unprotector

    def protect_request(self, body: bytes, provider: LLMProvider) -> Tuple[bytes, int]:
        """
        Protect PII in an outgoing request.
        Returns: (modified_body, pii_count)
        """
        try:
            data = json.loads(body)
        except json.JSONDecodeError:
            # Not JSON, protect as plain text
            protected = self.protect(body.decode('utf-8', errors='replace'))
            return protected.encode('utf-8'), 0

        pii_count = 0
        modified, count = self._protect_json_recursive(data, provider.message_paths)
        pii_count += count

        return json.dumps(modified).encode('utf-8'), pii_count

    def unprotect_response(self, body: bytes, provider: LLMProvider) -> bytes:
        """
        Unprotect (decrypt) tokens in an incoming response.
        """
        try:
            data = json.loads(body)
        except json.JSONDecodeError:
            # Not JSON, unprotect as plain text
            unprotected = self.unprotect(body.decode('utf-8', errors='replace'))
            return unprotected.encode('utf-8')

        modified = self._unprotect_json_recursive(data)
        return json.dumps(modified).encode('utf-8')

    def _protect_json_recursive(self, data: Any, message_paths: List[str], current_path: str = "") -> Tuple[Any, int]:
        """
        Recursively traverse JSON and protect strings in message paths.
        """
        pii_count = 0

        if isinstance(data, str):
            # Check if current path matches any message path pattern
            if self._path_matches(current_path, message_paths):
                protected = self.protect(data)
                if protected != data:
                    pii_count += 1
                return protected, pii_count
            return data, 0

        elif isinstance(data, dict):
            result = {}
            for key, value in data.items():
                new_path = f"{current_path}.{key}" if current_path else key
                modified, count = self._protect_json_recursive(value, message_paths, new_path)
                result[key] = modified
                pii_count += count
            return result, pii_count

        elif isinstance(data, list):
            result = []
            for i, item in enumerate(data):
                new_path = f"{current_path}[{i}]"
                # Also match wildcard [*]
                wildcard_path = re.sub(r'\[\d+\]', '[*]', new_path)
                modified, count = self._protect_json_recursive(item, message_paths, new_path)
                result.append(modified)
                pii_count += count
            return result, pii_count

        else:
            return data, 0

    def _unprotect_json_recursive(self, data: Any) -> Any:
        """
        Recursively traverse JSON and unprotect all token strings.
        We unprotect everywhere since tokens might appear in unexpected places.
        """
        if isinstance(data, str):
            return self.unprotect(data)
        elif isinstance(data, dict):
            return {k: self._unprotect_json_recursive(v) for k, v in data.items()}
        elif isinstance(data, list):
            return [self._unprotect_json_recursive(item) for item in data]
        else:
            return data

    def _path_matches(self, path: str, patterns: List[str]) -> bool:
        """
        Check if a JSON path matches any of the patterns.
        Supports wildcards like messages[*].content
        """
        # Normalize path
        path = path.lstrip(".")

        for pattern in patterns:
            # Convert pattern to regex
            regex_pattern = pattern
            regex_pattern = regex_pattern.replace("[*]", r"\[\d+\]")
            regex_pattern = regex_pattern.replace(".", r"\.")
            regex_pattern = f"^{regex_pattern}$|{regex_pattern}$"

            if re.search(regex_pattern, path):
                return True

        # Also protect any field named 'content', 'text', 'prompt', 'message', 'input'
        field_name = path.split(".")[-1] if "." in path else path
        field_name = re.sub(r'\[\d+\]', '', field_name)
        if field_name.lower() in ('content', 'text', 'prompt', 'message', 'input', 'query'):
            return True

        return False


class StreamingParser:
    """
    Handle streaming responses (SSE format).
    Unprotects tokens as they arrive in chunks.
    """

    def __init__(self, unprotector: Callable[[str], str]):
        self.unprotect = unprotector
        self.buffer = ""

    def process_chunk(self, chunk: bytes) -> bytes:
        """Process a streaming chunk, unprotecting any tokens"""
        try:
            text = chunk.decode('utf-8')
        except UnicodeDecodeError:
            return chunk

        # Handle SSE format: data: {...}\n\n
        lines = text.split('\n')
        result_lines = []

        for line in lines:
            if line.startswith('data: '):
                data_part = line[6:]
                if data_part.strip() == '[DONE]':
                    result_lines.append(line)
                else:
                    try:
                        json_data = json.loads(data_part)
                        unprotected = self._unprotect_recursive(json_data)
                        result_lines.append(f"data: {json.dumps(unprotected)}")
                    except json.JSONDecodeError:
                        # Not JSON, unprotect as text
                        result_lines.append(f"data: {self.unprotect(data_part)}")
            else:
                result_lines.append(line)

        return '\n'.join(result_lines).encode('utf-8')

    def _unprotect_recursive(self, data: Any) -> Any:
        """Recursively unprotect all strings"""
        if isinstance(data, str):
            return self.unprotect(data)
        elif isinstance(data, dict):
            return {k: self._unprotect_recursive(v) for k, v in data.items()}
        elif isinstance(data, list):
            return [self._unprotect_recursive(item) for item in data]
        return data


# Test
if __name__ == "__main__":
    # Mock protector/unprotector for testing
    token_map = {}
    counter = [0]

    def mock_protect(text: str) -> str:
        import re
        # Simple email detection for test
        def replace(match):
            email = match.group(0)
            token = f"◈PG:EMAIL_{counter[0]}◈"
            token_map[token] = email
            counter[0] += 1
            return token
        return re.sub(r'[\w.-]+@[\w.-]+\.\w+', replace, text)

    def mock_unprotect(text: str) -> str:
        result = text
        for token, value in token_map.items():
            result = result.replace(token, value)
        return result

    parser = RequestParser(mock_protect, mock_unprotect)

    # Test Anthropic-style request
    print("=== Anthropic Request Test ===")
    from llm_endpoints import LLM_PROVIDERS

    anthropic_request = {
        "model": "claude-3-opus",
        "messages": [
            {"role": "user", "content": "My email is test@example.com, please help me."}
        ],
        "max_tokens": 1024
    }

    protected, count = parser.protect_request(
        json.dumps(anthropic_request).encode(),
        LLM_PROVIDERS["anthropic"]
    )
    print(f"Original: {anthropic_request}")
    print(f"Protected: {json.loads(protected)}")
    print(f"PII count: {count}")

    # Test OpenAI-style request
    print("\n=== OpenAI Request Test ===")
    openai_request = {
        "model": "gpt-4",
        "messages": [
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": "Contact me at user@gmail.com"}
        ]
    }

    protected, count = parser.protect_request(
        json.dumps(openai_request).encode(),
        LLM_PROVIDERS["openai"]
    )
    print(f"Original: {openai_request}")
    print(f"Protected: {json.loads(protected)}")
    print(f"PII count: {count}")
