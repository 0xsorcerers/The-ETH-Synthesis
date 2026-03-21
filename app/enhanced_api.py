"""
Enhanced API endpoints for Skynet
Provides async processing, agent-first interfaces, and improved scalability
"""

from __future__ import annotations

import asyncio
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, BackgroundTasks, Depends
from fastapi.responses import JSONResponse

from app.enhanced_services import get_enhanced_tax_service, EnhancedTaxService
from app.models import (
    RuleSet, SupportedJurisdiction, AgentManifest, 
    ExplanationGuide, AutonomyPlan, TaxReport
)

router = APIRouter(prefix="/api/v2", tags=["enhanced"])


@router.get("/jurisdictions", response_model=List[SupportedJurisdiction])
async def get_supported_jurisdictions(
    service: EnhancedTaxService = Depends(get_enhanced_tax_service)
):
    """Get supported jurisdictions with enhanced metadata"""
    try:
        jurisdictions = await service.get_available_jurisdictions()
        result = []
        
        for jur in jurisdictions:
            years = await service.get_available_years(jur)
            # Get validation info for latest year
            latest_year = max(years) if years else None
            validation = await service.validate_ruleset(jur, latest_year) if latest_year else None
            
            result.append(SupportedJurisdiction(
                jurisdiction=jur,
                supported_years=years,
                status="active" if validation and validation["valid"] else "limited",
                latest_version=validation["version"] if validation else None,
                rules_count=validation["rules_count"] if validation else 0,
                last_updated=validation["last_modified"] if validation else None
            ))
        
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/agent/manifest", response_model=AgentManifest)
async def get_agent_manifest(
    service: EnhancedTaxService = Depends(get_enhanced_tax_service)
):
    """Enhanced agent manifest with async capabilities"""
    try:
        jurisdictions = await service.get_supported_jurisdictions()
        stats = await service.get_rule_engine_stats()
        
        return AgentManifest(
            agent_name="Skynet Enhanced",
            version="2.0.0",
            capabilities=[
                "async_processing",
                "batch_classification",
                "rule_caching",
                "enhanced_validation",
                "agent_webhooks",
                "telemetry"
            ],
            supported_jurisdictions=jurisdictions,
            endpoints={
                "classify": "/api/v2/classify",
                "classify_batch": "/api/v2/classify/batch",
                "generate_report": "/api/v2/report/generate",
                "validate_ruleset": "/api/v2/rules/validate",
                "webhook_register": "/api/v2/webhooks/register"
            },
            rate_limits={
                "requests_per_minute": 100,
                "batch_size_limit": 1000,
                "file_size_limit_mb": 50
            },
            cache_stats=stats
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/classify/batch")
async def classify_transactions_batch(
    transactions: List[Dict[str, Any]],
    jurisdiction: str,
    tax_year: int,
    service: EnhancedTaxService = Depends(get_enhanced_tax_service)
):
    """Classify multiple transactions in parallel"""
    try:
        # Validate input size
        if len(transactions) > 1000:
            raise HTTPException(status_code=400, detail="Batch size exceeds limit of 1000 transactions")
        
        # Get ruleset
        ruleset = await service.get_ruleset(jurisdiction, tax_year)
        
        # Convert to normalized transactions (simplified)
        from app.models import NormalizedTransaction
        normalized_txs = []
        for tx_data in transactions:
            # Basic validation - in production, this would be more robust
            if not all(key in tx_data for key in ["tx_id", "timestamp", "asset", "quantity"]):
                raise HTTPException(status_code=400, detail=f"Transaction missing required fields: {tx_data.get('tx_id', 'unknown')}")
            
            normalized_txs.append(NormalizedTransaction(**tx_data))
        
        # Classify in parallel
        classified = await service.classify_transactions_batch(normalized_txs, ruleset)
        
        return {
            "classified_transactions": [tx.dict() for tx in classified],
            "jurisdiction": jurisdiction,
            "tax_year": tax_year,
            "processed_count": len(classified),
            "processing_time_ms": 0  # Would be measured in production
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/report/generate")
async def generate_tax_report_enhanced(
    classified_transactions: List[Dict[str, Any]],
    jurisdiction: str,
    tax_year: int,
    service: EnhancedTaxService = Depends(get_enhanced_tax_service)
):
    """Generate tax report with enhanced processing"""
    try:
        # Get ruleset
        ruleset = await service.get_ruleset(jurisdiction, tax_year)
        
        # Convert to classified transactions
        from app.models import ClassifiedTransaction
        classified_txs = [ClassifiedTransaction(**tx) for tx in classified_transactions]
        
        # Generate report
        report = await service.generate_tax_report_async(classified_txs, ruleset)
        
        return report.dict()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/rules/validate/{jurisdiction}/{tax_year}")
async def validate_ruleset_endpoint(
    jurisdiction: str,
    tax_year: int,
    service: EnhancedTaxService = Depends(get_enhanced_tax_service)
):
    """Validate a specific ruleset"""
    try:
        validation = await service.validate_ruleset(jurisdiction, tax_year)
        return validation
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/rules/cache/clear")
async def clear_rule_cache(
    service: EnhancedTaxService = Depends(get_enhanced_tax_service)
):
    """Clear rule engine cache"""
    try:
        service.clear_rule_cache()
        return {"message": "Rule cache cleared successfully"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/stats")
async def get_service_stats(
    service: EnhancedTaxService = Depends(get_enhanced_tax_service)
):
    """Get service statistics"""
    try:
        cache_stats = await service.get_rule_engine_stats()
        jurisdictions = await service.get_available_jurisdictions()
        
        total_rules = 0
        for jur in jurisdictions:
            years = await service.get_available_years(jur)
            for year in years:
                validation = await service.validate_ruleset(jur, year)
                if validation and validation["valid"]:
                    total_rules += validation["rules_count"]
        
        return {
            "cache_stats": cache_stats,
            "total_jurisdictions": len(jurisdictions),
            "total_rules": total_rules,
            "service_version": "2.0.0",
            "uptime_seconds": 0  # Would be tracked in production
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# Webhook support for agent workflows
webhook_store: Dict[str, Dict[str, Any]] = {}


@router.post("/webhooks/register")
async def register_webhook(
    webhook_url: str,
    events: List[str],
    agent_id: str
):
    """Register a webhook for agent workflows"""
    try:
        webhook_id = f"{agent_id}_{datetime.now().timestamp()}"
        webhook_store[webhook_id] = {
            "url": webhook_url,
            "events": events,
            "agent_id": agent_id,
            "created_at": datetime.now().isoformat()
        }
        
        return {
            "webhook_id": webhook_id,
            "status": "registered",
            "events": events
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/webhooks")
async def list_webhooks():
    """List registered webhooks"""
    return webhook_store


# Background task processing
task_store: Dict[str, Dict[str, Any]] = {}


@router.post("/tasks/classify-async")
async def start_async_classification(
    transactions: List[Dict[str, Any]],
    jurisdiction: str,
    tax_year: int,
    background_tasks: BackgroundTasks,
    service: EnhancedTaxService = Depends(get_enhanced_tax_service)
):
    """Start async classification task"""
    try:
        task_id = f"classify_{datetime.now().timestamp()}"
        
        # Store initial task status
        task_store[task_id] = {
            "status": "queued",
            "created_at": datetime.now().isoformat(),
            "total_transactions": len(transactions),
            "progress": 0
        }
        
        # Start background task
        background_tasks.add_task(
            _process_classification_task,
            task_id,
            transactions,
            jurisdiction,
            tax_year,
            service
        )
        
        return {
            "task_id": task_id,
            "status": "queued",
            "estimated_time_seconds": len(transactions) * 0.1  # Rough estimate
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/tasks/{task_id}")
async def get_task_status(task_id: str):
    """Get task status"""
    if task_id not in task_store:
        raise HTTPException(status_code=404, detail="Task not found")
    return task_store[task_id]


async def _process_classification_task(
    task_id: str,
    transactions: List[Dict[str, Any]],
    jurisdiction: str,
    tax_year: int,
    service: EnhancedTaxService
):
    """Background task for async classification"""
    try:
        # Update status
        task_store[task_id]["status"] = "processing"
        
        # Get ruleset
        ruleset = await service.get_ruleset(jurisdiction, tax_year)
        
        # Process in batches
        batch_size = 100
        results = []
        
        for i in range(0, len(transactions), batch_size):
            batch = transactions[i:i + batch_size]
            
            # Process batch
            from app.models import NormalizedTransaction
            normalized_batch = [NormalizedTransaction(**tx) for tx in batch]
            classified_batch = await service.classify_transactions_batch(normalized_batch, ruleset)
            results.extend([tx.dict() for tx in classified_batch])
            
            # Update progress
            progress = min(100, (i + batch_size) / len(transactions) * 100)
            task_store[task_id]["progress"] = progress
        
        # Complete task
        task_store[task_id].update({
            "status": "completed",
            "completed_at": datetime.now().isoformat(),
            "results": results,
            "progress": 100
        })
        
        # Trigger webhooks if registered
        await _trigger_webhooks("classification_completed", {
            "task_id": task_id,
            "jurisdiction": jurisdiction,
            "tax_year": tax_year,
            "transaction_count": len(transactions)
        })
        
    except Exception as e:
        task_store[task_id].update({
            "status": "failed",
            "error": str(e),
            "failed_at": datetime.now().isoformat()
        })


async def _trigger_webhooks(event: str, data: Dict[str, Any]):
    """Trigger registered webhooks for an event"""
    for webhook_id, webhook in webhook_store.items():
        if event in webhook["events"]:
            try:
                # In production, this would make actual HTTP requests
                print(f"Would trigger webhook {webhook_id} for event {event}")
                # await httpx.post(webhook["url"], json={"event": event, "data": data})
            except Exception as e:
                print(f"Failed to trigger webhook {webhook_id}: {e}")
