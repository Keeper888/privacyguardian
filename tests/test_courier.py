"""
Courier tests: one block per issue (#16-#24), ending with the end-to-end test.
No network: the upstream provider is an httpx.MockTransport.
"""

import hashlib
import json
import tempfile
import time
from pathlib import Path

import httpx
import pytest
from fastapi.testclient import TestClient

from courier import Courier, SSEUnprotector
from guardian_proxy import PrivacyGuardianProxy, create_app
from pii_detector import PIIDetector
from vault import TokenVault, TOKEN_RE

EMAIL = "mario.rossi@example.org"
IBAN = "IT60X0542811101000000123456"
API_KEY = "sk-ant-api03-" + "Ab3dE6gH9jK2mN5pQ8sT1vW4yZ7" * 2
SSN = "123-45-6789"


def make_courier(tmp=None) -> Courier:
    d = Path(tmp or tempfile.mkdtemp(prefix="pg-c-"))
    return Courier(vault=TokenVault(d), detector=PIIDetector(use_nlp=False))


def token_of(courier: Courier, value: str) -> str:
    out = courier.protect_text(f"x {value} y")
    m = TOKEN_RE.search(out)
    assert m, f"no token for {value!r}: {out}"
    return m.group(0)


# -- #16 salt ---------------------------------------------------------------

def test_tokens_differ_between_installs():
    a, b = make_courier(), make_courier()
    assert token_of(a, EMAIL) != token_of(b, EMAIL)


def test_token_is_stable_within_an_install():
    c = make_courier()
    assert token_of(c, EMAIL) == token_of(c, EMAIL)


def test_ssn_cannot_be_brute_forced_without_the_key():
    c = make_courier()
    tok = token_of(c, SSN)
    digest = tok.split("_")[-1].rstrip("\u25c8")
    # The old scheme: sha256(value)[:12]. Guessing the right SSN must not hit the token.
    for guess in (SSN, SSN.replace("-", "")):
        assert hashlib.sha256(guess.encode()).hexdigest()[:12] not in digest
        assert hashlib.sha256(guess.encode()).hexdigest()[:16] != digest


def test_vault_file_holds_no_plaintext():
    d = tempfile.mkdtemp(prefix="pg-c-")
    c = make_courier(d)
    c.protect_text(f"mail {EMAIL}")
    c.vault.conn.commit()
    raw = (Path(d) / "courier.db").read_bytes()
    assert EMAIL.encode() not in raw


# -- #17 one upstream call --------------------------------------------------

def sse(*events) -> bytes:
    return "".join(f"event: {e['type']}\ndata: {json.dumps(e, ensure_ascii=False)}\n\n" for e in events).encode()


def stream_events(blocks):
    """blocks: list of (block_type, [fragments])"""
    ev = [{"type": "message_start", "message": {"id": "m1", "type": "message", "role": "assistant",
                                                 "content": [], "model": "x", "usage": {}}}]
    for i, (btype, frags) in enumerate(blocks):
        if btype == "text":
            ev.append({"type": "content_block_start", "index": i, "content_block": {"type": "text", "text": ""}})
            ev += [{"type": "content_block_delta", "index": i, "delta": {"type": "text_delta", "text": f}} for f in frags]
        else:
            ev.append({"type": "content_block_start", "index": i,
                       "content_block": {"type": "tool_use", "id": "t1", "name": "Edit", "input": {}}})
            ev += [{"type": "content_block_delta", "index": i,
                    "delta": {"type": "input_json_delta", "partial_json": f}} for f in frags]
        ev.append({"type": "content_block_stop", "index": i})
    ev += [{"type": "message_delta", "delta": {"stop_reason": "end_turn"}, "usage": {}},
           {"type": "message_stop"}]
    return ev


def rebuild(stream_bytes: bytes):
    """What a client reconstructs from the stream: {index: text or parsed tool input}."""
    out, kinds = {}, {}
    for raw in stream_bytes.decode().split("\n\n"):
        data = [l[6:] for l in raw.split("\n") if l.startswith("data: ")]
        if not data:
            continue
        e = json.loads(data[0])
        if e["type"] == "content_block_start":
            kinds[e["index"]] = e["content_block"]["type"]
            out[e["index"]] = ""
        elif e["type"] == "content_block_delta":
            d = e["delta"]
            out[e["index"]] += d.get("text", d.get("partial_json", ""))
    return {i: (json.loads(v) if kinds[i] == "tool_use" else v) for i, v in out.items()}


class Upstream:
    """Mock provider: records what it receives, answers with a canned stream."""

    def __init__(self, reply):
        self.reply = reply
        self.received = []

    async def __call__(self, request: httpx.Request) -> httpx.Response:
        body = await request.aread()
        self.received.append(body)
        reply = self.reply(json.loads(body)) if callable(self.reply) else self.reply
        if isinstance(reply, bytes):
            return httpx.Response(200, content=reply, headers={"content-type": "text/event-stream"})
        return httpx.Response(200, json=reply)


def app_with(upstream: Upstream, courier: Courier):
    proxy = PrivacyGuardianProxy(courier=courier, transport=httpx.MockTransport(upstream))
    return proxy, TestClient(create_app(proxy))


def test_streamed_request_goes_upstream_once():
    c = make_courier()
    up = Upstream(sse(*stream_events([("text", ["hi"])])))
    proxy, client = app_with(up, c)
    with client:
        r = client.post("/v1/messages", json={"model": "m", "stream": True,
                                               "messages": [{"role": "user", "content": "hello"}]})
    assert r.status_code == 200
    assert len(up.received) == 1
    assert proxy.upstream_calls == 1


# -- #18 split tokens -------------------------------------------------------

@pytest.mark.parametrize("kind", ["text", "tool"])
def test_token_split_at_every_offset_is_restored(kind):
    c = make_courier()
    tok = token_of(c, EMAIL)
    if kind == "text":
        whole = f"Write to {tok} now"
    else:
        whole = json.dumps({"file_path": "/tmp/a.txt", "new_string": f"mail: {tok}"}, ensure_ascii=False)
    for cut in range(1, len(whole)):
        sp = SSEUnprotector(c)
        frags = [whole[:cut], whole[cut:]]
        stream = sse(*stream_events([(kind if kind == "text" else "tool_use", frags)]))
        got = rebuild(sp.feed(stream) + sp.close())[0]
        if kind == "text":
            assert got == f"Write to {EMAIL} now", f"cut={cut}"
        else:
            assert got["new_string"] == f"mail: {EMAIL}", f"cut={cut}"


def test_escaped_token_in_tool_json_is_restored_with_json_escaping():
    c = make_courier()
    secret_path = r"C:\Users\mario\.ssh\id_rsa"
    tok = token_of(c, secret_path)
    whole = json.dumps({"file_path": tok})            # ensure_ascii -> \u25c8 form
    assert "\\u25c8" in whole
    sp = SSEUnprotector(c)
    stream = sse(*stream_events([("tool_use", [whole[:7], whole[7:20], whole[20:]])]))
    got = rebuild(sp.feed(stream) + sp.close())[0]
    assert got["file_path"] == secret_path


def test_stream_split_across_network_chunks():
    c = make_courier()
    tok = token_of(c, EMAIL)
    stream = sse(*stream_events([("text", [f"a {tok} b"])]))
    sp = SSEUnprotector(c)
    out = b"".join(sp.feed(stream[i:i + 7]) for i in range(0, len(stream), 7)) + sp.close()
    assert rebuild(out)[0] == f"a {EMAIL} b"


# -- #19 deny by default ----------------------------------------------------

def claude_code_history():
    return {
        "model": "claude-x",
        "system": f"You are a coding agent. User mail {EMAIL}",
        "tools": [{"name": "Bash", "description": "run", "input_schema": {"type": "object"}}],
        "messages": [
            {"role": "user", "content": [{"type": "text", "text": "fix my config"}]},
            {"role": "assistant", "content": [
                {"type": "thinking", "thinking": "plan", "signature": "sig=="},
                {"type": "tool_use", "id": "t1", "name": "Bash",
                 "input": {"command": f"grep {EMAIL} config.ini"}},
                {"type": "tool_use", "id": "t2", "name": "Edit",
                 "input": {"file_path": "config.ini", "old_string": f"iban={IBAN}", "new_string": f"key={API_KEY}"}},
            ]},
            {"role": "user", "content": [
                {"type": "tool_result", "tool_use_id": "t1", "content": f"config.ini: owner={EMAIL}"}]},
        ],
    }


def test_no_real_value_leaves_in_any_field():
    c = make_courier()
    out = c.protect_body(json.dumps(claude_code_history()).encode()).decode()
    for v in (EMAIL, IBAN, API_KEY):
        assert v not in out, f"{v} leaked"
    data = json.loads(out)
    assert data["messages"][1]["content"][0] == {"type": "thinking", "thinking": "plan", "signature": "sig=="}
    assert data["tools"] == claude_code_history()["tools"]
    assert data["model"] == "claude-x"


# -- #22 speed --------------------------------------------------------------

def test_unprotect_does_not_scale_with_vault_size():
    c = make_courier()
    for i in range(2000):
        c.vault.protect(f"user{i}@example.org", "EMAIL")
    tok = token_of(c, EMAIL)
    t = time.perf_counter()
    for _ in range(1000):
        c.unprotect_text(f"chunk with {tok} inside")
    assert time.perf_counter() - t < 0.5


# -- #24 end to end ---------------------------------------------------------

def test_end_to_end_real_data_stays_home():
    """
    A file with an email, an IBAN and an API key is read by the agent, sent as a
    tool_result, and the AI answers with an Edit that copies the tokens into a
    new file, split across stream events. Upstream must see none of the values;
    the client must get all of them back.
    """
    c = make_courier()
    file_text = f"owner={EMAIL}\niban={IBAN}\nkey={API_KEY}\n"

    def provider(req_json):
        seen = json.dumps(req_json, ensure_ascii=False)
        toks = TOKEN_RE.findall(seen)
        assert len(toks) >= 3, "provider should see tokens"
        full = [m.group(0) for m in TOKEN_RE.finditer(seen)]
        new = "\n".join(dict.fromkeys(full))
        edit = json.dumps({"file_path": "copy.txt", "content": new}, ensure_ascii=False)
        n = len(edit) // 5
        return sse(*stream_events([("text", ["Copying ", full[0][:9], full[0][9:], " and friends"]),
                                   ("tool_use", [edit[i:i + n] for i in range(0, len(edit), n)])]))

    up = Upstream(provider)
    proxy, client = app_with(up, c)
    first = {"model": "m", "stream": True, "messages": [
        {"role": "user", "content": "copy the config"},
        {"role": "assistant", "content": [{"type": "tool_use", "id": "r1", "name": "Read",
                                           "input": {"file_path": "config.ini"}}]},
        {"role": "user", "content": [{"type": "tool_result", "tool_use_id": "r1", "content": file_text}]},
    ]}
    with client:
        r = client.post("/v1/messages", json=first)
        got = rebuild(r.content)

        # upstream saw no real value
        for v in (EMAIL, IBAN, API_KEY):
            assert v.encode() not in up.received[0], f"{v} went upstream"
        assert len(up.received) == 1

        # client got the real values back, in text and in the tool input
        assert got[0].startswith(f"Copying {EMAIL}")
        for v in (EMAIL, IBAN, API_KEY):
            assert v in got[1]["content"]

        # next turn: the real values are now in history and must still not leave
        second = dict(first)
        second["messages"] = first["messages"] + [
            {"role": "assistant", "content": [{"type": "text", "text": got[0]},
                                              {"type": "tool_use", "id": "w1", "name": "Write", "input": got[1]}]},
            {"role": "user", "content": [{"type": "tool_result", "tool_use_id": "w1", "content": "ok"}]},
        ]
        client.post("/v1/messages", json=second)
    for v in (EMAIL, IBAN, API_KEY):
        assert v.encode() not in up.received[1], f"{v} leaked on turn 2"
