# Circuit Breaker Pattern

## 1. Overview & Purpose
The Circuit Breaker pattern prevents an application from repeatedly executing an operation that is highly likely to fail. It monitors external dependency calls; once failures cross a threshold, the breaker "trips" (opens) to fail requests immediately, sparing resources and giving the external system time to recover.

## 2. Backing App Scenarios
- **External API Clients**: Wrapping payment gateways or geolocation services that are experiencing network timeouts.
- **Database Failures**: Preventing new API requests from hitting an overloaded or recovering database replica.
- **Microservice Calls**: Isolating internal service communication in distributed mesh environments.

## 3. When to Apply
- When calling external backing services over the network that are subject to transient latency or outages.
- When you want to provide graceful fallbacks (e.g. returning stale cache data) instead of hanging requests or returning 500 errors.

## 4. Drawbacks & Risks
- **Complex Testing**: Simulating circuit state changes (Closed -> Open -> Half-Open) requires complex integration test configurations.
- **Tuning Thresholds**: Setting incorrect failure rates, timeouts, or sleep windows can cause the breaker to trip too early or remain open too long.

## 5. Language-Agnostic Design

```
Class CircuitBreaker {
    private state: String = "CLOSED" // CLOSED, OPEN, HALF_OPEN
    private failureCount: Integer = 0
    private lastStateChangeTime: Timestamp

    public execute(apiCall: Function, fallback: Function): Object {
        if (this.state == "OPEN") {
            if (hasSleepWindowExpired()) {
                this.state = "HALF_OPEN"
            } else {
                return fallback.run() // Return fallback immediately
            }
        }

        try {
            Object result = apiCall.run()
            if (this.state == "HALF_OPEN") {
                resetBreaker()
            }
            return result
        } catch (Exception ex) {
            handleFailure()
            if (this.state == "OPEN") {
                return fallback.run()
            }
            throw ex
        }
    }
}
```

## 6. Decision Matrix

| Dimension | Circuit Breaker Protection | Direct Network Execution |
|---|---|---|
| **Resource Isolation** | High (Fails fast, protecting threads and resources) | Low (Requests queue up, causing resource starvation) |
| **User Experience** | Clean (Returns cached values or fallback notices quickly) | Slow (Hangs client connections until timeout) |
| **System State Awareness**| Clear (Monitors metrics and error trends) | None (Blind execution) |
