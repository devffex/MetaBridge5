---
name: system-design-network-protocols
description: >-
  Network and communication protocols in system design. Use when choosing or explaining communication
  mechanisms, transport protocols, and data exchange layers including HTTP/HTTPS, TCP, UDP, WebSockets,
  gRPC, MQTT, DNS, AMQP, and WebRTC.
---

## Hypertext Transfer Protocol and Transport Layer Security

The Hypertext Transfer Protocol operates as an application layer request-response standard where clients initiate communication and servers reply with data. In unencrypted HTTP version 1.1 networks, sending plain-text payloads across public internet routers exposes sensitive session credentials and personal data to eavesdropping and man-in-the-middle attacks (malicious interception where third parties secretly intercept and alter network communications).

Furthermore, HTTP version 1.1 requires sequential head-of-line blocking on single TCP connections (where an earlier slow request blocks all subsequent requests behind it on the same socket), forcing browsers to open dozens of parallel connections and exhausting server socket limits.

```mermaid
flowchart TD
    Client["Client Browser"] -->|"1. Plaintext HTTP GET /login"| Router["Public Internet Router (Insecure)"]
    Router -.->|"2. Packet Interception (Credentials Exposed)"| Attacker["Eavesdropper / Man-in-the-Middle"]
    Router -->|"3. Unencrypted Forward"| Server["Origin Server"]
    Client -.->|"4. Heavy Asset Blocks Subsequent Requests"| Block["Head-of-Line Blocking Latency"]
```

Transport Layer Security encrypts communication channels using asymmetric public key cryptographic handshakes (a security protocol where a server proves identity with a certificate and exchanges a temporary symmetric session key). Modern HTTP version 2 and HTTP version 3 multiplex hundreds of concurrent requests over a single connection using binary frames, eliminating head-of-line blocking and reducing connection overhead.

The API gateway terminates TLS encryption at the infrastructure perimeter (handling cryptographic handshakes at the edge so internal microservices do not waste CPU cycles on security overhead), forwarding clean decrypted requests across secure internal networks.

```mermaid
flowchart TD
    Client["Client Browser"] -->|"1. TLS 1.3 Cryptographic Handshake"| Edge["Edge Reverse Proxy / CDN"]
    Edge -->|"2. Verify SSL Certificate & Establish Session Key"| Edge
    Client -->|"3. Multiplexed Encrypted Binary Stream (HTTP/2 / HTTP/3)"| Edge
    Edge -->|"4. Fast Decrypted Internal Forward"| AppServer["Private Backend Server Fleet"]
    AppServer -->|"5. Instant Response"| Edge
    Edge -->|"6. Encrypted Stream Response"| Client
```

This combination secures data in transit against eavesdropping while delivering sub-millisecond connection reuse across concurrent web requests. System architectures rely on edge content delivery networks to cache TLS session tickets and terminate encryption close to global users.

## Transmission Control Protocol and Reliable Byte Streams

Unreliable physical transmission lines suffer packet loss, out-of-order packet arrival, and network buffer congestion. When application services transmit financial database updates, SSH remote commands, or software binaries without transport verification, lost or rearranged packets result in truncated files, corrupted records, and invalid system state.

Attempting to implement custom packet retransmission logic inside every individual application introduces immense developer complexity and risks uncontrolled congestion collapse (a catastrophic network failure where retransmissions saturate available bandwidth).

```mermaid
flowchart TD
    Sender["Application Sending Byte Stream"] -->|"1. Raw Packets 1, 2, 3"| UnreliableNetwork["Unreliable IP Network"]
    UnreliableNetwork -.->|"2. Packet 2 Dropped / Lost in Transit"| Lost["Dropped Packet"]
    UnreliableNetwork -->|"3. Packet 3 arrives before Packet 1"| Receiver["Application Receiver"]
    Receiver -.->|"4. Corrupted Stream / Missing Bytes"| Corruption["Application Crash & Data Corruption"]
```

The Transmission Control Protocol provides a connection-oriented, reliable byte stream over unreliable IP networks through a structured three-way handshake (a synchronization sequence where sender and receiver agree on initial sequence numbers). TCP guarantees that every transmitted byte arrives intact and in exact sequential order by assigning incrementing sequence numbers to every packet and requiring explicit receiver acknowledgments.

If an acknowledgment is missing, TCP automatically retransmits the missing segment and regulates transmission speeds dynamically using sliding window flow control and congestion avoidance algorithms.

```mermaid
flowchart TD
    Client["Client Endpoint"] -->|"1. SYN (seq=x)"| Server["Server Endpoint"]
    Server -->|"2. SYN-ACK (seq=y, ack=x+1)"| Client
    Client -->|"3. ACK (ack=y+1)"| Server
    subgraph ReliableOrderedStream["Reliable Ordered Transmission"]
        Client -->|"4. Packet 1 (seq=1..1000)"| Server
        Server -->|"5. ACK 1001"| Client
        Client -->|"6. Packet 2 (seq=1001..2000)"| Server
        Server -->|"7. ACK 2001"| Client
    end
```

TCP guarantees absolute data accuracy and ordered delivery for mission-critical protocols like SQL databases, file transfers, and web browsing. The protocol trades connection setup latency (the initial round-trip time required for the handshake) and head-of-line byte buffering for total transmission reliability.

## User Datagram Protocol and Low-Latency Datagrams

Real-time interactive applications (such as live voice calls, multiplayer video games, and high-frequency video conferencing) require continuous, ultra-low latency updates. When real-time systems use connection-oriented protocols like TCP, a single lost packet causes the receiving operating system to pause data delivery and wait for retransmission, introducing noticeable audio stuttering and visual freezes.

In fast-paced competitive gaming or live video feeds, an outdated packet containing player coordinates or video frames from two hundred milliseconds ago is completely useless and should be discarded rather than retransmitted.

```mermaid
flowchart TD
    Player["Live Player (Sends position 60 times/sec)"] -->|"1. Position T1, T2, T3"| TCPSocket["TCP Stream"]
    TCPSocket -.->|"2. Packet T2 Dropped"| Lost["Packet Loss"]
    TCPSocket -.->|"3. Receiver halts execution waiting for retransmission"| Freeze["Screen Stutter / Lag Spike (250ms)"]
```

The User Datagram Protocol is a lightweight, connectionless transport protocol that transmits independent datagrams (self-contained data packets) immediately with zero handshake delay and zero retransmission guarantees. If a packet is dropped by an intermediate router, UDP does not retry, allowing subsequent real-time packets to be delivered instantly without buffering delays.

Applications process the incoming stream continuously, replacing lost coordinates or dropped video frames with the latest arriving state snapshot.

```mermaid
flowchart TD
    Player["Live Player Client"] -->|"1. UDP Datagram (Tick 101)"| GameServer["Dedicated Game Server"]
    Player -->|"2. UDP Datagram (Tick 102)"| GameServer
    Player -.->|"3. Datagram 103 Dropped (Ignored)"| Router["Network Router"]
    Player -->|"4. UDP Datagram (Tick 104)"| GameServer
    GameServer -->|"5. Instant Render Snapshot Tick 104 (< 10ms)"| Screen["Smooth Real-Time Game State"]
```

UDP delivers minimal latency and low transport overhead for time-sensitive, loss-tolerant streams. Applications implement optional sequencing or forward error correction (reconstructing lost packets mathematically from redundant data bits) at the application layer when specialized reliability is needed.

## WebSockets and Full-Duplex Bidirectional Streams

Traditional HTTP request-response architectures require the client to initiate all communication, preventing servers from pushing real-time updates directly to clients. Web applications attempting real-time features (like live chat rooms, stock market tickers, or multiplayer collaboration tools) resort to short polling (sending repeated HTTP GET requests every second), creating massive HTTP header overhead and overwhelming backend connection pools with empty responses.

Long polling reduces empty responses but still requires tearing down and renegotiating HTTP connections repeatedly, driving up server CPU utilization and adding network latency.

```mermaid
flowchart TD
    Client["Client Browser (Stock Ticker)"] -->|"1. GET /price (Header: 1KB)"| API["Web API Server"]
    API -->|"2. 200 OK: $150 (Header: 1KB)"| Client
    Client -->|"3. GET /price (1 second later)"| API
    API -->|"4. 304 Not Modified (No change)"| Client
    Client -.->|"5. 100,000 clients polling repeatedly"| Saturation["Network Bandwidth Waste & CPU Saturation"]
```

The WebSocket protocol initiates with a standard HTTP upgrade handshake and transitions immediately into a persistent, full-duplex TCP socket connection (a two-way communication channel where both client and server send messages independently at any millisecond). The connection remains open with tiny two-byte framing overhead, allowing servers to push live price updates or chat messages to millions of connected clients instantly without waiting for client requests.

Backend server fleets manage WebSocket connections using distributed pub-sub message brokers (such as Redis Pub/Sub) to broadcast updates across thousands of open persistent sockets simultaneously.

```mermaid
flowchart TD
    Client["Client Browser"] -->|"1. HTTP GET /ws (Upgrade: websocket)"| Gateway["WebSocket Gateway Fleet"]
    Gateway -->|"2. 101 Switching Protocols (Handshake Complete)"| Client
    subgraph PersistentBidirectionalPipe["Full-Duplex Persistent Socket"]
        Broker["Redis Pub/Sub (Live Market Feed)"] -->|"3. Price Update ($151.25)"| Gateway
        Gateway -->|"4. Instant Server-Push (2-byte frame)"| Client
        Client -->|"5. Client Action (Buy Order)"| Gateway
    end
```

WebSockets deliver sub-millisecond bidirectional communication and reduce network bandwidth consumption by eliminating repetitive HTTP headers. Systems must deploy specialized connection gateways to manage millions of persistent concurrent sockets and handle automatic reconnection logic during mobile network handoffs.

## Google Remote Procedure Calls and Binary Multiplexing

Internal microservices communicating over standard REST JSON APIs spend significant CPU time serializing objects into text strings and parsing large JSON payloads on every request. JSON formats include repetitive verbose field names and lack compile-time type validation, leading to runtime data parsing bugs and bloated network bandwidth consumption inside high-density data centers.

Furthermore, managing dozens of disparate REST endpoint contracts across multi-language engineering teams creates documentation drift and broken service integrations.

```mermaid
flowchart TD
    OrderSvc["Order Service"] -->|"1. JSON Serialize: {'user_id': 123, ...}"| REST["HTTP/1.1 REST Call"]
    REST -->|"2. Verbose Text Payload (1.5 KB)"| PaymentSvc["Payment Service"]
    PaymentSvc -->|"3. JSON Parse String & Validate Types"| PaymentSvc
    PaymentSvc -.->|"4. CPU Bottleneck on Serialization (15ms)"| Delay["Microservice Latency Accumulation"]
```

Google Remote Procedure Calls (gRPC) utilizes Protocol Buffers (a language-neutral binary serialization format that encodes structured data into compact binary bytes based on strict schema contracts). Microservices define typed service contracts in interface definition files, automatically generating high-performance client stubs and server interfaces across multiple programming languages.

Operating over HTTP/2, gRPC multiplexes multiple remote calls over single persistent connections, supporting bidirectional streaming, deadline propagation (automatically canceling downstream work if an upstream caller times out), and built-in binary compression.

```mermaid
flowchart TD
    OrderSvc["Order Service"] -->|"1. Strongly Typed RPC Call"| Stub["Generated Protobuf Stub"]
    Stub -->|"2. Binary Compact Payload (80 Bytes)"| HTTP2["HTTP/2 Multiplexed Socket"]
    HTTP2 -->|"3. Sub-Millisecond Binary Transport"| PaymentSvc["Payment Service"]
    PaymentSvc -->|"4. Instant Binary Unpack (< 1ms)"| PaymentLogic["Execute Payment Logic"]
    PaymentLogic -->|"5. Typed Binary Response"| OrderSvc
```

gRPC delivers up to ten times faster serialization throughput and drastically reduces network bandwidth inside backend microservice meshes. Because Protocol Buffers require compiled schemas, public browser clients typically interact through an edge API gateway that translates external JSON requests into internal gRPC calls.

## Message Queuing Telemetry Transport for Constrained Devices

Internet-of-Things devices (such as battery-powered agricultural soil sensors, smart home appliances, and vehicle GPS trackers) operate over fragile cellular networks with strict electrical power constraints. Connecting constrained devices over heavy protocols like HTTP or WebSockets exhausts device battery power through continuous large header transmissions and memory-heavy keepalive loops.

When thousands of remote sensors attempt to publish small telemetry readings over HTTP, mobile data costs surge and devices lose connectivity whenever cellular signals weaken.

```mermaid
flowchart TD
    Sensor["Battery-Powered Soil Sensor"] -->|"1. HTTPS POST /telemetry (1.2KB Headers)"| MobileNet["Cellular Network (2G / 3G)"]
    MobileNet -->|"2. Full TLS Handshake & Socket Teardown"| WebServer["HTTP Web Server"]
    Sensor -.->|"3. High Battery Drain & Radio Sleep Delay"| DeadBattery["Sensor Battery Depleted in 48 Hours"]
```

Message Queuing Telemetry Transport (MQTT) is a lightweight publish-subscribe protocol engineered specifically for low-bandwidth, high-latency, constrained network environments. MQTT packets require only a two-byte fixed header, minimizing network payload overhead and preserving device battery life.

The protocol provides three distinct Quality of Service levels (QoS 0 for at-most-once fire-and-forget, QoS 1 for at-least-once delivery, and QoS 2 for exactly-once delivery) alongside persistent session queues and last-will-and-testament messages (automated notifications published by the broker if a remote device disconnects unexpectedly).

```mermaid
flowchart TD
    Sensor["Soil Sensor (Battery Powered)"] -->|"1. Publish (2-byte header, QoS 1)"| Broker["MQTT Broker (Mosquitto / EMQX)"]
    Broker -->|"2. Instant Broker ACK"| Sensor
    Sensor -->|"3. Radio Enters Low-Power Sleep"| Sleep["Battery Preserved (2 Years)"]
    Broker -->|"4. Deliver to Subscribers (home/garden/soil)"| App["Monitoring Dashboard"]
```

MQTT provides reliable telemetry ingestion across millions of distributed hardware devices over constrained wireless links. Systems connect MQTT brokers to backend message streaming pipelines to ingest high-volume telemetry into analytics databases.

## Domain Name System and GeoDNS Routing

Internet routing relies on numerical IP addresses, but human users navigate networks using memorable domain names. Without an efficient address resolution mechanism, user devices cannot locate the physical servers hosting web applications.

Furthermore, if a global web platform resolves all domain queries to a single centralized server IP address, users on other continents suffer severe latency, and regional data center outages take down global traffic.

```mermaid
flowchart TD
    UserAsia["User in Singapore"] -->|"1. Query: example.com"| BasicDNS["Basic Static DNS Server"]
    BasicDNS -->|"2. Returns Static US IP Address"| UserAsia
    UserAsia -->|"3. Transpacific Request (250ms Latency)"| SingleServer["Single Server (us-east-1)"]
    SingleServer -.->|"4. Regional Outage"| Outage["Global Service Blackout"]
```

The Domain Name System functions as the decentralized hierarchical phonebook of the internet, resolving human domain names into computer-routable IP addresses through recursive resolvers, root servers, top-level domain servers, and authoritative nameservers. GeoDNS (geographic traffic routing) inspects the client IP address or subnet during the DNS lookup and returns the IP address of the closest regional edge data center.

GeoDNS services perform continuous health checks on backend server pools, automatically removing degraded data center IPs from DNS responses and rerouting traffic to healthy regional clusters within seconds.

```mermaid
flowchart TD
    UserAsia["User in Singapore"] -->|"1. DNS Query: example.com"| LocalResolver["Recursive DNS Resolver"]
    LocalResolver -->|"2. Query GeoDNS (Client IP Subnet)"| GeoDNS["Authoritative GeoDNS (Route 53)"]
    GeoDNS -->|"3. Return Singapore Edge IP (Healthy)"| LocalResolver
    LocalResolver -->|"4. Return 13.228.x.x"| UserAsia
    UserAsia -->|"5. Connect to Local Edge Server (< 10ms Latency)"| AsiaDC["Asia Edge Data Center"]
```

GeoDNS steering optimizes global latency and provides high-level disaster recovery across multiple geographic regions. Because DNS responses are cached by internet service providers according to time-to-live settings, systems set short TTL values (such as sixty seconds) to enable rapid traffic failover during major incidents.

## Advanced Message Queuing Protocol and Message Exchanges

Basic point-to-point queues lack flexible routing mechanisms, forcing producers to know the exact consumer queue destinations before publishing. When complex enterprise applications need to route a single business event (such as an order created event) to multiple independent downstream systems (such as billing, inventory, analytics, and shipping) with customized filtering rules, hardcoding queue logic in application servers creates fragile architectural coupling.

If a downstream billing system crashes, unbuffered direct API calls drop transactions, resulting in unbilled orders and severe financial discrepancies.

```mermaid
flowchart TD
    OrderAPI["Order API Server"] -->|"1. Direct POST /charge"| Billing["Billing Service (Crashed / Down)"]
    OrderAPI -->|"2. Direct POST /reserve"| Inventory["Inventory Service"]
    Billing -.->|"3. Connection Timeout & Lost Transaction"| DroppedOrder["Unbilled Order & Lost Revenue"]
```

The Advanced Message Queuing Protocol (AMQP) standardizes enterprise messaging through message brokers (such as RabbitMQ) that decouple producers from storage queues using flexible exchanges. Producers publish messages to an exchange with a routing key, and the exchange routes copies of the message to bound queues based on predefined rules (direct routing for exact matches, topic routing for wildcard pattern matches, and fanout routing for universal broadcasting).

Downstream worker services pull messages from their dedicated queues at their own processing capacity, acknowledging messages only after successful persistence to ensure zero data loss.

```mermaid
flowchart TD
    OrderAPI["Order API Server"] -->|"1. Publish with Routing Key: order.created"| Exchange["AMQP Topic Exchange"]
    Exchange -->|"2. Route (Binding: order.*)"| BillingQ[("Billing Queue")]
    Exchange -->|"2. Route (Binding: *.created)"| AnalyticsQ[("Analytics Queue")]
    BillingQ -->|"3. Pull & Acknowledge"| BillingWorker["Billing Worker Fleet"]
    AnalyticsQ -->|"4. Pull & Acknowledge"| AnalyticsWorker["Analytics Ingestion Worker"]
```

AMQP provides durable enterprise message queuing, fine-grained publish-subscribe routing, and guaranteed message delivery. The protocol safeguards distributed workflows from downstream service outages by buffering work in persistent queues until workers recover.

## Web Real-Time Communication and Direct Browser Streaming

Streaming real-time video, audio, and large data files between users through centralized media servers incurs massive cloud bandwidth costs and adds unnecessary latency hops. When two users in the same city communicate through a central cloud server located thousands of miles away, media streams suffer transit latency delays and video quality degradation.

Centralized media proxies also present a critical security target where unencrypted communication streams could potentially be intercepted on server disks.

```mermaid
flowchart TD
    UserA["User A (London)"] -->|"1. Upload Video Stream"| CentralServer["Central Media Server (California)"]
    CentralServer -->|"2. Transmit Video Stream"| UserB["User B (London)"]
    CentralServer -.->|"3. High Transit Latency (180ms) & Expensive Cloud Bandwidth"| Cost["Severe Latency & Bandwidth Costs"]
```

Web Real-Time Communication (WebRTC) enables direct, peer-to-peer audio, video, and data streaming between web browsers without routing media traffic through intermediate servers. Browsers use a lightweight signaling server only during the initial connection setup to exchange session description protocol profiles and interactive connectivity establishment network candidates (discovering public IP addresses and ports through STUN and TURN traversal servers).

Once the direct peer connection is established, audio and video streams travel directly between participant browsers over secure real-time transport protocol channels encrypted with end-to-end DTLS-SRTP encryption.

```mermaid
flowchart TD
    UserA["User A (Browser)"] <-->|"1. Initial Signaling (SDP & ICE Exchange)"| Signal["Signaling Server (Initial Setup Only)"]
    Signal <-->|"1. Initial Signaling"| UserB["User B (Browser)"]
    subgraph DirectP2PChannel["Direct Peer-to-Peer Encrypted Stream"]
        UserA <-->|"2. Direct Encrypted Media Stream (SRTP / UDP < 15ms Latency)"| UserB
    end
```

WebRTC eliminates central media server bandwidth expenses and achieves sub-fifty-millisecond real-time communication for video calling and browser file sharing. When direct peer connections are blocked by strict symmetric corporate firewalls, the connection falls back cleanly to relay traversal servers (TURN servers) to maintain connectivity.
