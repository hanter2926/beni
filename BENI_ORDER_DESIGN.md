# BENI Order Design and Migration Plan

Status: Design refinement only. No migrations, schema changes, or database writes were performed.

## 1. Audit summary and baseline constraints

This design is based on the current repo state as read-only inspected:
- Project settings in `beni/beni/settings.py` use Django + MySQL and a default database named `beni_db`.
- Installed apps include `accounts`, `customers`, `shops`, `products`, `orders`, `workers`, `bookings`, `billing`, `wallets`, `payments`, `reviews`, `notifications`, `verification`, and `dashboard`.
- The migration files in the repo confirm the following dependency chain:
  - `shops/migrations/0001_initial.py` depends on `settings.AUTH_USER_MODEL`
  - `products/migrations/0001_initial.py` depends on `('shops', '0001_initial')`
  - there is no `orders` migration file at all in the repo yet
- A read-only database check on `beni_db` confirms that only the Django `auth_user` table currently exists; `shops_shop` and `products_product` are not present yet in the live database.
- Existing models currently in use are:
  - `Shop` in `shops/models.py`
  - `Product` in `products/models.py`
- Existing constraints and validation already enforce:
  - shop latitude/longitude range checks
  - product price >= 0.00
  - product stock_quantity >= 0
  - unique SKU per shop
- Django 6.0.8 and MySQL 8.0.46 support the planned `CheckConstraint`, `UniqueConstraint`, `Index`, and row-level locking patterns used by `select_for_update()` on InnoDB tables.

This means the safest next phase is to design the order schema and checkout flow before any migration or schema change is approved, and the actual migration graph must remain limited to the files that already exist in the repo until the user approves a new `orders` migration.

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
        on_delete=models.PROTECT,
        related_name='order_items',
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
```

### 4.3 Product deletion and historical retention policy
The design requires historical order items to remain intact even if a product or shop is later removed or deactivated.

Consistent policy choice:
- `Order.customer` uses `PROTECT`.
- `Order.shop` uses `PROTECT`.
- `OrderItem.shop` uses `PROTECT`.
- `OrderItem.product` uses `PROTECT`, not `SET_NULL`, because a null product reference would weaken the historical record and make it harder to audit the exact purchased item.

Trade-offs:
- `PROTECT` preserves history and prevents accidental data loss, but prevents deleting a product or shop that still has order history. That is safer for auditability and is the correct default for immutable order records.
- `SET_NULL` would allow historical order lines to lose the product relationship, which undermines the audit trail and makes the order less useful for later customer support and dispute workflows.
- Soft deletion (`is_active = False` or a `deleted_at` flag) is a useful operational control for a live storefront, but it is not a replacement for historical integrity. The existing `Product` model does not implement soft deletion, and order history should remain intact even if a product is deactivated later.

The snapshot fields (`product_name`, `product_category`, `product_sku`, `unit_price`, and `line_total`) remain the authoritative source-of-truth for the order history. This makes future product edits, price changes, or shop deletions non-destructive to historical records.

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
- Model-level `choices` and constraints only describe allowed values; they do not enforce valid transition sequences. Transition validation must be enforced in the checkout/order service layer and in any mutation view or form that changes an order status.
- For the initial design, cancellation should be allowed only while the order is still unfulfilled (for example `pending` or `confirmed`). Once the order has entered `processing` or a later fulfillment state, cancellation must require an explicit fulfillment/refund workflow that restores only the unfulfilled quantity or is otherwise explicitly blocked.

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
If an order is cancelled or refunded, stock restoration must be part of the same atomic database transaction as the status change:
- `transaction.atomic()` begins.
- The order row is locked or selected with a status transition check.
- The system verifies that the order is in a cancellable state (`pending`/`confirmed` for the initial design) and that stock has not already been restored for this cancellation event.
- For each `OrderItem`, the corresponding `Product` row is locked with `select_for_update()` and `stock_quantity += item.quantity` is applied in the same transaction.
- The order status changes to `cancelled` or `refunded` only after the stock restoration succeeds.
- If the order is partially fulfilled, the design should not silently restore full stock. For the initial implementation, the order should be blocked from cancellation once fulfillment has started. A future fulfillment ledger or `fulfilled_quantity` field is required before a partial cancellation model can be safely introduced.

This pattern prevents double-restoration because the atomic transaction re-reads the order state and only permits restoration once; if a second cancellation request arrives concurrently, it will either serialize behind the lock or fail the transition check.

### Duplicate submission prevention
Multiple protections should be combined:
- A session checkout token or cart hash to prevent repeated POSTs for the same cart payload.
- A unique `checkout_token` or `client_order_key` on the order model, stored and checked before insertion.
- An idempotency guard in the view/service before order creation.
- Server-side validation for cart contents and totals at every checkout.
- The session cart is cleared only after the transaction commits successfully; if any validation or database error occurs, the cart remains intact and the user can retry with the same order payload.

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

## 9. Verified migration dependency graph

Current state supported by the actual migration files and a read-only database inspection:
- `django.contrib.auth` migrations are present in the project and in the live database.
- `shops/migrations/0001_initial.py` exists and depends on `settings.AUTH_USER_MODEL`.
- `products/migrations/0001_initial.py` exists and depends on `('shops', '0001_initial')`.
- `orders` has no migration files yet, and the live `beni_db` does not currently contain `shops_shop` or `products_product` tables.

The exact dependency graph supported by the repo is therefore:

```text
auth
 └─ shops.0001_initial
     └─ products.0001_initial
```

There is no repo-backed `orders.0001_initial` dependency chain yet, and no `orders.0002_*` migration should be assumed until an actual `orders` migration is approved and generated.

### Safe future order migration plan
If the design is approved, the first and only order migration in the current phase should be:
1. `orders.0001_initial`

It should depend on `products` and, indirectly, on `shops` and `auth` through the existing migration graph. No second migration should be planned as part of this design review unless a later, explicit design change requires it.

### Migration sequence from a safe implementation perspective
1. Create `Order` and `OrderItem` models in `orders/models.py`.
2. Add model-level indexing, checks, and unique constraints.
3. Generate `orders.0001_initial` only after explicit approval.
4. Run only a focused migration and validate the resulting schema before checkout implementation continues.

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
- leave the customer on the same checkout page or return a validation error without clearing session state

This matches the selected `PROTECT` deletion policy: historical order rows are never silently orphaned or partially purged.

### Recovery from interrupted transactions
- The app should not assume a browser redirect confirms a completed payment.
- For the order phase without payment integration, order creation must be idempotent and safe to retry.
- A checkout token can be saved in the session and database to prevent duplicate processing.
- The cart is cleared only after the transaction commits successfully; if any exception occurs, the cart remains available for retry.

### Data integrity safeguards
- `on_delete=PROTECT` prevents losing historical records when a customer, shop, or product with legacy order history is deleted.
- The snapshot fields preserve the exact historical purchase data even if product pricing or naming changes later.
- Unique order numbers avoid accidental duplicates.
- Decimal totals prevent floating-point precision errors.
- `select_for_update()` and atomic transactions prevent concurrent oversell and duplicate status changes when stock and order state are updated together.

## 12. Refined checkout workflow

### Cart composition
Cart entries remain keyed by `product_id` and `shop_id` and are persisted in the session, but the final accepted order is built from grouped order lines.

### Checkout steps
1. Load the customer session cart.
2. Group cart entries by `shop_id` to create one order per shop.
3. Revalidate each product from the database:
   - exists and active
   - belongs to an active shop
   - price still matches the current DB price
   - requested quantity <= stock_quantity
4. Start `transaction.atomic()`.
5. Lock each affected `Product` row with `select_for_update()`.
6. Re-check the latest database values within the transaction and reject the entire checkout if any line is invalid.
7. Generate a unique order number and a unique `checkout_token` if not already provided.
8. Create `Order` rows for each shop in the same transaction.
9. Create `OrderItem` rows with immutable snapshots for each product line.
10. Decrease each product `stock_quantity` by the ordered amount.
11. Save the order totals and commit the transaction.
12. Clear the session cart only after a successful commit.
13. Redirect to the customer order detail page.

### Multi-shop and rollback behavior
- The checkout is all-or-nothing across all shops. If any shop-specific order fails validation or insert, the transaction is rolled back.
- This prevents partial fulfillment and avoids inconsistent stock deductions across shops.
- Duplicate submission is blocked by a unique checkout token and an idempotency check before inserting any order rows.
- If the transaction fails, the view returns a user-facing error and leaves the session cart intact for retry.

### If any step fails
- rollback the transaction
- return a human-readable error message to the user
- do not mutate cart or stock
- do not clear the session cart

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
