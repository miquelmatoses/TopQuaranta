"""Staff audit logging (R9 of Phase 9 — Excellence).

Single entry point for every destructive or consequential staff action.
Call sites do ONE line:

    from music.audit import log_staff_action
    log_staff_action(request, "canco_rebutjar", target=canco, motiu=motiu)

Design notes:

- The helper never raises. If logging fails (e.g. DB outage during a write),
  the calling action is NOT blocked. Logging the audit is best-effort; the
  business operation is what matters, and a missed audit entry is better
  than a user-facing 500. The failure is itself logged.
- `actor` is extracted from request.user. If unauthenticated or unavailable,
  it stays None and the action is still recorded.
- `target` can be any Django model instance — we sniff `_meta.model_name`
  and `pk`, and derive a human label from `__str__` (truncated).
"""

from __future__ import annotations

import logging
from typing import Any

from django.db import models

from .models import StaffAuditLog

logger = logging.getLogger(__name__)

_LABEL_MAX = 500
_TYPE_MAX = 30


def log_staff_action(
    request,
    action: str,
    target: models.Model | None = None,
    **metadata: Any,
) -> StaffAuditLog | None:
    """Record a staff action. Returns the created row, or None on failure.

    Arguments:
        request   — Django request (for request.user). May be None for
                    management-command-driven actions.
        action    — one of StaffAuditLog.ACTION_CHOICES keys.
        target    — the primary object the action operates on (optional).
        metadata  — arbitrary JSON-safe kwargs to store as context.
    """
    actor = None
    if request is not None:
        user = getattr(request, "user", None)
        if user is not None and getattr(user, "is_authenticated", False):
            actor = user

    target_type = ""
    target_id = None
    target_label = ""
    if target is not None:
        try:
            target_type = target._meta.model_name[:_TYPE_MAX]
            target_id = getattr(target, "pk", None)
            target_label = str(target)[:_LABEL_MAX]
        except Exception as exc:  # defensive; never let audit break the action
            logger.warning("Audit target introspection failed: %s", exc)

    try:
        return StaffAuditLog.objects.create(
            actor=actor,
            action=action,
            target_type=target_type,
            target_id=target_id,
            target_label=target_label,
            metadata=metadata or None,
        )
    except Exception as exc:
        # Never propagate — the audit is secondary to the action itself.
        logger.exception("Staff audit log write failed: action=%s err=%s",
                         action, exc)
        return None
