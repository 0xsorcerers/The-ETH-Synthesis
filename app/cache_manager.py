"""
Caching Layer for Skynet Tax Engine

Provides in-memory and optional Redis caching for:
- Jurisdiction rules (TTL: 1 hour)
- Classification results (TTL: 30 minutes)
- Report generations (TTL: 15 minutes)
- Moltbook insights (TTL: 10 minutes)

Build Criteria: Step 2 - Architecture Improvement (Scalability)
"""

import json
import hashlib
import asyncio
from typing import Optional, Any, Dict
from datetime import datetime, timedelta
from dataclasses import dataclass, asdict
from functools import wraps
import os

# Try to import redis, fallback to in-memory if not available
try:
    import redis.asyncio as redis
    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False


@dataclass
class CacheEntry:
    """A single cache entry with metadata"""
    key: str
    value: Any
    created_at: str
    expires_at: str
    access_count: int = 0
    last_accessed: Optional[str] = None
    
    def is_expired(self) -> bool:
        """Check if this entry has expired"""
        return datetime.utcnow() > datetime.fromisoformat(self.expires_at)
    
    def touch(self):
        """Update access metadata"""
        self.access_count += 1
        self.last_accessed = datetime.utcnow().isoformat()


class InMemoryCache:
    """Thread-safe in-memory cache with TTL support"""
    
    def __init__(self, max_size: int = 1000):
        self._cache: Dict[str, CacheEntry] = {}
        self._max_size = max_size
        self._lock = asyncio.Lock()
        self._hits = 0
        self._misses = 0
    
    async def get(self, key: str) -> Optional[Any]:
        """Get value from cache if it exists and hasn't expired"""
        async with self._lock:
            entry = self._cache.get(key)
            
            if entry is None:
                self._misses += 1
                return None
            
            if entry.is_expired():
                del self._cache[key]
                self._misses += 1
                return None
            
            entry.touch()
            self._hits += 1
            return entry.value
    
    async def set(
        self, 
        key: str, 
        value: Any, 
        ttl_seconds: int = 3600
    ) -> bool:
        """Set value in cache with TTL"""
        async with self._lock:
            # Evict expired entries if at capacity
            if len(self._cache) >= self._max_size:
                await self._evict_expired()
            
            # If still at capacity, evict least recently used
            if len(self._cache) >= self._max_size:
                await self._evict_lru()
            
            now = datetime.utcnow()
            entry = CacheEntry(
                key=key,
                value=value,
                created_at=now.isoformat(),
                expires_at=(now + timedelta(seconds=ttl_seconds)).isoformat()
            )
            
            self._cache[key] = entry
            return True
    
    async def delete(self, key: str) -> bool:
        """Delete a key from cache"""
        async with self._lock:
            if key in self._cache:
                del self._cache[key]
                return True
            return False
    
    async def clear(self):
        """Clear all cache entries"""
        async with self._lock:
            self._cache.clear()
            self._hits = 0
            self._misses = 0
    
    async def _evict_expired(self):
        """Remove all expired entries"""
        expired_keys = [
            key for key, entry in self._cache.items() 
            if entry.is_expired()
        ]
        for key in expired_keys:
            del self._cache[key]
    
    async def _evict_lru(self):
        """Evict least recently used entry"""
        if not self._cache:
            return
        
        # Find entry with oldest last_accessed
        lru_key = min(
            self._cache.keys(),
            key=lambda k: self._cache[k].last_accessed or self._cache[k].created_at
        )
        del self._cache[lru_key]
    
    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics"""
        total = self._hits + self._misses
        hit_rate = self._hits / total if total > 0 else 0
        
        return {
            "size": len(self._cache),
            "max_size": self._max_size,
            "hits": self._hits,
            "misses": self._misses,
            "hit_rate": round(hit_rate, 4),
            "utilization": round(len(self._cache) / self._max_size, 4)
        }


class RedisCache:
    """Redis-backed cache for distributed deployments"""
    
    def __init__(self, redis_url: Optional[str] = None):
        self._redis_url = redis_url or os.getenv("REDIS_URL", "redis://localhost:6379")
        self._client: Optional[redis.Redis] = None
        self._hits = 0
        self._misses = 0
    
    async def connect(self):
        """Connect to Redis"""
        if not REDIS_AVAILABLE:
            raise RuntimeError("Redis not installed. Install with: pip install redis")
        
        self._client = await redis.from_url(self._redis_url, decode_responses=True)
    
    async def disconnect(self):
        """Disconnect from Redis"""
        if self._client:
            await self._client.close()
    
    async def get(self, key: str) -> Optional[Any]:
        """Get value from Redis"""
        if not self._client:
            await self.connect()
        
        value = await self._client.get(key)
        
        if value is None:
            self._misses += 1
            return None
        
        self._hits += 1
        return json.loads(value)
    
    async def set(
        self, 
        key: str, 
        value: Any, 
        ttl_seconds: int = 3600
    ) -> bool:
        """Set value in Redis with TTL"""
        if not self._client:
            await self.connect()
        
        serialized = json.dumps(value, default=str)
        await self._client.setex(key, ttl_seconds, serialized)
        return True
    
    async def delete(self, key: str) -> bool:
        """Delete a key from Redis"""
        if not self._client:
            await self.connect()
        
        result = await self._client.delete(key)
        return result > 0
    
    async def clear(self):
        """Clear all cache entries (use with caution)"""
        if not self._client:
            await self.connect()
        
        await self._client.flushdb()
        self._hits = 0
        self._misses = 0
    
    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics"""
        total = self._hits + self._misses
        hit_rate = self._hits / total if total > 0 else 0
        
        return {
            "backend": "redis",
            "hits": self._hits,
            "misses": self._misses,
            "hit_rate": round(hit_rate, 4)
        }


class CacheManager:
    """Unified cache manager with fallback to in-memory"""
    
    # TTL configurations
    TTL_RULES = 3600  # 1 hour for jurisdiction rules
    TTL_CLASSIFICATION = 1800  # 30 minutes for classifications
    TTL_REPORT = 900  # 15 minutes for reports
    TTL_MOLTBOOK = 600  # 10 minutes for Moltbook data
    
    def __init__(self, use_redis: bool = False):
        self._redis_url = os.getenv("REDIS_URL")
        self._use_redis = use_redis and REDIS_AVAILABLE and self._redis_url
        
        if self._use_redis:
            self._cache: Any = RedisCache(self._redis_url)
        else:
            self._cache = InMemoryCache(max_size=1000)
    
    async def get_rule_set(self, jurisdiction: str, tax_year: int) -> Optional[Dict]:
        """Get cached rule set for a jurisdiction"""
        key = f"rules:{jurisdiction.lower()}:{tax_year}"
        return await self._cache.get(key)
    
    async def set_rule_set(
        self, 
        jurisdiction: str, 
        tax_year: int, 
        rules: Dict
    ) -> bool:
        """Cache rule set for a jurisdiction"""
        key = f"rules:{jurisdiction.lower()}:{tax_year}"
        return await self._cache.set(key, rules, self.TTL_RULES)
    
    async def get_classification(self, tx_hash: str) -> Optional[Dict]:
        """Get cached classification for a transaction"""
        key = f"classification:{tx_hash}"
        return await self._cache.get(key)
    
    async def set_classification(self, tx_hash: str, classification: Dict) -> bool:
        """Cache classification result"""
        key = f"classification:{tx_hash}"
        return await self._cache.set(key, classification, self.TTL_CLASSIFICATION)
    
    async def get_report(self, report_key: str) -> Optional[Dict]:
        """Get cached report"""
        key = f"report:{report_key}"
        return await self._cache.get(key)
    
    async def set_report(self, report_key: str, report: Dict) -> bool:
        """Cache generated report"""
        key = f"report:{report_key}"
        return await self._cache.set(key, report, self.TTL_REPORT)
    
    async def get_moltbook_insights(self, query: str) -> Optional[list]:
        """Get cached Moltbook insights"""
        key = f"moltbook:{hashlib.md5(query.encode()).hexdigest()}"
        return await self._cache.get(key)
    
    async def set_moltbook_insights(self, query: str, insights: list) -> bool:
        """Cache Moltbook insights"""
        key = f"moltbook:{hashlib.md5(query.encode()).hexdigest()}"
        return await self._cache.set(key, insights, self.TTL_MOLTBOOK)
    
    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics"""
        return self._cache.get_stats()
    
    async def clear(self):
        """Clear all cache"""
        await self._cache.clear()


# Global cache instance
_cache_manager: Optional[CacheManager] = None


def get_cache_manager() -> CacheManager:
    """Get or create global cache manager"""
    global _cache_manager
    if _cache_manager is None:
        use_redis = os.getenv("USE_REDIS", "false").lower() == "true"
        _cache_manager = CacheManager(use_redis=use_redis)
    return _cache_manager


def cached(ttl_seconds: int = 3600, key_prefix: str = ""):
    """Decorator to cache function results"""
    def decorator(func):
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            # Generate cache key from function name and arguments
            key_parts = [key_prefix or func.__name__]
            key_parts.extend(str(arg) for arg in args)
            key_parts.extend(f"{k}={v}" for k, v in sorted(kwargs.items()))
            cache_key = hashlib.md5(":".join(key_parts).encode()).hexdigest()
            
            cache = get_cache_manager()
            
            # Try to get from cache
            cached_value = await cache._cache.get(cache_key)
            if cached_value is not None:
                return cached_value
            
            # Execute function and cache result
            result = await func(*args, **kwargs)
            await cache._cache.set(cache_key, result, ttl_seconds)
            return result
        
        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            # For sync functions, we can't use async cache
            # Just execute the function
            return func(*args, **kwargs)
        
        # Return appropriate wrapper based on function type
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        return sync_wrapper
    return decorator


# Convenience functions for direct use
async def get_cached_rules(jurisdiction: str, tax_year: int) -> Optional[Dict]:
    """Get cached rules for a jurisdiction"""
    return await get_cache_manager().get_rule_set(jurisdiction, tax_year)


async def cache_rules(jurisdiction: str, tax_year: int, rules: Dict) -> bool:
    """Cache rules for a jurisdiction"""
    return await get_cache_manager().set_rule_set(jurisdiction, tax_year, rules)


async def invalidate_jurisdiction_cache(jurisdiction: str):
    """Invalidate all cached data for a jurisdiction"""
    cache = get_cache_manager()
    # Delete rule set
    await cache._cache.delete(f"rules:{jurisdiction.lower()}:2025")


if __name__ == "__main__":
    # Test the cache
    import asyncio
    
    async def test():
        cache = get_cache_manager()
        
        # Test rule caching
        test_rules = {"jurisdiction": "us", "version": "1.0"}
        await cache.set_rule_set("us", 2025, test_rules)
        
        cached = await cache.get_rule_set("us", 2025)
        print(f"Cached rules: {cached}")
        
        # Test stats
        stats = cache.get_stats()
        print(f"Cache stats: {stats}")
    
    asyncio.run(test())
