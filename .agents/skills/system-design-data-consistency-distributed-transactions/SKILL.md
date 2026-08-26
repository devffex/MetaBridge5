---
name: system-design-data-consistency-distributed-transactions
description: >-
  Distributed data consistency, transaction management, and consensus protocols in system design.
  Use when designing multi-service transactions, implementing Saga patterns, Transactional Outbox with CDC,
  batch data reconciliation, CAP/PACELC trade-offs, and Raft/Paxos leader election.
---

## Dual Writes and Transactional Outbox

Dual writing occurs when an application service attempts to update a primary database and publish an event to a message broker sequentially within a single request cycle. Because distributed transactions across disparate datastores are fragile and expensive, network failures or process crashes between the first write and the second write inevitably leave the system in an inconsistent state (a broken condition where one database has updated data but the second database still holds outdated information).

When the database write succeeds but the message broker publish fails, downstream subscriber services never receive the event notification, causing permanent state discrepancies across microservices. Retrying the message publish synchronously blocks the client request while waiting for the network, increasing response latency and risking thread exhaustion during downstream broker outages.

```mermaid
flowchart TD
    Client["Client Application"] --> Service["Order Service"]
    Service -->|"1. INSERT Order (Committed)"| DB[("PostgreSQL Database")]
    Service -.->|"2. POST Event (Network Failure / Timeout)"| Broker["Message Broker (Kafka / SQS)"]
    Broker -.->|"3. Event lost forever"| Inventory["Inventory Service (Never allocates stock)"]
```

The transactional outbox pattern eliminates dual writing by recording the domain entity mutation and an outgoing event record together inside a single ACID transaction (a database guarantee that all grouped write operations either completely succeed together or safely roll back without partial data corruption). A separate asynchronous relay process monitors the outbox table via change data capture (a technology that listens directly to database transaction logs to detect new records in real time) and reliably publishes events to the message broker.

Downstream consumer worker services pull events from the message broker and update secondary datastores asynchronously, guaranteeing that no state updates are lost even if downstream components experience temporary downtime.

```mermaid
flowchart TD
    Client["Client Application"] -->|"1. Create Order"| Service["Order Service (Responds immediately)"]
    Service -->|"2. Atomic Local Write"| DB[("PostgreSQL DB + Outbox Table")]
    DB -->|"3. Tail Commit Log (WAL)"| CDC["CDC Relay Worker (Debezium)"]
    CDC -->|"4. Reliable Publish"| Broker["Message Broker (Kafka / SQS)"]
    Worker["Inventory Worker (Idempotent Handler)"] -->|"5. Pull Event"| Broker
    Worker -->|"6. Update Stock State"| SecondaryDB[("Inventory Database")]
```

This pattern trades immediate consistency for eventual consistency (a model where data replicas become synchronized across all systems after a slight delay) while achieving complete fault isolation and zero data loss. The application must design downstream consumer services to be idempotent (capable of receiving the exact same message multiple times without creating duplicate records or incorrect side effects).

## Two-Phase Commit and Blocking Coordinator Risks

Two-phase commit coordinates transactions across multiple independent databases by locking resources across all participating nodes during a prepare phase and committing them in a second phase. A centralized transaction coordinator node queries all participant nodes to ensure they are ready to commit before sending the final commit directive.

In high-throughput distributed systems, holding physical locks across network boundaries creates extreme latency spikes and severe cascading bottlenecks. If the coordinator node crashes or loses network connectivity after participants have voted and acquired locks, participant nodes remain blocked indefinitely holding database locks, causing connection pool exhaustion (running out of available database sockets) across the entire cluster.

```mermaid
flowchart TD
    Client["Client Application"] --> Coordinator["Transaction Coordinator"]
    Coordinator -->|"1. PREPARE (Acquires exclusive table locks)"| OrderDB[("Order Database (Locked)")]
    Coordinator -->|"1. PREPARE (Acquires exclusive table locks)"| PaymentDB[("Payment Database (Locked)")]
    Coordinator -.->|"2. Coordinator Crashes / Network Partitions"| Crash["Coordinator Down"]
    OrderDB -.->|"3. Locks held indefinitely; blocks all incoming queries"| Outage["Cascading Lock Contention Outage"]
```

Modern architectures replace blocking two-phase commits with non-blocking coordination patterns and asynchronous consensus protocols. By avoiding synchronous inter-database locks, individual microservices execute atomic local transactions within their private databases and coordinate subsequent steps using durable messaging queues and change streams.

When cross-service consistency is strictly required, distributed systems employ non-blocking state machines with explicit lease timeouts (automatic lock expirations that safely release reserved resources if a coordinator process fails to respond within a short time limit).

```mermaid
flowchart TD
    Client["Client Application"] --> Gateway["API Gateway"]
    Gateway -->|"1. Fast Local Transaction"| OrderSvc["Order Service"]
    OrderSvc -->|"2. Commit with Expirable Reservation"| OrderDB[("Order Database (Lease Lock)")]
    OrderSvc -->|"3. Enqueue Next Step"| Queue["Durable Message Queue"]
    Worker["Payment Worker Fleet"] -->|"4. Process Next Local Step"| Queue
    Worker -->|"5. Commit Payment"| PaymentDB[("Payment Database")]
```

This non-blocking approach eliminates single points of failure and prevents transient network partitions from freezing independent databases. Services preserve maximum local write throughput while ensuring that unconfirmed transactions expire safely without human intervention.

## Saga Pattern and Compensating Transactions

Managing long-running business workflows across multiple microservices (such as booking a vacation package involving flights, hotels, and car rentals) cannot rely on traditional database transactions because locking resources across third-party APIs for several minutes is impossible. If the third step of a multi-step booking workflow fails after the first two steps have already committed locally, the system is left in a corrupted state with stranded, paid reservations.

Attempting to undo committed database rows with simple delete queries fails because subsequent operations may have already modified adjacent records, producing phantom data corruption.

```mermaid
flowchart TD
    Orchestrator["Booking Coordinator"] -->|"1. Book Flight (Tx Committed)"| FlightSvc["Flight Service"]
    Orchestrator -->|"2. Book Hotel (Tx Committed)"| HotelSvc["Hotel Service"]
    Orchestrator -->|"3. Book Car Rental"| CarSvc["Car Rental Service"]
    CarSvc -.->|"4. Out of Cars (Transaction Fails)"| Fail["Car Booking Error"]
    Fail -.->|"5. No compensation mechanism; flight & hotel remain charged"| StrandedState["Corrupted State & Customer Overcharged"]
```

The saga pattern manages distributed business transactions as a sequence of independent local transactions across participating services. For every local transaction that commits a state change, the system defines an explicit compensating transaction (a semantic undo operation like issuing a refund or releasing a seat reservation) designed to reverse the business effects if a downstream step fails.

When a failure occurs midway through the saga, the orchestrator triggers the compensating transactions in reverse chronological order, cleanly restoring overall business consistency across all participating microservices.

```mermaid
flowchart TD
    Orchestrator["Saga Orchestrator"] -->|"1. Forward: Book Flight"| FlightSvc["Flight Service"]
    FlightSvc -->|"2. Success"| Orchestrator
    Orchestrator -->|"3. Forward: Book Hotel"| HotelSvc["Hotel Service"]
    HotelSvc -->|"4. Success"| Orchestrator
    Orchestrator -->|"5. Forward: Book Car"| CarSvc["Car Rental Service (Sold Out)"]
    CarSvc -.->|"6. Failure Triggered"| Orchestrator
    Orchestrator -->|"7. Compensate: Refund Hotel"| HotelSvc
    Orchestrator -->|"8. Compensate: Cancel Flight"| FlightSvc
    Orchestrator -->|"9. Return Clean Cancellation Response"| Client["Client Application"]
```

Sagas provide reliable business consistency across loosely coupled services without requiring distributed resource locking. Because compensating transactions execute after initial commits, intermediate uncommitted states may be briefly visible to external readers before compensation completes.

## Batch Data Reconciliation and Self-Healing Audits

In high-volume distributed systems relying on asynchronous messaging and webhooks (automated HTTP notifications sent between platforms when events occur), transient network drops, partition hiccups, or expired retry timers occasionally cause individual event notifications to be lost silently. Over months of operation, these small unhandled anomalies accumulate into severe data drift (unnoticed discrepancies between two independent records representing the same financial or business reality).

Relying solely on real-time event streaming without scheduled verification guarantees that undetected discrepancies will persist until customers complain about missing refunds or mismatched accounting ledgers.

```mermaid
flowchart TD
    PaymentGateway["Stripe Payment Gateway"] -->|"1. Charge Customer (Success)"| Webhook["Stripe Webhook Event"]
    Webhook -.->|"2. Network Drop / 500 Error during deployment"| InternalSvc["Billing Service"]
    InternalSvc -.->|"3. Webhook lost; database never updated"| InternalDB[("Internal Database (Order Marked Unpaid)")]
    InternalDB -.->|"4. Unfulfilled order unnoticed for weeks"| Drift["Accumulated Data Drift & Revenue Loss"]
```

Batch data reconciliation operates as an automated background audit loop that periodically compares two independent sources of truth (such as internal transactional database records and external payment settlement files) to detect anomalies. A scheduled worker process pulls end-of-day settlement reports, executes high-speed cryptographic diffs (comparisons that identify mismatched or missing rows), and flags discrepancies.

When data drift is detected, the reconciliation engine automatically triggers a self-healing workflow (an automated script that safely inserts missing records or syncs status flags) to re-align internal state with external reality.

```mermaid
flowchart TD
    InternalDB[("Internal Orders DB")] --> Reconciler["Nightly Reconciliation Worker"]
    StripeReport[("Stripe Settlement Report (CSV / API)")] --> Reconciler
    Reconciler -->|"1. Compare Records"| DiffEngine{"Discrepancy Found?"}
    DiffEngine -->|"Match (Clean)"| LogOK["Record Audit Success"]
    DiffEngine -->|"Diff Found (Paid in Stripe, Unpaid in DB)"| AutoHealer["Trigger Self-Healing Workflow"]
    AutoHealer -->|"2. Update Order to Paid & Dispatch Delivery"| InternalDB
    AutoHealer -->|"3. Log Audit Trail"| AuditLog[("Compliance Audit Log")]
```

This dual-layer architecture pairs fast real-time event streaming with reliable scheduled audit safety nets. Automated reconciliation guarantees long-term ledger accuracy and ensures that unavoidable transient network anomalies are systematically resolved within twenty-four hours.

## Distributed Consensus and Leader Election

Distributed data clusters require multiple participant nodes to agree on a single shared state, such as electing a single primary leader to coordinate write operations. When network connections between nodes fail, naive clustering algorithms risk split-brain scenarios (a catastrophic condition where a cluster fractures into two isolated factions, each independently electing a leader and accepting conflicting writes).

Split-brain conditions permanently corrupt data because two distinct leaders accept incompatible write mutations on the same records simultaneously, making automated reconciliation mathematically impossible.

```mermaid
flowchart TD
    subgraph IsolatedFactionA["Network Partition Side A (US East)"]
        Node1["Node 1 (Believes it is Leader)"] -->|"Accepts Write A"| DB1[("Split Storage 1")]
    end
    subgraph IsolatedFactionB["Network Partition Side B (US West)"]
        Node2["Node 2 (Believes it is Leader)"] -->|"Accepts Write B"| DB2[("Split Storage 2")]
    end
    Node1 -.->|"Network Partition Severed"| Node2
    DB1 -.->|"Conflicting Writes on Same Key"| CorruptedData["Permanent Split-Brain Data Corruption"]
```

Modern distributed systems enforce consensus algorithms like Raft or Paxos that require a strict quorum (a mathematical majority consisting of more than half of all total cluster nodes) before any leader election or write operation can be confirmed. In a five-node cluster, a leader candidate must successfully obtain affirmative votes from at least three nodes to assume the leadership role.

If a network partition divides the cluster into a minority partition with two nodes and a majority partition with three nodes, the minority nodes recognize they cannot reach a quorum, automatically step down, and reject write operations until connectivity is restored.

```mermaid
flowchart TD
    subgraph MajorityQuorum["Majority Partition (3 Nodes - Quorum Reached)"]
        Leader["Node A (Elected Leader - 3/5 Votes)"]
        NodeB["Node B (Follower)"]
        NodeC["Node C (Follower)"]
        Leader -->|"Heartbeat & Log Append"| NodeB
        Leader -->|"Heartbeat & Log Append"| NodeC
        Leader -->|"Accepts Writes Safely"| Storage[("Consistent Cluster Log")]
    end
    subgraph MinorityPartition["Minority Partition (2 Nodes - No Quorum)"]
        NodeD["Node D (Follower - Stepped Down)"]
        NodeE["Node E (Follower - Stepped Down)"]
        NodeD -.->|"Rejects Writes (Cannot reach 3 votes)"| Error["Read-Only / Fast Reject"]
    end
    MajorityQuorum -.->|"Network Partition Severed"| MinorityPartition
```

Quorum-based consensus guarantees that only one valid leader can ever exist across the entire network at any given time. This eliminates split-brain data corruption and ensures continuous safe operation across unreliable physical networks.
