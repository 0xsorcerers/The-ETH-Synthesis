"""
UN Jurisdiction API Routes
Provides comprehensive tax information for all 193 UN member states
"""

from fastapi import APIRouter, HTTPException, Query
from typing import List, Optional, Dict, Any
from pydantic import BaseModel

from app.un_jurisdictions import (
    get_un_jurisdiction_db,
    UNJurisdiction,
    TaxTreatmentCategory,
    ComplianceLevel
)

router = APIRouter(prefix="/jurisdictions", tags=["UN Jurisdictions"])


# Pydantic models for API responses
class JurisdictionResponse(BaseModel):
    name: str
    iso_code: str
    iso_numeric: str
    un_m49: str
    region: str
    subregion: str
    crypto_classification: str
    primary_tax_authority: str
    capital_gains_taxable: Optional[bool]
    capital_gains_rate: Optional[str]
    income_taxable: Optional[bool]
    income_tax_rate: Optional[str]
    mining_taxable: Optional[bool]
    staking_taxable: Optional[bool]
    airdrop_taxable: Optional[bool]
    cost_basis_methods: List[str]
    annual_reporting_required: Optional[bool]
    transaction_threshold: Optional[str]
    specific_crypto_form: Optional[str]
    fiscal_year_end: Optional[str]
    tax_filing_deadline: Optional[str]
    guidance_level: str
    official_sources: List[str]
    agent_notes: Optional[str]


class JurisdictionListResponse(BaseModel):
    total: int
    jurisdictions: List[Dict[str, Any]]


class JurisdictionStats(BaseModel):
    total_jurisdictions: int
    by_region: Dict[str, int]
    by_classification: Dict[str, int]
    by_compliance_level: Dict[str, int]
    comprehensive_guidance_count: int
    crypto_friendly_count: int
    banned_restricted_count: int


def _convert_jurisdiction(j: UNJurisdiction) -> Dict[str, Any]:
    """Convert UNJurisdiction to dict for API response"""
    return {
        "name": j.name,
        "iso_code": j.iso_code,
        "iso_numeric": j.iso_numeric,
        "un_m49": j.un_m49,
        "region": j.region,
        "subregion": j.subregion,
        "crypto_classification": j.crypto_classification.value,
        "primary_tax_authority": j.primary_tax_authority,
        "capital_gains_taxable": j.capital_gains_taxable,
        "capital_gains_rate": j.capital_gains_rate,
        "income_taxable": j.income_taxable,
        "income_tax_rate": j.income_tax_rate,
        "mining_taxable": j.mining_taxable,
        "staking_taxable": j.staking_taxable,
        "airdrop_taxable": j.airdrop_taxable,
        "cost_basis_methods": j.cost_basis_methods,
        "annual_reporting_required": j.annual_reporting_required,
        "transaction_threshold": j.transaction_threshold,
        "specific_crypto_form": j.specific_crypto_form,
        "fiscal_year_end": j.fiscal_year_end,
        "tax_filing_deadline": j.tax_filing_deadline,
        "guidance_level": j.guidance_level.value,
        "official_sources": j.official_sources,
        "agent_notes": j.agent_notes
    }


@router.get("/un/all", response_model=JurisdictionListResponse)
async def get_all_un_jurisdictions(
    region: Optional[str] = Query(None, description="Filter by region (e.g., 'Europe', 'Asia')"),
    compliance_level: Optional[str] = Query(None, description="Filter by compliance level (e.g., 'comprehensive', 'moderate')"),
    crypto_friendly_only: bool = Query(False, description="Only return crypto-friendly jurisdictions")
):
    """
    Get all UN member states with their crypto tax treatment.
    Covers all 193 UN member states with publicly available tax information.
    """
    db = get_un_jurisdiction_db()
    
    jurisdictions = list(db.jurisdictions.values())
    
    # Apply filters
    if region:
        jurisdictions = [j for j in jurisdictions if j.region.lower() == region.lower()]
    
    if compliance_level:
        try:
            level = ComplianceLevel(compliance_level.lower())
            jurisdictions = [j for j in jurisdictions if j.guidance_level == level]
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid compliance level: {compliance_level}")
    
    if crypto_friendly_only:
        jurisdictions = db.get_crypto_friendly()
    
    return {
        "total": len(jurisdictions),
        "jurisdictions": [_convert_jurisdiction(j) for j in jurisdictions]
    }


@router.get("/un/{iso_code}", response_model=JurisdictionResponse)
async def get_jurisdiction_by_code(iso_code: str):
    """
    Get detailed crypto tax information for a specific UN jurisdiction by ISO code.
    
    - **iso_code**: ISO 3166-1 alpha-2 code (e.g., 'US', 'DE', 'JP')
    """
    db = get_un_jurisdiction_db()
    jurisdiction = db.get_jurisdiction(iso_code)
    
    if not jurisdiction:
        raise HTTPException(status_code=404, detail=f"Jurisdiction with code '{iso_code}' not found")
    
    return JurisdictionResponse(**_convert_jurisdiction(jurisdiction))


@router.get("/un/{iso_code}/tax-summary")
async def get_jurisdiction_tax_summary(iso_code: str):
    """
    Get a concise tax summary for a jurisdiction - useful for AI agents and quick reference.
    """
    db = get_un_jurisdiction_db()
    j = db.get_jurisdiction(iso_code)
    
    if not j:
        raise HTTPException(status_code=404, detail=f"Jurisdiction '{iso_code}' not found")
    
    return {
        "jurisdiction": j.name,
        "iso_code": j.iso_code,
        "crypto_treatment": j.crypto_classification.value,
        "capital_gains": {
            "taxable": j.capital_gains_taxable,
            "rate": j.capital_gains_rate
        },
        "income_tax": {
            "taxable": j.income_taxable,
            "rate": j.income_tax_rate
        },
        "cost_basis_methods": j.cost_basis_methods,
        "filing_deadline": j.tax_filing_deadline,
        "guidance_quality": j.guidance_level.value,
        "key_warning": j.agent_notes[:200] + "..." if j.agent_notes and len(j.agent_notes) > 200 else j.agent_notes
    }


@router.get("/un/stats/summary", response_model=JurisdictionStats)
async def get_jurisdiction_statistics():
    """
    Get statistics about UN jurisdiction coverage and crypto tax guidance levels.
    """
    db = get_un_jurisdiction_db()
    stats = db.get_statistics()
    return JurisdictionStats(**stats)


@router.get("/un/regions/all")
async def get_all_regions():
    """Get list of all UN geographical regions"""
    db = get_un_jurisdiction_db()
    regions = set(j.region for j in db.jurisdictions.values())
    
    region_data = {}
    for region in regions:
        countries = db.get_by_region(region)
        region_data[region] = {
            "country_count": len(countries),
            "countries": [c.name for c in countries]
        }
    
    return {
        "regions": list(regions),
        "region_details": region_data
    }


@router.get("/un/friendly/list")
async def get_crypto_friendly_jurisdictions():
    """
    Get list of crypto-friendly jurisdictions (no capital gains tax or 0% rate).
    """
    db = get_un_jurisdiction_db()
    friendly = db.get_crypto_friendly()
    
    return {
        "count": len(friendly),
        "jurisdictions": [
            {
                "name": j.name,
                "iso_code": j.iso_code,
                "capital_gains_rate": j.capital_gains_rate,
                "region": j.region,
                "agent_notes": j.agent_notes
            }
            for j in friendly
        ]
    }


@router.get("/un/restricted/list")
async def get_banned_restricted_jurisdictions():
    """
    Get list of jurisdictions with crypto bans or heavy restrictions.
    """
    db = get_un_jurisdiction_db()
    restricted = db.get_banned_restricted()
    
    return {
        "count": len(restricted),
        "jurisdictions": [
            {
                "name": j.name,
                "iso_code": j.iso_code,
                "classification": j.crypto_classification.value,
                "region": j.region,
                "agent_notes": j.agent_notes
            }
            for j in restricted
        ],
        "warning": "These jurisdictions have banned or heavily restricted cryptocurrency. Extreme caution advised."
    }


@router.get("/un/search")
async def search_jurisdictions(
    query: str = Query(..., description="Search query for jurisdiction name or ISO code"),
    min_compliance: Optional[str] = Query(None, description="Minimum compliance level filter")
):
    """
    Search jurisdictions by name or ISO code.
    """
    db = get_un_jurisdiction_db()
    query_lower = query.lower()
    
    results = []
    for j in db.jurisdictions.values():
        # Check if query matches name or ISO code
        if query_lower in j.name.lower() or query_lower in j.iso_code.lower():
            # Apply compliance filter if specified
            if min_compliance:
                try:
                    level_order = ['unclear', 'limited', 'moderate', 'comprehensive']
                    min_idx = level_order.index(min_compliance.lower())
                    result_idx = level_order.index(j.guidance_level.value.lower())
                    if result_idx < min_idx:
                        continue
                except ValueError:
                    pass
            
            results.append(_convert_jurisdiction(j))
    
    return {
        "query": query,
        "results_count": len(results),
        "results": results
    }


@router.get("/un/compliance-levels")
async def get_compliance_levels_info():
    """
    Get information about compliance levels and which jurisdictions fall into each category.
    """
    db = get_un_jurisdiction_db()
    
    levels = {}
    for level in ComplianceLevel:
        countries = db.get_by_compliance_level(level)
        levels[level.value] = {
            "count": len(countries),
            "description": _get_compliance_description(level),
            "examples": [c.name for c in countries[:5]]  # First 5 examples
        }
    
    return {
        "compliance_levels": levels,
        "note": "Countries migrate to higher compliance levels as tax authorities issue guidance"
    }


def _get_compliance_description(level: ComplianceLevel) -> str:
    """Get human-readable description of compliance level"""
    descriptions = {
        ComplianceLevel.COMPREHENSIVE: "Detailed official guidance from tax authority, clear rules, established forms",
        ComplianceLevel.MODERATE: "Some official guidance exists, general principles established",
        ComplianceLevel.LIMITED: "Minimal guidance, general tax principles may apply",
        ComplianceLevel.UNCLEAR: "No clear guidance, high uncertainty",
        ComplianceLevel.RESTRICTIVE: "Heavy restrictions or bans on cryptocurrency"
    }
    return descriptions.get(level, "Unknown")


# For agent-friendly integration
@router.get("/un/agent-manifest")
async def get_agent_manifest():
    """
    Get agent-friendly manifest of all jurisdictions for AI agent consumption.
    Designed for autonomous agents handling multi-jurisdiction tax calculations.
    """
    db = get_un_jurisdiction_db()
    
    manifest = {
        "manifest_version": "1.0",
        "total_jurisdictions": len(db.jurisdictions),
        "coverage": {
            "comprehensive": len(db.get_by_compliance_level(ComplianceLevel.COMPREHENSIVE)),
            "moderate": len(db.get_by_compliance_level(ComplianceLevel.MODERATE)),
            "limited": len(db.get_by_compliance_level(ComplianceLevel.LIMITED)),
            "unclear": len(db.get_by_compliance_level(ComplianceLevel.UNCLEAR)),
            "restrictive": len(db.get_by_compliance_level(ComplianceLevel.RESTRICTIVE))
        },
        "jurisdictions": {},
        "agent_instructions": {
            "comprehensive": "Safe to process with high confidence",
            "moderate": "Process with standard validation",
            "limited": "Flag for human review if significant amounts",
            "unclear": "Always flag for human review",
            "restrictive": "Halt processing - jurisdiction banned/restricted"
        }
    }
    
    for iso_code, j in db.jurisdictions.items():
        manifest["jurisdictions"][iso_code] = {
            "name": j.name,
            "classification": j.crypto_classification.value,
            "confidence": j.guidance_level.value,
            "cgt_applicable": j.capital_gains_taxable,
            "cgt_rate": j.capital_gains_rate,
            "income_applicable": j.income_taxable,
            "filing_deadline": j.tax_filing_deadline,
            "requires_review": j.guidance_level in [ComplianceLevel.UNCLEAR, ComplianceLevel.RESTRICTIVE]
        }
    
    return manifest
