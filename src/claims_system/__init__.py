"""Mock claims system of record.

Stands in for a real insurer's claims platform. It serves policy, prior-claim
and repair-benchmark lookups, and accepts claim decisions **only** when the
request carries an approval token minted by a human through the orchestrator.
"""

__version__ = "0.1.0"
