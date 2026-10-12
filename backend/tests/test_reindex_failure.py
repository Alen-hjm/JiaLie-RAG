from types import SimpleNamespace

from scripts import reindex_embeddings as script


def test_dry_run_never_opens_database_for_index(monkeypatch):
    monkeypatch.setattr(script, "engine", None)
    script.rebuild_index(dry_run=True, drop_first=True)


def test_failed_batch_keeps_index_pending(tmp_path, monkeypatch):
    class Session:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

        def scalar(self, query):
            return 1

        def scalars(self, query):
            return [SimpleNamespace(id="chunk-1", content="fictional resume")]

        def commit(self):
            pass

    class FailingModel:
        def __init__(self, db):
            pass

        def embed(self, texts):
            raise RuntimeError("unavailable")

    monkeypatch.setattr(script.sys, "argv", ["reindex", "--force"])
    monkeypatch.setattr(script, "get_settings", lambda: SimpleNamespace(
        embedding_provider="custom", embedding_model="embed", embedding_dimensions=3,
        embedding_uses_remote=True, embedding_is_placeholder=False))
    monkeypatch.setattr(script, "engine", SimpleNamespace(dialect=SimpleNamespace(name="sqlite")))
    monkeypatch.setattr(script, "SessionLocal", Session)
    monkeypatch.setattr(script, "ModelService", FailingModel)
    monkeypatch.setattr(script, "resize_column", lambda *args: None)
    monkeypatch.setattr(script, "null_mismatched_dimensions", lambda *args: 0)
    monkeypatch.setattr(script, "pending_chunk_ids", lambda *args: ["chunk-1"])
    monkeypatch.setattr(script, "SIGNATURE_FILE", tmp_path / "signature")
    monkeypatch.setattr(script, "FAILED_FILE", tmp_path / "failed.json")
    script.write_signature("custom:old-model:3")
    assert script.main() == 1
    assert script.read_signature() == "pending-reindex"
    assert "chunk-1" in script.FAILED_FILE.read_text()
