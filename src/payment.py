from __future__ import annotations

from typing import Tuple


def process(method: str, amount_cents: int) -> Tuple[str, str | None]:
    """Mock payment processor.

    Returns (status, ref) where status is 'APPROVED' or 'DECLINED'.
    Deterministic decline if method == 'DECLINE_TEST'.
    """
    if method == "DECLINE_TEST":
        return ("DECLINED", None)
    # trivial 'approval' path with a fake reference
    return ("APPROVED", f"REF-{method}-{amount_cents}")
