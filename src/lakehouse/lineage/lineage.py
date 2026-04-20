"""
Data Lineage Tracking
=====================
Records input/output relationships, transformations, and row counts
across the Bronze → Silver → Gold pipeline.

Enhancements over v1.0.0
-------------------------
* ``LineageEvent`` — typed dataclass for a single lineage record.
* ``LineageTracker`` — accumulates events and exposes a graph view.
* ``log_lineage()`` is kept for backward compatibility.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from lakehouse.monitoring.logging import logger


class LineageEvent:
    """Immutable record of a single source → target data movement."""

    __slots__ = (
        "timestamp",
        "source_datasets",
        "target_dataset",
        "transformation",
        "layer",
        "row_count",
        "metadata",
    )

    def __init__(
        self,
        source_datasets: List[str],
        target_dataset: str,
        transformation: str,
        layer: str,
        row_count: int = 0,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        self.timestamp = datetime.now(timezone.utc).isoformat()
        self.source_datasets = source_datasets
        self.target_dataset = target_dataset
        self.transformation = transformation
        self.layer = layer
        self.row_count = row_count
        self.metadata = metadata or {}

    def to_dict(self) -> Dict[str, Any]:
        return {
            "timestamp": self.timestamp,
            "source_datasets": self.source_datasets,
            "target_dataset": self.target_dataset,
            "transformation": self.transformation,
            "layer": self.layer,
            "row_count": self.row_count,
            "metadata": self.metadata,
        }


class LineageTracker:
    """Accumulates lineage events for a pipeline run."""

    def __init__(self) -> None:
        self.events: List[LineageEvent] = []

    def record(
        self,
        source_datasets: List[str],
        target_dataset: str,
        transformation: str,
        layer: str,
        row_count: int = 0,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> LineageEvent:
        event = LineageEvent(
            source_datasets=source_datasets,
            target_dataset=target_dataset,
            transformation=transformation,
            layer=layer,
            row_count=row_count,
            metadata=metadata,
        )
        self.events.append(event)
        logger.info(
            f"LINEAGE | {' + '.join(event.source_datasets)} → {event.target_dataset} "
            f"| layer={event.layer} rows={event.row_count}",
            event_type="lineage",
        )
        return event

    def get_lineage_graph(self) -> Dict[str, Any]:
        return {
            "events": [e.to_dict() for e in self.events],
            "total_events": len(self.events),
        }


# --- backward-compatible helper kept from v1.0.0 ---


def log_lineage(source: str, target: str, rows: int) -> None:
    """Log a simple source→target lineage entry (v1 API)."""
    timestamp = datetime.now(timezone.utc).isoformat()
    logger.info(
        f"LINEAGE | Timestamp: {timestamp} | Source: {source} -> Target: {target} | Rows: {rows}",
        event_type="lineage",
        source=source,
        target=target,
        row_count=rows,
    )
