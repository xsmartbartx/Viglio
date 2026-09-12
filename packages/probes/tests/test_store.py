from vigilo_probes.seal import seal
from vigilo_probes.store import LocalFileEvidenceStore


def test_local_store_round_trips_a_bundle(tmp_path):
    store = LocalFileEvidenceStore(tmp_path)
    bundle = seal("https://example.com", None, None, None)

    path = store.save(bundle)
    assert path.endswith(f"{bundle.bundle_id}.json")

    loaded = store.load(bundle.bundle_id)
    assert loaded.bundle_id == bundle.bundle_id
    assert loaded.target_origin == bundle.target_origin


def test_local_store_shards_by_id_prefix(tmp_path):
    store = LocalFileEvidenceStore(tmp_path)
    bundle = seal("https://example.com", None, None, None)
    store.save(bundle)

    shard_dir = tmp_path / bundle.bundle_id[:2]
    assert shard_dir.is_dir()
    assert (shard_dir / f"{bundle.bundle_id}.json").is_file()
