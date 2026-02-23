<!--
SPDX-FileCopyrightText: 2026 Knitli Inc.

SPDX-License-Identifier: MIT OR Apache-2.0
-->

# Analysis Cache Implementation

## Overview

The Analysis Cache provides persistent caching of file analysis results for the lazy import system, using SHA-256 hash-based validation to ensure cache correctness.

## Features

### ✅ Hash-Based Validation
- SHA-256 hashing of file content for cache key validation
- Automatic invalidation when file content changes
- Protection against stale cache entries

### ✅ JSON Persistence
- Atomic writes using temp file + rename pattern
- Schema versioning for cache invalidation on structure changes
- Stored at `.exportify/cache/analysis_cache.json`

### ✅ Circuit Breaker Pattern
- Automatically disables cache after 5 consecutive failures
- Prevents cascading failures
- Auto-reset after 60 seconds (configurable)

### ✅ Graceful Error Handling
- **FM-001**: Corrupt JSON → Auto-delete and rebuild
- **FM-008**: Repeated failures → Circuit breaker disables cache
- **FM-013**: Disk full → Warn and disable cache

### ✅ Performance Optimized
- Target: <50ms per file operation (REQ-PERF-004)
- Target: >90% hit rate across runs (REQ-PERF-002)
- In-memory cache data for fast lookups
- Chunked file reading for large files

## API

### Basic Operations

```python
from exportify.common.cache import JSONAnalysisCache

# Initialize cache (AnalysisCache is an alias for JSONAnalysisCache)
cache = JSONAnalysisCache()  # Uses .exportify/cache/ by default
# or
cache = JSONAnalysisCache(cache_dir=Path("/custom/path"))

# Get cached analysis (returns None if not found/invalid)
# Note: get() requires both file_path and file_hash
analysis = cache.get(file_path, file_hash)

# Cache analysis result (set() is an alias for put(), extracting hash from analysis)
cache.set(file_path, analysis_result)
# or use put() directly with an explicit hash
cache.put(file_path, file_hash, analysis_result)

# Invalidate specific entry
cache.invalidate(file_path)

# Clear entire cache
cache.clear()

# Get statistics
stats = cache.get_statistics()
print(f"Hit rate: {stats.hit_rate:.2%}")
print(f"Total entries: {stats.total_entries}")
```

### Statistics

```python
stats = cache.get_statistics()

# Returns CacheStatistics with:
# - total_entries: int
# - valid_entries: int (files still exist)
# - invalid_entries: int (files deleted)
# - total_size_bytes: int (cache file size)
# - hit_rate: float (0.0 to 1.0)
```

### Properties

```python
# Check circuit breaker state
if cache.circuit_breaker.can_attempt():
    ...

# Get current statistics
stats = cache.get_statistics()
print(f"Hit rate: {stats.hit_rate:.2%}")
```

## Configuration

### Schema Version
Current version: `1.0`

Increment when `AnalysisResult` structure changes to invalidate old cache entries:

```python
CACHE_SCHEMA_VERSION = "1.0"
```

### Circuit Breaker

```python
# CircuitBreaker default parameters:
failure_threshold = 5   # Failures before opening
recovery_timeout = 60   # Seconds before trying half-open (timedelta(seconds=60))
success_threshold = 2   # Successes to close circuit from half-open
```

## Error Handling

### Automatic Recovery

| Error | Detection | Recovery | Impact |
|-------|-----------|----------|--------|
| Corrupt JSON | Parse error | Delete + rebuild | None (cache miss) |
| Wrong schema | Version check | Clear cache | None (cache miss) |
| File changed | Hash mismatch | Invalidate entry | None (cache miss) |
| Disk full | Write error | Disable cache | Performance degradation |
| Repeated failures | Failure counter | Circuit breaker | Performance degradation |

### No Manual Intervention Required

All errors are handled gracefully with automatic recovery. The cache never fails the build - it degrades to direct analysis when necessary.

## Implementation Details

### Serialization

The cache handles complex Python objects:

- **Path objects** → Converted to strings
- **Sets** → Converted to lists (JSON compatible)
- **Nested dataclasses** → Recursively serialized

Deserialization reconstructs the original types:

- **Strings** → Path objects
- **Lists** → Sets (for `propagates_to`, `dependencies`)
- **Dicts** → ExportNode objects

### Atomic Writes

Cache writes are atomic to prevent corruption:

```python
# Cache writes use Python's json.dump() directly to the file at:
#   .exportify/cache/analysis_cache.json
# Path keys are serialized as strings; deserialization reconstructs Path objects.
```

This ensures the cache file is never partially written.

### Hash Computation

SHA-256 hashing with chunked reading for large files:

```python
hasher = hashlib.sha256()
for chunk in iter(lambda: f.read(8192), b""):
    hasher.update(chunk)
```

## Testing

See `tests/test_cache.py` for comprehensive tests covering:

- ✅ Basic operations (get, set, invalidate, clear)
- ✅ Hash-based validation
- ✅ File modification detection
- ✅ Corruption recovery
- ✅ Circuit breaker functionality
- ✅ Statistics tracking

## Performance Characteristics

| Operation | Expected Time | Notes |
|-----------|---------------|-------|
| Cache hit | <10ms | In-memory lookup + hash validation |
| Cache miss | <50ms | Hash computation + analysis |
| Cache write | <30ms | Serialization + atomic write |
| Circuit check | <1ms | Simple counter check |

## Future Enhancements

Potential improvements (not in current scope):

1. **LRU Eviction**: Limit cache size with LRU eviction policy
2. **Compression**: GZIP compression for large cache files
3. **Metrics Export**: Prometheus metrics for monitoring
4. **TTL Support**: Time-based cache invalidation
5. **Distributed Cache**: Redis/Memcached backend option

## Dependencies

- `hashlib` (stdlib): SHA-256 hashing
- `json` (stdlib): Serialization
- `pathlib` (stdlib): Path handling
- `dataclasses` (stdlib): Serialization support
- `logging` (stdlib): Error reporting
- `time` (stdlib): Timestamps and circuit breaker

## License

See project LICENSE file.
