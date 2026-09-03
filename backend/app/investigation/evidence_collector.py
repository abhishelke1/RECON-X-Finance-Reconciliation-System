"""Evidence Collector for compiling end-to-end audit dossiers for exceptions."""
from typing import Any
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.exception import Exception_, ExceptionEvidence
from app.models.reconciliation import ReconciliationMatch
from app.models.payment import Payment
from app.models.order import Order
from app.models.settlement import Settlement
from app.models.refund import Refund
from app.models.chargeback import Chargeback
from app.models.ledger_entry import LedgerEntry
from app.investigation.evidence_graph import EvidenceGraph


class EvidenceCollector:
    """Collects and organizes all contextual evidence surrounding a reconciliation exception."""

    async def collect_evidence(self, db: AsyncSession, exception_id: uuid.UUID) -> EvidenceGraph:
        """
        Retrieves all evidence snapshots and database entities tied to an exception,
        building a connected causality graph.
        """
        exc = await db.get(Exception_, exception_id)
        if not exc:
            raise ValueError(f"Exception {exception_id} not found")

        graph = EvidenceGraph(exception_id=exception_id)

        # 1. Fetch persisted evidence snapshots
        stmt = select(ExceptionEvidence).where(ExceptionEvidence.exception_id == exception_id)
        evidence_records = (await db.execute(stmt)).scalars().all()

        for ev in evidence_records:
            node_id = f"{ev.record_type}_{ev.record_id}"
            graph.add_node(
                node_id=node_id,
                entity_type=ev.evidence_type,
                data=ev.data_snapshot,
                label=f"{ev.relationship or ev.evidence_type}",
            )

        # 2. Fetch the associated ReconciliationMatch
        if exc.match_id:
            match = await db.get(ReconciliationMatch, exc.match_id)
            if match:
                match_node_id = f"match_{match.id}"
                graph.add_node(
                    node_id=match_node_id,
                    entity_type="reconciliation_match",
                    data={
                        "match_status": match.match_status,
                        "confidence": str(match.match_confidence),
                        "recon_status": match.recon_status,
                        "expected_amount": str(match.expected_amount) if match.expected_amount else None,
                        "actual_amount": str(match.actual_amount) if match.actual_amount else None,
                        "variance": str(match.variance) if match.variance else None,
                        "reasons": match.match_reasons,
                    },
                    label=f"Match ({match.match_status})",
                )

                # Fetch and connect primary entities
                if match.payment_id:
                    pay = await db.get(Payment, match.payment_id)
                    if pay:
                        p_id = f"payment_{pay.id}"
                        graph.add_node(
                            node_id=p_id,
                            entity_type="payment",
                            data={
                                "source_id": pay.source_id,
                                "amount": str(pay.amount),
                                "fee": str(pay.fee) if pay.fee else "0.0000",
                                "tax": str(pay.tax) if pay.tax else "0.0000",
                                "status": pay.status,
                                "method": pay.method,
                                "customer_email": pay.customer_email,
                                "timestamp": pay.payment_timestamp.isoformat(),
                            },
                            label=f"Payment {pay.source_id}",
                        )
                        graph.add_edge(p_id, match_node_id, "subject_of_match")

                        # If payment has order
                        if pay.order_source_id:
                            order_stmt = select(Order).where(
                                Order.merchant_id == pay.merchant_id,
                                Order.source_id == pay.order_source_id,
                            )
                            ord_res = (await db.execute(order_stmt)).scalar_one_or_none()
                            if ord_res:
                                o_id = f"order_{ord_res.id}"
                                graph.add_node(
                                    node_id=o_id,
                                    entity_type="order",
                                    data={
                                        "source_id": ord_res.source_id,
                                        "amount": str(ord_res.amount),
                                        "receipt": ord_res.receipt,
                                        "status": ord_res.status,
                                    },
                                    label=f"Order {ord_res.source_id}",
                                )
                                graph.add_edge(p_id, o_id, "fulfills_order")

                if match.ledger_entry_id:
                    ledg = await db.get(LedgerEntry, match.ledger_entry_id)
                    if ledg:
                        l_id = f"ledger_{ledg.id}"
                        graph.add_node(
                            node_id=l_id,
                            entity_type="ledger_entry",
                            data={
                                "source_id": ledg.source_id,
                                "amount": str(ledg.amount),
                                "type": ledg.entry_type,
                                "reference_id": ledg.reference_id,
                                "description": ledg.description,
                                "timestamp": ledg.entry_timestamp.isoformat(),
                            },
                            label=f"Ledger {ledg.source_id}",
                        )
                        graph.add_edge(l_id, match_node_id, "reconciles_match")

        return graph

    @staticmethod
    def extract_ground_truth_entities(graph: EvidenceGraph) -> set[str]:
        """
        Extracts all canonical identifiers, monetary amounts, and keys from the graph
        to validate that AI outputs do NOT hallucinate non-existent IDs or values.
        """
        allowed: set[str] = set()
        for node in graph.nodes:
            allowed.add(node.id)
            for k, v in node.data.items():
                if v is not None:
                    allowed.add(str(v).strip())
                    if isinstance(v, list):
                        for item in v:
                            allowed.add(str(item).strip())
        return allowed
