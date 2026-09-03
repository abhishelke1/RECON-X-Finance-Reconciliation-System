from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_
from typing import Any, Type

class Deduplicator:
    """Handles deduplication of incoming records by checking source_id + source_system."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def filter_new_records(self, model: Type[Any], records: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], int]:
        """
        Check which records already exist in the database based on source_id and source_system.
        Returns a tuple of (new_records, duplicates_count).
        """
        if not records:
            return [], 0

        # Extract (source_id, source_system) from records
        record_keys = [(r["source_id"], r["source_system"]) for r in records if "source_id" in r and "source_system" in r]
        
        if not record_keys:
            return records, 0

        # Build conditions for bulk lookup
        conditions = [and_(model.source_id == k[0], model.source_system == k[1]) for k in record_keys]
        query = select(model.source_id, model.source_system).where(or_(*conditions))
        
        result = await self.session.execute(query)
        existing_keys = set((row[0], row[1]) for row in result.all())

        new_records = []
        duplicates = 0

        for record in records:
            key = (record.get("source_id"), record.get("source_system"))
            if key in existing_keys:
                duplicates += 1
            else:
                new_records.append(record)

        return new_records, duplicates
