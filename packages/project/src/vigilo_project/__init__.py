"""Vigilo project: projects, targets, ownership proofs (docs/modules.md §2b).

Depends on core + persistence + identity (for the `accounts.id` FK type).
"""

from __future__ import annotations

from vigilo_project.models import OwnershipProof, Project
from vigilo_project.repository import (
    create_target,
    get_or_create_default_project,
    get_ownership_proof,
    get_target,
    get_target_by_origin,
    has_valid_ownership_proof,
    issue_ownership_proof,
    mark_proof_verified,
    set_opt_out,
)

__all__ = [
    "Project",
    "OwnershipProof",
    "get_or_create_default_project",
    "create_target",
    "get_target",
    "get_target_by_origin",
    "set_opt_out",
    "issue_ownership_proof",
    "get_ownership_proof",
    "has_valid_ownership_proof",
    "mark_proof_verified",
]
