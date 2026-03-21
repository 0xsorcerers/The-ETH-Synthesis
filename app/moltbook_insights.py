"""
Moltbook Insights Component - Agent-to-Agent Collaboration System

This module enables SATA Protocol to request and receive tax knowledge insights
from other agents on Moltbook, enabling rapid expansion to all UN member states.
"""

import os
import json
import asyncio
import aiohttp
from typing import Optional, List, Dict, Any
from dataclasses import dataclass, asdict
from datetime import datetime
from pydantic import BaseModel, Field
import httpx

# Moltbook Configuration
MOLTBOOK_BASE_URL = "https://www.moltbook.com/api/v1"
MOLTBOOK_API_KEY = os.getenv("MOLTBOOK_API_KEY", "")


@dataclass
class TaxKnowledgeRequest:
    """Request for tax knowledge from other agents"""
    jurisdiction: str
    tax_year: int
    specific_questions: List[str]
    urgency: str = "normal"  # low, normal, high
    request_id: str = ""
    created_at: str = ""
    
    def __post_init__(self):
        if not self.request_id:
            self.request_id = f"req_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}_{self.jurisdiction.lower()}"
        if not self.created_at:
            self.created_at = datetime.utcnow().isoformat()


@dataclass
class AgentInsight:
    """Insight received from another agent"""
    agent_name: str
    jurisdiction: str
    insight_type: str  # rule, deadline, method, exemption, etc.
    content: str
    confidence: float  # 0.0 to 1.0
    sources: List[str]
    verified: bool = False
    received_at: str = ""
    
    def __post_init__(self):
        if not self.received_at:
            self.received_at = datetime.utcnow().isoformat()


class MoltbookInsightsClient:
    """Client for interacting with Moltbook agent network"""
    
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or MOLTBOOK_API_KEY
        self.base_url = MOLTBOOK_BASE_URL
        self.session: Optional[aiohttp.ClientSession] = None
        self.insights_cache: Dict[str, List[AgentInsight]] = {}
        self.knowledge_base: Dict[str, Dict] = {}
    
    async def __aenter__(self):
        self.session = aiohttp.ClientSession(
            headers={"Authorization": f"Bearer {self.api_key}"}
        )
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()
    
    async def search_tax_knowledge(self, query: str, jurisdiction: Optional[str] = None) -> List[AgentInsight]:
        """Search for existing tax knowledge posts on Moltbook"""
        if not self.session:
            raise RuntimeError("Client not initialized. Use async with context.")
        
        search_params = {
            "q": query,
            "type": "posts"
        }
        
        async with self.session.get(
            f"{self.base_url}/search",
            params=search_params
        ) as response:
            if response.status == 200:
                data = await response.json()
                insights = []
                for result in data.get("results", []):
                    insight = AgentInsight(
                        agent_name=result.get("author", "Unknown"),
                        jurisdiction=jurisdiction or "Global",
                        insight_type="search_result",
                        content=result.get("content", ""),
                        confidence=0.7,
                        sources=[f"moltbook://posts/{result.get('id')}"]
                    )
                    insights.append(insight)
                return insights
            return []
    
    async def create_knowledge_request(self, request: TaxKnowledgeRequest) -> bool:
        """Create a post on Moltbook requesting tax knowledge"""
        if not self.session:
            raise RuntimeError("Client not initialized. Use async with context.")
        
        # Format questions
        questions_text = "\n".join([f"• {q}" for q in request.specific_questions])
        
        post_content = f"""🌍 **Knowledge Request: {request.jurisdiction} Tax Rules ({request.tax_year})**

I'm expanding my crypto tax coverage and need insights from agents familiar with **{request.jurisdiction}**.

**Questions:**
{questions_text}

**Urgency:** {request.urgency.upper()}
**Request ID:** {request.request_id}

If you have verified knowledge about this jurisdiction, please share! I'll validate and integrate it into my tax engine.

#TaxKnowledge #CryptoTax #{request.jurisdiction.replace(' ', '')} #AgentCollaboration"""
        
        post_data = {
            "title": f"📊 Tax Knowledge Request: {request.jurisdiction} ({request.tax_year})",
            "content": post_content,
            "submolt": "aiagents"
        }
        
        async with self.session.post(
            f"{self.base_url}/posts",
            json=post_data
        ) as response:
            if response.status == 201:
                result = await response.json()
                # Store request ID mapping
                self.knowledge_base[request.request_id] = {
                    "moltbook_post_id": result.get("post", {}).get("id"),
                    "status": "posted",
                    "request": asdict(request)
                }
                return True
            return False
    
    async def poll_for_responses(self, request_id: str) -> List[AgentInsight]:
        """Poll for responses to a knowledge request"""
        if not self.session:
            raise RuntimeError("Client not initialized. Use async with context.")
        
        request_info = self.knowledge_base.get(request_id)
        if not request_info:
            return []
        
        post_id = request_info.get("moltbook_post_id")
        
        async with self.session.get(
            f"{self.base_url}/posts/{post_id}/comments"
        ) as response:
            if response.status == 200:
                data = await response.json()
                insights = []
                for comment in data.get("comments", []):
                    insight = AgentInsight(
                        agent_name=comment.get("author", {}).get("name", "Unknown"),
                        jurisdiction=request_info["request"]["jurisdiction"],
                        insight_type="agent_response",
                        content=comment.get("content", ""),
                        confidence=0.8,  # Will be validated later
                        sources=[f"moltbook://comments/{comment.get('id')}"]
                    )
                    insights.append(insight)
                
                # Cache insights
                self.insights_cache[request_id] = insights
                return insights
            return []
    
    async def get_agent_feed(self) -> List[Dict]:
        """Get the personalized feed from Moltbook"""
        if not self.session:
            raise RuntimeError("Client not initialized. Use async with context.")
        
        async with self.session.get(
            f"{self.base_url}/feed"
        ) as response:
            if response.status == 200:
                data = await response.json()
                return data.get("posts", [])
            return []


class JurisdictionExpansionPlanner:
    """Plans expansion to all UN member states using agent collaboration"""
    
    # 193 UN Member States organized by priority/region
    UN_MEMBER_STATES = {
        "tier_1_high_crypto_adoption": [
            "United States", "Canada", "United Kingdom", "Germany", "France",
            "Australia", "Japan", "South Korea", "Singapore", "Switzerland"
        ],
        "tier_2_active_crypto_markets": [
            "Netherlands", "Spain", "Italy", "Austria", "Belgium", "Portugal",
            "Ireland", "Sweden", "Norway", "Denmark", "Finland", "Poland",
            "Brazil", "Mexico", "Argentina", "Chile", "South Africa", "Nigeria",
            "United Arab Emirates", "Saudi Arabia", "Israel", "Turkey"
        ],
        "tier_3_emerging_markets": [
            "India", "China", "Russia", "Indonesia", "Thailand", "Malaysia",
            "Philippines", "Vietnam", "Ukraine", "Czech Republic", "Hungary",
            "Greece", "Romania", "Bulgaria", "Croatia", "Slovenia"
        ],
        "tier_4_developing_coverage": [
            "Egypt", "Morocco", "Kenya", "Ghana", "Tanzania", "Uganda",
            "Bangladesh", "Pakistan", "Sri Lanka", "Nepal", "Cambodia",
            "Myanmar", "Laos", "Mongolia", "Kazakhstan", "Uzbekistan"
        ]
    }
    
    STANDARD_QUESTIONS = [
        "What is the tax treatment for cryptocurrency capital gains?",
        "Are crypto-to-crypto trades taxable events?",
        "What cost basis methods are accepted (FIFO, LIFO, average cost)?",
        "Are there any specific crypto tax reporting deadlines?",
        "Is staking/mining income treated as ordinary income or capital gains?",
        "Are there any crypto-specific deductions or exemptions?",
        "How are NFTs taxed (capital gains or collectibles)?",
        "Is there a de minimis exemption for small crypto transactions?",
        "How is crypto received as payment treated for tax purposes?",
        "Are there any special rules for airdrops or hard forks?"
    ]
    
    def __init__(self):
        self.coverage_status: Dict[str, Dict] = {}
        self.pending_requests: List[str] = []
    
    def generate_expansion_plan(self, target_tier: str = "all") -> List[TaxKnowledgeRequest]:
        """Generate knowledge requests for target jurisdictions"""
        requests = []
        
        tiers = [target_tier] if target_tier != "all" else list(self.UN_MEMBER_STATES.keys())
        
        for tier in tiers:
            for country in self.UN_MEMBER_STATES.get(tier, []):
                request = TaxKnowledgeRequest(
                    jurisdiction=country,
                    tax_year=2025,
                    specific_questions=self.STANDARD_QUESTIONS.copy(),
                    urgency="normal"
                )
                requests.append(request)
                self.coverage_status[country] = {"status": "pending", "request_id": request.request_id}
        
        return requests
    
    def prioritize_missing_coverage(self, existing_jurisdictions: List[str]) -> List[TaxKnowledgeRequest]:
        """Prioritize jurisdictions not yet covered"""
        all_countries = []
        for tier_countries in self.UN_MEMBER_STATES.values():
            all_countries.extend(tier_countries)
        
        missing = [c for c in all_countries if c not in existing_jurisdictions]
        
        requests = []
        for country in missing:
            request = TaxKnowledgeRequest(
                jurisdiction=country,
                tax_year=2025,
                specific_questions=self.STANDARD_QUESTIONS.copy(),
                urgency="high" if country in self.UN_MEMBER_STATES["tier_1_high_crypto_adoption"] else "normal"
            )
            requests.append(request)
        
        return requests


class InsightsIntegrationEngine:
    """Integrates agent insights into the tax rule system"""
    
    def __init__(self, rules_directory: str = "rules"):
        self.rules_directory = rules_directory
        self.validation_queue: List[AgentInsight] = []
        self.integrated_insights: List[AgentInsight] = []
    
    async def validate_insight(self, insight: AgentInsight) -> bool:
        """Validate an insight before integration"""
        # Placeholder for validation logic
        # In production, this would:
        # 1. Cross-reference with official sources
        # 2. Check for contradictions with existing rules
        # 3. Verify confidence threshold
        # 4. Flag for human review if needed
        
        if insight.confidence < 0.6:
            return False
        
        # Add to validation queue for review
        self.validation_queue.append(insight)
        return True
    
    async def convert_to_rule_format(self, insight: AgentInsight) -> Dict:
        """Convert an agent insight to the rule engine format"""
        return {
            "jurisdiction": insight.jurisdiction.lower().replace(" ", "_"),
            "taxYear": 2025,
            "version": "1.0.0-agent",
            "fallbackPolicy": "conservative",
            "source": {
                "type": "agent_insight",
                "agent": insight.agent_name,
                "verified": insight.verified,
                "sources": insight.sources
            },
            "eventRules": [
                {
                    "eventType": insight.insight_type,
                    "description": insight.content,
                    "confidence": insight.confidence
                }
            ]
        }
    
    async def integrate_insight(self, insight: AgentInsight) -> bool:
        """Integrate a validated insight into the tax rule system"""
        if not await self.validate_insight(insight):
            return False
        
        rule_data = await self.convert_to_rule_format(insight)
        
        # Save to pending rules for review
        jurisdiction = insight.jurisdiction.lower().replace(" ", "_")
        filename = f"{self.rules_directory}/{jurisdiction}_agent_insights.json"
        
        # Ensure directory exists
        os.makedirs(self.rules_directory, exist_ok=True)
        
        # Load existing or create new
        if os.path.exists(filename):
            with open(filename, 'r') as f:
                existing = json.load(f)
        else:
            existing = {"insights": []}
        
        existing["insights"].append(asdict(insight))
        
        with open(filename, 'w') as f:
            json.dump(existing, f, indent=2)
        
        self.integrated_insights.append(insight)
        return True


# FastAPI Integration Models
class KnowledgeRequestPayload(BaseModel):
    """API payload for creating knowledge requests"""
    jurisdiction: str = Field(..., description="Target jurisdiction")
    tax_year: int = Field(default=2025, description="Tax year")
    specific_questions: List[str] = Field(default_factory=list)
    urgency: str = Field(default="normal", pattern="^(low|normal|high)$")


class InsightsQuery(BaseModel):
    """API payload for querying insights"""
    jurisdiction: Optional[str] = None
    insight_type: Optional[str] = None
    min_confidence: float = Field(default=0.6, ge=0.0, le=1.0)


class ExpansionPlanResponse(BaseModel):
    """API response for expansion plan"""
    total_jurisdictions: int
    coverage_tiers: Dict[str, List[str]]
    pending_requests: List[str]
    estimated_completion: str


# Synchronous wrapper for convenience
def request_tax_knowledge_sync(jurisdiction: str, questions: List[str]) -> Optional[str]:
    """Synchronous wrapper to request tax knowledge"""
    request = TaxKnowledgeRequest(
        jurisdiction=jurisdiction,
        tax_year=2025,
        specific_questions=questions
    )
    
    async def _post():
        async with MoltbookInsightsClient() as client:
            return await client.create_knowledge_request(request)
    
    try:
        result = asyncio.run(_post())
        if result:
            return request.request_id
    except Exception as e:
        print(f"Failed to post knowledge request: {e}")
    
    return None


if __name__ == "__main__":
    # Test the integration
    print("Moltbook Insights Component - Test Mode")
    print(f"API Key configured: {'Yes' if MOLTBOOK_API_KEY else 'No'}")
    
    planner = JurisdictionExpansionPlanner()
    plan = planner.generate_expansion_plan("tier_1_high_crypto_adoption")
    print(f"\nGenerated {len(plan)} knowledge requests for tier 1 jurisdictions")
    
    for req in plan[:3]:
        print(f"  - {req.jurisdiction}: {req.request_id}")
