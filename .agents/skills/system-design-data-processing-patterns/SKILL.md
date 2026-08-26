---
name: system-design-data-processing-patterns
description: >-
  Data engineering processing patterns, batch computing architectures, and historical data backfilling.
  Use when designing batch processing pipelines (Spark/Flink/Hadoop), ETL/ELT architectures,
  or orchestrating historical data re-computations and backfills with Airflow/dbt.
---

## Batch Processing and MapReduce Distributed Compute

Executing large-scale analytical queries, monthly financial reconciliations, or machine learning feature aggregations directly against operational online transaction processing databases (databases optimized for fast, individual row reads and writes like PostgreSQL or MySQL) creates severe resource contention. Heavy multi-table scan operations lock relational tables, exhaust disk input-output capacity, and slow down user-facing checkout transactions to the point of complete system failure.

When raw uncompressed transaction logs and change streams are queried without preprocessing, single server nodes run out of memory and execution times stretch from minutes into days.

```mermaid
flowchart TD
    Analytics["BI Dashboard / Heavy Analytics Query"] -->|"1. Complex Multi-Table JOIN & Full Table Scan"| ProdDB[("Operational Production DB")]
    ProdDB -.->|"2. Disk I/O Saturation & Table Locks"| ProdDB
    UserTraffic["Live User Transactions"] -->|"3. INSERT / UPDATE Order"| ProdDB
    ProdDB -.->|"4. Saturated Connection Pool & Locks"| Crash["User Checkout Outage (504 Gateway Timeout)"]
```

Batch processing moves analytical workloads into a dedicated distributed computing pipeline that operates over scheduled intervals (such as nightly or hourly data runs). Operational databases export incremental change dumps directly into a scalable data lake (a centralized storage repository that holds raw structured and unstructured data files in cost-effective object storage).

Distributed compute clusters (such as Apache Spark or Apache Hadoop) partition the raw files across worker nodes using the MapReduce paradigm (a programming model that filters and transforms data chunks in parallel before combining them into consolidated aggregates), writing the final optimized records into a columnar data warehouse (a database organized by columns rather than rows to accelerate analytical filtering and aggregations).

```mermaid
flowchart TD
    ProdDB[("Production DBs & Event Logs")] -->|"1. Scheduled Data Dump"| DataLake[("Raw Data Lake (S3 / GCS Parquet)")]
    DataLake -->|"2. Partitioned Chunks"| SparkMaster["Compute Master / Driver (Apache Spark)"]
    SparkMaster -->|"3. Parallel Map Task"| Worker1["Worker Node 1"]
    SparkMaster -->|"3. Parallel Map Task"| Worker2["Worker Node 2"]
    Worker1 -->|"4. Reduce & Aggregate"| DW[("Data Warehouse (Snowflake / BigQuery)")]
    Worker2 -->|"4. Reduce & Aggregate"| DW
    DW -->|"5. Instant Sub-Second Query"| BI["BI Dashboards & Executive Reports"]
```

This pattern isolates operational transactional systems completely from heavy analytical queries while allowing data teams to process petabytes of information in parallel. Systems trade real-time reporting latency for massive aggregate data throughput and predictable compute costs.

## Stream Processing and Real-Time Event Windowing

Traditional batch pipelines introduce substantial data latency because reports and metrics only update when scheduled batch jobs execute hours or days later. In fraud detection, live cybersecurity intrusion monitoring, or dynamic ride-sharing pricing, waiting for a nightly batch job allows fraudulent transactions or system breaches to execute undetected.

Attempting to achieve real-time analytics by running short-interval micro-batch jobs every few seconds creates massive scheduler overhead and struggles to handle out-of-order events (messages that arrive late due to network delays or mobile disconnection).

```mermaid
flowchart TD
    Sensor["IoT Sensor / Payment Stream"] -->|"1. Continuous Stream (100k events/s)"| Storage[("Raw Disk Storage")]
    MicroBatch["Frequent Batch Job (Every 5s)"] -->|"2. Query Storage & Lock Rows"| Storage
    MicroBatch -.->|"3. Scheduler Overhead & Late Event Dropping"| Outage["High Latency & Missing Fraud Alerts"]
```

Stream processing processes incoming data records individually or in micro-windows as soon as they are produced, eliminating batch scheduling delays. Stream engines (such as Apache Flink or Apache Kafka Streams) ingest events continuously from message topics and maintain stateful in-memory accumulators across defined time windows.

The engine handles out-of-order records through watermark tracking (a mechanism that tracks event timestamps rather than arrival time to wait a designated duration for late-arriving messages), emitting updated calculations immediately when time thresholds expire.

```mermaid
flowchart TD
    CreditCard["Payment Terminal"] -->|"1. Swipe Event (Timestamp: T1)"| Kafka["Event Stream (Apache Kafka)"]
    Kafka -->|"2. Ingest Stream"| Flink["Stream Processing Engine (Apache Flink)"]
    subgraph WindowingEngine["Stateful Event Windowing (Sliding 60s Window)"]
        Flink -->|"3. Aggregate Velocity & Amount"| StateStore[("In-Memory State Store (RocksDB)")]
        StateStore -->|"4. Evaluate Fraud Rule: > 3 Swipes in 60s"| AlertRule{"Suspicious?"}
    end
    AlertRule -->|"Yes (Fraud Detected)"| Block["Block Card & Trigger Real-Time SMS Alert"]
    AlertRule -->|"No (Legitimate)"| CleanStore[("Analytics Stream")]
```

Stream processing provides sub-second detection and action boundaries for critical operational events. In exchange, the architecture requires managing state checkpointing (periodically saving in-memory stream state to durable storage) to ensure exact once-processing guarantees during sudden worker node crashes.

## Historical Data Backfilling and Partition Overwriting

When data engineering teams update transformation logic (such as fixing a bug in customer lifetime value formulas or adding a new regulatory tax breakdown), analytical reporting tables immediately contain inconsistent metrics. Historical records calculated under legacy business logic clash with newly generated records, corrupting long-term financial reports and predictive machine learning models.

Attempting to update millions of historical rows with live SQL update queries creates massive database lock contention, risks partially corrupted tables if the script fails midway, and exhausts transaction log capacity.

```mermaid
flowchart TD
    Engineer["Data Engineer (Updated Tax Formula)"] -->|"1. Run In-Place SQL UPDATE on Historical Table"| ProdTable[("Live Analytics Table (500M Rows)")]
    ProdTable -.->|"2. Table Locks Held for Hours"| ProdTable
    ProdTable -.->|"3. Script Fails at 60% (Partial Corruption)"| CorruptData["Corrupted Data State & Inconsistent Reports"]
```

Data backfilling solves metric updates by re-running deterministic transformation directed acyclic graphs (workflow DAGs where processing steps follow a defined topological order without loops) retroactively across partitioned historical time ranges. An orchestrator (such as Apache Airflow or Dagster) coordinates the parallel execution of compute jobs across individual historical partitions (for example, monthly or daily data folders).

Each backfill worker computes the updated partition in an isolated staging location and performs an atomic partition swap (a fast metadata pointer switch that replaces an entire old data partition with a new one instantaneously), ensuring zero read downtime and preventing partial table corruption.

```mermaid
flowchart TD
    Airflow["Orchestrator (Apache Airflow / Dagster)"] -->|"1. Trigger Backfill: Date Range 2026-01 to 2026-06"| DAG["Transformation DAG"]
    subgraph ParallelPartitionRuns["Concurrent Partition Execution"]
        DAG -->|"Recompute Jan"| Worker1["Worker Jan (Staging)"]
        DAG -->|"Recompute Feb"| Worker2["Worker Feb (Staging)"]
        DAG -->|"Recompute Mar"| Worker3["Worker Mar (Staging)"]
    end
    Worker1 -->|"2. Atomic Partition Swap"| TargetTable[("Production Analytics Table (Clean Overwrite)")]
    Worker2 -->|"2. Atomic Partition Swap"| TargetTable
    Worker3 -->|"2. Atomic Partition Swap"| TargetTable
```

Atomic partition overwriting guarantees that readers always observe complete, consistent historical datasets even while massive re-computations occur concurrently. If any individual backfill task fails, the staging output is discarded without altering the active production reporting tables.

## Lambda versus Kappa Architecture Tradeoffs

Organizations that require both real-time dashboards and comprehensive historical reporting frequently struggle to balance the low latency of stream processing with the heavy re-computation power of batch systems. Attempting to force a single batch system to handle real-time streaming causes intolerable reporting delays, while forcing a stream system to process years of historical data can overwhelm in-memory state stores.

Deploying separate, uncoordinated systems for streaming and batch processing causes code duplication and logic drift, where the real-time stream engine and the nightly batch engine produce conflicting metric calculations for the exact same business events.

```mermaid
flowchart TD
    EventSource["User Event Source"] -->|"Direct Feed"| StreamApp["Streaming App (Custom Logic V1)"]
    EventSource -->|"Daily Dump"| BatchApp["Batch Job (Custom Logic V2)"]
    StreamApp -->|"Writes Real-Time View"| RealtimeDB[("Real-Time Store")]
    BatchApp -->|"Writes Historical Mart"| HistoricalDB[("Historical Store")]
    RealtimeDB -.->|"Conflicting Metric Values (Logic Drift)"| Dashboard["Confused Executive Dashboard"]
```

The Lambda architecture unifies these needs by maintaining three distinct layers: a speed layer (stream processing that computes real-time views with low latency), a batch layer (an immutable master data lake that computes perfectly accurate comprehensive views over time), and a serving layer that merges results from both layers when queried.

The Kappa architecture simplifies this model by eliminating the batch layer entirely, treating all data as a single continuous append-only event stream stored in a durable, replayable log (such as Apache Kafka). When business logic changes or historical re-computations are needed, the team deploys a new streaming consumer instance, replays the event log from the beginning of time into a fresh view, and redirects user queries once processing catches up.

```mermaid
flowchart TD
    subgraph KappaArchitecture["Kappa Architecture (Unified Stream Engine)"]
        Producer["Application Event Producer"] -->|"1. Append Event"| KafkaLog[("Durable Replayable Event Log (Kafka)")]
        KafkaLog -->|"2. Live Stream Consumer"| SpeedView[("Active Serving View (Fast Queries)")]
        KafkaLog -.->|"3. Replay from Offset 0 (Logic Update)"| NewConsumer["Updated Stream Worker Fleet"]
        NewConsumer -.->|"4. Populate Fresh View"| NewView[("Upgraded Serving View")]
    end
    Client["Analytical Client Query"] -->|"5. Switch Traffic to New View"| NewView
```

Kappa architectures reduce operational overhead by maintaining a single codebase for both real-time processing and historical recalculations. Lambda architectures remain valuable when batch algorithms are fundamentally different from real-time heuristics, while Kappa excels when stream transformation logic can be replayed deterministically over immutable logs.
