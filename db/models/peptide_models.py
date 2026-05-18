"""
db/models/peptide_models.py
===========================
SQLAlchemy 2.0 ORM models for the PeptidIQ V3 Peptide Condition Library.

Tables:
    peptide_condition_library   — one row per gene × variant × peptide combination
    peptide_trade_offs          — one row per compound (aggregate trade-off data)

Patterns:
    - SQLAlchemy 2.0 DeclarativeBase + Mapped[] typed annotations
    - Async session support via AsyncSession (compatible with FastAPI lifespan)
    - ARRAY columns mapped through sqlalchemy.dialects.postgresql.ARRAY
    - Helper query functions accept an AsyncSession and return typed results

Usage example (FastAPI route):
    from sqlalchemy.ext.asyncio import AsyncSession
    from fastapi import Depends
    from db.models.peptide_models import get_peptide_responses, get_trade_off

    @router.get("/peptide-response")
    async def peptide_response(
        gene: str,
        rsid: str | None = None,
        variant_desc: str | None = None,
        db: AsyncSession = Depends(get_async_session),
    ):
        rows = await get_peptide_responses(db, gene, rsid, variant_desc)
        return rows
"""

from __future__ import annotations

from datetime import date, datetime
from typing import List, Optional

from sqlalchemy import (
    Boolean,
    CHAR,
    CheckConstraint,
    Column,
    Date,
    ForeignKey,         # noqa: F401  (available for future FK use)
    Index,
    String,
    Text,
    UniqueConstraint,
    func,
    or_,
    select,
)
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

# ---------------------------------------------------------------------------
# Base class — shared by all PeptidIQ models.
# If the project already defines a Base in db/base.py, import and use that
# instead of redeclaring here.
# ---------------------------------------------------------------------------

class Base(DeclarativeBase):
    """Project-wide declarative base for SQLAlchemy 2.0 ORM models."""
    pass


# ---------------------------------------------------------------------------
# Model 1: PeptideConditionLibrary
# ---------------------------------------------------------------------------

class PeptideConditionLibrary(Base):
    """
    Core lookup table for PeptidIQ V3.

    One row per gene × variant × peptide combination.  The annotation engine
    queries this table after variant scoring to retrieve predicted response
    direction, mechanism, dosing guidance, and safety flags for the patient.
    """

    __tablename__ = "peptide_condition_library"

    __table_args__ = (
        # Uniqueness: one clinical recommendation per gene-variant-peptide triplet
        UniqueConstraint(
            "gene_symbol",
            "rsid",
            "variant_description",
            "peptide_name",
            name="uq_gene_variant_peptide",
        ),
        # Enforce valid confidence tier values at the ORM level (mirrors DB CHECK)
        CheckConstraint(
            "confidence_tier IN ('A', 'B', 'C')",
            name="chk_confidence_tier",
        ),
        # Composite index mirroring annotation-engine query pattern
        Index("idx_pcl_gene_rsid_orm", "gene_symbol", "rsid"),
    )

    # ------------------------------------------------------------------
    # Primary key
    # ------------------------------------------------------------------
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    # ------------------------------------------------------------------
    # Variant identity
    # ------------------------------------------------------------------
    gene_symbol: Mapped[str] = mapped_column(
        String(20), nullable=False, index=True,
        comment="HGNC gene symbol, e.g. 'AR', 'ESR1', 'MC4R'",
    )
    variant_type: Mapped[str] = mapped_column(
        String(20), nullable=False,
        comment="'SNP', 'CNV', or 'STR_repeat'",
    )
    rsid: Mapped[Optional[str]] = mapped_column(
        String(20), nullable=True, index=True,
        comment="dbSNP rsID — NULL for CNVs and STRs",
    )
    variant_description: Mapped[Optional[str]] = mapped_column(
        Text, nullable=True,
        comment="Human-readable variant description, e.g. 'CAG repeat < 22'",
    )

    # ------------------------------------------------------------------
    # Peptide / compound identity
    # ------------------------------------------------------------------
    peptide_name: Mapped[str] = mapped_column(
        String(100), nullable=False, index=True,
        comment="Compound name, e.g. 'Testosterone (topical)'",
    )
    peptide_class: Mapped[Optional[str]] = mapped_column(
        String(50), nullable=True,
        comment="Therapeutic class: Androgen | HRT | GLP-1 RA | Neuropeptide | …",
    )
    target_receptor: Mapped[Optional[str]] = mapped_column(
        String(50), nullable=True,
        comment="Primary receptor target, e.g. 'AR', 'MC3R/MC4R', 'GLP1R'",
    )

    # ------------------------------------------------------------------
    # Response characterisation
    # ------------------------------------------------------------------
    response_direction: Mapped[str] = mapped_column(
        String(20), nullable=False, index=True,
        comment="enhanced | standard | blunted | contraindicated",
    )
    confidence_tier: Mapped[str] = mapped_column(
        CHAR(1), nullable=False,
        comment="A=RCT/meta-analysis  B=cohort/case-control  C=case series/expert consensus",
    )

    # ------------------------------------------------------------------
    # Clinical content
    # ------------------------------------------------------------------
    mechanism_summary: Mapped[str] = mapped_column(
        Text, nullable=False,
        comment="2–3 sentence scientific explanation of the genotype–response link",
    )
    dosing_guidance: Mapped[Optional[str]] = mapped_column(
        Text, nullable=True,
        comment="Genotype-informed dosing context for the prescribing clinician",
    )
    trade_off_text: Mapped[Optional[str]] = mapped_column(
        Text, nullable=True,
        comment="'No Free Lunch' section: biological costs, conversion risks",
    )

    # ------------------------------------------------------------------
    # Safety flags
    # ------------------------------------------------------------------
    contraindication_flag: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False,
        comment="True when this variant-peptide combination is contraindicated",
    )
    contraindication_genes: Mapped[Optional[List[str]]] = mapped_column(
        ARRAY(Text), nullable=True,
        comment="Gene symbols that render this peptide unsafe, e.g. ARRAY['TP53','BRCA1']",
    )

    # ------------------------------------------------------------------
    # Pathway / evidence linkage
    # ------------------------------------------------------------------
    kegg_pathways: Mapped[Optional[List[str]]] = mapped_column(
        ARRAY(Text), nullable=True,
        comment="KEGG pathway IDs, e.g. ARRAY['hsa04915','hsa04912']",
    )
    source_pmids: Mapped[Optional[List[str]]] = mapped_column(
        ARRAY(Text), nullable=True,
        comment="PubMed IDs supporting this entry",
    )

    # ------------------------------------------------------------------
    # Auditing
    # ------------------------------------------------------------------
    created_at: Mapped[datetime] = mapped_column(
        nullable=False, server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        nullable=False, server_default=func.now(), onupdate=func.now(),
    )

    # ------------------------------------------------------------------
    # Dunder helpers
    # ------------------------------------------------------------------
    def __repr__(self) -> str:
        return (
            f"<PeptideConditionLibrary id={self.id} "
            f"gene={self.gene_symbol!r} rsid={self.rsid!r} "
            f"peptide={self.peptide_name!r} response={self.response_direction!r}>"
        )


# ---------------------------------------------------------------------------
# Model 2: PeptideTradeOff
# ---------------------------------------------------------------------------

class PeptideTradeOff(Base):
    """
    Compound-level trade-off and anecdote data for PeptidIQ V3.

    One row per unique compound.  Complements PeptideConditionLibrary by
    holding aggregate safety, regulatory, and real-world anecdote information
    that applies to the compound regardless of the patient's specific variant.
    """

    __tablename__ = "peptide_trade_offs"

    # ------------------------------------------------------------------
    # Primary key
    # ------------------------------------------------------------------
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    # ------------------------------------------------------------------
    # Compound identity
    # ------------------------------------------------------------------
    peptide_name: Mapped[str] = mapped_column(
        String(100), nullable=False, unique=True,
        comment="Compound name — must match peptide_condition_library.peptide_name",
    )
    peptide_class: Mapped[Optional[str]] = mapped_column(
        String(50), nullable=True, index=True,
        comment="Therapeutic class (mirrors peptide_condition_library)",
    )

    # ------------------------------------------------------------------
    # Regulatory & clinical context
    # ------------------------------------------------------------------
    regulatory_status: Mapped[Optional[str]] = mapped_column(
        String(50), nullable=True,
        comment="FDA-approved | Compounded | Research only | FDA safety concern",
    )
    efficacy_med_logic: Mapped[Optional[str]] = mapped_column(
        Text, nullable=True,
        comment="How patient genetics modify the minimum effective dose",
    )

    # ------------------------------------------------------------------
    # Safety & risk profile
    # ------------------------------------------------------------------
    known_trade_offs: Mapped[str] = mapped_column(
        Text, nullable=False,
        comment="Biological costs, side effects, and conversion risks",
    )
    hormonal_conversion_risks: Mapped[Optional[str]] = mapped_column(
        Text, nullable=True,
        comment="Specific downstream conversion pathways (e.g. T → DHT via SRD5A2)",
    )
    clinical_anecdotes: Mapped[Optional[str]] = mapped_column(
        Text, nullable=True,
        comment="De-identified real-world observations",
    )

    # ------------------------------------------------------------------
    # Contraindication genetics
    # ------------------------------------------------------------------
    contraindication_genetics: Mapped[Optional[List[str]]] = mapped_column(
        ARRAY(Text), nullable=True,
        comment="Gene symbols that are absolute contraindications for this compound",
    )

    # ------------------------------------------------------------------
    # Evidence
    # ------------------------------------------------------------------
    source_pmids: Mapped[Optional[List[str]]] = mapped_column(
        ARRAY(Text), nullable=True,
        comment="PubMed IDs supporting this entry",
    )

    # ------------------------------------------------------------------
    # Review provenance
    # ------------------------------------------------------------------
    last_reviewed: Mapped[Optional[date]] = mapped_column(
        Date, nullable=True,
        comment="Date this entry was last clinically reviewed",
    )
    reviewed_by: Mapped[Optional[str]] = mapped_column(
        String(100), nullable=True,
        comment="Name or identifier of the reviewing clinician / scientist",
    )

    # ------------------------------------------------------------------
    # Auditing
    # ------------------------------------------------------------------
    created_at: Mapped[datetime] = mapped_column(
        nullable=False, server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        nullable=False, server_default=func.now(), onupdate=func.now(),
    )

    # ------------------------------------------------------------------
    # Dunder helpers
    # ------------------------------------------------------------------
    def __repr__(self) -> str:
        return (
            f"<PeptideTradeOff id={self.id} "
            f"peptide={self.peptide_name!r} "
            f"class={self.peptide_class!r} "
            f"regulatory={self.regulatory_status!r}>"
        )


# ---------------------------------------------------------------------------
# Query helpers
# ---------------------------------------------------------------------------

async def get_peptide_responses(
    session: AsyncSession,
    gene_symbol: str,
    rsid: str | None = None,
    variant_desc: str | None = None,
) -> list[PeptideConditionLibrary]:
    """
    Query the condition library for all peptide-response entries that match
    a given gene/variant combination.

    Matching strategy (in order of specificity):
      1. gene_symbol is always required.
      2. If rsid is provided, include rows where rsid matches OR rsid IS NULL
         (so STR_repeat / CNV rows for the same gene are always surfaced).
      3. If variant_desc is provided, apply an additional ILIKE filter so
         callers can narrow to a specific allele or repeat range.

    Args:
        session:      An active SQLAlchemy AsyncSession (injected by FastAPI).
        gene_symbol:  HGNC gene symbol to filter on, e.g. "AR".
        rsid:         dbSNP rsID from the annotated VCF, e.g. "rs2234693".
                      Pass None when the variant is a CNV or STR.
        variant_desc: Optional free-text description for narrower matching,
                      e.g. "CAG repeat < 22".

    Returns:
        A list of PeptideConditionLibrary ORM instances, ordered by
        confidence_tier ASC (A first) then response_direction.
    """
    stmt = (
        select(PeptideConditionLibrary)
        .where(PeptideConditionLibrary.gene_symbol == gene_symbol)
    )

    if rsid is not None:
        # Include exact rsid match OR rows with no rsid (CNV/STR rows for gene)
        stmt = stmt.where(
            or_(
                PeptideConditionLibrary.rsid == rsid,
                PeptideConditionLibrary.rsid.is_(None),
            )
        )

    if variant_desc is not None:
        stmt = stmt.where(
            PeptideConditionLibrary.variant_description.ilike(
                f"%{variant_desc}%"
            )
        )

    stmt = stmt.order_by(
        PeptideConditionLibrary.confidence_tier.asc(),
        PeptideConditionLibrary.response_direction.asc(),
    )

    result = await session.execute(stmt)
    return list(result.scalars().all())


async def get_trade_off(
    session: AsyncSession,
    peptide_name: str,
) -> PeptideTradeOff | None:
    """
    Return the trade-off row for a compound by its canonical name.

    Args:
        session:      An active SQLAlchemy AsyncSession.
        peptide_name: Exact compound name, e.g. "Semaglutide".

    Returns:
        A PeptideTradeOff instance if found, otherwise None.
    """
    stmt = select(PeptideTradeOff).where(
        PeptideTradeOff.peptide_name == peptide_name
    )
    result = await session.execute(stmt)
    return result.scalar_one_or_none()


async def get_contraindicated_peptides(
    session: AsyncSession,
    gene_symbols: list[str],
) -> list[PeptideConditionLibrary]:
    """
    Return all contraindicated peptide entries for a given set of gene symbols.

    Designed for the safety-alert pass in the annotation engine: after all
    variants are scored, call this once with every gene hit to surface any
    hard contraindications before generating the patient report.

    Args:
        session:      An active SQLAlchemy AsyncSession.
        gene_symbols: List of gene symbols found in the patient's VCF,
                      e.g. ["TP53", "BRCA1", "RET"].

    Returns:
        A list of PeptideConditionLibrary rows where contraindication_flag
        is TRUE and gene_symbol is in the provided list.
    """
    if not gene_symbols:
        return []

    stmt = (
        select(PeptideConditionLibrary)
        .where(
            PeptideConditionLibrary.contraindication_flag.is_(True),
            PeptideConditionLibrary.gene_symbol.in_(gene_symbols),
        )
        .order_by(
            PeptideConditionLibrary.gene_symbol,
            PeptideConditionLibrary.peptide_name,
        )
    )
    result = await session.execute(stmt)
    return list(result.scalars().all())


# ---------------------------------------------------------------------------
# Public API surface
# ---------------------------------------------------------------------------

__all__ = [
    "Base",
    "PeptideConditionLibrary",
    "PeptideTradeOff",
    "get_peptide_responses",
    "get_trade_off",
    "get_contraindicated_peptides",
]
