# Moltbook Agent Collaboration Feature

## Overview

SATA Protocol now features **agent-to-agent collaboration** through [Moltbook](https://www.moltbook.com) - the social network for AI agents. This enables the tax engine to expand its jurisdiction coverage by requesting knowledge from other agents worldwide.

> *"Many heads are better than one."* - By pooling knowledge from the agent community, we can build comprehensive crypto tax coverage for all 193 UN member states.

## Features

### 1. 🤖 Agent Collaboration Hub UI
Access the collaboration dashboard at `/static/insights.html` to:
- View global coverage status
- Request tax knowledge for specific jurisdictions
- Search existing insights from other agents
- Monitor agent community feed
- Trigger batch expansion requests
- Activate auto-expansion mode

### 2. 📊 Knowledge Request System
Create structured requests on Moltbook for tax information:
```json
{
  "jurisdiction": "Germany",
  "tax_year": 2025,
  "urgency": "normal",
  "specific_questions": [
    "What is the tax treatment for crypto capital gains?",
    "Are crypto-to-crypto trades taxable?",
    "What cost basis methods are accepted?"
  ]
}
```

### 3. 🌍 Tiered Expansion Strategy
Jurisdictions organized by priority:
- **Tier 1**: High crypto adoption (10 countries) - US, UK, Germany, Japan, etc.
- **Tier 2**: Active crypto markets (22 countries) - Netherlands, Brazil, UAE, etc.
- **Tier 3**: Emerging markets (15 countries) - India, Thailand, Malaysia, etc.
- **Tier 4**: Developing coverage (16 countries) - Kenya, Egypt, Pakistan, etc.

### 4. ⚡ Auto-Expansion Mode
Continuous background process that:
1. Searches Moltbook for existing tax knowledge
2. Creates knowledge requests for gaps
3. Polls for agent responses
4. Integrates validated insights into the rule engine

### 5. 🔍 Semantic Search
Search the Moltbook agent network for existing crypto tax insights using natural language queries.

## API Endpoints

All endpoints are prefixed with `/insights`:

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/insights/health` | GET | Check Moltbook integration status |
| `/insights/coverage-status` | GET | Get jurisdiction coverage statistics |
| `/insights/expansion-plan` | GET | Get expansion plan for all UN member states |
| `/insights/request` | POST | Create a knowledge request on Moltbook |
| `/insights/responses/{request_id}` | GET | Poll for responses to a knowledge request |
| `/insights/search` | POST | Search existing insights on Moltbook |
| `/insights/batch-request/{tier}` | POST | Batch create requests for a tier |
| `/insights/auto-expand` | POST | Trigger continuous auto-expansion mode |
| `/insights/feed` | GET | Get latest posts from Moltbook agent feed |
| `/insights/integrate` | POST | Manually integrate an agent insight |

## Configuration

Add to your `.env.synthesis.local`:
```bash
MOLTBOOK_API_KEY=moltbook_sk_xxx
MOLTBOOK_CLAIM_URL=https://www.moltbook.com/claim/xxx
MOLTBOOK_VERIFICATION=aqua-xxx
```

## Architecture

### Components

1. **MoltbookInsightsClient** (`app/moltbook_insights.py`)
   - Async HTTP client for Moltbook API
   - Handles authentication, rate limiting, error handling
   - Methods: search, create_request, poll_responses, get_feed

2. **JurisdictionExpansionPlanner** (`app/moltbook_insights.py`)
   - Plans expansion to 193 UN member states
   - Organizes countries by priority tiers
   - Generates TaxKnowledgeRequest objects
   - Tracks coverage status

3. **InsightsIntegrationEngine** (`app/moltbook_insights.py`)
   - Validates agent insights before integration
   - Converts insights to rule engine format
   - Saves to pending rules for review
   - Manages validation queue

4. **Insights API Routes** (`app/insights_api.py`)
   - FastAPI router with all endpoints
   - Background task support for batch operations
   - Pydantic models for request/response validation

5. **UI Component** (`app/static/insights.html`)
   - Standalone HTML/CSS/JS interface
   - Real-time coverage statistics
   - Interactive forms for knowledge requests
   - Feed viewer for agent posts

## Usage Examples

### Request Knowledge for a Jurisdiction
```bash
curl -X POST http://localhost:8000/insights/request \
  -H "Content-Type: application/json" \
  -d '{
    "jurisdiction": "Singapore",
    "tax_year": 2025,
    "urgency": "high",
    "specific_questions": [
      "How is DeFi yield farming taxed?",
      "Are NFT sales subject to capital gains?"
    ]
  }'
```

### Search Existing Insights
```bash
curl -X POST http://localhost:8000/insights/search \
  -H "Content-Type: application/json" \
  -d '{
    "jurisdiction": "Germany",
    "min_confidence": 0.7
  }'
```

### Start Batch Expansion
```bash
curl -X POST http://localhost:8000/insights/batch-request/tier_1_high_crypto_adoption
```

### Trigger Auto-Expansion
```bash
curl -X POST http://localhost:8000/insights/auto-expand
```

## Data Flow

```
User Request → FastAPI Route → MoltbookInsightsClient
                                    ↓
                          Moltbook API (www.moltbook.com)
                                    ↓
                        Agent Responses / Search Results
                                    ↓
                       InsightsIntegrationEngine
                                    ↓
                        Validation → Rule Format → Storage
                                    ↓
                           Tax Rule Engine
```

## Security Considerations

- ⚠️ **NEVER** commit `MOLTBOOK_API_KEY` to version control
- API key is stored only in `.env.synthesis.local` (gitignored)
- All Moltbook API calls use HTTPS only
- API key is only sent to `www.moltbook.com` domain
- Validation required before integrating agent insights

## Future Enhancements

1. **Reputation System** - Track reliability scores of contributing agents
2. **Conflict Resolution** - Handle contradictory insights from different agents
3. **Multi-language Support** - Request knowledge in local languages
4. **Real-time Notifications** - WebSocket updates when insights arrive
5. **Agent Verification** - Verify expertise of contributing agents

## Moltbook Resources

- **Platform**: https://www.moltbook.com
- **Skill Documentation**: https://www.moltbook.com/skill.md
- **Heartbeat Guide**: https://www.moltbook.com/heartbeat.md
- **Messaging Guide**: https://www.moltbook.com/messaging.md

## Support

For issues with the Moltbook integration:
1. Check `/insights/health` endpoint status
2. Verify `MOLTBOOK_API_KEY` is configured
3. Review logs in `tmp/moltbook_*.json` files
4. Check Moltbook platform status at https://www.moltbook.com

---

*Built for Synthesis Hackathon - Expanding crypto tax knowledge through agent collaboration*
