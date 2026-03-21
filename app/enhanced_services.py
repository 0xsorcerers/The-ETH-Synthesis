"""
Enhanced Services for Skynet
Integrates the new rule engine with improved scalability and agent support
"""

from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional
from concurrent.futures import ThreadPoolExecutor

from app.rule_engine import RuleEngine, RuleValidationError
from app.models import (
    RuleSet, EventRule, EventType, TaxTreatment,
    ClassifiedTransaction, NormalizedTransaction,
    TaxReport, ReportLineItem, ReportSummary
)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class EnhancedTaxService:
    """Enhanced tax service with async processing and improved rule management"""
    
    def __init__(self, rules_dir: Path):
        self.rule_engine = RuleEngine(rules_dir)
        self.executor = ThreadPoolExecutor(max_workers=4)
        
    async def get_available_jurisdictions(self) -> List[str]:
        """Get list of available jurisdictions asynchronously"""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            self.executor, 
            self.rule_engine.list_available_jurisdictions
        )
    
    async def get_available_years(self, jurisdiction: str) -> List[int]:
        """Get available tax years for a jurisdiction asynchronously"""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            self.executor,
            lambda: self.rule_engine.list_available_years(jurisdiction)
        )
    
    async def get_ruleset(self, jurisdiction: str, tax_year: int) -> RuleSet:
        """Get ruleset asynchronously with caching"""
        loop = asyncio.get_event_loop()
        try:
            return await loop.run_in_executor(
                self.executor,
                self.rule_engine.get_ruleset,
                jurisdiction,
                tax_year
            )
        except FileNotFoundError:
            raise ValueError(f"No ruleset found for {jurisdiction} {tax_year}")
        except RuleValidationError as e:
            raise ValueError(f"Invalid ruleset for {jurisdiction} {tax_year}: {e}")
    
    async def classify_transaction_async(
        self, 
        transaction: NormalizedTransaction, 
        ruleset: RuleSet
    ) -> ClassifiedTransaction:
        """Classify a single transaction asynchronously"""
        loop = asyncio.get_event_loop()
        
        def _classify():
            # Rule-based classification
            for rule in ruleset.eventRules:
                if self._matches_rule(transaction, rule):
                    return ClassifiedTransaction(
                        tx_id=transaction.tx_id,
                        timestamp=transaction.timestamp,
                        asset=transaction.asset,
                        quantity=transaction.quantity,
                        tx_hash=transaction.tx_hash,
                        network=transaction.network,
                        wallet_provider=transaction.wallet_provider,
                        source_app=transaction.source_app,
                        event_hint=transaction.event_hint,
                        price_usd=transaction.price_usd,
                        proceeds_usd=transaction.proceeds_usd,
                        fee_usd=transaction.fee_usd,
                        counter_asset=transaction.counter_asset,
                        counter_quantity=transaction.counter_quantity,
                        description=transaction.description,
                        event_type=rule.eventType,
                        tax_treatment=rule.taxTreatment,
                        confidence=rule.confidence,
                        applied_rule_id=f"{ruleset.jurisdiction}_{ruleset.tax_year}_{rule.eventType}",
                        classification_method="rule_based"
                    )
            
            # Fallback classification
            return ClassifiedTransaction(
                tx_id=transaction.tx_id,
                timestamp=transaction.timestamp,
                asset=transaction.asset,
                quantity=transaction.quantity,
                tx_hash=transaction.tx_hash,
                network=transaction.network,
                wallet_provider=transaction.wallet_provider,
                source_app=transaction.source_app,
                event_hint=transaction.event_hint,
                price_usd=transaction.price_usd,
                proceeds_usd=transaction.proceeds_usd,
                fee_usd=transaction.fee_usd,
                counter_asset=transaction.counter_asset,
                counter_quantity=transaction.counter_quantity,
                description=transaction.description,
                event_type="transfer",  # Default fallback
                tax_treatment="non_taxable",  # Conservative fallback
                confidence=0.3,  # Low confidence for fallback
                applied_rule_id="fallback_rule",
                classification_method="fallback"
            )
        
        return await loop.run_in_executor(self.executor, _classify)
    
    async def classify_transactions_batch(
        self, 
        transactions: List[NormalizedTransaction], 
        ruleset: RuleSet
    ) -> List[ClassifiedTransaction]:
        """Classify multiple transactions in parallel"""
        tasks = [
            self.classify_transaction_async(tx, ruleset) 
            for tx in transactions
        ]
        return await asyncio.gather(*tasks)
    
    def _matches_rule(self, transaction: NormalizedTransaction, rule: EventRule) -> bool:
        """Check if a transaction matches a rule"""
        # Enhanced rule matching logic
        if transaction.event_hint:
            # Check event hint first
            hint_lower = transaction.event_hint.lower()
            if rule.eventType == "income" and any(word in hint_lower for word in ["income", "reward", "yield", "interest"]):
                return True
            elif rule.eventType == "swap" and any(word in hint_lower for word in ["swap", "trade", "exchange"]):
                return True
            elif rule.eventType == "staking" and any(word in hint_lower for word in ["staking", "reward", "validator"]):
                return True
            elif rule.eventType == "nft_sale" and any(word in hint_lower for word in ["nft", "sale", "mint"]):
                return True
        
        # Check transaction characteristics
        if rule.eventType == "transfer" and transaction.counter_asset:
            return True
        elif rule.eventType == "airdrop" and "airdrop" in (transaction.description or "").lower():
            return True
        elif rule.eventType == "mining" and "mining" in (transaction.description or "").lower():
            return True
        
        return False
    
    async def generate_tax_report_async(
        self,
        classified_transactions: List[ClassifiedTransaction],
        ruleset: RuleSet
    ) -> TaxReport:
        """Generate tax report asynchronously"""
        loop = asyncio.get_event_loop()
        
        def _calculate_report():
            report_items = []
            total_taxable_income = 0.0
            total_capital_gains = 0.0
            total_non_taxable = 0.0
            
            for tx in classified_transactions:
                if tx.tax_treatment == "taxable_income":
                    amount = tx.proceeds_usd or (tx.quantity * (tx.price_usd or 0))
                    total_taxable_income += amount
                elif tx.tax_treatment == "capital_gains":
                    # Simplified capital gains calculation
                    proceeds = tx.proceeds_usd or (tx.quantity * (tx.price_usd or 0))
                    total_capital_gains += proceeds
                elif tx.tax_treatment == "non_taxable":
                    amount = tx.proceeds_usd or (tx.quantity * (tx.price_usd or 0))
                    total_non_taxable += amount
                
                report_items.append(
                    ReportLineItem(
                        tx_id=tx.tx_id,
                        timestamp=tx.timestamp,
                        asset=tx.asset,
                        event_type=tx.event_type,
                        tax_treatment=tx.tax_treatment,
                        amount=tx.proceeds_usd or (tx.quantity * (tx.price_usd or 0)),
                        confidence=tx.confidence,
                        applied_rule_id=tx.applied_rule_id
                    )
                )
            
            summary = ReportSummary(
                total_transactions=len(classified_transactions),
                total_taxable_income=total_taxable_income,
                total_capital_gains=total_capital_gains,
                total_non_taxable=total_non_taxable,
                jurisdiction=ruleset.jurisdiction,
                tax_year=ruleset.taxYear,
                confidence=sum(tx.confidence for tx in classified_transactions) / len(classified_transactions) if classified_transactions else 0.0
            )
            
            return TaxReport(
                summary=summary,
                items=report_items,
                ruleset_info={
                    "jurisdiction": ruleset.jurisdiction,
                    "tax_year": ruleset.taxYear,
                    "version": ruleset.version,
                    "fallback_policy": ruleset.fallbackPolicy.dict() if ruleset.fallbackPolicy else None
                },
                generated_at=datetime.now()
            )
        
        return await loop.run_in_executor(self.executor, _calculate_report)
    
    async def get_rule_engine_stats(self) -> Dict[str, Any]:
        """Get rule engine statistics"""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(self.executor, self.rule_engine.get_cache_stats)
    
    def clear_rule_cache(self) -> None:
        """Clear rule engine cache"""
        self.rule_engine.clear_cache()
        logger.info("Rule engine cache cleared")
    
    async def validate_ruleset(self, jurisdiction: str, tax_year: int) -> Dict[str, Any]:
        """Validate a ruleset and return validation results"""
        try:
            ruleset = await self.get_ruleset(jurisdiction, tax_year)
            metadata = self.rule_engine.get_rule_metadata(jurisdiction, tax_year)
            
            return {
                "valid": True,
                "jurisdiction": jurisdiction,
                "tax_year": tax_year,
                "version": ruleset.version,
                "rules_count": len(ruleset.eventRules),
                "checksum": metadata.checksum if metadata else None,
                "last_modified": metadata.last_modified.isoformat() if metadata else None
            }
        except Exception as e:
            return {
                "valid": False,
                "jurisdiction": jurisdiction,
                "tax_year": tax_year,
                "error": str(e)
            }


# Global service instance
_enhanced_tax_service: Optional[EnhancedTaxService] = None


def get_enhanced_tax_service() -> EnhancedTaxService:
    """Get or create the enhanced tax service singleton"""
    global _enhanced_tax_service
    if _enhanced_tax_service is None:
        rules_dir = Path(__file__).resolve().parent.parent / "rules"
        _enhanced_tax_service = EnhancedTaxService(rules_dir)
    return _enhanced_tax_service
