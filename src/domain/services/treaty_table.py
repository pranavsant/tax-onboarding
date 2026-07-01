"""Hardcoded tax treaty country reference table.

This module provides a minimal mapping of countries to their US tax treaty
status and applicable withholding rate on US-source income (e.g. dividends).

.. important::
   **This is a placeholder** intended to support early-stage development and
   testing.  The table currently covers only four countries to satisfy
   immediate business requirements.  It must be replaced by a comprehensive,
   data-driven treaty table (e.g. backed by a database or authoritative IRS
   Publication 901 feed) in a later workflow before this system is used in
   production.

Withholding rate conventions
-----------------------------
* ``withholding_rate_pct`` is expressed as a percentage value
  (e.g. ``30.0`` means 30 %, ``15.0`` means 15 %).
* For countries **without** a treaty the statutory US NRA withholding rate of
  **30 %** applies (IRC § 1441).
* For countries **with** a treaty the ``withholding_rate_pct`` reflects the
  reduced rate negotiated in the applicable tax treaty for dividend income
  (the most common category encountered during W-8BEN onboarding).  Article
  numbers vary by treaty; callers that need article-level detail should
  consult the full treaty text or a future enriched data source.

Included countries
-------------------
+----------+-----------+--------------------------------------+
| Country  | Treaty?   | Withholding rate (dividend income)   |
+==========+===========+======================================+
| Brazil   | No        | 30 % (statutory)                     |
+----------+-----------+--------------------------------------+
| Germany  | Yes       | 15 % (Art. 10, US–Germany treaty)    |
+----------+-----------+--------------------------------------+
| Israel   | Yes       | 15 % (Art. 10, US–Israel treaty)     |
+----------+-----------+--------------------------------------+
| UK       | Yes       | 15 % (Art. 10, US–UK treaty)         |
+----------+-----------+--------------------------------------+
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class TreatyEntry:
    """Immutable descriptor for a country's US tax treaty status.

    Attributes:
        country: Canonical country name as stored in the table (title-cased).
        has_treaty: ``True`` when the country has an active income tax treaty
            with the United States; ``False`` otherwise.
        withholding_rate_pct: Applicable US withholding rate as a percentage
            (e.g. ``30.0`` for 30 %, ``15.0`` for 15 %).  For treaty
            countries this is the reduced dividend rate; for non-treaty
            countries this is the statutory 30 % rate.
    """

    country: str
    has_treaty: bool
    withholding_rate_pct: float


# ---------------------------------------------------------------------------
# Internal table — all lookups normalise to lowercase for case-insensitivity.
# ---------------------------------------------------------------------------

# NOTE: This is a placeholder covering only the four countries required by
# the initial acceptance criteria.  Extend or replace with a data-driven
# source (see module docstring).
_TREATY_TABLE: dict[str, TreatyEntry] = {
    "brazil": TreatyEntry(
        country="Brazil",
        has_treaty=False,
        withholding_rate_pct=30.0,
    ),
    "germany": TreatyEntry(
        country="Germany",
        has_treaty=True,
        withholding_rate_pct=15.0,
    ),
    "israel": TreatyEntry(
        country="Israel",
        has_treaty=True,
        withholding_rate_pct=15.0,
    ),
    "united kingdom": TreatyEntry(
        country="United Kingdom",
        has_treaty=True,
        withholding_rate_pct=15.0,
    ),
    # Common alternative spellings / abbreviations
    "uk": TreatyEntry(
        country="United Kingdom",
        has_treaty=True,
        withholding_rate_pct=15.0,
    ),
    "great britain": TreatyEntry(
        country="United Kingdom",
        has_treaty=True,
        withholding_rate_pct=15.0,
    ),
}

# Statutory fallback — applies to all countries not listed in the table.
_STATUTORY_ENTRY = TreatyEntry(
    country="",
    has_treaty=False,
    withholding_rate_pct=30.0,
)


class TreatyTable:
    """Stateless domain service for US tax treaty country lookups.

    All lookups are case-insensitive.  Unknown countries return the statutory
    30 % withholding rate with ``has_treaty=False``.

    .. note::
       This class is a **placeholder** covering four countries.  It must be
       replaced by a fuller implementation before production use (see module
       docstring).
    """

    @staticmethod
    def lookup(country: str) -> TreatyEntry:
        """Return the :class:`TreatyEntry` for *country*.

        Lookup is case-insensitive and strips surrounding whitespace.

        Args:
            country: Country name as supplied by the caller (e.g. from the
                ``country_of_citizenship`` field of a W-8BEN form).

        Returns:
            The matching :class:`TreatyEntry` if the country is in the table;
            otherwise a synthetic :class:`TreatyEntry` with ``has_treaty=False``
            and ``withholding_rate_pct=30.0`` (the statutory NRA rate).

        Raises:
            ValueError: If *country* is ``None``, empty, or whitespace-only.
        """
        if not country or not country.strip():
            raise ValueError(
                "country must not be empty or whitespace-only."
            )

        key = country.strip().lower()
        entry = _TREATY_TABLE.get(key)
        if entry is not None:
            return entry

        # Unknown country — return statutory withholding, preserve the
        # caller-supplied name in the result.
        return TreatyEntry(
            country=country.strip(),
            has_treaty=False,
            withholding_rate_pct=30.0,
        )

    @staticmethod
    def is_treaty_country(country: str) -> bool:
        """Return ``True`` if *country* has an active US tax treaty.

        Convenience wrapper around :meth:`lookup`.

        Args:
            country: Country name (case-insensitive).

        Returns:
            ``True`` when a treaty entry exists and ``has_treaty`` is
            ``True``; ``False`` otherwise (including unknown countries).

        Raises:
            ValueError: If *country* is ``None``, empty, or whitespace-only.
        """
        return TreatyTable.lookup(country).has_treaty

    @staticmethod
    def known_countries() -> list[str]:
        """Return the canonical country names currently in the table.

        Excludes alias entries (e.g. 'UK' and 'Great Britain' are both
        aliases for 'United Kingdom' and are not duplicated in this list).

        Returns:
            Sorted list of canonical country names.
        """
        seen: set[str] = set()
        canonical: list[str] = []
        for entry in _TREATY_TABLE.values():
            if entry.country not in seen:
                seen.add(entry.country)
                canonical.append(entry.country)
        return sorted(canonical)
