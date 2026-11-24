import pytest


def chat(client, session, message, **kwargs):
    return client.post("/chat", json={"session_id": session, "message": message}, **kwargs)


def test_health(client):
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok", "keys_configured": 2, "cache_enabled": True}


def test_live_then_cache_across_sessions(client):
    first = chat(client, "s-1", "What is the capital of France?").json()
    second = chat(client, "s-2", "What is the capital of France?").json()

    assert first["metadata"]["resolution_source"] == "LIVE_INFERENCE"
    assert first["metadata"]["key_id"] == "key_1"
    assert second["metadata"]["resolution_source"] == "LLM_CACHE"
    assert second["metadata"]["key_id"] is None
    assert second["metadata"]["fallback_attempts"] == 0
    assert second["reply"] == first["reply"]
    assert second["metadata"]["input_tokens"] == first["metadata"]["input_tokens"]
    assert second["metadata"]["output_tokens"] == first["metadata"]["output_tokens"]


def test_different_message_is_never_cached(client):
    chat(client, "s-1", "alpha question")
    other = chat(client, "s-2", "beta question").json()
    assert other["metadata"]["resolution_source"] == "LIVE_INFERENCE"


def test_latency_is_integer(client):
    meta = chat(client, "s-1", "hello").json()["metadata"]
    assert isinstance(meta["latency_ms"], int) and meta["latency_ms"] >= 1


def test_multi_turn_history_is_sent_and_stored(client, provider):
    chat(client, "s-1", "My name is Asha")
    chat(client, "s-1", "What is my name?")

    sent = provider.calls[-1][1]
    assert [m["role"] for m in sent] == ["system", "user", "assistant", "user", "assistant", "user"][:len(sent)]
    assert sent[1]["content"] == "My name is Asha"
    assert sent[-1]["content"] == "What is my name?"

    stored = client.get("/sessions/s-1/messages").json()
    assert stored["session_id"] == "s-1"
    assert [m["role"] for m in stored["messages"]] == ["user", "assistant", "user", "assistant"]
    assert "metadata" not in stored["messages"][0]
    assert stored["messages"][1]["metadata"]["resolution_source"] == "LIVE_INFERENCE"
    assert all(m["role"] != "system" for m in stored["messages"])


def test_sessions_are_separate(client):
    chat(client, "a", "first for a")
    chat(client, "b", "first for b")
    assert len(client.get("/sessions/a/messages").json()["messages"]) == 2
    assert client.get("/sessions/b/messages").json()["messages"][0]["content"] == "first for b"


def test_tokens_are_per_request_not_cumulative(client):
    first = chat(client, "s-1", "tell me a fact").json()["metadata"]
    chat(client, "s-1", "tell me another")
    fresh = chat(client, "s-2", "tell me a fact").json()["metadata"]
    # Same first message in a new session reports the same per-request usage.
    assert fresh["input_tokens"] == first["input_tokens"]
    assert fresh["output_tokens"] == first["output_tokens"]


def test_custom_system_prompt_is_used_and_remembered(client, provider):
    client.post("/chat", json={"session_id": "s-1", "message": "hi", "system_prompt": "Speak like a pirate"})
    chat(client, "s-1", "again")
    assert provider.calls[-1][1][0] == {"role": "system", "content": "Speak like a pirate"}


def test_unknown_session_404(client):
    r = client.get("/sessions/nope/messages")
    assert r.status_code == 404
    assert r.json() == {"detail": "session not found"}


@pytest.mark.parametrize(
    "payload",
    [
        {"session_id": "s", "message": ""},
        {"session_id": "s", "message": "   "},
        {"session_id": "", "message": "hi"},
        {"message": "hi"},
        {"session_id": "s"},
        {"session_id": "s", "message": "x" * 4001},
        {"session_id": "s" * 129, "message": "hi"},
    ],
)
def test_validation_errors_are_422_and_not_stored(client, payload):
    r = client.post("/chat", json=payload)
    assert r.status_code == 422
    assert "detail" in r.json()
    assert client.get("/sessions/s/messages").status_code == 404


def test_malformed_json_is_422(client):
    r = client.post("/chat", content="{not json", headers={"Content-Type": "application/json"})
    assert r.status_code == 422
    assert "detail" in r.json()


def test_message_is_trimmed(client):
    chat(client, "s-1", "   hello   ")
    assert client.get("/sessions/s-1/messages").json()["messages"][0]["content"] == "hello"


# ---- failover ----
@pytest.mark.parametrize("header", ["key_1=429", "key_1=500", "key_1=502", "key_1=503"])
def test_simulated_failure_falls_over_to_key_2(client, header):
    r = chat(client, "s-1", "unique " + header, headers={"X-Simulate-Failure": header})
    assert r.status_code == 200
    meta = r.json()["metadata"]
    assert meta["key_id"] == "key_2"
    assert meta["fallback_attempts"] == 1
    assert meta["resolution_source"] == "LIVE_INFERENCE"
    assert not r.json()["reply"].lower().startswith("error")


def test_simulated_failure_of_both_keys_is_503_and_not_stored(client):
    r = chat(client, "s-1", "hello", headers={"X-Simulate-Failure": "*=429"})
    assert r.status_code == 503
    assert r.json() == {"detail": "all providers unavailable"}
    assert client.get("/sessions/s-1/messages").status_code == 404


def test_explicit_pairs_fail_all_keys(client):
    r = chat(client, "s-1", "hello", headers={"X-Simulate-Failure": "key_1=429,key_2=500"})
    assert r.status_code == 503


def test_simulated_requests_bypass_cache(client):
    chat(client, "s-1", "cached question")
    r = chat(client, "s-2", "cached question", headers={"X-Simulate-Failure": "key_1=429"})
    assert r.json()["metadata"]["resolution_source"] == "LIVE_INFERENCE"
    assert r.json()["metadata"]["key_id"] == "key_2"


def test_simulation_header_ignored_when_disabled(make_client):
    client = make_client(simulation=False)
    r = chat(client, "s-1", "hello", headers={"X-Simulate-Failure": "*=429"})
    assert r.status_code == 200
    assert r.json()["metadata"]["key_id"] == "key_1"


def test_real_provider_error_falls_over(client, provider):
    provider.failing_keys["k1"] = RuntimeError("429 quota exceeded")
    r = chat(client, "s-1", "real failure")
    assert r.status_code == 200
    assert r.json()["metadata"]["key_id"] == "key_2"
    assert r.json()["metadata"]["fallback_attempts"] == 1


def test_all_real_keys_failing_is_clean_503(client, provider):
    provider.failing_keys.update({"k1": RuntimeError("boom"), "k2": RuntimeError("boom")})
    r = chat(client, "s-1", "everything down")
    assert r.status_code == 503
    assert r.json() == {"detail": "all providers unavailable"}
