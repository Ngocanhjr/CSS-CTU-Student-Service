from app.embedding import embedder


def test_get_embedding_uses_configured_model(monkeypatch):
    monkeypatch.setenv("NVIDIA_API_KEY", "test-key")

    model = embedder.get_embedding()

    assert model.model == embedder.EMBEDDING_MODEL_NAME
