---
name: system-design-architectures
description: >-
  Architectural patterns and structural models in system design. Use when designing, evaluating,
  or explaining software architectures such as Monolithic, Client-Server, Microservices, Event-Driven,
  Serverless, and Peer-to-Peer (P2P).
---

## Monolithic Architecture and Modular Decomposition

A monolithic architecture is a software design where all user interface handling, business logic rules, and database queries are packaged together as a single executable program sharing one centralized database (a single storage system that holds all company data). Teams initially benefit from fast local development, simple testing, and instant function calls without any network latency (the delay caused by sending data over physical cables between servers).

As engineering teams and codebases grow larger, tightly coupled code boundaries create severe deployment bottlenecks (slowdowns where work piles up) and eliminate fault isolation (preventing a crash in one small feature from bringing down the entire website). A single memory leak (a software bug where unused memory is never freed) or slow database query inside an auxiliary module can exhaust server capacity and crash the entire application process.

```mermaid
flowchart TD
    %% PROBLEM DIAGRAM: Monolith Resource Starvation
    Client["Client Devices"] -->|"1. HTTP Requests"| App["Monolithic Server (Shared application process)"]
    App -->|"2. Heavy Analytical Query"| DB[("Single Shared DB (Connection exhaustion)")]
    App -.->|"3. Unhandled Out-of-Memory Crash"| Outage["Complete System Outage (All modules down)"]
```

Refactoring into a modular monolith enforces strict code boundaries with explicit module interfaces and isolated database tables before introducing physical network complexity. Compute-heavy operations and long-running background tasks are pushed onto dedicated asynchronous workers (background processes that execute tasks independently without blocking the user interface) while core application code remains unified.

```mermaid
flowchart TD
    %% SOLUTION DIAGRAM: Modular Monolith with Async Offload (Delivery Framework)
    Client["Client Devices"] -->|"1. HTTP Request"| LB["Load Balancer (Distributes traffic)"]
    LB --> WebApp["Modular Core Server (Responds immediately)"]
    WebApp -->|"2. Fast Transaction"| CoreDB[("Core Database")]
    WebApp -->|"3. Enqueue Background Task"| JobQueue["Job Queue (Redis / SQS)"]
    Worker["Worker Fleet (Processes async jobs)"] -->|"4. Pull Jobs"| JobQueue
    Worker -->|"5. Update Status"| CoreDB
```

This architecture provides fast in-process execution speed while eliminating chaotic dependencies between teams and features. Teams maintain high delivery velocity without needing distributed tracing (monitoring tools that track requests across dozens of servers) or eventual consistency (a model where data syncs across nodes after a short delay).

## Client-Server Architecture and Gateway Scaling

A client-server architecture separates user-facing applications (clients like web browsers and mobile apps) from central backend servers that process data and manage security rules. Clients send structured network requests over standard communication protocols (established rules for transferring data like HTTP and WebSockets) to fetch account balances, create orders, and synchronize state.

Connecting mobile and web clients directly to internal database servers or legacy backend instances causes rapid connection exhaustion (running out of available communication sockets) during sudden traffic spikes. Heterogeneous client applications (devices running different hardware, operating systems, or outdated application versions) flood backend servers with chatty requests and struggle when server data schemas (the organizational format of database records) change.

```mermaid
flowchart TD
    %% PROBLEM DIAGRAM: Direct Client Coupling & Connection Exhaustion
    WebClient["Web Browser"] -->|"1. Direct Unauthenticated Request"| LegacyServer["Single Backend Server"]
    MobileApp["Mobile App (Legacy Version)"] -->|"2. Chatty Unfiltered Requests"| LegacyServer
    PartnerAPI["Third-Party Webhooks"] -->|"3. Uncontrolled Traffic Surge"| LegacyServer
    LegacyServer -->|"4. Unbuffered Queries"| DB[("Primary Database (Socket contention)")]
    LegacyServer -.->|"5. Connection exhaustion drops incoming requests"| Outage["Service Unavailable (503 Dropped Connections)"]
```

Deploying an edge API gateway (a front-door reverse proxy that manages incoming traffic before it hits internal servers) centralizes transport termination (handling encryption handshakes at the edge so internal servers do not expend compute on security overhead), rate limiting (restricting the number of requests a user can make in a given timeframe), request authentication, and response caching (storing frequently requested data in fast memory for instant retrieval). Downstream backend services sit safely inside private networks behind load balancers, shielded from client variances and malicious network attacks.

```mermaid
flowchart TD
    %% SOLUTION DIAGRAM: Edge Gateway with Private Server Fleet (Delivery Framework)
    Client["Client (Web / Mobile)"] -->|"1. HTTPS Request"| Gateway["API Gateway (Rate limits & authenticates)"]
    Gateway -->|"2. Cache Lookup"| EdgeCache[("Redis Cache (Instant response)")]
    Gateway -->|"3. Route to Healthy Server"| Server["Application Server Fleet (Private network)"]
    Server -->|"4. Fast Query"| DB[("Primary Database")]
```

The gateway pattern simplifies backend code by handling cross-cutting concerns (tasks like security checks, logging, and metrics that apply to every service) in one central place. It introduces a small additional network hop (the physical route taken by data between two connected machines) and requires careful gateway redundancy to prevent the gateway itself from becoming a single point of failure (a solitary component whose shutdown halts the entire system).

## Microservices and Domain Boundaries

Microservices architecture divides a large software system into a collection of small, independently deployable services organized around distinct business capabilities (such as authentication, billing, product catalog, and shipping). Each microservice owns its private database and exposes clean programming interfaces (contracts defining how software modules communicate with each other) to communicate with other services.

When microservices communicate primarily through long chains of synchronous HTTP calls (requests where each server must wait idle for the next server to respond), the system becomes a distributed monolith (a fragile system that suffers the complexity of microservices without the benefits of independence). If a deep downstream dependency suffers high latency or crashes, thread pools across all upstream callers exhaust rapidly, causing cascading failures (a domino effect where one broken server brings down all connected servers).

```mermaid
flowchart TD
    %% PROBLEM DIAGRAM: Synchronous HTTP Cascading Outage
    Client["User App"] -->|"1. Checkout Request"| OrderSvc["Order Service (Thread pool blocking)"]
    OrderSvc -->|"2. Sync HTTP"| UserSvc["User Service (Waiting on downstream)"]
    UserSvc -->|"3. Sync HTTP"| InventorySvc["Inventory Service (Waiting on downstream)"]
    InventorySvc -->|"4. Sync HTTP (Slow Response / Timeout)"| PaymentSvc["Payment Service (Crashed / Unresponsive)"]
    PaymentSvc -.->|"5. Cascading timeout exhausts all upstream threads"| Outage["Cascading Failure (All services unresponsive)"]
```

Applying event-driven patterns and localized read caches (fast temporary memory stores that hold frequently accessed data to avoid querying slower remote services) eliminates synchronous blocking chains between independent microservices. When synchronous communication is unavoidable, developers wrap remote calls inside circuit breakers (software switches that immediately fail fast and return fallback data instead of waiting endlessly for an unresponsive service).

```mermaid
flowchart TD
    %% SOLUTION DIAGRAM: Fault-Isolated Microservices (Delivery Framework)
    Client["User App"] -->|"1. Checkout Request"| OrderSvc["Order Service (Responds immediately)"]
    OrderSvc -->|"2. Commit Order"| OrderDB[("Order DB")]
    OrderSvc -->|"3. Publish OrderPlaced Event"| Broker["Event Broker (Kafka / SQS)"]
    InventorySvc["Inventory Worker"] -->|"4. Pull Event Async"| Broker
    PaymentSvc["Payment Worker"] -->|"4. Pull Event Async"| Broker
    EmailSvc["Notification Worker"] -->|"4. Pull Event Async"| Broker
```

Microservices maximize organizational scaling and allow teams to deploy updates independently without coordinating release schedules across the entire engineering department. In return, systems require higher operational maturity to manage distributed tracing (monitoring tools that record the entire path of a request across dozens of network services), container deployment pipelines (automated systems that package code into standardized units and release them to servers), and eventual consistency across isolated databases.

## Event-Driven Architecture and Distributed Consistency

Event-driven architecture connects decoupled applications through the asynchronous generation and consumption of events (records describing an action that occurred in the system, like a payment receipt or user signup). Services publish events to a central message broker (an intermediary messaging software that receives, stores, and routes messages between applications) without waiting for downstream consumers to process them.

Dual writing occurs when an application service updates its local database and immediately attempts to send an event to a remote message broker inside the same request handler. If a network interruption or server crash happens between the database write and the message dispatch, downstream subscribers never receive the event, causing permanent data inconsistency (a broken state where different databases hold conflicting data).

```mermaid
flowchart TD
    %% PROBLEM DIAGRAM: Dual-Write Failure Mode
    Client["Customer App"] -->|"1. Place Order"| OrderSvc["Order Service"]
    OrderSvc -->|"2. INSERT Order (Committed)"| DB[("Order Database")]
    OrderSvc -.->|"3. Network Timeout / Crash before publish"| Broker["Message Broker"]
    Broker -.->|"4. Event lost forever"| BillingSvc["Billing Service (Never charges customer)"]
```

The transactional outbox pattern prevents lost events by recording the business mutation and an event record together within a single ACID transaction (a database guarantee that all grouped writes succeed together or safely cancel without partial corruption). A separate change data capture process (a background worker that reads database commit logs) reliably delivers outbox records to the message broker.

```mermaid
flowchart TD
    %% SOLUTION DIAGRAM: Transactional Outbox Delivery Flow (Delivery Framework)
    Client["Customer App"] -->|"1. Place Order"| OrderSvc["Order Service (Responds immediately)"]
    OrderSvc -->|"2. Write Order & Outbox Table"| DB[("Order DB + Outbox Table")]
    DB -->|"3. Tail Commit Log"| Relay["CDC Relay Worker (Debezium)"]
    Relay -->|"4. Reliable Publish"| Broker["Message Broker (Kafka / RabbitMQ)"]
    BillingSvc["Billing Worker (Idempotent Handler)"] -->|"5. Pull Event Async"| Broker
    BillingSvc -->|"6. Update State"| BillingDB[("Billing DB")]
```

This pattern ensures that every committed business state change is published reliably without risking message loss during unexpected hardware failures. Downstream consumer services must be built to be idempotent (able to process duplicate message deliveries safely without creating repeated billing charges or redundant records).

## Serverless Architecture and Event Execution

Serverless architecture runs software logic inside stateless compute containers (short-lived computing environments that spin up on demand and shut down immediately after execution). Cloud providers automatically allocate server capacity to run functions when events arrive, charging exclusively for exact execution time.

Sudden traffic bursts create thousands of simultaneous serverless function instances, leading to severe cold starts (the startup delay incurred when a cloud provider prepares a fresh container runtime). Uncontrolled concurrency (many functions executing at the exact same moment) can instantly overwhelm downstream relational databases (structured databases that organize data into tables with predefined relationships) by exhausting available database connections and saturating CPU cores with connection handshakes (the initial cryptographic and network verification exchanges required to establish a communication channel).

```mermaid
flowchart TD
    %% PROBLEM DIAGRAM: Serverless Connection Storm
    Traffic["Sudden Traffic Surge (10,000 Invocations)"] --> CloudRuntime["Serverless Runtime"]
    CloudRuntime --> Fn1["Function Instance 1"]
    CloudRuntime --> Fn2["Function Instance 2"]
    CloudRuntime --> FnN["Function Instance N (Cold Starts)"]
    Fn1 -->|"Direct Connection Request"| DB[("Relational Database")]
    Fn2 -->|"Direct Connection Request"| DB
    FnN -.->|"Connection Pool Exhaustion"| Outage["Database Crash (Maximum connections reached)"]
```

Placing managed connection proxies and intermediate task queues between serverless functions and relational databases regulates concurrency and stabilizes database throughput (the total volume of read and write queries processed per second). Managed database proxies pool persistent sockets (reusable open network connections) so thousands of short-lived functions share a small, controlled number of physical database connections.

```mermaid
flowchart TD
    %% SOLUTION DIAGRAM: Serverless Architecture with Connection Pooling (Delivery Framework)
    Client["Client Traffic"] -->|"1. HTTP Request"| API["API Gateway"]
    API -->|"2. Buffer Surge"| Queue["Buffer Queue (SQS)"]
    FnFleet["Serverless Function Fleet"] -->|"3. Controlled Batch Pull"| Queue
    FnFleet -->|"4. Multiplexed Queries"| Proxy["Managed DB Proxy (RDS Proxy)"]
    Proxy -->|"5. Persistent Socket Pool"| DB[("Relational Database")]
```

Serverless compute eliminates idle infrastructure bills and automates horizontal scaling (adding more machines automatically to handle heavier traffic loads). Developers must manage cold start latency considerations, maximum execution time limits, and vendor ecosystem constraints (technical limitations or specific proprietary tools enforced by a cloud hosting provider) when building serverless systems.

## Peer-to-Peer Architecture and Decentralized Coordination

Peer-to-peer architecture distributes computational workloads and file storage across a network of equal participant machines called peers. Each peer node functions simultaneously as a client requesting data and a server fulfilling requests for other network participants without requiring a central authority.

Unstructured peer networks that rely on broadcast flooding (sending search queries blindly to every neighboring machine) suffer catastrophic network congestion (network slowdowns caused by too much data traffic). When nodes join and leave the network frequently (rapid node turnover where participants connect and disconnect unpredictably), query messages repeat redundantly across nodes, saturating user bandwidth and creating long lookup delays.

```mermaid
flowchart TD
    %% PROBLEM DIAGRAM: Broadcast Flooding & Bandwidth Saturation
    NodeA["Requesting Peer A"] -->|"1. Broadcast Query Flood"| NodeB["Peer B"]
    NodeA -->|"1. Broadcast Query Flood"| NodeC["Peer C"]
    NodeB -->|"2. Redundant Query Relay"| NodeD["Peer D"]
    NodeC -->|"2. Redundant Query Relay"| NodeD
    NodeD -.->|"3. Bandwidth Saturation & Dropped Lookups"| Outage["Network Congestion (Lookup Failure)"]
```

Structured peer-to-peer networks organize nodes into distributed hash tables (decentralized key-value indexes distributed across participating machines) with deterministic routing algorithms (mathematically predictable rules used to find the exact node storing a specific piece of data) like Kademlia. A small set of bootstrap servers (initial contact servers used only to discover active peers) facilitates network entry, after which nodes route search queries in logarithmic network hops (a fast lookup mechanism where query time grows very slowly even as the network reaches millions of nodes) and download file pieces simultaneously from multiple peers.

```mermaid
flowchart TD
    %% SOLUTION DIAGRAM: Structured DHT Peer Swarm (Delivery Framework)
    Bootstrap["Bootstrap Tracker (Initial Peer Discovery Only)"] -.->|"1. Discover Active Peers"| PeerA["Peer Node A"]
    PeerA -->|"2. Logarithmic Key Lookup"| PeerB["Peer Node B"]
    PeerB -->|"2. Logarithmic Key Lookup"| PeerC["Peer Node C"]
    PeerC -->|"2. Logarithmic Key Lookup"| PeerD["Peer Node D"]
    PeerA -->|"3. Parallel Chunk Download"| PeerC
    PeerA -->|"3. Parallel Chunk Download"| PeerD
```

Peer-to-peer systems offer high fault tolerance against censorship and scale aggregate download bandwidth automatically as new participants join the network. Applications must incorporate cryptographic validation (verifying data chunks against cryptographic hash signatures to confirm authenticity) to prevent malicious nodes from distributing corrupted file content.
