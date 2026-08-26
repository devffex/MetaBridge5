# Bulkhead Pattern

## 1. Overview & Purpose
The Bulkhead pattern isolates system elements into separate resource pools (threads, connections, memory) so that if one component fails, the others can continue to function. It is named after the watertight partitions of a ship's hull.

## 2. Backing App Scenarios
- **HTTP Thread Isolation**: Assigning a dedicated thread pool for critical endpoints (e.g. login/checkout) and a separate pool for slow, resource-intensive endpoints (e.g. PDF exports).
- **Database Connection Pools**: Creating isolated connection pools for write-heavy services vs. read-only analytics queries.
- **Microservices Deployment**: Separating high-throughput chat services from slow payment processing services onto distinct physical nodes.

## 3. When to Apply
- When a failure or traffic spike in one downstream system can consume all available host resources (like threads or sockets), causing the entire application to crash.
- When consumers have different SLA requirements (e.g., premium APIs vs. free APIs).

## 4. Drawbacks & Risks
- **Resource Underutilization**: Unused capacity in one isolated pool cannot be shared with an overloaded pool, potentially lowering overall system efficiency.
- **Management Complexity**: Requires configuring and monitoring multiple thread pools or execution limits instead of a single resource pool.

## 5. Language-Agnostic Design

```
Class Bulkhead {
    private maxConcurrentCalls: Integer
    private currentConcurrentCalls: Integer = 0

    public constructor(limit: Integer) {
        this.maxConcurrentCalls = limit
    }

    public execute(task: Function): Object {
        acquireLock()
        if (this.currentConcurrentCalls >= this.maxConcurrentCalls) {
            releaseLock()
            throw new BulkheadFullException("Request rejected by bulkhead protection")
        }
        this.currentConcurrentCalls++
        releaseLock()

        try {
            return task.run()
        } finally {
            acquireLock()
            this.currentConcurrentCalls--
            releaseLock()
        }
    }
}
```

## 6. Decision Matrix

| Dimension | Bulkhead Partitioning | Shared Resource Pool |
|---|---|---|
| **Fault Tolerance** | High (Failures are contained within specific pools) | Low (A single slow dependency can consume all threads, crashing the app) |
| **Capacity Utilization** | Inflexible (Dedicated resources cannot be dynamically reallocated) | Flexible (All resources are shared based on current demand) |
| **Operations Overhead** | Higher (Requires monitoring and configuring multiple limits) | Lower (Single pool, simple setup) |
