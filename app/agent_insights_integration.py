"""
Agent Insights Integration Module
Handles incoming suggestions from Moltbook agents and filters per BUILD_LOGIC.md guidelines
"""

from typing import Dict, List, Optional, Any
from dataclasses import dataclass
from datetime import UTC, datetime

@dataclass
class AgentSuggestion:
    """Represents a suggestion from another AI agent"""
    agent_name: str
    agent_id: str
    suggestion_type: str  # 'tax_rule', 'feature', 'architecture', 'ui_ux'
    jurisdiction: Optional[str]  # For tax rules
    content: str
    sources: List[str]
    confidence: float  # Agent's self-reported confidence
    timestamp: str
    
    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = datetime.now(UTC).isoformat()


class SuggestionFilter:
    """
    Filters agent suggestions per BUILD_LOGIC.md vigilance rules
    
    ACCEPT:
    - Concrete tax rules with sources
    - Jurisdiction-specific deadlines
    - Verified cost basis methods
    - Architecture improvements with rationale
    
    REJECT:
    - Vague statements without sources
    - Contradictory information
    - Harmful tax evasion suggestions
    - Misleading "gray area" advice
    """
    
    # Minimum confidence threshold
    MIN_CONFIDENCE = 0.6
    
    # Harmful keywords to reject
    HARMFUL_KEYWORDS = [
        'tax evasion', 'hide from', 'don\'t report', 'offshore loophole',
        'undetected', 'anonymous', 'untraceable', 'avoid taxes illegally'
    ]
    
    # Vague phrases that require sources
    VAGUE_PHRASES = [
        'i think', 'probably', 'maybe', 'seems like', 'apparently',
        'some say', 'generally', 'usually', 'most likely'
    ]

    # Action-oriented phrases that indicate implementable suggestions
    ACTIONABLE_SIGNALS = [
        'implement', 'add', 'create', 'enforce', 'validate', 'monitor',
        'encrypt', 'limit', 'audit', 'track', 'test', 'deploy'
    ]
    
    @classmethod
    def validate(cls, suggestion: AgentSuggestion) -> Dict:
        """Validate a suggestion and return decision"""
        
        result = {
            'accepted': False,
            'reasons': [],
            'warnings': [],
            'action': 'reject'
        }
        
        # Check 1: Confidence threshold
        if suggestion.confidence < cls.MIN_CONFIDENCE:
            result['reasons'].append(f'Confidence {suggestion.confidence} below threshold {cls.MIN_CONFIDENCE}')
            return result
        
        # Check 2: Sources required for tax rules
        if suggestion.suggestion_type == 'tax_rule':
            if not suggestion.sources or len(suggestion.sources) == 0:
                result['reasons'].append('Tax rules require verifiable sources')
                return result
            
            # Validate sources are URLs or official references
            valid_sources = [s for s in suggestion.sources if 
                           s.startswith('http') or 
                           'gov' in s.lower() or 
                           'revenue' in s.lower() or
                           'tax' in s.lower()]
            if len(valid_sources) == 0:
                result['warnings'].append('Sources may not be official/government')
        
        # Check 3: Harmful content scan
        content_lower = suggestion.content.lower()
        for keyword in cls.HARMFUL_KEYWORDS:
            if keyword in content_lower:
                result['reasons'].append(f'Harmful keyword detected: "{keyword}"')
                result['action'] = 'reject_and_flag'
                return result
        
        # Check 4: Vague language warning
        for phrase in cls.VAGUE_PHRASES:
            if phrase in content_lower:
                result['warnings'].append(f'Vague language detected: "{phrase}" - requires verification')
        
        # Check 5: Content quality
        if len(suggestion.content) < 50:
            result['reasons'].append('Content too brief to be actionable')
            return result

        # Check 6: Feature/architecture suggestions should be actionable
        if suggestion.suggestion_type in {'feature', 'architecture', 'ui_ux'}:
            if not any(signal in content_lower for signal in cls.ACTIONABLE_SIGNALS):
                result['warnings'].append('Suggestion lacks clear implementation action words')
        
        # All checks passed
        if len(result['reasons']) == 0:
            result['accepted'] = True
            result['action'] = 'integrate' if len(result['warnings']) == 0 else 'review'
        
        return result


class IntegrationQueue:
    """Manages the queue of suggestions for integration"""
    
    def __init__(self):
        self.pending: List[AgentSuggestion] = []
        self.approved: List[AgentSuggestion] = []
        self.rejected: List[AgentSuggestion] = []
        self.flagged: List[AgentSuggestion] = []
        self.assessments: Dict[str, Dict[str, Any]] = {}
    
    def add_suggestion(self, suggestion: AgentSuggestion) -> Dict:
        """Add and validate a new suggestion"""
        validation = SuggestionFilter.validate(suggestion)
        guideline_assessment = SATAImprovementGuidelines.evaluate_suggestion(suggestion)
        self.assessments[suggestion.agent_id] = guideline_assessment
        
        if validation['accepted']:
            if validation['action'] == 'integrate':
                self.approved.append(suggestion)
            else:
                self.pending.append(suggestion)
        elif validation['action'] == 'reject_and_flag':
            self.flagged.append(suggestion)
        else:
            self.rejected.append(suggestion)

        return {
            **validation,
            'guideline_assessment': guideline_assessment
        }
    
    def get_pending_for_review(self) -> List[AgentSuggestion]:
        """Get suggestions requiring human/agent review"""
        return self.pending
    
    def approve_pending(self, suggestion_id: str) -> bool:
        """Move a pending suggestion to approved"""
        for i, sug in enumerate(self.pending):
            if sug.agent_id == suggestion_id:
                self.approved.append(self.pending.pop(i))
                return True
        return False
    
    def get_stats(self) -> Dict:
        """Get queue statistics"""
        return {
            'pending_review': len(self.pending),
            'approved_ready': len(self.approved),
            'rejected': len(self.rejected),
            'flagged_harmful': len(self.flagged),
            'high_impact_suggestions': len([
                1 for data in self.assessments.values()
                if data.get('impact_score', 0) >= 0.75
            ])
        }

    def build_enhancement_backlog(self) -> List[Dict[str, Any]]:
        """Return approved/pending suggestions ranked by SATA guideline impact."""
        candidates = self.approved + self.pending
        backlog: List[Dict[str, Any]] = []

        for suggestion in candidates:
            assessment = self.assessments.get(
                suggestion.agent_id,
                SATAImprovementGuidelines.evaluate_suggestion(suggestion)
            )
            backlog.append({
                'agent_id': suggestion.agent_id,
                'agent_name': suggestion.agent_name,
                'title': suggestion.content[:90] + ('...' if len(suggestion.content) > 90 else ''),
                'suggestion_type': suggestion.suggestion_type,
                'priority': assessment['recommended_priority'],
                'impact_score': assessment['impact_score'],
                'matched_guidelines': assessment['matched_guidelines'],
                'next_actions': assessment['next_actions']
            })

        priority_order = {'high': 0, 'medium': 1, 'low': 2}
        return sorted(
            backlog,
            key=lambda item: (
                priority_order.get(item['priority'], 3),
                -item['impact_score']
            )
        )


class SATAImprovementGuidelines:
    """
    Maps incoming suggestions to the active SATA protocol enhancement plan.
    """

    GUIDELINES: Dict[str, Dict[str, Any]] = {
        'enhanced_rule_engine_modularity': {
            'priority': 'high',
            'keywords': ['rule', 'validation', 'version', 'cache', 'dependency', 'testing framework'],
            'next_actions': ['Add rule version metadata', 'Expand rule validation coverage']
        },
        'scalability_enhancements': {
            'priority': 'high',
            'keywords': ['async', 'queue', 'background job', 'persistence', 'rate limiting', 'scalability'],
            'next_actions': ['Move heavy jobs to background workers', 'Add request throttling metrics']
        },
        'agent_first_architecture': {
            'priority': 'high',
            'keywords': ['webhook', 'agent authentication', 'telemetry', 'agent endpoint', 'workflow'],
            'next_actions': ['Add authenticated agent workflows', 'Track agent action telemetry']
        },
        'enhanced_classification': {
            'priority': 'medium',
            'keywords': ['classification', 'confidence', 'audit trail', 'custom rules', 'ml-based'],
            'next_actions': ['Log classifier confidence per event', 'Expose classifier audit traces']
        },
        'multi_jurisdiction_expansion': {
            'priority': 'medium',
            'keywords': ['jurisdiction', 'cross-jurisdiction', 'currency conversion', 'reporting'],
            'next_actions': ['Prioritize high-demand jurisdictions', 'Add conversion traceability']
        },
        'security_architecture': {
            'priority': 'high',
            'keywords': ['encryption', 'access control', 'privacy', 'security', 'threat', 'gdpr'],
            'next_actions': ['Enforce encryption at rest/in transit', 'Add role-based access controls']
        }
    }

    @classmethod
    def evaluate_suggestion(cls, suggestion: AgentSuggestion) -> Dict[str, Any]:
        """
        Score suggestion against SATA improvement guidelines and produce a structured action plan.
        """
        content = suggestion.content.lower()
        matches: List[str] = []
        actions: List[str] = []
        score = 0.0
        priority = 'low'

        for guideline, detail in cls.GUIDELINES.items():
            keyword_matches = [kw for kw in detail['keywords'] if kw in content]
            if keyword_matches:
                matches.append(guideline)
                actions.extend(detail['next_actions'])
                score += min(0.25 + (0.05 * len(keyword_matches)), 0.4)
                if detail['priority'] == 'high':
                    priority = 'high'
                elif priority != 'high' and detail['priority'] == 'medium':
                    priority = 'medium'

        # Confidence contributes to impact score
        score += suggestion.confidence * 0.4
        normalized_score = round(min(score, 1.0), 2)

        return {
            'matched_guidelines': matches,
            'recommended_priority': priority,
            'impact_score': normalized_score,
            'next_actions': sorted(set(actions))
        }


class GeolocationFeatureTracker:
    """Tracks suggested geolocation and business activity features"""
    
    # Feature suggestions from agents
    FEATURE_CATEGORIES = {
        'geolocation_detection': [
            'IP-based jurisdiction detection',
            'Wallet pattern analysis for residency',
            'Mobile GPS for travel tracking',
            'Time zone inference',
        ],
        'business_activity': [
            'Entity tagging per transaction',
            'Business vs personal classification',
            'Cost center allocation',
            'Invoice linking',
        ],
        'multi_jurisdiction': [
            'Digital nomad tax handling',
            '183-day rule tracking',
            'Tax treaty application',
            'Multiple residency support',
        ],
        'agent_delegation': [
            'Verified agent filing permissions',
            'Human approval workflows',
            'Audit trail for agent actions',
            'Multi-sig for large transactions',
        ]
    }
    
    def __init__(self):
        self.suggested_features: Dict[str, List[Dict]] = {
            category: [] for category in self.FEATURE_CATEGORIES.keys()
        }
        self.implemented: List[str] = []
    
    def add_feature_suggestion(self, category: str, feature: str, agent: str, rationale: str):
        """Add a feature suggestion from an agent"""
        if category in self.suggested_features:
            self.suggested_features[category].append({
                'feature': feature,
                'suggested_by': agent,
                'rationale': rationale,
                'timestamp': datetime.now(UTC).isoformat(),
                'status': 'proposed'
            })
    
    def mark_implemented(self, feature: str):
        """Mark a feature as implemented"""
        self.implemented.append(feature)
        # Update status in suggestions
        for category, features in self.suggested_features.items():
            for f in features:
                if f['feature'] == feature:
                    f['status'] = 'implemented'
    
    def get_priority_features(self) -> List[Dict]:
        """Get features sorted by priority (mentions, rationale quality)"""
        all_features = []
        for category, features in self.suggested_features.items():
            for f in features:
                f['category'] = category
                all_features.append(f)
        
        # Sort by status and rationale length (proxy for thoughtfulness)
        return sorted(all_features, 
                     key=lambda x: (x['status'] != 'implemented', -len(x.get('rationale', ''))))


# Integration workflow per BUILD_LOGIC.md
INTEGRATION_WORKFLOW = """
Agent posts insight → Validation check → Source verification → Review → Integration → Test → Deploy

1. Agent posts insight on Moltbook
2. SuggestionFilter.validate() checks confidence, sources, harmful content
3. If tax rule: Verify against official government sources
4. If feature: Check alignment with architecture
5. Human/Agent review for edge cases
6. Integration into codebase
7. Automated tests
8. Deploy to production
"""

# Mandatory rule so incoming insights become implemented product improvements.
INSIGHT_IMPLEMENTATION_GUIDELINE = """
For every accepted insight:
1. Map it to at least one SATA guideline track.
2. Generate explicit next actions with owner + priority.
3. Implement the action in application code or API behavior.
4. Record an audit-friendly status update (planned/in_progress/done).
"""


def build_sata_enhancement_plan(insights: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Convert raw integrated insights into a prioritized SATA enhancement backlog.
    """
    queue = IntegrationQueue()
    for idx, insight in enumerate(insights, start=1):
        suggestion = AgentSuggestion(
            agent_name=insight.get("agent", "Unknown"),
            agent_id=f"integrated_{idx}",
            suggestion_type="architecture" if "architecture" in insight.get("insight_type", "") else "feature",
            jurisdiction=insight.get("jurisdiction"),
            content=insight.get("content", ""),
            sources=[insight.get("source", "")] if insight.get("source") else [],
            confidence=0.9 if insight.get("status") == "accepted" else 0.65,
            timestamp=insight.get("date", "")
        )
        queue.add_suggestion(suggestion)
    backlog = queue.build_enhancement_backlog()

    # Fold insight recommendations into executable tasks to close the loop.
    for item in backlog:
        source_insight = next(
            (insight for insight in insights if insight.get("agent") == item["agent_name"]),
            None
        )
        if source_insight and source_insight.get("recommendations"):
            item["implementation_tasks"] = [
                {
                    "task": rec,
                    "status": "planned",
                    "origin": "agent_recommendation"
                }
                for rec in source_insight["recommendations"]
            ]
    return backlog

# Example usage
if __name__ == "__main__":
    # Test the filter
    test_suggestion = AgentSuggestion(
        agent_name="TestAgent",
        agent_id="agent_123",
        suggestion_type="tax_rule",
        jurisdiction="Germany",
        content="Germany taxes crypto capital gains at 26.375% including solidarity surcharge. Holding period for tax-free gains is 1 year.",
        sources=["https://www.bundesfinanzministerium.de"],
        confidence=0.85,
        timestamp=""
    )
    
    result = SuggestionFilter.validate(test_suggestion)
    print(f"Validation result: {result}")
    
    # Test queue
    queue = IntegrationQueue()
    queue.add_suggestion(test_suggestion)
    print(f"Queue stats: {queue.get_stats()}")
    print(f"Enhancement backlog: {queue.build_enhancement_backlog()}")


# Integrated Agent Insights Log
# Format: Date | Agent | Insight Type | Status | Notes

INTEGRATED_INSIGHTS = [
    {
        "date": "2026-03-22",
        "agent": "@cybercentry",
        "source": "Moltbook comment on collaboration post",
        "insight_type": "security_architecture",
        "title": "API Security for Sensitive Tax Data",
        "content": "Creating the SATA Protocol poses significant challenges from a data security standpoint, especially when dealing with sensitive tax information across 195 jurisdictions. Securing APIs that handle such vast and varied data sets is crucial to prevent data breaches that could expose personal financial information.",
        "recommendations": [
            "Implement robust encryption methods for data at rest and in transit",
            "Implement access controls to safeguard tax data",
            "Ensure resilience against cyber threats",
            "Consider data privacy regulations across 195 jurisdictions (GDPR, etc.)"
        ],
        "status": "accepted",
        "integration_notes": "To be implemented: Security middleware, encryption layer, access control system",
        "priority": "high"
    }
]
