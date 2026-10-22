# Adapter Pattern

## 1. Overview & Purpose
The Adapter pattern allows incompatible interfaces to collaborate. It acts as a wrapper that translates inputs and outputs between a client and an external system whose interface cannot be modified.

## 2. Backing App Scenarios
- **Payment Gateways**: Adapting external APIs (Stripe, PayPal, Adyen) to conform to a standard internal `PaymentProcessor` interface.
- **Log Sinks**: Wrapping various logger systems (e.g., standard console, Cloud Logging API, Datadog) under a unified logger API.
- **Legacy Migrations**: Wrapping an old database client to look like a new service interface while shifting query logic behind the scenes.

## 3. When to Apply
- When you need to integrate a third-party class or system, but its interface does not match the rest of your application code.
- When you want to decouple the core business logic from unstable or frequently changing third-party API contracts.

## 4. Drawbacks & Risks
- **Indirection Overhead**: Small performance cost due to parameter mapping and wrapper functions.
- **Leaky Abstractions**: If the third-party system exposes specific behavior (e.g., Stripe-specific card errors) that the adapter interface doesn't account for, callers may still receive unexpected exceptions.

## 5. Language-Agnostic Design

```
// Standard target interface
Interface PaymentProcessor {
    processCharge(amountInCents: Integer, currency: String): TransactionReceipt
}

// Incompatible external service SDK
Class StripeSDK {
    public createCharge(params: Map): StripeCharge {
        // Stripe-specific API network call
    }
}

// Adapter implementing the target interface
Class StripeAdapter implements PaymentProcessor {
    private stripeClient: StripeSDK

    public constructor(client: StripeSDK) {
        this.stripeClient = client
    }

    public processCharge(amountInCents: Integer, currency: String): TransactionReceipt {
        Map stripeParams = new Map()
        stripeParams.put("amount", amountInCents)
        stripeParams.put("curr", currency.lowercase())
        
        StripeCharge charge = this.stripeClient.createCharge(stripeParams)
        return new TransactionReceipt(charge.id, charge.status == "succeeded")
    }
}
```

## 6. Decision Matrix

| Dimension | Adapter Wrapping | Direct API Calls |
|---|---|---|
| **Vendor Lock-in** | Low (Switching vendors only requires writing a new adapter) | High (Requires changing caller files everywhere) |
| **Interface Control** | Complete (You control the internal signature) | None (Depends on vendor changes) |
| **Complexity** | Higher (Needs interface + implementation files) | Low (Straightforward, simple requests) |
