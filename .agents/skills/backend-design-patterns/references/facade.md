# Facade Pattern

## 1. Overview & Purpose
The Facade pattern provides a simplified, high-level interface to a complex subsystem of classes, library calls, or microservices. It makes the subsystem easier to use and reduces coupling between caller components and internal operations.

## 2. Backing App Scenarios
- **Order Checkout Orchestrator**: Simplifying checkout by wrapping Inventory Check, Payment Charging, Shipping Order creation, and Email Notification systems behind a single `CheckoutFacade`.
- **Media Transcoder Subsystem**: Bundling video slicing, audio extraction, metadata writing, and S3 uploading operations under a single `VideoUploadFacade.transcode(file)`.

## 3. When to Apply
- When you want to expose a simple, readable API to clients or controllers instead of forcing them to coordinate multiple internal services.
- When you need to isolate layer boundaries so callers are unaware of internal dependency wiring.

## 4. Drawbacks & Risks
- **God Class risk**: The facade can grow into an oversized orchestrator containing too much domain logic instead of delegation.
- **Hidden Customization**: High-level simplifications can limit the client's ability to tweak specific sub-step parameters if required.

## 5. Language-Agnostic Design

```
Class OrderFacade {
    private billingService: BillingService
    private shippingService: ShippingService
    private inventoryService: InventoryService

    public constructor(bill: BillingService, ship: ShippingService, inv: InventoryService) {
        this.billingService = bill
        this.shippingService = ship
        this.inventoryService = inv
    }

    public placeOrder(cart: Cart, user: User): OrderResult {
        if (!this.inventoryService.verifyStock(cart)) {
            return OrderResult.fail("OutOfStock")
        }
        Receipt receipt = this.billingService.charge(user, cart.total)
        TrackingCode track = this.shippingService.scheduleShipment(user, cart)
        return OrderResult.success(receipt.id, track.id)
    }
}
```

## 6. Decision Matrix

| Dimension | Facade Orchestration | Direct Client Coordination |
|---|---|---|
| **Subsystem Coupling** | Low (Subsystem can evolve independently) | High (Client breaks if any sub-service interface changes) |
| **Simplicity** | High (Single client call) | Low (Client manages multiple imports/parameters) |
| **Control** | Standardized (Encapsulated workflow rules) | Granular (Client controls every sub-step) |
