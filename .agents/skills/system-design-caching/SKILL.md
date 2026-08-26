---
name: system-design-caching
description: >-
  Caching strategies, patterns, invalidation mechanisms, and in-memory optimizations.
  Use when designing latency reduction layers, evaluating Cache-Aside, Write-Through, Write-Back patterns,
  or preventing cache stampede, penetration, and avalanche issues.
---

## Cache-Aside Pattern and Latency Reduction

Relational and document databases store data persistently on physical disks, requiring rotational or solid-state input-output operations (reading data from disk blocks into memory) and query parsing for every read request. When application servers execute repetitive queries for identical, static records like user profile headers or product descriptions directly against disk storage, database CPU utilization and connection pools quickly become saturated, leading to severe latency degradation (slow response times).

If database query latency spikes under high traffic loads, web worker threads remain blocked waiting on network sockets, causing upstream request queues to overflow and triggering gateway timeouts (errors returned when an intermediary proxy gives up waiting for a response).

```mermaid
flowchart TD
    Client["Client Traffic (Surge of 50,000 req/s)"] --> API["Application Server Fleet"]
    API -->|"1. Repetitive SELECT Queries"| DB[("Disk Database (PostgreSQL / MySQL)")]
    DB -.->|"2. Disk I/O Saturation & High Latency (500ms)"| API
    API -.->|"3. Connection Pool Depleted (504 Gateway Timeout)"| Outage["Client Outage (Service Unresponsive)"]
```

The cache-aside pattern places a high-speed in-memory data store (a fast temporary storage system like Redis or Memcached that holds data directly in RAM) alongside the application server. The application code first queries the in-memory cache; if a cache hit occurs (the requested record exists in fast RAM), the server returns the cached payload immediately with sub-millisecond response latency.

When a cache miss occurs (the record is not found in memory), the application queries the persistent database, writes the retrieved record into the cache with a time-to-live expiration (a scheduled timestamp after which cached data is automatically deleted), and returns the payload to the client.

```mermaid
flowchart TD
    Client["Client Traffic"] --> API["Application Server Fleet"]
    API -->|"1. Check In-Memory Cache"| Cache[("In-Memory Cache (Redis)")]
    Cache -->|"2. Cache Hit (< 1ms)"| API
    API -.->|"3. Cache Miss -> Query Database"| DB[("Primary Database")]
    DB -.->|"4. Return Record"| API
    API -.->|"5. Populate Cache with TTL"| Cache
    API -->|"6. Fast Response (200 OK)"| Client
```

This pattern isolates persistent database disks from repetitive read traffic, allowing systems to serve hundreds of thousands of read requests per second cost-effectively. Because the cache operates independently from the database, a temporary cache restart degrades system performance by falling back to the database without causing complete system failure.

## Write-Through and Write-Back Caching Strategies

Direct database writes followed by manual cache eviction can introduce race conditions (unpredictable timing bugs where concurrent operations overwrite data in the wrong sequence), causing stale data (outdated information that does not match the actual database state) to remain in memory indefinitely. If an application updates the database but crashes before updating or evicting the corresponding cache key, subsequent read queries will continue serving outdated data to users.

Conversely, in high-frequency write environments like live multiplayer game leaderboards or high-volume sensor telemetry, writing every single update synchronously to disk creates severe database write contention (multiple write queries competing for disk locks).

```mermaid
flowchart TD
    Client["Client Application"] --> API["Application Server"]
    API -->|"1. INSERT / UPDATE Record (Success)"| DB[("Primary Database")]
    API -.->|"2. Network Failure / Crash before cache eviction"| Cache[("In-Memory Cache")]
    Cache -.->|"3. Stale Data Served to Readers indefinitely"| Inconsistency["Data Inconsistency (Stale Cache State)"]
```

Write-through caching treats the cache as the primary data interface, where the cache layer synchronously writes data to both in-memory storage and the persistent database within a single unified operation before returning a success confirmation. This guarantees that cached data is never stale and eliminates complex cache synchronization logic from application code.

Write-back caching (also called write-behind caching) accepts write updates into high-speed memory immediately, acknowledges the write to the client with microsecond latency, and asynchronously flushes accumulated batches of dirty pages (modified in-memory records that have not yet been written to persistent disk storage) to the database in the background.

```mermaid
flowchart TD
    Client["Client Application"] -->|"1. Fast Write"| Cache[("In-Memory Cache (Write-Back)")]
    Cache -->|"2. Instant Acknowledgment"| Client
    subgraph AsyncBatchFlusher["Background Persistence Engine"]
        Cache -->|"3. Batch Flush Dirty Pages"| Worker["Async Flush Worker"]
        Worker -->|"4. Bulk Optimized Write"| DB[("Persistent Database")]
    end
```

Write-through caching prioritizes absolute data freshness at the expense of slightly higher write latency, making it ideal for financial accounts and order management. Write-back caching delivers extreme write throughput by absorbing write bursts in RAM, trading the risk of transient data loss during ungraceful server power outages for massive performance gains.

## Cache Stampede and Distributed Mutex Locking

A cache stampede (also known as a thundering herd problem) occurs when a heavily accessed, hot cache key expires while thousands of concurrent client requests are reading it simultaneously. Because the key is suddenly missing from memory, all incoming application threads experience a simultaneous cache miss and execute identical expensive database queries at the exact same millisecond.

This sudden surge of identical complex database queries instantly overwhelms database CPU cores, exhausts available connection pools, and drives database response latency into complete operational collapse.

```mermaid
flowchart TD
    Clients["5,000 Concurrent Requests"] --> API["Application Server Fleet"]
    API -->|"1. Simultaneous Cache Miss (Key Expired)"| Cache[("In-Memory Cache (Key Expired)")]
    API -->|"2. 5,000 Identical Heavy SQL Queries"| DB[("Primary Database (Connection Pool Exhausted)")]
    DB -.->|"3. CPU Saturation & Query Queue Overflow"| Crash["Database Outage & Cascading 500 Errors"]
```

Distributed mutex locking (a synchronization mechanism that restricts access to a shared resource across multiple servers to one worker at a time) eliminates cache stampedes by ensuring that only a single worker queries the database on a cache miss. When a cache miss occurs, the first application thread acquires a short-lived distributed lock in Redis using atomic operations (commands that execute completely in a single step without interruption).

The winning thread queries the persistent database and repopulates the cache, while all other concurrent threads wait briefly and retry the cache lookup, reading the freshly populated value without touching the database.

```mermaid
flowchart TD
    Clients["5,000 Concurrent Requests"] --> API["Application Server Fleet"]
    API -->|"1. Cache Miss"| Cache[("In-Memory Cache")]
    API -->|"2. Try Acquire Lock (SET key NX EX 5)"| LockManager[("Redis Distributed Lock")]
    LockManager -->|"3. Lock Granted (Single Worker)"| Worker1["Worker Node 1"]
    Worker1 -->|"4. Execute SQL Query"| DB[("Primary Database")]
    Worker1 -->|"5. Populate Cache with Fresh TTL"| Cache
    LockManager -.->|"6. Lock Denied -> Wait 50ms & Read Cache"| OtherWorkers["Other 4,999 Workers"]
    OtherWorkers -->|"7. Read Fresh Cache Value (< 1ms)"| Cache
```

This single-flight execution pattern guarantees that the database experiences only one single query during key regeneration regardless of incoming concurrency volume. The database remains completely protected from traffic spikes, maintaining stable sub-second response times across the entire cluster.

## Cache Penetration and Bloom Filters

Cache penetration occurs when external clients repeatedly send queries for non-existent records, such as malicious attackers requesting random, non-existent user identification numbers. Because the requested keys do not exist in the database, the cache never stores a value for them, causing every single request to bypass the cache entirely and hit the database directly.

An attacker sending high-velocity requests for invalid keys can easily bypass the caching layer entirely, driving database CPU utilization to maximum capacity and causing denial of service (an outage where legitimate users cannot access the system).

```mermaid
flowchart TD
    Attacker["Malicious Client / Web Bot"] -->|"1. Query Non-Existent IDs (e.g. user_-9999)"| API["Application Server"]
    API -->|"2. Cache Miss (Key not found)"| Cache[("In-Memory Cache")]
    API -->|"3. Query Database for Invalid ID"| DB[("Primary Database (Scans full table)")]
    DB -.->|"4. Empty Result (Nothing cached)"| API
    API -.->|"5. Uncached path repeated 10,000 req/s"| SaturatedDB["Database Resource Starvation & Crash"]
```

To eliminate cache penetration, systems deploy Bloom filters (space-efficient probabilistic data structures used to test whether an element is definitely not in a set or might be in a set) at the edge of the data layer. Before querying the cache or database, the application checks the in-memory Bloom filter; if the filter indicates the key does not exist, the request is rejected immediately with an HTTP 404 response without executing any storage queries.

Additionally, for legitimate cache misses that return empty results, the application writes a null placeholder value into the cache with a very short expiration time (for example, sixty seconds), ensuring subsequent queries for that missing key return an instant cache hit for the null value.

```mermaid
flowchart TD
    Client["Client Request (ID: 9999999)"] --> API["Application Server"]
    API -->|"1. Check Key Existence"| Bloom["In-Memory Bloom Filter"]
    Bloom -.->|"2. Key Definitely Does Not Exist"| Reject["Return 404 Not Found (Zero DB Load)"]
    Bloom -->|"3. Key Might Exist"| Cache[("In-Memory Cache")]
    Cache -->|"4. Cache Hit"| ReturnData["Return Data"]
    Cache -.->|"5. Cache Miss -> Query DB & Cache Null Value"| DB[("Primary Database")]
```

This dual-defense mechanism protects backend databases from malicious scraping and random key enumeration attacks while consuming minimal RAM. The Bloom filter processes lookups in constant time (execution speed that remains instantaneous regardless of dataset size), shielding the core infrastructure from artificial traffic surges.

## Cache Avalanche and Jittered Expirations

A cache avalanche happens when a massive portion of cached keys expire at the exact same moment, or when the entire caching cluster suddenly restarts or becomes unreachable. When thousands of distinct keys expire simultaneously, all subsequent user traffic cascades directly onto the backend database at once, causing sudden hardware saturation and site-wide outages.

Systems that populate large batches of cache keys with identical fixed time-to-live durations (for example, setting every product cache key to expire in exactly twenty-four hours during a midnight data sync) inherently create predictable avalanche conditions.

```mermaid
flowchart TD
    MidnightSync["Midnight Data Sync"] -->|"1. Set 500,000 Keys with Fixed TTL = 3600s"| Cache[("In-Memory Cache")]
    Timer["Timer: 3600 Seconds Elapses"] -.->|"2. All 500,000 Keys Expire Simultaneously"| Cache
    Traffic["Normal User Read Traffic"] -->|"3. Massive Simultaneous Cache Misses"| API["Application Server Fleet"]
    API -->|"4. Millions of SQL Queries Surge at Once"| DB[("Primary Database (Uncached Surge)")]
    DB -.->|"5. Complete Crash under Instant Load"| Outage["Complete System Outage (Cache Avalanche)"]
```

Preventing cache avalanches requires introducing randomized TTL jitter (adding a small random interval of extra seconds to key expiration times) so that cache expirations distribute evenly across time windows instead of occurring in a single synchronized spike.

Furthermore, deploying high-availability cache clusters with multi-replica master-follower topologies (deploying secondary follower cache nodes that automatically take over if the primary node fails) ensures the caching layer remains operational even during physical server failures.

```mermaid
flowchart TD
    Sync["Data Ingestion Service"] -->|"1. Calculate Jittered TTL (Base: 3600s + Random: 0-300s)"| Keys["Keys with Staggered Expirations"]
    Keys -->|"2. Distribute Evenly Across Time"| CachePrimary[("Redis Primary Cluster")]
    CachePrimary -->|"3. Replicate Data"| CacheStandby[("Redis Standby Replica (Auto-Failover)")]
    Traffic["User Read Traffic"] -->|"4. Continuous Steady Cache Hits (> 99.5%)"| CachePrimary
    Traffic -.->|"5. Small Staggered DB Misses (Easily Handled)"| DB[("Primary Database (Stable CPU < 20%)")]
```

Staggered expirations smooth out database query traffic into a predictable, manageable trickle that persistent storage easily absorbs without latency degradation. Multi-node cache replication guarantees fault resilience, preventing hardware outages from triggering devastating cascade effects across the broader application architecture.
