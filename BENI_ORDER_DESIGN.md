# BENI Order Design and Migration Plan

Status: Design refinement only. No migrations, schema changes, or database writes were performed.

## 1. Audit summary and baseline constraints

This design is based on the current repo state as read-only inspected:
- Project settings in `beni/beni/settings.py` use Django + MySQL and a default database named `beni_db`.
- Installed apps include `accounts`, `customers`, `shops`, `products`, `orders`, `workers`, `bookings`, `billing`, `wallets`, `payments`, `reviews`, `notifications`, `verification`, and `dashboard`.
- The `shops` and `products` apps are the only ones that currently have migrations in the repo:
  - `shops.0001_initial`
  - `products.0001_initial`
- The `orders` app is present but empty; no `orders` models or migrations exist yet.
- Existing models currently in use are:
  - `Shop` in `shops/models.py`
  - `Product` in `products/models.py`
- Existing constraints and validation already enforce:
  - shop latitude/longitude range checks
  - product price >= 0.00
  - product stock_quantity >= 0
  - unique SKU per shop
- `showmigrations` confirms the current database has applied auth, admin, contenttypes, sessions, shops, and products migrations, but no orders data model exists yet.

This means the safest next phase is to design the order schema and checkout flow before any migration or schema change is approved.

## 2. Design goals

1. Support a multi-shop customer cart.
2. At checkout, create one independent order per shop.
3. Preserve historical product and pricing snapshots.
4. Prevent overselling and price manipulation.
5. Enforce customer and shop-owner authorization in every relevant view.
6. Preserve order history even if a shop, customer, or product record is later changed or removed.
7. Keep payment processing outside this phase; only create payment-status placeholders and a future integration hook.

## 3. Recommended checkout strategy: one order per shop

### Why this is safer than one order with mixed shops
A single order across multiple shops creates difficult fulfillment, inventory, payment allocation, and cancellation behavior. A safer normalized approach is:
- One customer cart can contain products across multiple shops.
- On checkout, the system creates one `Order` per shop.
- Each order contains only the items for that shop.
- Payment processing can later be applied per order or aggregated at the checkout level, but the underlying data model stays shop-scoped.

### Proposed flow
1. Customer adds products from different shops into the session cart.
2. Customer reaches checkout.
3. Server groups cart items by `shop_id`.
4. Server validates availability and current price for each product.
5. Server calculates item-level and order-level totals per shop.
6. Server locks relevant `Product` rows and reduces stock in a single atomic transaction.
7. Server creates one `Order` per shop and `OrderItem` records for each grouped set.
8. If one shop order fails during creation, the transaction is rolled back and no partial writes remain.

### Partial failure handling
If any shop-specific order cannot be created, the whole checkout should fail in one transaction. This avoids:
- some products shipped while others not
- inconsistent inventory deduction
- impossible refund scenarios

Recommended behavior:
- Validation is done first.
- `transaction.atomic()` starts.
- `select_for_update()` is used on all product rows involved.
- All orders and items are inserted within one transaction.
- If any step fails, `TransactionError` or validation exception triggers rollback.
- The cart remains unchanged for the customer unless the checkout is successfully committed.

## 4. Proposed database schema

### 4.1 Order model

```python
from decimal import Decimal
from django.conf import settings
from django.db import models


class Order(models.Model):
    STATUS_PENDING = 'pending'
    STATUS_CONFIRMED = 'confirmed'
    STATUS_PROCESSING = 'processing'
    STATUS_READY_FOR_PICKUP = 'ready_for_pickup'
    STATUS_OUT_FOR_DELIVERY = 'out_for_delivery'
    STATUS_DELIVERED = 'delivered'
    STATUS_CANCELLED = 'cancelled'
    STATUS_REFUNDED = 'refunded'

    PAYMENT_NOT_STARTED = 'not_started'
    PAYMENT_PENDING = 'pending'
    PAYMENT_PAID = 'paid'
    PAYMENT_FAILED = 'failed'
    PAYMENT_REFUNDED = 'refunded'

    ORDER_STATUS_CHOICES = [
        (STATUS_PENDING, 'Pending'),
        (STATUS_CONFIRMED, 'Confirmed'),
        (STATUS_PROCESSING, 'Processing'),
        (STATUS_READY_FOR_PICKUP, 'Ready for pickup'),
        (STATUS_OUT_FOR_DELIVERY, 'Out for delivery'),
        (STATUS_DELIVERED, 'Delivered'),
        (STATUS_CANCELLED, 'Cancelled'),
        (STATUS_REFUNDED, 'Refunded'),
    ]

    PAYMENT_STATUS_CHOICES = [
        (PAYMENT_NOT_STARTED, 'Not started'),
        (PAYMENT_PENDING, 'Pending'),
        (PAYMENT_PAID, 'Paid'),
        (PAYMENT_FAILED, 'Failed'),
        (PAYMENT_REFUNDED, 'Refunded'),
    ]

    customer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='orders',
        db_index=True,
    )
    shop = models.ForeignKey(
        'shops.Shop',
        on_delete=models.PROTECT,
        related_name='orders',
        db_index=True,
    )
    order_number = models.CharField(max_length=40, unique=True, db_index=True)
    status = models.CharField(
        max_length=24,
        choices=ORDER_STATUS_CHOICES,
        default=STATUS_PENDING,
        db_index=True,
    )
    payment_status = models.CharField(
        max_length=18,
        choices=PAYMENT_STATUS_CHOICES,
        default=PAYMENT_NOT_STARTED,
        db_index=True,
    )
    contact_name = models.CharField(max_length=150)
    contact_phone = models.CharField(max_length=30)
    address_line1 = models.CharField(max_length=255)
    city = models.CharField(max_length=100)
    state = models.CharField(max_length=100)
    postal_code = models.CharField(max_length=20)
    delivery_notes = models.TextField(blank=True, default='')
    subtotal = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    delivery_fee = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    service_fee = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    total = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)
    checkout_token = models.CharField(max_length=64, null=True, blank=True, unique=True, db_index=True)

    class Meta:
        ordering = ('-created_at', '-id')
        constraints = [
            models.CheckConstraint(
                condition=models.Q(total__gte=Decimal('0.00')),
                name='order_total_nonnegative',
            ),
            models.CheckConstraint(
                condition=models.Q(subtotal__gte=Decimal('0.00')),
                name='order_subtotal_nonnegative',
            ),
            models.CheckConstraint(
                condition=models.Q(delivery_fee__gte=Decimal('0.00')),
                name='order_delivery_fee_nonnegative',
            ),
            models.CheckConstraint(
                condition=models.Q(service_fee__gte=Decimal('0.00')),
                name='order_service_fee_nonnegative',
            ),
        ]
        indexes = [
            models.Index(fields=['customer', 'created_at']),
            models.Index(fields=['shop', 'status']),
            models.Index(fields=['status', 'payment_status']),
        ]

    def __str__(self):
        return self.order_number
```

### 4.2 OrderItem model

```python
from decimal import Decimal
from django.db import models
from django.db.models import Q


class OrderItem(models.Model):
    order = models.ForeignKey(
        'orders.Order',
        on_delete=models.CASCADE,
        related_name='items',
        db_index=True,
    )
    shop = models.ForeignKey(
        'shops.Shop',
        on_delete=models.PROTECT,
        related_name='order_items',
        db_index=True,
    )
    product = models.ForeignKey(
        'products.Product',
        on_delete=models.SET_NULL,
        related_name='order_items',
        null=True,
        blank=True,
        db_index=True,
    )
    product_name = models.CharField(max_length=150)
    product_category = models.CharField(max_length=100, blank=True, default='')
    product_sku = models.CharField(max_length=64, blank=True, null=True)
    unit_price = models.DecimalField(max_digits=12, decimal_places=2)
    quantity = models.PositiveIntegerField()
    line_total = models.DecimalField(max_digits=12, decimal_places=2)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ('order_id', 'id')
        constraints = [
            models.CheckConstraint(
                condition=models.Q(unit_price__gte=Decimal('0.00')),
                name='orderitem_unit_price_nonnegative',
            ),
            models.CheckConstraint(
                condition=models.Q(quantity__gt=0),
                name='orderitem_quantity_positive',
            ),
            models.CheckConstraint(
                condition=models.Q(line_total__gte=Decimal('0.00')),
                name='orderitem_line_total_nonnegative',
            ),
        ]
        indexes = [
            models.Index(fields=['order', 'shop']),
            models.Index(fields=['shop', 'product']),
        ]

    def save(self, *args, **kwargs):
        if self.line_total == Decimal('0.00') and self.quantity:
            self.line_total = self.unit_price * self.quantity
        super().save(*args, **kwargs)
```

### 4.3 Why these foreign keys are safe
- `Order.customer` uses `PROTECT` to prevent accidental deletion of a customer who already has order history.
- `Order.shop` uses `PROTECT` to keep shop order history intact.
- `OrderItem.product` uses `SET_NULL` to preserve historical snapshots if a product is deleted later.
- `OrderItem.shop` uses `PROTECT` to keep the origin shop attached to historical order lines.
- `product_name`, `product_category`, `product_sku`, `unit_price`, and `line_total` are stored as immutable snapshots so future price changes do not mutate historical order records.

## 5. Order status and payment status transitions

### Valid order status transitions

```text
pending -> confirmed -> processing -> ready_for_pickup -> out_for_delivery -> delivered
      \-> cancelled
confirmed -> cancelled
processing -> cancelled
ready_for_pickup -> cancelled
out_for_delivery -> delivered
out_for_delivery -> cancelled
```

Rules:
- `pending` is the initial state after cart validation but before confirmation.
- `confirmed` means the shop-specific order amount is accepted and inventory has been reserved.
- `cancelled` requires stock restoration and optional refund bookkeeping.
- `refunded` is a terminal state after refund processing.

### Valid payment status transitions

```text
not_started -> pending -> paid
not_started -> failed
pending -> paid
pending -> failed
paid -> refunded
failed -> pending
```

Rules:
- Payment is intentionally out of scope here; status values are placeholders for a later payment integration.
- Real payment webhooks should never directly change order totals; they only update `payment_status` and related gateway metadata in a dedicated payment model later.

## 6. Order number generation strategy

Recommended strategy:
- Generate a unique human-readable, database-safe order number at checkout time.
- Example pattern: `BENI-20261018-7F4C1A2B`
- Use `uuid.uuid4().hex[:8].upper()` or an incremented DB sequence combined with date.
- Store `order_number` as a unique `CharField` with a unique index.
- Guard generation inside a DB transaction and fallback to retry on collision.

Example generation logic:

```python
from datetime import datetime
import uuid

order_number = f"BENI-{datetime.utcnow():%Y%m%d}-{uuid.uuid4().hex[:8].upper()}"
```

This is unique enough for storefront checkout and avoids exposing integer IDs in a user-facing sequence.

## 7. Inventory safety and stock management

### Stock validation
Before any order is created:
1. Group cart items by shop.
2. Query product rows with `select_for_update()` for the relevant IDs.
3. Ensure each product:
   - exists
   - is active
   - belongs to a live shop
   - price matches the current DB price
   - quantity requested <= stock_quantity
4. If any product fails validation, abort checkout.

### Reservation / deduction strategy
For a transaction-safe design:
- Use `transaction.atomic()`.
- Lock the relevant product rows with `select_for_update()`. This prevents concurrent checkouts from racing over the same inventory.
- Deduct stock immediately after validation (`stock_quantity -= qty`) in the same transaction.
- This creates a reservation effect without an extra stock-table layer.

### Overselling prevention under concurrency
Because MySQL is used, row-level locking via `select_for_update()` prevents two concurrent checkouts from reading the same row and both seeing the same stock. The second transaction waits until the first commits and then reads the updated quantity. This prevents overselling in a safe, minimal design.

### Cancellation and restoration
If an order is cancelled or refunded:
- The stock restoration should happen in the same transaction as the order status update.
- Example:
  - `Order.status = 'cancelled'`
  - for each `OrderItem`, increment `Product.stock_quantity += item.quantity`
  - only if not already partially fulfilled or if refund logic is active
- To prevent double-restoration, guard with a status transition check and do not allow restoring stock twice.

### Duplicate submission prevention
Multiple protections should be combined:
- Session checkout token to prevent repeated POST for the same cart payload.
- Unique `checkout_token` or `client_order_key` in the DB.
- Idempotency check in the view before order creation.
- Server-side validation for cart contents and totals at every checkout.

## 8. Security rules for views and authorization

Every order-related route must enforce the following:

### Customer rules
- The user must be authenticated.
- The user must be a customer (not staff, shopkeeper, or repair worker).
- Cart items may only be created/updated for valid active products.
- Checkout totals must be rederived on the server based on current product records.
- The customer may not modify `unit_price`, `subtotal`, `total`, or `payment_status` in a request body.

### Shopkeeper rules
- Shopkeeper must only see orders connected to shops they own.
- Query pattern:
  - `shop_ids = request.user.shops.values_list('id', flat=True)`
  - `Order.objects.filter(shop_id__in=shop_ids)` or `OrderItem.objects.filter(shop_id__in=shop_ids)`
- Do not expose order IDs or order details for unrelated shops.
- Do not allow a shop owner to change another shop’s order status or update totals.

### Order detail access control
- Customer route must resolve the order by `customer=request.user` and `order_number`.
- Shopkeeper route must resolve the order by a join on `OrderItem.shop__owner=request.user` or `Order.shop__owner=request.user`.
- No order should ever be retrieved by a raw request parameter without ownership enforcement.

### Payment safety
This phase intentionally does not process real payments. The system must not treat a redirect or browser success page as payment delivery. A payment model inserted later should require:
- gateway verification
- webhook signature validation
- idempotency keys
- no direct trust of client-side redirect state

## 9. Proposed migration dependency graph

Current state (read-only audited):
- `auth` migrations already exist
- `shops.0001_initial` exists
- `products.0001_initial` exists
- `orders` has no migrations yet

Proposed order migration order:
1. `orders.0001_initial`
2. `orders.0002_add_order_status_constraints` (if needed for stricter transitions)
3. Later `payments.0001_initial` and `billing.0001_initial` in separate payment/billing workstreams

Dependency graph for the order phase:

```text
auth
 └─ shops.0001_initial
     └─ products.0001_initial
         └─ orders.0001_initial
```

This is the safe migration dependency sequence because the order model depends on existing `Shop` and `Product` tables and the Django auth model.

### Migration sequence from a safe implementation perspective
1. Create `Order` and `OrderItem` models in `orders/models.py`.
2. Add model-level indexing and constraints.
3. Add migration `orders.0001_initial` only after explicit approval.
4. Run a focused migration plan and validate the schema before checkout implementation continues.

## 10. Proposed `orders` app model file structure

The current `orders` app is empty and should remain empty until the migration is explicitly approved. Proposed files after approval:
- `orders/models.py` — `Order`, `OrderItem`
- `orders/forms.py` — checkout and order status forms
- `orders/views.py` — customer checkout, order detail, shopkeeper order management
- `orders/urls.py` — customer and shopkeeper routes
- `orders/tests.py` — order creation, stock deduction, authorization, and status tests
- `orders/migrations/0001_initial.py` — to be generated only after approval

## 11. Rollback and recovery considerations

### Safe rollback plan
If an order checkout fails after starting a transaction:
- rollback the transaction
- leave the cart unchanged
- keep no orphan order rows or partially created items
- preserve stock quantities

### Recovery from interrupted transactions
- The app should not assume a browser redirect confirms a completed payment.
- For the order phase without payment integration, order creation must be idempotent and safe to retry.
- A checkout token can be saved in the session and database to prevent duplicate processing.

### Data integrity safeguards
- `on_delete=PROTECT` prevents losing historical records when a customer or shop is deleted.
- `SET_NULL` on product reference preserves historical snapshot data.
- Unique order numbers avoid accidental duplicates.
- Decimal totals prevent floating-point precision errors.

## 12. Refined checkout workflow

### Cart composition
Cart entries remain keyed by `product_id` and `shop_id` and are persisted in the session, but the final accepted order is built from grouped order lines.

### Checkout steps
1. Load customer session cart.
2. Group items by shop.
3. Validate each product:
   - exists and active
   - belongs to an active shop
   - price equals live DB price
   - requested quantity <= stock
4. Start `transaction.atomic()`.
5. `select_for_update()` on product rows.
6. Create `Order` per shop.
7. Create `OrderItem` rows with snapshots.
8. Decrease each product stock value.
9. Save `Order` totals.
10. Clear the session cart only after DB commit succeeds.
11. Redirect to order detail.

### If any step fails
- rollback transaction
- return a human-readable error message to the user
- do not mutate cart or stock

## 13. Test plan

The following tests should be added after approval and before migration execution:

1. Multi-shop cart grouping test
   - cart with two shops
   - checkout creates two orders
   - each order only contains the matching shop's items

2. Inventory race test
   - simulate two concurrent checkouts for the same product
   - ensure final stock is not negative and total quantity is correct

3. Price tampering rejection
   - modify cart item price in the session
   - ensure server rejects checkout and leaves the cart intact

4. Customer authorization test
   - customer cannot access or mutate another customer’s order

5. Shopkeeper authorization test
   - shopkeeper can only view orders from their shops
   - shopkeeper cannot access other shops’ orders

6. Duplicate submission test
   - repeated checkout with same checkout token should be rejected

7. Cancellation restoration test
   - cancelling an order restores stock according to item quantities

8. Historical snapshot test
   - product price changes after order creation should not affect previously placed order totals

9. Migration validation test
   - after migration approval, confirm all constraints, indexes, and foreign keys are created as expected

## 14. Final recommendation

The safest, most maintainable design is:
- keep the cart as a session-based collection for this stage
- plan one `Order` per shop, each containing `OrderItem` snapshots
- preserve historical snapshots and enforce stock deduction within a single transactional checkout
- keep payment as a separate later integration
- wait for explicit approval before any migration file or schema application

This design fits the current repository state, respects the existing `Shop` and `Product` models, keeps data integrity consistent with the project’s current baseline, and avoids risking the working database state.
