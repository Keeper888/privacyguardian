"""
PrivacyGuardian - LLM Monitor
==============================
Optional tiny LLM that monitors outgoing traffic to ensure
no PII leaks through the regex-based detection.

Uses TinyLlama (1.1B) or Phi-2 (2.7B) - minimal resource usage.
Can run on CPU with ~2GB RAM overhead.
"""

import os
import json
import threading
import queue
from pathlib import Path
from typing import Optional, List, Dict, Any
from dataclasses import dataclass
from datetime import datetime


@dataclass
class MonitorResult:
    timestamp: str
    text_sample: str
    detected_pii: List[str]
    confidence: float
    action: str  # "blocked", "warned", "passed"


class LLMMonitor:
    """
    Tiny LLM-based PII monitor
    Runs in background thread, samples outgoing traffic
    """

    SYSTEM_PROMPT = """You are a privacy protection monitor. Your job is to detect if any Personally Identifiable Information (PII) exists in the text.

PII includes:
- Names of real people
- Email addresses
- Phone numbers
- Physical addresses
- Social Security Numbers
- Credit card numbers
- Dates of birth
- Medical information
- Financial account numbers
- API keys and secrets
- Passwords

Respond in JSON format:
{"has_pii": true/false, "items": ["list of detected PII"], "confidence": 0.0-1.0}"""

    def __init__(self, model_path: Optional[str] = None):
        self.model = None
        self.model_path = model_path or self._find_model()
        self.monitor_queue = queue.Queue(maxsize=100)
        self.results: List[MonitorResult] = []
        self.running = False
        self._thread = None

    def _find_model(self) -> Optional[str]:
        """Find a suitable tiny model"""
        search_paths = [
            Path.home() / ".cache" / "huggingface" / "hub",
            Path.home() / "models",
            Path("/usr/share/models"),
        ]

        model_patterns = [
            "*tinyllama*",
            "*phi-2*",
            "*qwen*1.5b*",
            "*gemma-2b*",
        ]

        for path in search_paths:
            if path.exists():
                for pattern in model_patterns:
                    matches = list(path.glob(f"**/{pattern}/*.gguf"))
                    if matches:
                        return str(matches[0])

        return None

    def load(self) -> bool:
        """Load the tiny LLM model"""
        if self.model is not None:
            return True

        if not self.model_path:
            print("No model found. Monitor running in regex-only mode.")
            return False

        try:
            from llama_cpp import Llama

            print(f"Loading monitor model: {self.model_path}")
            self.model = Llama(
                model_path=self.model_path,
                n_ctx=1024,        # Small context window
                n_threads=2,       # Minimal CPU threads
                n_gpu_layers=0,    # CPU only
                verbose=False,
                use_mlock=False,   # Don't lock memory
            )
            print("Monitor model loaded successfully")
            return True

        except ImportError:
            print("llama-cpp-python not installed. Install with:")
            print("  pip install llama-cpp-python")
            return False
        except Exception as e:
            print(f"Failed to load model: {e}")
            return False

    def analyze(self, text: str) -> MonitorResult:
        """Analyze text for PII using the LLM"""
        timestamp = datetime.utcnow().isoformat()

        # Truncate for analysis
        sample = text[:500] if len(text) > 500 else text

        if self.model is None:
            # Fallback: just check if tokens exist (they should be protected)
            has_tokens = "◈PG:" in text
            return MonitorResult(
                timestamp=timestamp,
                text_sample=sample[:100],
                detected_pii=[],
                confidence=0.5,
                action="passed" if has_tokens else "warned"
            )

        try:
            prompt = f"{self.SYSTEM_PROMPT}\n\nText to analyze:\n{sample}\n\nJSON response:"

            response = self.model(
                prompt,
                max_tokens=200,
                temperature=0.1,
                stop=["\n\n", "```"]
            )

            result_text = response['choices'][0]['text'].strip()

            # Parse JSON response
            try:
                result = json.loads(result_text)
                has_pii = result.get("has_pii", False)
                items = result.get("items", [])
                confidence = result.get("confidence", 0.5)

                if has_pii and confidence > 0.8:
                    action = "blocked"
                elif has_pii:
                    action = "warned"
                else:
                    action = "passed"

                return MonitorResult(
                    timestamp=timestamp,
                    text_sample=sample[:100],
                    detected_pii=items,
                    confidence=confidence,
                    action=action
                )

            except json.JSONDecodeError:
                return MonitorResult(
                    timestamp=timestamp,
                    text_sample=sample[:100],
                    detected_pii=[],
                    confidence=0.5,
                    action="passed"
                )

        except Exception as e:
            print(f"Monitor analysis error: {e}")
            return MonitorResult(
                timestamp=timestamp,
                text_sample=sample[:100],
                detected_pii=[],
                confidence=0.0,
                action="error"
            )

    def submit(self, text: str):
        """Submit text for background analysis"""
        try:
            self.monitor_queue.put_nowait(text)
        except queue.Full:
            pass  # Drop if queue is full

    def _monitor_loop(self):
        """Background monitoring thread"""
        while self.running:
            try:
                text = self.monitor_queue.get(timeout=1.0)
                result = self.analyze(text)
                self.results.append(result)

                # Keep last 100 results
                if len(self.results) > 100:
                    self.results = self.results[-100:]

                # Log warnings/blocks
                if result.action == "blocked":
                    print(f"\n⚠️  BLOCKED: Potential PII detected: {result.detected_pii}")
                elif result.action == "warned":
                    print(f"\n⚡ WARNING: Possible PII: {result.detected_pii}")

            except queue.Empty:
                continue
            except Exception as e:
                print(f"Monitor error: {e}")

    def start(self):
        """Start background monitoring"""
        if self.running:
            return

        self.running = True
        self._thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self._thread.start()
        print("🔍 LLM Monitor started")

    def stop(self):
        """Stop background monitoring"""
        self.running = False
        if self._thread:
            self._thread.join(timeout=2.0)
        print("LLM Monitor stopped")

    def get_stats(self) -> Dict[str, Any]:
        """Get monitoring statistics"""
        total = len(self.results)
        blocked = sum(1 for r in self.results if r.action == "blocked")
        warned = sum(1 for r in self.results if r.action == "warned")
        passed = sum(1 for r in self.results if r.action == "passed")

        return {
            "total_analyzed": total,
            "blocked": blocked,
            "warned": warned,
            "passed": passed,
            "recent_detections": [
                {"pii": r.detected_pii, "action": r.action}
                for r in self.results[-10:]
                if r.detected_pii
            ]
        }


# Download helper for tiny models
def download_tinyllama():
    """Download TinyLlama 1.1B model (smallest usable model)"""
    try:
        from huggingface_hub import hf_hub_download

        print("Downloading TinyLlama 1.1B (Q4_K_M quantized)...")
        print("This is a ~670MB download, runs with ~1GB RAM")

        model_path = hf_hub_download(
            repo_id="TheBloke/TinyLlama-1.1B-Chat-v1.0-GGUF",
            filename="tinyllama-1.1b-chat-v1.0.Q4_K_M.gguf",
            cache_dir=str(Path.home() / ".cache" / "privacyguardian")
        )

        print(f"Downloaded to: {model_path}")
        return model_path

    except ImportError:
        print("Install huggingface_hub: pip install huggingface_hub")
        return None


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--download", action="store_true", help="Download TinyLlama model")
    parser.add_argument("--test", type=str, help="Test analysis on text")
    args = parser.parse_args()

    if args.download:
        download_tinyllama()
    elif args.test:
        monitor = LLMMonitor()
        if monitor.load():
            result = monitor.analyze(args.test)
            print(f"\nResult: {result}")
        else:
            print("Model not available")
    else:
        print("Usage:")
        print("  --download    Download TinyLlama model")
        print("  --test TEXT   Test PII detection on text")
