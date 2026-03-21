"""
Enhanced Rule Engine for Skynet
Provides modular, versioned, and cached rule processing
"""

from __future__ import annotations

import hashlib
import json
import time
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

from app.models import EventRule, RuleSet, EventType, TaxTreatment


@dataclass
class RuleMetadata:
    """Metadata for rule caching and versioning"""
    rule_id: str
    version: str
    jurisdiction: str
    tax_year: int
    checksum: str
    last_modified: datetime
    dependencies: List[str]


@dataclass
class CachedRule:
    """Cached rule with TTL"""
    rule: RuleSet
    metadata: RuleMetadata
    cached_at: datetime
    ttl: timedelta = timedelta(hours=1)

    def is_expired(self) -> bool:
        return datetime.now() > self.cached_at + self.ttl


class RuleValidationError(Exception):
    """Raised when rule validation fails"""
    pass


class RuleEngine:
    """Enhanced rule engine with caching and validation"""
    
    def __init__(self, rules_dir: Path):
        self.rules_dir = rules_dir
        self._cache: Dict[str, CachedRule] = {}
        self._rule_metadata: Dict[str, RuleMetadata] = {}
        
    def _calculate_checksum(self, rule_data: dict) -> str:
        """Calculate checksum for rule data"""
        rule_str = json.dumps(rule_data, sort_keys=True)
        return hashlib.sha256(rule_str.encode()).hexdigest()[:16]
    
    def _validate_rule(self, rule_data: dict) -> None:
        """Validate rule structure and content"""
        required_fields = ['jurisdiction', 'taxYear', 'version', 'eventRules']
        for field in required_fields:
            if field not in rule_data:
                raise RuleValidationError(f"Missing required field: {field}")
        
        # Validate event rules
        for i, event_rule in enumerate(rule_data.get('eventRules', [])):
            if 'eventType' not in event_rule:
                raise RuleValidationError(f"Event rule {i} missing eventType")
            if 'taxTreatment' not in event_rule:
                raise RuleValidationError(f"Event rule {i} missing taxTreatment")
            
            # Validate enum values
            try:
                EventType(event_rule['eventType'])
                TaxTreatment(event_rule['taxTreatment'])
            except ValueError as e:
                raise RuleValidationError(f"Invalid enum value in event rule {i}: {e}")
    
    def _load_rule_metadata(self, rule_file: Path) -> RuleMetadata:
        """Load metadata for a rule file"""
        with open(rule_file, 'r') as f:
            rule_data = json.load(f)
        
        self._validate_rule(rule_data)
        
        rule_id = f"{rule_data['jurisdiction']}_{rule_data['taxYear']}_{rule_data['version']}"
        checksum = self._calculate_checksum(rule_data)
        
        return RuleMetadata(
            rule_id=rule_id,
            version=rule_data['version'],
            jurisdiction=rule_data['jurisdiction'],
            tax_year=rule_data['taxYear'],
            checksum=checksum,
            last_modified=datetime.fromtimestamp(rule_file.stat().st_mtime),
            dependencies=rule_data.get('dependencies', [])
        )
    
    def _load_rule(self, rule_file: Path) -> RuleSet:
        """Load rule from file"""
        with open(rule_file, 'r') as f:
            rule_data = json.load(f)
        
        self._validate_rule(rule_data)
        return RuleSet(**rule_data)
    
    def _get_cache_key(self, jurisdiction: str, tax_year: int) -> str:
        """Generate cache key for ruleset"""
        return f"{jurisdiction}_{tax_year}"
    
    def get_ruleset(self, jurisdiction: str, tax_year: int, force_refresh: bool = False) -> RuleSet:
        """Get ruleset with caching"""
        cache_key = self._get_cache_key(jurisdiction, tax_year)
        
        # Check cache first
        if not force_refresh and cache_key in self._cache:
            cached_rule = self._cache[cache_key]
            if not cached_rule.is_expired():
                return cached_rule.rule
        
        # Find rule file
        rule_file = self.rules_dir / f"{jurisdiction.lower()}_{tax_year}.sample.json"
        if not rule_file.exists():
            raise FileNotFoundError(f"No rule file found for {jurisdiction} {tax_year}")
        
        # Load and cache rule
        rule = self._load_rule(rule_file)
        metadata = self._load_rule_metadata(rule_file)
        
        self._cache[cache_key] = CachedRule(
            rule=rule,
            metadata=metadata,
            cached_at=datetime.now()
        )
        
        return rule
    
    def get_rule_metadata(self, jurisdiction: str, tax_year: int) -> Optional[RuleMetadata]:
        """Get metadata for a ruleset"""
        cache_key = self._get_cache_key(jurisdiction, tax_year)
        
        if cache_key in self._cache:
            return self._cache[cache_key].metadata
        
        try:
            rule_file = self.rules_dir / f"{jurisdiction.lower()}_{tax_year}.sample.json"
            if rule_file.exists():
                return self._load_rule_metadata(rule_file)
        except Exception:
            pass
        
        return None
    
    def list_available_jurisdictions(self) -> List[str]:
        """List all available jurisdictions"""
        jurisdictions = set()
        for rule_file in self.rules_dir.glob("*.json"):
            try:
                metadata = self._load_rule_metadata(rule_file)
                jurisdictions.add(metadata.jurisdiction)
            except Exception:
                continue
        return sorted(list(jurisdictions))
    
    def list_available_years(self, jurisdiction: str) -> List[int]:
        """List available tax years for a jurisdiction"""
        years = set()
        for rule_file in self.rules_dir.glob(f"{jurisdiction.lower()}_*.json"):
            try:
                metadata = self._load_rule_metadata(rule_file)
                if metadata.jurisdiction == jurisdiction:
                    years.add(metadata.tax_year)
            except Exception:
                continue
        return sorted(list(years))
    
    def clear_cache(self) -> None:
        """Clear all cached rules"""
        self._cache.clear()
    
    def get_cache_stats(self) -> Dict[str, Any]:
        """Get cache statistics"""
        total_cached = len(self._cache)
        expired_count = sum(1 for cached in self._cache.values() if cached.is_expired())
        
        return {
            'total_cached': total_cached,
            'active': total_cached - expired_count,
            'expired': expired_count,
            'cache_keys': list(self._cache.keys())
        }
