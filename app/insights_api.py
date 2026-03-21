"""
Moltbook Insights API Routes

Provides endpoints for agent-to-agent collaboration and jurisdiction expansion.
"""

from fastapi import APIRouter, HTTPException, BackgroundTasks, Depends
from typing import List, Optional, Dict, Any
import asyncio
import os

from app.moltbook_insights import (
    MoltbookInsightsClient,
    TaxKnowledgeRequest,
    AgentInsight,
    JurisdictionExpansionPlanner,
    InsightsIntegrationEngine,
    KnowledgeRequestPayload,
    InsightsQuery,
    ExpansionPlanResponse,
    request_tax_knowledge_sync
)

router = APIRouter(prefix="/insights", tags=["Agent Collaboration"])

# Initialize components
expansion_planner = JurisdictionExpansionPlanner()
integration_engine = InsightsIntegrationEngine()


@router.post("/request", response_model=Dict[str, Any])
async def request_knowledge(payload: KnowledgeRequestPayload):
    """
    Create a knowledge request on Moltbook for a specific jurisdiction.
    Other agents can respond with tax insights.
    """
    api_key = os.getenv("MOLTBOOK_API_KEY")
    if not api_key:
        raise HTTPException(status_code=503, detail="Moltbook integration not configured")
    
    request = TaxKnowledgeRequest(
        jurisdiction=payload.jurisdiction,
        tax_year=payload.tax_year,
        specific_questions=payload.specific_questions,
        urgency=payload.urgency
    )
    
    async with MoltbookInsightsClient(api_key) as client:
        success = await client.create_knowledge_request(request)
        
        if success:
            return {
                "success": True,
                "request_id": request.request_id,
                "jurisdiction": request.jurisdiction,
                "message": f"Knowledge request posted to Moltbook for {payload.jurisdiction}",
                "status": "pending_responses"
            }
        else:
            raise HTTPException(status_code=500, detail="Failed to create knowledge request")


@router.get("/responses/{request_id}", response_model=List[Dict[str, Any]])
async def get_responses(request_id: str):
    """
    Poll for responses to a knowledge request from other agents.
    """
    api_key = os.getenv("MOLTBOOK_API_KEY")
    if not api_key:
        raise HTTPException(status_code=503, detail="Moltbook integration not configured")
    
    async with MoltbookInsightsClient(api_key) as client:
        insights = await client.poll_for_responses(request_id)
        
        return [
            {
                "agent_name": i.agent_name,
                "jurisdiction": i.jurisdiction,
                "insight_type": i.insight_type,
                "content": i.content,
                "confidence": i.confidence,
                "sources": i.sources,
                "received_at": i.received_at
            }
            for i in insights
        ]


@router.post("/search", response_model=List[Dict[str, Any]])
async def search_insights(query: InsightsQuery):
    """
    Search for existing tax knowledge on Moltbook from other agents.
    """
    api_key = os.getenv("MOLTBOOK_API_KEY")
    if not api_key:
        raise HTTPException(status_code=503, detail="Moltbook integration not configured")
    
    search_query = query.jurisdiction or "crypto tax rules worldwide"
    
    async with MoltbookInsightsClient(api_key) as client:
        insights = await client.search_tax_knowledge(search_query, query.jurisdiction)
        
        # Filter by confidence
        filtered = [i for i in insights if i.confidence >= query.min_confidence]
        
        return [
            {
                "agent_name": i.agent_name,
                "jurisdiction": i.jurisdiction,
                "insight_type": i.insight_type,
                "content": i.content,
                "confidence": i.confidence,
                "sources": i.sources
            }
            for i in filtered
        ]


@router.get("/expansion-plan", response_model=ExpansionPlanResponse)
async def get_expansion_plan(
    target_tier: Optional[str] = "all",
    existing_coverage: Optional[str] = None
):
    """
    Get a plan for expanding tax coverage to all UN member states.
    
    - **target_tier**: Which tier to target (tier_1_high_crypto_adoption, tier_2_active_crypto_markets, tier_3_emerging_markets, tier_4_developing_coverage, or all)
    - **existing_coverage**: Comma-separated list of jurisdictions already covered
    """
    if existing_coverage:
        covered = [j.strip() for j in existing_coverage.split(",")]
        requests = expansion_planner.prioritize_missing_coverage(covered)
    else:
        requests = expansion_planner.generate_expansion_plan(target_tier)
    
    # Calculate coverage stats
    all_countries = []
    for tier_countries in expansion_planner.UN_MEMBER_STATES.values():
        all_countries.extend(tier_countries)
    
    covered_count = len(expansion_planner.coverage_status)
    pending_count = len([r for r in requests if expansion_planner.coverage_status.get(r.jurisdiction, {}).get("status") == "pending"])
    
    return {
        "total_jurisdictions": len(all_countries),
        "current_coverage": covered_count,
        "pending_requests": pending_count,
        "coverage_tiers": expansion_planner.UN_MEMBER_STATES,
        "generated_requests": len(requests),
        "pending_request_ids": [r.request_id for r in requests[:10]],  # First 10
        "estimated_completion": "3-6 months with active agent collaboration"
    }


@router.post("/batch-request/{tier}")
async def batch_request_knowledge(tier: str, background_tasks: BackgroundTasks):
    """
    Batch create knowledge requests for all jurisdictions in a tier.
    This runs in the background.
    """
    api_key = os.getenv("MOLTBOOK_API_KEY")
    if not api_key:
        raise HTTPException(status_code=503, detail="Moltbook integration not configured")
    
    if tier not in expansion_planner.UN_MEMBER_STATES and tier != "all":
        raise HTTPException(status_code=400, detail=f"Invalid tier. Choose from: {list(expansion_planner.UN_MEMBER_STATES.keys())} or 'all'")
    
    async def _batch_post():
        requests = expansion_planner.generate_expansion_plan(tier)
        async with MoltbookInsightsClient(api_key) as client:
            for request in requests:
                try:
                    await client.create_knowledge_request(request)
                    await asyncio.sleep(2)  # Rate limiting
                except Exception as e:
                    print(f"Failed to post request for {request.jurisdiction}: {e}")
    
    background_tasks.add_task(_batch_post)
    
    return {
        "success": True,
        "message": f"Batch knowledge request started for {tier} tier",
        "status": "processing_in_background",
        "estimated_requests": len(expansion_planner.UN_MEMBER_STATES.get(tier, [])) if tier != "all" else sum(len(v) for v in expansion_planner.UN_MEMBER_STATES.values())
    }


@router.post("/integrate")
async def integrate_insight(insight_data: Dict[str, Any]):
    """
    Manually integrate an agent insight into the tax rule system.
    Typically called after validating a received insight.
    """
    insight = AgentInsight(
        agent_name=insight_data.get("agent_name", "Unknown"),
        jurisdiction=insight_data.get("jurisdiction", "Unknown"),
        insight_type=insight_data.get("insight_type", "general"),
        content=insight_data.get("content", ""),
        confidence=insight_data.get("confidence", 0.5),
        sources=insight_data.get("sources", []),
        verified=insight_data.get("verified", False)
    )
    
    success = await integration_engine.integrate_insight(insight)
    
    if success:
        return {
            "success": True,
            "message": f"Insight from {insight.agent_name} integrated for {insight.jurisdiction}",
            "jurisdiction": insight.jurisdiction,
            "status": "pending_review"
        }
    else:
        return {
            "success": False,
            "message": "Insight failed validation and was not integrated",
            "added_to_validation_queue": True
        }


@router.get("/coverage-status")
async def get_coverage_status():
    """
    Get current jurisdiction coverage status.
    """
    return {
        "total_un_members": 193,
        "coverage_by_tier": {
            tier: {
                "total": len(countries),
                "covered": len([c for c in countries if expansion_planner.coverage_status.get(c, {}).get("status") == "completed"]),
                "pending": len([c for c in countries if expansion_planner.coverage_status.get(c, {}).get("status") == "pending"]),
                "countries": countries
            }
            for tier, countries in expansion_planner.UN_MEMBER_STATES.items()
        },
        "overall_progress": {
            "target": 193,
            "completed": len([v for v in expansion_planner.coverage_status.values() if v.get("status") == "completed"]),
            "in_progress": len([v for v in expansion_planner.coverage_status.values() if v.get("status") in ["pending", "in_progress"]])
        }
    }


@router.get("/feed")
async def get_moltbook_feed():
    """
    Get the latest posts from Moltbook agent feed.
    Useful for discovering new tax knowledge shared by other agents.
    """
    api_key = os.getenv("MOLTBOOK_API_KEY")
    if not api_key:
        raise HTTPException(status_code=503, detail="Moltbook integration not configured")
    
    async with MoltbookInsightsClient(api_key) as client:
        feed = await client.get_agent_feed()
        
        return {
            "posts": feed,
            "count": len(feed),
            "filtered_for_tax_knowledge": [
                p for p in feed 
                if any(kw in p.get("title", "").lower() or p.get("content", "").lower() 
                       for kw in ["tax", "crypto", "jurisdiction", "regulation"])
            ]
        }


@router.post("/auto-expand")
async def trigger_auto_expansion(background_tasks: BackgroundTasks):
    """
    Trigger automatic expansion mode.
    
    This will:
    1. Search Moltbook for existing tax knowledge
    2. Create knowledge requests for gaps
    3. Poll for responses
    4. Integrate validated insights
    
    Runs continuously in the background.
    """
    api_key = os.getenv("MOLTBOOK_API_KEY")
    if not api_key:
        raise HTTPException(status_code=503, detail="Moltbook integration not configured")
    
    async def _auto_expand():
        """Background task for continuous expansion"""
        while True:
            try:
                # Phase 1: Search for existing knowledge
                async with MoltbookInsightsClient(api_key) as client:
                    for tier, countries in expansion_planner.UN_MEMBER_STATES.items():
                        for country in countries:
                            if expansion_planner.coverage_status.get(country, {}).get("status") != "completed":
                                # Search for existing knowledge
                                insights = await client.search_tax_knowledge(f"{country} crypto tax", country)
                                
                                if insights:
                                    # Integrate found insights
                                    for insight in insights:
                                        await integration_engine.integrate_insight(insight)
                                    expansion_planner.coverage_status[country] = {"status": "in_progress", "source": "moltbook_search"}
                                else:
                                    # Create knowledge request
                                    request = TaxKnowledgeRequest(
                                        jurisdiction=country,
                                        tax_year=2025,
                                        specific_questions=expansion_planner.STANDARD_QUESTIONS.copy(),
                                        urgency="normal"
                                    )
                                    await client.create_knowledge_request(request)
                                    expansion_planner.coverage_status[country] = {"status": "pending", "request_id": request.request_id}
                                
                                await asyncio.sleep(5)  # Rate limiting between countries
                
                # Phase 2: Poll for responses (every hour)
                await asyncio.sleep(3600)
                
            except Exception as e:
                print(f"Auto-expansion error: {e}")
                await asyncio.sleep(300)  # Wait 5 minutes on error
    
    background_tasks.add_task(_auto_expand)
    
    return {
        "success": True,
        "message": "Auto-expansion mode activated",
        "mode": "continuous",
        "target": "All 193 UN member states",
        "strategy": "Search existing → Request missing → Integrate responses"
    }


# Health check endpoint
@router.get("/health")
async def insights_health():
    """Check Moltbook integration status"""
    api_key = os.getenv("MOLTBOOK_API_KEY")
    
    return {
        "moltbook_configured": bool(api_key),
        "expansion_planner_ready": True,
        "integration_engine_ready": True,
        "coverage_tiers_defined": len(expansion_planner.UN_MEMBER_STATES),
        "total_target_jurisdictions": sum(len(v) for v in expansion_planner.UN_MEMBER_STATES.values())
    }


# Agent Heartbeat Endpoints (Hazel_OC inspired)
@router.post("/heartbeat/run")
async def run_heartbeat():
    """
    Run agent heartbeat once.
    Checks: tax deadlines, jurisdiction updates, API health, Moltbook feed.
    """
    from app.heartbeat import HeartbeatEngine
    
    try:
        engine = HeartbeatEngine()
        results = await engine.run_heartbeat()
        
        return {
            "success": True,
            "agent": engine.agent_name,
            "checks_run": len(results),
            "results": results,
            "last_heartbeat": engine.heartbeat.last_full_heartbeat
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Heartbeat failed: {str(e)}")


@router.get("/heartbeat/daily")
async def get_daily_changelog():
    """
    Get the daily changelog for the human operator.
    Inspired by Hazel_OC: 'One message, delivered before coffee.'
    """
    from app.heartbeat import HeartbeatEngine
    
    try:
        engine = HeartbeatEngine()
        changelog = engine.get_daily_changelog()
        
        return {
            "agent": engine.agent_name,
            "date": datetime.utcnow().strftime('%Y-%m-%d'),
            "changelog": changelog,
            "checks_configured": len(engine.heartbeat.checks)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to generate changelog: {str(e)}")


@router.post("/heartbeat/continuous")
async def start_continuous_heartbeat(background_tasks: BackgroundTasks):
    """
    Start continuous heartbeat in background.
    Runs every 5 minutes by default.
    """
    from app.heartbeat import HeartbeatEngine
    
    async def _run_continuous():
        engine = HeartbeatEngine()
        await engine.continuous_heartbeat(interval_seconds=300)
    
    background_tasks.add_task(_run_continuous)
    
    return {
        "success": True,
        "message": "Continuous heartbeat started",
        "interval": "5 minutes",
        "checks": [
            "tax_deadlines",
            "jurisdiction_updates", 
            "api_health",
            "moltbook_feed",
            "knowledge_requests"
        ],
        "note": "Inspired by Hazel_OC: Simple cron job that watches the world for the human."
    }


@router.get("/heartbeat/status")
async def get_heartbeat_status():
    """Get current heartbeat status and pending checks"""
    from app.heartbeat import HeartbeatEngine
    
    try:
        engine = HeartbeatEngine()
        pending = engine.heartbeat.get_pending_checks()
        
        return {
            "agent": engine.agent_name,
            "last_full_heartbeat": engine.heartbeat.last_full_heartbeat,
            "total_checks": len(engine.heartbeat.checks),
            "pending_checks": len(pending),
            "checks": {
                name: {
                    "enabled": check.enabled,
                    "last_run": check.last_run,
                    "next_run": check.next_run,
                    "interval_minutes": check.interval_minutes
                }
                for name, check in engine.heartbeat.checks.items()
            }
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get status: {str(e)}")
