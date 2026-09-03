"""Conflict resolution for matching candidates."""
from collections import defaultdict
from decimal import Decimal
import uuid

from app.matching.scorer import MatchStatus, ScoredMatch


class ConflictResolver:
    """Detects and resolves 1-to-N or N-to-1 candidate collisions."""

    def resolve_conflicts(self, matches: list[ScoredMatch]) -> list[ScoredMatch]:
        """
        Ensures 1-to-1 relationship integrity:
        - If multiple matches claim the same payment_id: keep highest confidence, demote others to CONFLICT.
        - If multiple matches claim the same ledger_entry_id: keep highest confidence, demote others to CONFLICT.
        - If confidence scores are identical, mark all colliding entries as CONFLICT for human review.
        """
        if not matches:
            return []

        resolved: list[ScoredMatch] = []

        # Check ledger_entry_id collisions
        ledger_claims: dict[uuid.UUID, list[ScoredMatch]] = defaultdict(list)
        for m in matches:
            if m.ledger_entry_id is not None:
                ledger_claims[m.ledger_entry_id].append(m)
            else:
                resolved.append(m)

        for ledger_id, claimants in ledger_claims.items():
            if len(claimants) == 1:
                resolved.append(claimants[0])
            else:
                # Multiple matches claimed this ledger entry
                # Sort descending by confidence
                sorted_claimants = sorted(claimants, key=lambda x: x.confidence, reverse=True)
                top = sorted_claimants[0]
                runner_up = sorted_claimants[1]

                # If confidence is tied or margin is negligibly small (< 0.05)
                if top.confidence == runner_up.confidence or (top.confidence - runner_up.confidence) < Decimal("0.05"):
                    # Both are in conflict!
                    for c in claimants:
                        c.match_status = MatchStatus.CONFLICT
                        c.reasons.append(
                            f"Ambiguous match conflict: {len(claimants)} payments claimed ledger entry {ledger_id} with similar confidence"
                        )
                        resolved.append(c)
                else:
                    # Clear winner
                    resolved.append(top)
                    for loser in sorted_claimants[1:]:
                        loser.match_status = MatchStatus.CONFLICT
                        loser.reasons.append(
                            f"Conflict: Superseded by higher confidence match ({top.confidence} vs {loser.confidence})"
                        )
                        resolved.append(loser)

        # Check payment_id collisions
        payment_claims: dict[uuid.UUID, list[ScoredMatch]] = defaultdict(list)
        final_list: list[ScoredMatch] = []
        for m in resolved:
            if m.payment_id is not None:
                payment_claims[m.payment_id].append(m)
            else:
                final_list.append(m)

        for payment_id, claimants in payment_claims.items():
            if len(claimants) == 1:
                final_list.append(claimants[0])
            else:
                sorted_claimants = sorted(claimants, key=lambda x: x.confidence, reverse=True)
                top = sorted_claimants[0]
                runner_up = sorted_claimants[1]

                if top.confidence == runner_up.confidence or (top.confidence - runner_up.confidence) < Decimal("0.05"):
                    for c in claimants:
                        c.match_status = MatchStatus.CONFLICT
                        c.reasons.append(
                            f"Ambiguous match conflict: Payment {payment_id} matched multiple ledger entries with similar confidence"
                        )
                        final_list.append(c)
                else:
                    final_list.append(top)
                    for loser in sorted_claimants[1:]:
                        loser.match_status = MatchStatus.CONFLICT
                        loser.reasons.append(
                            f"Conflict: Superseded by higher confidence match ({top.confidence} vs {loser.confidence})"
                        )
                        final_list.append(loser)

        return final_list
