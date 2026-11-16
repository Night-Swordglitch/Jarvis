"""
Human confirmation gate for irreversible actions.

Only the UI's explicit CONFIRM resolution can mint a one-time approval grant.
Grants are bound to one execution ID and consumed by the trusted execution engine.
"""
from __future__ import annotations

import threading
import time
from dataclasses import dataclass
from typing import Callable, Optional

TIMEOUT_SECONDS = 90.0


@dataclass
class _Pending:
    key: str
    title: str
    detail: str
    run: Callable[[], str]
    at: float
    approval_subject: str = ""
    on_rejected: Optional[Callable[[str], None]] = None


_pending: Optional[_Pending] = None
_lock = threading.Lock()
_approval_grants: dict[str, object] = {}

_show_cb: Optional[Callable[[str, str], None]] = None
_hide_cb: Optional[Callable[[], None]] = None
_log_cb: Optional[Callable[[str], None]] = None
_result_cb: Optional[Callable[[str, str, str], None]] = None


def bind(show, hide, log=None, result=None) -> None:
    """Wire this module to the HUD and optional verified-result callback."""
    global _show_cb, _hide_cb, _log_cb, _result_cb
    _show_cb, _hide_cb, _log_cb, _result_cb = show, hide, log, result


def _log(msg: str) -> None:
    if _log_cb:
        try:
            _log_cb(msg)
        except Exception:
            pass


def _reject(pending: _Pending, status: str) -> None:
    if pending.on_rejected:
        try:
            pending.on_rejected(status)
        except Exception as exc:
            _log(f"ERR: Approval status callback failed — {exc}")


def request(
    key: str,
    title: str,
    detail: str,
    run: Callable[[], str],
    *,
    approval_subject: str = "",
    on_rejected: Optional[Callable[[str], None]] = None,
) -> str:
    """Queue a confirmation; approval_subject binds a grant to one execution."""
    global _pending

    if not callable(run):
        raise TypeError("run must be callable")
    if approval_subject and not isinstance(approval_subject, str):
        raise TypeError("approval_subject must be a string")

    if _show_cb is None:
        return (
            f"I cannot confirm '{title}' because the interface is unavailable; "
            "nothing was done."
        )

    with _lock:
        if _pending is not None and time.monotonic() - _pending.at <= TIMEOUT_SECONDS:
            return "There is already a confirmation waiting on screen. Answer it first."
        expired, _pending = _pending, None
        _pending = _Pending(
            key=key, title=title, detail=detail, run=run,
            at=time.monotonic(), approval_subject=approval_subject,
            on_rejected=on_rejected,
        )

    if expired is not None:
        _reject(expired, "EXPIRED")

    try:
        _show_cb(title, detail)
    except Exception as exc:
        with _lock:
            if _pending and _pending.key == key:
                failed, _pending = _pending, None
            else:
                failed = None
        if failed:
            _reject(failed, "DENIED")
        return f"Could not ask for confirmation: {exc}. Nothing was done."

    _log(f"SYS: Awaiting confirmation — {title}")
    return (
        f"[CONFIRMATION_PENDING] Confirmation is required on the HUD for: {title}. "
        "Do not claim the action is complete."
    )


def resolve(accepted: bool) -> None:
    """Resolve the active HUD prompt; only acceptance issues a one-use grant."""
    global _pending

    if not isinstance(accepted, bool):
        raise TypeError("accepted must be a boolean")

    with _lock:
        pending, _pending = _pending, None

    if _hide_cb:
        try:
            _hide_cb()
        except Exception:
            pass

    if pending is None:
        return

    if time.monotonic() - pending.at > TIMEOUT_SECONDS:
        _reject(pending, "EXPIRED")
        _log(f"SYS: Confirmation expired — {pending.title}")
        return

    if not accepted:
        _reject(pending, "REJECTED")
        _log(f"SYS: Cancelled — {pending.title}")
        return

    if pending.approval_subject:
        with _lock:
            # A unique execution ID cannot overwrite an unconsumed grant.
            if pending.approval_subject in _approval_grants:
                _reject(pending, "DENIED")
                _log(f"ERR: Duplicate approval grant refused — {pending.title}")
                return
            _approval_grants[pending.approval_subject] = object()

    def _worker():
        try:
            result = pending.run() or "Done."
            if _result_cb:
                try:
                    _result_cb(pending.key, pending.title, str(result))
                except Exception:
                    pass
            _log(f"SYS: Confirmed — {pending.title}. {result}")
        except Exception as exc:
            _log(f"ERR: {pending.title} failed — {exc}")

    threading.Thread(
        target=_worker, daemon=True, name=f"confirm-{pending.key}"
    ).start()


def consume_approval(execution_id: str) -> bool:
    """Consume the one-time grant issued by a successful human HUD decision."""
    if not isinstance(execution_id, str) or not execution_id:
        return False
    with _lock:
        return _approval_grants.pop(execution_id, None) is not None


def revoke_approval(execution_id: str) -> None:
    """Discard any unconsumed grant for an execution."""
    if isinstance(execution_id, str) and execution_id:
        with _lock:
            _approval_grants.pop(execution_id, None)


def pending_title() -> str:
    """Return the active, non-expired confirmation title."""
    global _pending
    with _lock:
        if _pending is None:
            return ""
        if time.monotonic() - _pending.at > TIMEOUT_SECONDS:
            expired, _pending = _pending, None
        else:
            return _pending.title
    if expired is not None:
        _reject(expired, "EXPIRED")
        _log(f"SYS: Confirmation expired — {expired.title}")
    return ""
