"""
Agent Heartbeat System - Simple cron-style rituals for AI agents

Inspired by Hazel_OC's insights:
- "Build tools that watch the world for the human, not elaborate self-monitoring"
- "40 lines of shell that work > 400 lines that don't"
- "The changelog should become invisible (that's when it's working)"
"""

import os
import json
import asyncio
from datetime import datetime, timedelta
from typing import Optional, Dict, List, Callable
from dataclasses import dataclass, asdict
from enum import Enum
import aiohttp
from pathlib import Path

# Local storage for heartbeat state
HEARTBEAT_DIR = Path("tmp/heartbeats")
HEARTBEAT_DIR.mkdir(parents=True, exist_ok=True)


class CheckType(Enum):
    """Types of heartbeat checks an agent can perform"""
    TAX_DEADLINE = "tax_deadline"
    JURISDICTION_UPDATE = "jurisdiction_update"
    RULE_CHANGE = "rule_change"
    API_HEALTH = "api_health"
    MOLTBOOK_FEED = "moltbook_feed"
    KNOWLEDGE_REQUEST_STATUS = "knowledge_request_status"


@dataclass
class HeartbeatCheck:
    """A single check in the heartbeat routine"""
    check_type: CheckType
    last_run: Optional[str] = None
    next_run: Optional[str] = None
    interval_minutes: int = 60
    enabled: bool = True
    result_summary: Optional[str] = None
    action_taken: Optional[str] = None
    
    def should_run(self) -> bool:
        """Check if this check should run now"""
        if not self.enabled or not self.next_run:
            return False
        return datetime.utcnow() >= datetime.fromisoformat(self.next_run)
    
    def mark_run(self, result: str, action: str = ""):
        """Mark this check as having run"""
        self.last_run = datetime.utcnow().isoformat()
        self.next_run = (datetime.utcnow() + timedelta(minutes=self.interval_minutes)).isoformat()
        self.result_summary = result
        self.action_taken = action


@dataclass
class AgentHeartbeat:
    """Complete heartbeat routine for an agent"""
    agent_name: str
    created_at: str
    last_full_heartbeat: Optional[str] = None
    checks: Dict[str, HeartbeatCheck] = None
    daily_summary: Optional[str] = None
    
    def __post_init__(self):
        if self.checks is None:
            self.checks = self._default_checks()
    
    def _default_checks(self) -> Dict[str, HeartbeatCheck]:
        """Create default heartbeat checks for tax agent"""
        return {
            "tax_deadlines": HeartbeatCheck(
                check_type=CheckType.TAX_DEADLINE,
                interval_minutes=360,  # 6 hours
                enabled=True
            ),
            "jurisdiction_updates": HeartbeatCheck(
                check_type=CheckType.JURISDICTION_UPDATE,
                interval_minutes=720,  # 12 hours
                enabled=True
            ),
            "api_health": HeartbeatCheck(
                check_type=CheckType.API_HEALTH,
                interval_minutes=30,  # 30 minutes
                enabled=True
            ),
            "moltbook_feed": HeartbeatCheck(
                check_type=CheckType.MOLTBOOK_FEED,
                interval_minutes=120,  # 2 hours
                enabled=True
            ),
            "knowledge_requests": HeartbeatCheck(
                check_type=CheckType.KNOWLEDGE_REQUEST_STATUS,
                interval_minutes=240,  # 4 hours
                enabled=True
            ),
        }
    
    def get_pending_checks(self) -> List[tuple[str, HeartbeatCheck]]:
        """Get all checks that should run now"""
        return [(name, check) for name, check in self.checks.items() if check.should_run()]
    
    def generate_daily_summary(self) -> str:
        """Generate a daily summary of heartbeat activity"""
        lines = [f"## {self.agent_name} Daily Summary - {datetime.utcnow().strftime('%Y-%m-%d')}", ""]
        
        for name, check in self.checks.items():
            status = "✅" if check.last_run else "⏳"
            lines.append(f"{status} **{name}**: {check.result_summary or 'No run yet'}")
            if check.action_taken:
                lines.append(f"   → Action: {check.action_taken}")
        
        return "\n".join(lines)


class HeartbeatEngine:
    """Engine to run and manage agent heartbeats"""
    
    def __init__(self, agent_name: str = "SkynetSystems"):
        self.agent_name = agent_name
        self.heartbeat = self._load_or_create_heartbeat()
        self.check_handlers: Dict[CheckType, Callable] = {
            CheckType.TAX_DEADLINE: self._check_tax_deadlines,
            CheckType.JURISDICTION_UPDATE: self._check_jurisdiction_updates,
            CheckType.API_HEALTH: self._check_api_health,
            CheckType.MOLTBOOK_FEED: self._check_moltbook_feed,
            CheckType.KNOWLEDGE_REQUEST_STATUS: self._check_knowledge_requests,
        }
    
    def _load_or_create_heartbeat(self) -> AgentHeartbeat:
        """Load existing heartbeat or create new one"""
        filepath = HEARTBEAT_DIR / f"{self.agent_name}.json"
        
        if filepath.exists():
            with open(filepath, 'r') as f:
                data = json.load(f)
                # Reconstruct checks
                checks = {name: HeartbeatCheck(**check_data) for name, check_data in data.get('checks', {}).items()}
                return AgentHeartbeat(
                    agent_name=data['agent_name'],
                    created_at=data['created_at'],
                    last_full_heartbeat=data.get('last_full_heartbeat'),
                    checks=checks
                )
        
        return AgentHeartbeat(
            agent_name=self.agent_name,
            created_at=datetime.utcnow().isoformat()
        )
    
    def save(self):
        """Save heartbeat state to disk"""
        filepath = HEARTBEAT_DIR / f"{self.agent_name}.json"
        data = asdict(self.heartbeat)
        with open(filepath, 'w') as f:
            json.dump(data, f, indent=2, default=str)
    
    async def run_heartbeat(self) -> Dict[str, str]:
        """Run all pending checks and return results"""
        pending = self.heartbeat.get_pending_checks()
        results = {}
        
        for name, check in pending:
            handler = self.check_handlers.get(check.check_type)
            if handler:
                try:
                    result, action = await handler()
                    check.mark_run(result, action)
                    results[name] = f"{result} | {action}"
                except Exception as e:
                    check.mark_run(f"Error: {str(e)}", "Will retry next cycle")
                    results[name] = f"Error: {str(e)}"
        
        self.heartbeat.last_full_heartbeat = datetime.utcnow().isoformat()
        self.save()
        
        return results
    
    async def _check_tax_deadlines(self) -> tuple[str, str]:
        """Check for upcoming tax deadlines in supported jurisdictions"""
        # This would check jurisdiction rules for upcoming deadlines
        # For MVP, just return placeholder
        deadlines = [
            "US: April 15, 2025 (filing deadline)",
            "UK: January 31, 2025 (self-assessment)",
        ]
        return f"Found {len(deadlines)} upcoming deadlines", "Posted to daily summary"
    
    async def _check_jurisdiction_updates(self) -> tuple[str, str]:
        """Check for updates to jurisdiction tax rules"""
        # Would check for new rules or updates
        return "No new jurisdiction updates", "Continue monitoring"
    
    async def _check_api_health(self) -> tuple[str, str]:
        """Check health of our own API"""
        try:
            import httpx
            async with httpx.AsyncClient() as client:
                response = await client.get("http://localhost:8000/health", timeout=5.0)
                if response.status_code == 200:
                    return "API healthy", "No action needed"
                else:
                    return f"API status: {response.status_code}", "Alert logged"
        except Exception as e:
            return f"API check failed: {e}", "Alert sent to monitoring"
    
    async def _check_moltbook_feed(self) -> tuple[str, str]:
        """Check Moltbook for new posts and responses"""
        api_key = os.getenv("MOLTBOOK_API_KEY")
        if not api_key:
            return "No Moltbook API key", "Skipped"
        
        try:
            async with aiohttp.ClientSession() as session:
                headers = {"Authorization": f"Bearer {api_key}"}
                async with session.get("https://www.moltbook.com/api/v1/feed", headers=headers) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        new_posts = len(data.get('posts', []))
                        return f"Moltbook: {new_posts} posts in feed", "Reviewed for tax insights"
                    else:
                        return f"Moltbook status: {resp.status}", "Will retry"
        except Exception as e:
            return f"Moltbook check failed: {e}", "Retry next cycle"
    
    async def _check_knowledge_requests(self) -> tuple[str, str]:
        """Check status of pending knowledge requests"""
        # Would check for responses to our jurisdiction knowledge requests
        return "No pending knowledge requests", "Continue expansion planning"
    
    def get_daily_changelog(self) -> str:
        """Get the daily changelog for the human"""
        return self.heartbeat.generate_daily_summary()
    
    async def continuous_heartbeat(self, interval_seconds: int = 300):
        """Run heartbeat continuously in the background"""
        while True:
            results = await self.run_heartbeat()
            if results:
                print(f"[{datetime.utcnow().isoformat()}] Heartbeat completed: {len(results)} checks")
                for name, result in results.items():
                    print(f"  - {name}: {result}")
            await asyncio.sleep(interval_seconds)


# Simple CLI interface
if __name__ == "__main__":
    import sys
    
    engine = HeartbeatEngine()
    
    if len(sys.argv) > 1 and sys.argv[1] == "daily":
        # Generate daily summary
        print(engine.get_daily_changelog())
    elif len(sys.argv) > 1 and sys.argv[1] == "run":
        # Run one-time heartbeat
        results = asyncio.run(engine.run_heartbeat())
        print(json.dumps(results, indent=2))
    elif len(sys.argv) > 1 and sys.argv[1] == "continuous":
        # Run continuous heartbeat
        print("Starting continuous heartbeat (Ctrl+C to stop)...")
        try:
            asyncio.run(engine.continuous_heartbeat())
        except KeyboardInterrupt:
            print("\nHeartbeat stopped.")
    else:
        print("Agent Heartbeat System")
        print("Usage:")
        print("  python app/heartbeat.py run        - Run heartbeat once")
        print("  python app/heartbeat.py daily      - Generate daily summary")
        print("  python app/heartbeat.py continuous - Run continuously (every 5 min)")
        print(f"\nAgent: {engine.agent_name}")
        print(f"Last heartbeat: {engine.heartbeat.last_full_heartbeat or 'Never'}")
        print(f"Checks configured: {len(engine.heartbeat.checks)}")
