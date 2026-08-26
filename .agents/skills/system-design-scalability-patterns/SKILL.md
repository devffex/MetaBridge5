---
name: system-design-scalability-patterns
description: >-
  System scalability techniques and horizontal partitioning strategies. Use when evaluating,
  designing, or comparing Horizontal vs. Vertical Scaling, Auto Scaling Groups, Database Sharding,
  and distributed data synchronization mechanisms.
---

## Horizontal Scaling and Stateless Server Fleets

Stateful monolithic server architectures store user session states (in-memory user login credentials, shopping cart items, and active websocket handles) directly inside local server RAM. When incoming user traffic surges, the single application server runs out of physical memory and CPU processing capacity, while opening additional server nodes fails because user requests routed to a new machine cannot find the session state stored on the previous machine.

Storing session data locally ties clients to specific physical machines, creating severe operational bottlenecks where servers cannot be restarted, upgraded, or dynamically scaled without abruptly logging out users.

```mermaid
flowchart TD
    Client["User Client"] -->|"1. Login (Session stored in local RAM)"| ServerA["Stateful Server A (RAM Saturated)"]
    TrafficSurge["Traffic Spike (50,000 Users)"] --> ServerA
    ServerA -.->|"2. Out of Memory Crash"| Outage["Server Crash (All sessions lost)"]
    Client -->|"3. Reconnect routed to Server B"| ServerB["Server B (Session Missing -> Force Re-login)"]
```

Horizontal scaling (scaling out) distributes compute workloads across a dynamic pool of stateless application servers placed behind an edge load balancer. Stateless servers store zero session state in local memory, persisting all transient user sessions and authentication tokens in a shared, high-speed in-memory datastore (such as Redis) or encoding state into cryptographically signed JSON Web Tokens held by the client.

Cloud orchestration platforms utilize Auto Scaling Groups (automated scaling controllers that monitor metric thresholds like average CPU utilization or request latency) to provision additional server instances dynamically during traffic surges and terminate idle instances when demand subsides.

```mermaid
flowchart TD
    Traffic["Client Traffic (100,000 req/s)"] --> LB["Application Load Balancer"]
    subgraph AutoScalingFleet["Stateless Server Fleet (Auto Scaling Group)"]
        LB --> Srv1["Stateless Instance 1"]
        LB --> Srv2["Stateless Instance 2"]
        LB --> SrvN["Stateless Instance N (Auto-Provisioned)"]
    end
    Srv1 -->|"Fetch Session State (< 1ms)"| SessionStore[("Shared Redis Session Store")]
    Srv2 -->|"Fetch Session State (< 1ms)"| SessionStore
    SrvN -->|"Fetch Session State (< 1ms)"| SessionStore
```

Stateless horizontal scaling allows web applications to handle virtually unlimited concurrent traffic by adding inexpensive commodity compute nodes. Systems achieve high fault tolerance because the load balancer automatically detects unhealthy instances and redirects traffic to healthy nodes without user disruption.

## Vertical Scaling and Hardware Resource Ceilings

When single-node database instances or legacy enterprise monolithic systems encounter performance bottlenecks, engineering teams frequently choose vertical scaling (scaling up by upgrading the physical or virtual hardware specifications of an existing server, such as upgrading from 16 CPU cores to 128 cores and 64 gigabytes of RAM to 1 terabyte of RAM). While vertical scaling requires zero architectural code changes, physical server hardware introduces strict upper boundaries known as the hardware ceiling (the maximum compute, memory, and bus throughput capacity that current physical computer hardware can provide on a single motherboard).

Beyond hardware limits, vertical scaling exhibits an exponential cost curve (where ultra-high-end enterprise server instances cost disproportionately more per gigabyte of RAM than standard commodity machines) and requires scheduled maintenance downtime whenever resizing instances.

```mermaid
flowchart TD
    Workload["Growing Database Workload"] --> SmallSrv["Small DB Instance (16 vCPU / 64GB RAM)"]
    SmallSrv -.->|"1. Saturated CPU & Disk I/O"| Resize["Vertical Scale Up (Requires Scheduled Downtime)"]
    Resize --> LargeSrv["Max Hardware Instance (128 vCPU / 1TB RAM)"]
    LargeSrv -.->|"2. Traffic Surges Beyond Max Hardware Limits"| HardLimit["Hardware Ceiling Hit (Cannot scale further)"]
```

Modern architectures use vertical scaling as an initial pragmatic stepping stone for relational databases while simultaneously planning modular horizontal partitioning before reaching the hardware ceiling. For read-heavy relational workloads, systems deploy asynchronous read replicas behind database proxies to offload read traffic from the primary write node.

For write-heavy workloads approaching the hardware ceiling, systems introduce horizontal database sharding or transition high-throughput event ingestion components into distributed NoSQL datastores.

```mermaid
flowchart TD
    Workload["Growing Application Workload"] --> Router["Database Routing Proxy"]
    Router -->|"1. Route Writes (Preserves ACID Integrity)"| PrimaryDB[("Primary Database (Right-Sized Instance)")]
    Router -->|"2. Offload Read Traffic"| ReadFleet[("Horizontal Read Replica Fleet")]
    PrimaryDB -.->|"3. Async WAL Replication"| ReadFleet
    Router -.->|"4. Offload High-Velocity Telemetry"| NoSQL[("Distributed NoSQL Cluster (Horizontally Scaled)")]
```

Pairing vertical instance optimization with targeted horizontal offloading maximizes infrastructure cost efficiency. Systems maintain ACID relational consistency for core business ledgers while scaling read and telemetry throughput horizontally across independent nodes.

## Database Sharding and Horizontal Partitioning

Single relational database instances face physical storage and write input-output limits when datasets grow to tens of terabytes or write traffic exceeds tens of thousands of queries per second. When a table contains hundreds of millions of rows, B-Tree index scans slow down and disk storage fills the physical volume capacity.

Attempting to run complex analytics or write batches on massive monolithic tables degrades transaction latency across the entire database cluster.

```mermaid
flowchart TD
    Traffic["High-Velocity Writes (50,000 writes/s)"] --> SingleDB[("Single Monolithic DB (50TB Storage)")]
    SingleDB -.->|"1. Disk Volume Full & Buffer Cache Depleted"| SingleDB
    SingleDB -.->|"2. B-Tree Index Thrashing & Lock Contention"| Outage["Database Write Outage (Disk Saturation)"]
```

Database sharding (horizontal partitioning) splits a massive database table across multiple independent physical database instances called shards, where each shard stores a distinct subset of total rows based on a shard key (a specific column attribute such as user identification number or tenant ID). A lightweight sharding router evaluates the shard key of each incoming query using mathematical hashing (such as applying a modulo hash function to the user ID) and routes the query directly to the specific shard hosting that user data.

Because each shard operates as an autonomous database with its own CPU, RAM, and disk volume, total cluster write throughput and storage capacity expand linearly as new shards are added.

```mermaid
flowchart TD
    Client["Client Application"] --> Router["Sharding Router (Hash(user_id) % 3)"]
    Router -->|"user_id: 101 -> Shard 1"| Shard1[("Shard 1: Users A - H (Autonomous DB)")]
    Router -->|"user_id: 102 -> Shard 2"| Shard2[("Shard 2: Users I - Q (Autonomous DB)")]
    Router -->|"user_id: 103 -> Shard 3"| Shard3[("Shard 3: Users R - Z (Autonomous DB)")]
    Shard1 --> Storage1[("Independent Disk Volume 1")]
    Shard2 --> Storage2[("Independent Disk Volume 2")]
    Shard3 --> Storage3[("Independent Disk Volume 3")]
```

Database sharding provides virtually unlimited horizontal storage and write throughput scaling for massive multi-tenant platforms. Systems avoid cross-shard joins (expensive distributed operations that join tables located on different physical machines over the network) by co-locating related entity records on the same shard using consistent shard keys.

## Consistent Hashing and Virtual Node Rebalancing

Traditional sharding routers distribute data across database or caching nodes using a simple modulo hash formula (calculating the hash of the key modulo the total number of server nodes). However, when the cluster scales by adding a new server node or contracts when a server node crashes, the modulo divisor changes (for example, transitioning from modulo four to modulo five).

Changing the divisor causes virtually all existing keys (up to ninety percent of all stored data) to remap to different server nodes, triggering a catastrophic cache storm (mass simultaneous cache misses that hammer backend databases) and requiring massive, complex data migrations across database shards.

```mermaid
flowchart TD
    Key["Key 'user_99' (Hash: 99)"] --> Modulo["Modulo Formula: Hash % N"]
    Modulo -->|"N = 3 Nodes -> Key maps to Node 0"| Node0["Node 0"]
    Resize["Scale Out: Add Node 3 (N = 4)"] -.->|"Modulo changes to Hash % 4"| Modulo
    Modulo -.->|"Key 99 now maps to Node 3 (Cache Miss!)"| Node3["Node 3"]
    Modulo -.->|"Mass remapping of 90% of keys"| Storm["Cache Avalanche & Massive Data Migration"]
```

Consistent hashing maps both server nodes and data keys to positions along a continuous circular ring (a fixed integer mathematical space from zero to two raised to the power of thirty-two minus one). When looking up a key, the router hashes the key to locate its point on the ring and travels clockwise to find the first server node encountered.

When a new server node is added to the ring, it takes over only a small fraction of keys from its immediate clockwise neighbor, leaving the vast majority of existing key mappings completely untouched.

```mermaid
flowchart TD
    subgraph HashRing["Consistent Hash Ring (360-Degree Space)"]
        NodeA["Node A (Position: 0)"]
        NodeB["Node B (Position: 120)"]
        NodeC["Node C (Position: 240)"]
        NodeNew["Node D (New Node - Position: 60)"]
        KeyX["Key X (Position: 45)"]
    end
    KeyX -->|"Clockwise Navigation -> Stored on Node D"| NodeNew
    NodeNew -.->|"Takes only small fraction from Node B"| NodeB
    NodeA -->|"Untouched (Zero data movement)"| NodeA
    NodeC -->|"Untouched (Zero data movement)"| NodeC
```

Consistent hashing ensures that adding or removing server nodes moves only a minimal fraction of total data (specifically one divided by the total number of nodes). Systems deploy virtual nodes (assigning multiple pseudo-random positions along the ring to each physical server) to distribute data and traffic load evenly across physical machines, preventing hot spots.
