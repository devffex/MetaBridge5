---
name: system-design-load-balancing
description: >-
  Load balancing strategies, traffic distribution algorithms, Layer 4 vs Layer 7 routing, and health checks.
  Use when designing high-availability traffic routing, eliminating single points of failure, or optimizing server pool utilization.
---

## Traffic Distribution and Server Fleet Health Checks

Deploying application servers without an intermediate traffic distributor forces client applications to hardcode direct server IP addresses. When a physical host crashes, experiences a kernel panic, or undergoes an operating system update, client applications continue directing traffic to the dead host, resulting in immediate connection dropouts and service outages.

Furthermore, direct client-to-server connections create uneven traffic distribution, where one server runs at maximum CPU capacity while adjacent servers sit completely idle.

```mermaid
flowchart TD
    Client1["Web Client 1"] -->|"1. Direct Request (Hardcoded IP)"| HostA["Server A (Healthy)"]
    Client2["Web Client 2"] -->|"1. Direct Request (Hardcoded IP)"| HostB["Server B (Crashed / Unresponsive)"]
    HostB -.->|"2. Socket Connection Refused"| Drop["Immediate Client Outage (Connection Refused)"]
    Client3["Web Client 3"] -->|"1. Direct Request"| HostA
    HostA -.->|"3. Uneven Load -> CPU Saturated (100%)"| CrashA["Server A Overloaded"]
```

Load balancers sit as reverse proxy entry points that accept all incoming traffic and distribute connections evenly across a pool of healthy backend server instances. The load balancer runs continuous automated health checks (sending periodic HTTP probe requests like checking a health status endpoint every ten seconds) to verify backend responsiveness.

If a backend instance fails consecutive health checks or returns HTTP error codes, the load balancer automatically marks the node unhealthy and isolates it from the active rotation, seamlessly redirecting subsequent client requests to remaining healthy instances with zero user downtime.

```mermaid
flowchart TD
    ClientTraffic["Incoming User Traffic"] --> LB["Load Balancer Fleet"]
    subgraph TargetPool["Backend Server Pool (Multi-AZ)"]
        LB -->|"1. Forward Request (200 OK)"| Srv1["App Server 1 (Healthy)"]
        LB -->|"1. Forward Request (200 OK)"| Srv2["App Server 2 (Healthy)"]
        LB -.->|"2. Health Probe Fails (HTTP 500)"| Srv3["App Server 3 (Marked Unhealthy)"]
        LB -->|"3. Reroute Traffic Away from Srv 3"| Srv4["App Server 4 (Healthy)"]
    end
    Srv3 -.->|"Isolated from Active Pool"| Quarantine["Quarantined for Self-Healing"]
```

Automated health checking eliminates single points of failure and provides high availability across server fleets. Engineering teams execute rolling deployments (replacing old software versions with new versions one server at a time) with zero customer downtime by draining traffic from target instances before updates occur.

## Layer 4 Transport versus Layer 7 Application Load Balancing

Network architects must balance raw packet routing speed against intelligent, application-aware routing capabilities. Layer 4 load balancers operate strictly at the transport layer (TCP and UDP), making routing decisions based purely on source IP, destination IP, and port numbers without inspecting or decrypting packet payloads.

Because Layer 4 load balancers do not terminate TLS encryption or inspect HTTP headers, they cannot route traffic based on URL paths (such as separating shopping cart requests from static image requests) or inspect user cookies for authentication routing.

```mermaid
flowchart TD
    Client["Client Request (POST /api/v1/checkout)"] --> L4["Layer 4 Load Balancer (TCP Only)"]
    L4 -->|"1. Blind Round Robin by IP/Port"| StaticServer["Static Asset Server Fleet"]
    StaticServer -.->|"2. Cannot process checkout logic (404 Error)"| Error["Misrouted Request & Application Error"]
```

Layer 7 load balancers operate at the application layer, fully terminating TLS encryption handshakes and parsing incoming HTTP headers, cookies, and URL paths. This allows the load balancer to execute content-based routing (directing requests matching specific URL paths like api/orders to dedicated microservice clusters and static paths to cache servers), enforce Web Application Firewall security rules, and manage gRPC request multiplexing.

For extreme scale, architectures deploy a two-tier load balancing topology: ultra-high-throughput Layer 4 load balancers at the network edge distribute packets across a fleet of Layer 7 application load balancers, which in turn perform intelligent path-based routing to internal microservices.

```mermaid
flowchart TD
    Client["Client Request (POST /api/v1/checkout)"] --> L4["Tier 1: Layer 4 NLB (Millions of TCP packets/s)"]
    L4 --> L7["Tier 2: Layer 7 ALB (TLS Termination & URL Inspection)"]
    subgraph PathBasedRouting["Intelligent L7 Microservice Routing"]
        L7 -->|"Path: /api/v1/checkout"| OrderFleet["Order Microservice Fleet"]
        L7 -->|"Path: /static/*"| AssetFleet["Asset Cache Fleet"]
    end
```

Layer 4 load balancers provide raw packet performance with microsecond latencies for gaming, database connections, and DNS services. Layer 7 load balancers provide rich application routing, security inspection, and path multiplexing for modern microservices architectures.

## Load Balancing Algorithms and Capacity Weighting

Using simple round-robin algorithms (distributing requests sequentially to servers one by one in a fixed circular order) assumes that all incoming requests consume identical processing time and that all backend servers have identical hardware specifications. In real-world environments with mixed instance sizes or long-running WebSocket connections, round-robin routing inevitably overloads weaker instances while underutilizing high-capacity machines.

When an application server receives several compute-heavy analytical requests simultaneously under round robin, its CPU saturates and incoming requests queue up, leading to request timeouts.

```mermaid
flowchart TD
    Requests["Stream of Mixed Requests (Light vs Heavy)"] --> LB["Round Robin Load Balancer"]
    LB -->|"1. Heavy Request (60s PDF Export)"| SmallSrv["Server 1 (2 vCPU - Overloaded 100%)"]
    LB -->|"2. Light Request (5ms Ping)"| LargeSrv["Server 2 (16 vCPU - Idle 2%)"]
    LB -->|"3. Heavy Request (60s Report)"| SmallSrv
    SmallSrv -.->|"4. CPU Saturated -> Drops Connections"| Outage["Server 1 Crash (Unbalanced Load)"]
```

Modern load balancers employ dynamic routing algorithms tailored to workload characteristics. The Least Connections algorithm routes incoming requests to the server currently maintaining the fewest active concurrent connections, making it ideal for long-running transactions and WebSocket streams.

Weighted Round Robin assigns capacity weights to backend servers based on hardware specifications (routing four times as many requests to a 16-vCPU instance compared to a 4-vCPU instance), while IP Hash (sticky sessions) computes a mathematical hash of the client IP address to consistently direct a user to the same backend node for stateful applications.

```mermaid
flowchart TD
    Requests["Incoming Request Stream"] --> LB["Intelligent Load Balancer"]
    subgraph WeightedLeastConnections["Dynamic Capacity & Connection Routing"]
        LB -->|"Active Conns: 2 (Weight: 4x)"| HighCap["Server A (16 vCPU - Handles 80% Traffic)"]
        LB -->|"Active Conns: 5 (Weight: 1x - Full)"| Hold["Bypass Saturated Node"]
        LB -->|"Active Conns: 1 (Weight: 1x)"| LowCap["Server B (4 vCPU - Handles 20% Traffic)"]
    end
    HighCap -->|"Smooth Fast Execution"| DB[("Primary Database")]
    LowCap -->|"Smooth Fast Execution"| DB
```

Selecting the appropriate load balancing algorithm maximizes hardware utilization and prevents localized server hotspots. Systems dynamically update server weights during autoscaling events to maintain smooth traffic distribution across heterogeneous fleets.

## Global Server Load Balancing and Anycast Routing

Directing all global users to a single regional load balancer forces international clients to cross continental fiber optic links for every request, adding hundreds of milliseconds of round-trip network latency. Furthermore, if a physical natural disaster or regional power grid failure disables that single cloud data center, global service goes dark completely.

Relying purely on DNS-based geo-routing can result in delayed traffic failovers because internet service providers frequently cache DNS responses past their designated expiration times.

```mermaid
flowchart TD
    UserAsia["User in Singapore"] -->|"1. Transoceanic Route (250ms Latency)"| SingleLB["Single Load Balancer (US East Region)"]
    UserEurope["User in London"] -->|"1. Transatlantic Route (120ms Latency)"| SingleLB
    SingleLB -.->|"2. Regional Datacenter Power Grid Failure"| Blackout["Global Site Blackout (100% Outage)"]
```

Global Server Load Balancing (GSLB) pairs Anycast Border Gateway Protocol routing (a network addressing technique where multiple edge data centers across the globe advertise the exact same public IP address) with regional GeoDNS controllers. Internet routers automatically direct client network packets to the physically nearest edge data center point-of-presence along the shortest geographical BGP network path.

If an entire regional data center fails, BGP routing withdraws the IP route advertisement from that region within seconds, and global internet routers automatically reroute user packets to the nearest healthy regional data center without waiting for DNS cache expiration.

```mermaid
flowchart TD
    AnycastIP["Shared Global Anycast IP (198.51.100.1)"]
    UserAsia["User in Singapore"] -->|"1. Shortest BGP Network Path (< 5ms)"| EdgeAsia["Singapore Edge Data Center (Healthy)"]
    UserEurope["User in London"] -->|"1. Shortest BGP Network Path (< 5ms)"| EdgeEU["London Edge Data Center (Healthy)"]
    EdgeUS["US East Data Center (Offline)"] -.->|"2. BGP Route Withdrawn on Failure"| BGP["BGP Autonomous System Routing"]
    UserUS["User in New York"] -->|"3. Auto-Rerouted to Healthy Facility"| EdgeEU
```

Anycast routing delivers sub-ten-millisecond edge response times for global users and provides automated, resilient failover during catastrophic regional disasters. Systems terminate TCP and TLS handshakes at the Anycast edge, forwarding requests to backend data centers over optimized private fiber backbones.
