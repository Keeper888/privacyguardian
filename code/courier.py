"""
PrivacyGuardian - Courier
=========================
Swaps real values for tokens on the way out, and tokens back for real values
on the way in. The AI carries tokens around (copy, paste, edit) without ever
seeing what is behind them.

Outgoing (request):  deny by default. Every string is scanned except a short
                     list of structural fields (issue #19).
Incoming (response): tokens are restored everywhere except thinking blocks,
                     which are signed by the provider and must stay untouched.
Streams:             a token split across two stream events is held back until
                     it is complete (issue #18).
"""

import codecs
import json
import re
from typing import Any, Callable, Dict, List, Optional, Tuple

from pii_detector import PIIDetector
from vault import TokenVault, TOKEN_RE, TOKEN_MAX_LEN

MARK = "◈"            # ◈ as a character
MARK_ESC = "\\u25c8"       # ◈ as it may appear escaped inside raw JSON text
TOKEN_ESC_RE = re.compile(r"\\u25c8PG:([A-Z0-9_]{1,8})_([0-9a-f]{16})\\u25c8")

# Fields that are structure, not content: never tokenized.
STRUCT_KEYS = {
    "model", "role", "type", "id", "tool_use_id", "name", "stop_reason", "stop_sequence",
    "media_type", "signature", "cache_control", "data", "tool_choice", "stream",
    "anthropic_version", "service_tier", "object", "finish_reason",
}
# Whole subtrees left alone: tool schemas and request metadata.
SKIP_SUBTREES = {"tools", "metadata"}
# Content blocks signed by the provider: changing a byte breaks the next turn.
SIGNED_BLOCKS = {"thinking", "redacted_thinking"}

# After the opening mark, what an unfinished token can still look like.
_PARTIAL_AFTER_MARK = re.compile(r"^(?:P|PG|PG:[A-Za-z0-9_]{0,26}(?:\\(?:u(?:2(?:5(?:c)?)?)?)?)?)?$")


def _json_escape(value: str) -> str:
    return json.dumps(value, ensure_ascii=False)[1:-1]


class Courier:
    def __init__(self, vault: Optional[TokenVault] = None, detector: Optional[PIIDetector] = None):
        self.vault = vault or TokenVault()
        self.detector = detector or PIIDetector()
        self.items_protected = 0

    # -- text ---------------------------------------------------------------

    def protect_text(self, text: str, provider: Optional[str] = None) -> str:
        """Replace PII with tokens. Existing tokens are left as they are."""
        if not text:
            return text
        out: List[str] = []
        pos = 0
        for m in TOKEN_RE.finditer(text):
            out.append(self._protect_segment(text[pos:m.start()], provider))
            out.append(m.group(0))
            pos = m.end()
        out.append(self._protect_segment(text[pos:], provider))
        return "".join(out)

    def _protect_segment(self, text: str, provider: Optional[str]) -> str:
        if not text:
            return text
        matches = self.detector.detect(text)
        if not matches:
            return text
        for match in sorted(matches, key=lambda m: m.start, reverse=True):
            token, is_new = self.vault.protect(match.value, match.pii_type.value, provider)
            text = text[:match.start] + token + text[match.end:]
            if is_new:
                self.items_protected += 1
        return text

    def unprotect_text(self, text: str, json_escaped: bool = False) -> str:
        """Replace tokens with real values. json_escaped=True when text is raw JSON source."""
        if not text or (MARK not in text and MARK_ESC not in text):
            return text

        def swap(m: "re.Match") -> str:
            value = self.vault.reveal(m.group(0).replace(MARK_ESC, MARK))
            if value is None:
                return m.group(0)
            return _json_escape(value) if json_escaped else value

        text = TOKEN_RE.sub(swap, text)
        if json_escaped:
            text = TOKEN_ESC_RE.sub(swap, text)
        return text

    def split_complete(self, text: str, json_escaped: bool = False) -> Tuple[str, str]:
        """Unprotect what is complete; hold back a trailing piece that may be half a token."""
        text = self.unprotect_text(text, json_escaped)
        hold_from = len(text)
        marks = [text.rfind(MARK)]
        if json_escaped:
            marks.append(text.rfind(MARK_ESC))
            # the escaped mark itself may be cut: "...\\u25"
            for n in range(len(MARK_ESC) - 1, 0, -1):
                if text.endswith(MARK_ESC[:n]):
                    hold_from = len(text) - n
                    break
        for p in marks:
            if p < 0 or p >= hold_from:
                continue
            mark_len = len(MARK_ESC) if text.startswith(MARK_ESC, p) else 1
            rest = text[p + mark_len:]
            if len(rest) <= TOKEN_MAX_LEN and _PARTIAL_AFTER_MARK.match(rest):
                hold_from = min(hold_from, p)
        return text[:hold_from], text[hold_from:]

    # -- JSON ---------------------------------------------------------------

    def protect_json(self, data: Any, provider: Optional[str] = None, key: Optional[str] = None) -> Any:
        if isinstance(data, str):
            return data if key in STRUCT_KEYS else self.protect_text(data, provider)
        if isinstance(data, dict):
            if data.get("type") in SIGNED_BLOCKS:
                return data
            return {k: (v if k in SKIP_SUBTREES else self.protect_json(v, provider, k))
                    for k, v in data.items()}
        if isinstance(data, list):
            return [self.protect_json(item, provider, key) for item in data]
        return data

    def unprotect_json(self, data: Any) -> Any:
        if isinstance(data, str):
            return self.unprotect_text(data)
        if isinstance(data, dict):
            if data.get("type") in SIGNED_BLOCKS:
                return data
            return {k: self.unprotect_json(v) for k, v in data.items()}
        if isinstance(data, list):
            return [self.unprotect_json(item) for item in data]
        return data

    # -- bodies -------------------------------------------------------------

    def protect_body(self, body: bytes, provider: Optional[str] = None) -> bytes:
        if not body:
            return body
        try:
            data = json.loads(body)
        except (json.JSONDecodeError, UnicodeDecodeError):
            try:
                return self.protect_text(body.decode("utf-8"), provider).encode("utf-8")
            except UnicodeDecodeError:
                return body  # binary upload: nothing we can scan
        return json.dumps(self.protect_json(data, provider), ensure_ascii=False,
                          separators=(",", ":")).encode("utf-8")

    def unprotect_body(self, body: bytes) -> bytes:
        try:
            data = json.loads(body)
        except (json.JSONDecodeError, UnicodeDecodeError):
            try:
                return self.unprotect_text(body.decode("utf-8")).encode("utf-8")
            except UnicodeDecodeError:
                return body
        return json.dumps(self.unprotect_json(data), ensure_ascii=False).encode("utf-8")


class SSEUnprotector:
    """
    Restores tokens in a Server-Sent Events stream.

    Anthropic: text_delta.text and input_json_delta.partial_json are carried per
    content block, so a token cut in two is restored once its second half arrives,
    and anything still held is flushed before content_block_stop.
    Other providers: each event is restored as a whole.
    """

    DELTA_FIELDS = {"text_delta": ("text", False), "input_json_delta": ("partial_json", True)}

    def __init__(self, courier: Courier):
        self.courier = courier
        self._buf = ""
        self._decoder = codecs.getincrementaldecoder("utf-8")(errors="replace")  # a chunk may cut a character
        self._carry: Dict[Any, str] = {}
        self._carry_type: Dict[Any, str] = {}

    def feed(self, chunk: bytes) -> bytes:
        self._buf += self._decoder.decode(chunk).replace("\r\n", "\n")
        out: List[str] = []
        while "\n\n" in self._buf:
            raw, self._buf = self._buf.split("\n\n", 1)
            out.append(self._event(raw))
        return "".join(out).encode("utf-8")

    def close(self) -> bytes:
        tail, self._buf = self._buf + self._decoder.decode(b"", final=True), ""
        return (self._event(tail) if tail.strip() else "").encode("utf-8")

    # -- internals ----------------------------------------------------------

    def _event(self, raw: str) -> str:
        lines = raw.split("\n")
        data_lines = [l[5:].lstrip(" ") if l.startswith("data:") else None for l in lines]
        payload = "\n".join(d for d in data_lines if d is not None)
        other = [l for l, d in zip(lines, data_lines) if d is None]
        event_name = next((l[6:].strip() for l in other if l.startswith("event:")), None)

        if not payload or payload.strip() == "[DONE]":
            return raw + "\n\n"
        try:
            data = json.loads(payload)
        except json.JSONDecodeError:
            return self._emit(other, self.courier.unprotect_text(payload))

        prefix = ""
        if isinstance(data, dict) and data.get("type") == "content_block_start":
            idx = data.get("index")
            self._carry[idx] = ""
            data = self.courier.unprotect_json(data)
        elif isinstance(data, dict) and data.get("type") == "content_block_delta":
            idx = data.get("index")
            delta = data.get("delta") or {}
            field = self.DELTA_FIELDS.get(delta.get("type"))
            if field:
                name, escaped = field
                ready, held = self.courier.split_complete(self._carry.get(idx, "") + delta.get(name, ""), escaped)
                self._carry[idx] = held
                self._carry_type[idx] = delta.get("type")
                if not ready:
                    return ""   # whole fragment is half a token: wait for the rest
                data = {**data, "delta": {**delta, name: ready}}
            # thinking_delta / signature_delta pass through untouched
        elif isinstance(data, dict) and data.get("type") == "content_block_stop":
            idx = data.get("index")
            held = self._carry.pop(idx, "")
            dtype = self._carry_type.pop(idx, None)
            if held and dtype:
                name, escaped = self.DELTA_FIELDS[dtype]
                flush = {"type": "content_block_delta", "index": idx,
                         "delta": {"type": dtype, name: self.courier.unprotect_text(held, escaped)}}
                prefix = self._emit(["event: content_block_delta"] if event_name else [],
                                    json.dumps(flush, ensure_ascii=False))
        else:
            data = self.courier.unprotect_json(data)

        return prefix + self._emit(other, json.dumps(data, ensure_ascii=False))

    @staticmethod
    def _emit(other_lines: List[str], payload: str) -> str:
        head = "".join(l + "\n" for l in other_lines if l)
        return f"{head}data: {payload}\n\n"
