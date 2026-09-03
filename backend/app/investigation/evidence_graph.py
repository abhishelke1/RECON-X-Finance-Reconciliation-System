"""Structured Evidence Graph data structure for exception investigation."""
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any
import uuid


@dataclass
class EvidenceNode:
    id: str
    entity_type: str  # payment, order, settlement, refund, chargeback, ledger_entry, calculation
    data: dict[str, Any]
    label: str


@dataclass
class EvidenceEdge:
    source_id: str
    target_id: str
    relation: str  # e.g. "order_of", "settles", "refunds", "disputes", "reconciled_with", "variance_of"
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class EvidenceGraph:
    """Graph structure capturing the entire causality chain of an exception."""
    exception_id: uuid.UUID
    nodes: list[EvidenceNode] = field(default_factory=list)
    edges: list[EvidenceEdge] = field(default_factory=list)

    def add_node(self, node_id: str, entity_type: str, data: dict[str, Any], label: str) -> EvidenceNode:
        node = EvidenceNode(id=node_id, entity_type=entity_type, data=data, label=label)
        self.nodes.append(node)
        return node

    def add_edge(self, source_id: str, target_id: str, relation: str, metadata: dict[str, Any] | None = None) -> EvidenceEdge:
        edge = EvidenceEdge(source_id=source_id, target_id=target_id, relation=relation, metadata=metadata or {})
        self.edges.append(edge)
        return edge

    def to_dict(self) -> dict[str, Any]:
        return {
            "exception_id": str(self.exception_id),
            "nodes": [
                {
                    "id": n.id,
                    "entity_type": n.entity_type,
                    "label": n.label,
                    "data": n.data,
                }
                for n in self.nodes
            ],
            "edges": [
                {
                    "source_id": e.source_id,
                    "target_id": e.target_id,
                    "relation": e.relation,
                    "metadata": e.metadata,
                }
                for e in self.edges
            ],
        }

    def to_text_summary(self) -> str:
        """Serializes the evidence chain into a clean, human-readable summary for the AI analyst."""
        lines = [f"EVIDENCE DOSSIER FOR EXCEPTION {self.exception_id}:"]
        lines.append("\nENTITIES PRESENT IN AUDIT CHAIN:")
        for n in self.nodes:
            lines.append(f"- [{n.entity_type.upper()}] {n.label} (ID: {n.id}): {n.data}")

        lines.append("\nRELATIONSHIPS & FLOW:")
        for e in self.edges:
            lines.append(f"- {e.source_id} --({e.relation})--> {e.target_id}")

        return "\n".join(lines)
