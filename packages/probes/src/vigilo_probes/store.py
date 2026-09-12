"""Evidence storage. `LocalFileEvidenceStore` is Phase 1's implementation —
content-addressed, git-style sharded, local filesystem only. Object-store
(S3/MinIO) wiring per docs/architecture.md §5 is Phase 3; this module's
`EvidenceStore` protocol is the seam that swap happens behind.
"""

from __future__ import annotations

from pathlib import Path
from typing import Protocol

from vigilo_core.evidence import EvidenceBundle


class EvidenceStore(Protocol):
    def save(self, bundle: EvidenceBundle) -> str: ...
    def load(self, bundle_id: str) -> EvidenceBundle: ...


class LocalFileEvidenceStore:
    def __init__(self, root: Path | str) -> None:
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)

    def _path_for(self, bundle_id: str) -> Path:
        shard = bundle_id[:2]
        return self.root / shard / f"{bundle_id}.json"

    def save(self, bundle: EvidenceBundle) -> str:
        path = self._path_for(bundle.bundle_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(bundle.model_dump_json(indent=2), encoding="utf-8")
        return str(path)

    def load(self, bundle_id: str) -> EvidenceBundle:
        path = self._path_for(bundle_id)
        return EvidenceBundle.model_validate_json(path.read_text(encoding="utf-8"))
