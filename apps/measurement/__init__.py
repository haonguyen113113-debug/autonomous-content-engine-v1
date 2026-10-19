"""Economic-truth layer (PROJECT_SPEC section 11).

Platform estimates are never treated as realized cash::

    artifact -> distribution -> audience response -> conversion
        -> platform earnings -> actual payout -> verified cash received
"""

from .ledger import (
    PAYOUT_KIND,
    PayoutRecord,
    ObservationRecord,
    record_observation,
    record_payout,
    summarize_by_channel,
    summarize_by_run,
)
from .lifecycle import STATES, classify_lifecycle

__all__ = [
    "ObservationRecord",
    "PAYOUT_KIND",
    "PayoutRecord",
    "STATES",
    "classify_lifecycle",
    "record_observation",
    "record_payout",
    "summarize_by_channel",
    "summarize_by_run",
]
