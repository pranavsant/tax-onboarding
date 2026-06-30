"""SQLite implementation of the ClientRepository port.

Maps DB rows to/from TaxClient domain entities. No business logic
lives here — only persistence concerns.
"""
from __future__ import annotations

import json
import sqlite3
from datetime import datetime
from typing import List, Optional

from src.domain.entities.client import OnboardingStatus, TaxClient
from src.domain.repositories.client_repository import ClientRepository
from src.domain.value_objects.tax_id import TaxId
from src.infrastructure.db.database import closing_connection


class SqliteClientRepository(ClientRepository):
    """Persists TaxClient entities in a local SQLite database."""

    def save(self, client: TaxClient) -> TaxClient:
        with closing_connection() as conn:
            conn.execute(
                """
                INSERT INTO clients
                    (client_id, full_name, email, tax_id, tax_id_kind, status,
                     submitted_documents, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    client.client_id,
                    client.full_name,
                    client.email,
                    client.tax_id.value,
                    client.tax_id.kind,
                    client.status.value,
                    json.dumps(client.submitted_documents),
                    client.created_at.isoformat(),
                ),
            )
            conn.commit()
        return client

    def get_by_id(self, client_id: str) -> Optional[TaxClient]:
        with closing_connection() as conn:
            row = conn.execute(
                "SELECT * FROM clients WHERE client_id = ?", (client_id,)
            ).fetchone()
        return _row_to_entity(row) if row else None

    def list_all(self) -> List[TaxClient]:
        with closing_connection() as conn:
            rows = conn.execute(
                "SELECT * FROM clients ORDER BY created_at DESC"
            ).fetchall()
        return [_row_to_entity(row) for row in rows]

    def update(self, client: TaxClient) -> TaxClient:
        with closing_connection() as conn:
            conn.execute(
                """
                UPDATE clients
                SET full_name = ?, email = ?, status = ?, submitted_documents = ?
                WHERE client_id = ?
                """,
                (
                    client.full_name,
                    client.email,
                    client.status.value,
                    json.dumps(client.submitted_documents),
                    client.client_id,
                ),
            )
            conn.commit()
        return client


def _row_to_entity(row: sqlite3.Row) -> TaxClient:
    return TaxClient(
        full_name=row["full_name"],
        email=row["email"],
        tax_id=TaxId(value=row["tax_id"], kind=row["tax_id_kind"]),
        client_id=row["client_id"],
        status=OnboardingStatus(row["status"]),
        submitted_documents=json.loads(row["submitted_documents"]),
        created_at=datetime.fromisoformat(row["created_at"]),
    )
