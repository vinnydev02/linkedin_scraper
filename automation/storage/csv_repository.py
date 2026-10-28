"""CSV persistence for post records."""

import csv
from pathlib import Path

from automation.models.post import PostRecord


class CsvPostRepository:
    """Small repository abstraction so scraping logic does not depend on CSV APIs."""

    def __init__(self, output_path: Path) -> None:
        self.output_path = output_path

    def load_seen_ids(self) -> set[str]:
        if not self.output_path.exists() or self.output_path.stat().st_size == 0:
            return set()

        with self.output_path.open("r", newline="", encoding="utf-8") as file:
            return {
                row["post_id"]
                for row in csv.DictReader(file)
                if row.get("post_id")
            }

    def append(self, records: list[PostRecord]) -> None:
        if not records:
            return

        self.output_path.parent.mkdir(parents=True, exist_ok=True)
        write_header = not self.output_path.exists() or self.output_path.stat().st_size == 0
        fieldnames = list(PostRecord.model_fields.keys())

        with self.output_path.open("a", newline="", encoding="utf-8") as file:
            writer = csv.DictWriter(file, fieldnames=fieldnames)
            if write_header:
                writer.writeheader()
            writer.writerows(record.model_dump() for record in records)
