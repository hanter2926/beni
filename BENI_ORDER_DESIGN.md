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
    checkout_attempt = models.ForeignKey(
        'orders.CheckoutAttempt',
        on_delete=models.PROTECT,
        related_name='orders',
    )

    class Meta:
        ordering = ('-created_at', '-id')
        constraints = [
            models.UniqueConstraint(
                fields=['checkout_attempt', 'shop'],
                name='order_attempt_shop_unique',
            ),
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
            models.Index(fields=['order', 'product']),
        ]
```

### 4.3 CheckoutAttempt model and idempotency

Use a persistent `CheckoutAttempt` as the parent record for one customer submission. Proposed fields:

```python
class CheckoutAttempt(models.Model):
    customer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='checkout_attempts',
    )
    token = models.UUIDField(unique=True, editable=False)
    cart_digest = models.CharField(max_length=64)
    created_at = models.DateTimeField(auto_now_add=True)
```

`Order.checkout_attempt` points to this record, and `UniqueConstraint(checkout_attempt, shop)` allows one order per shop for the attempt while preventing a retry from creating a second order for that same shop. The token identifies the whole multi-shop submission, not an individual `Order`; it must not be a unique field on `Order`, since one attempt may create several shop orders.

Token lifecycle for the existing session cart:
1. On the first checkout page load for a non-empty cart, create an opaque random token in the session and bind it to a server-computed canonical cart digest. Reuse it for subsequent checkout page loads while the cart digest is unchanged; do not rotate it on ordinary refresh.
2. Every add, update, or remove cart action invalidates the active, uncommitted token. The next checkout load issues a new token bound to the changed cart. A POST with an old token or a digest mismatch is rejected as stale and must not create or alter orders.
3. At POST, the server rebuilds and validates the cart from database product/shop data, recomputes the canonical digest, and checks that the submitted token belongs to the authenticated customer and this exact cart state. Client-supplied totals or product data are not trusted.
4. Inside one `transaction.atomic()` block, create the `CheckoutAttempt`, then every per-shop `Order`, `OrderItem`, and stock deduction. The unique token and `(checkout_attempt, shop)` constraint are the durable concurrency/idempotency guard. If any validation or write fails, rollback removes all attempt/order/item rows and stock changes; keep the same session token and cart so a retry may safely reuse them.
5. On a replay after a successful commit, find the existing attempt for that token and customer, verify the cart digest, and return its existing orders rather than inserting more. A repeated POST and a browser refresh must never create another order set. If the session still contains the exact submitted cart because the response was lost, clear it only after the existing committed attempt is confirmed. If the cart has since changed, do not clear the changed cart.
6. After a new checkout commits successfully, clear the session cart and active token. Keep a completed receipt reference/token long enough for a stale POST or refresh to redirect to the already-created order set; never delete the persistent attempt as a way to make the token reusable.

The current implementation uses a session cart signature and stores orders/signatures in the session. That only limits repeat submissions within that browser session, keeps no durable idempotency record, and cannot coordinate concurrent requests or devices. It should not be treated as an adequate substitute for the persistent attempt key and database uniqueness above.

Trade-off: `CheckoutAttempt` is an additional table beyond the initially proposed `Order` and `OrderItem`, but it gives the multi-shop checkout one durable idempotency identity and a single result set. A per-shop derived token stored on each `Order` would avoid that table but complicates lookup, customer binding, and recovery of the complete multi-shop result. The parent attempt is the recommended design.

### 4.4 OrderItem shop consistency

Do not add `OrderItem.shop` in the proposed schema. The current `Product` model has a required foreign key to `Shop`; each `Order` already has a required foreign key to its one shop. Keeping another shop foreign key on every line duplicates data and creates a consistency condition that a normal foreign key cannot enforce: MySQL cannot ensure that `OrderItem.shop_id = Order.shop_id` using independent foreign keys alone.

At checkout, the service must lock and load the products, group them by their current `product.shop_id`, create one `Order` per group, and reject the entire checkout unless every product assigned to an order has `product.shop_id == order.shop_id`. Create line items only from this validated grouping. Shopkeeper authorization and listing then use `Order.shop`, not an item-level shop field.

Trade-off: removing the redundant field avoids contradictory shop IDs and saves a foreign key/index. Historical shop ownership is taken from the protected `Order.shop` plus the immutable order snapshots. The `OrderItem.product` foreign key remains `PROTECT`; if products can be reassigned to another shop later, the current Product relation will no longer describe their historical shop, so the order's shop and snapshots remain authoritative. A future product reassignment policy should disallow reassignment after order history or explicitly preserve additional historical provenance; do not change the existing Product model as part of this design-only decision.

### 4.5 Product deletion and historical retention policy
The design requires historical order items to remain intact even if a product or shop is later removed or deactivated.

Consistent policy choice:
- `Order.customer` uses `PROTECT`.
- `Order.shop` uses `PROTECT`.
- `OrderItem.product` uses `PROTECT`, not `SET_NULL`, because a null product reference would weaken the historical record and make it harder to audit the exact purchased item.

Trade-offs:
- `PROTECT` preserves history and prevents accidental data loss, but prevents deleting a product or shop that still has order history. That is safer for auditability and is the correct default for immutable order records.
- `SET_NULL` would allow historical order lines to lose the product relationship, which undermines the audit trail and makes the order less useful for later customer support and dispute workflows.
- Soft deletion (`is_active = False` or a `deleted_at` flag) is a useful operational control for a live storefront, but it is not a replacement for historical integrity. The existing `Product` model does not implement soft deletion, and order history should remain intact even if a product is deactivated later.

The snapshot fields (`product_name`, `product_category`, `product_sku`, `unit_price`, and `line_total`) and `Order.shop` remain authoritative for order history. This makes future product edits or price changes non-destructive to historical records. `PROTECT` means shops with historical orders cannot be deleted; deactivation is the supported operational path.

## 5. Order status and payment status transitions

### Valid order status transitions

```text
pending -> confirmed -> processing -> ready_for_pickup -> out_for_delivery -> delivered
      \-> cancelled
confirmed -> cancelled
```

For this phase, cancellation is allowed only before fulfillment starts (`pending` or `confirmed`). Cancellation after entering `processing`, `ready_for_pickup`, or `out_for_delivery` is rejected. Partial cancellation and partial stock restoration are deferred until a reliable fulfillment ledger exists.

Rules:
- `pending` is the initial state after cart validation but before confirmation.
- `confirmed` means the shop-specific order amount is accepted and inventory has been reserved.
- `cancelled` requires full stock restoration, performed once and atomically, and is not a payment refund.
- `refunded` is a payment outcome and must not itself restore inventory.
- Model-level `choices` and constraints only describe allowed values; they do not enforce valid transition sequences. Transition validation must be enforced in the checkout/order service layer and in any mutation view or form that changes an order status.
- Partial cancellation remains out of scope until fulfillment quantities/events can be recorded and audited. Status transitions and cancellation authorization must be enforced by the order service and object-scoped views, not by `choices` alone.

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
For a full cancellation before fulfillment starts, stock restoration must be part of the same atomic database transaction as the status change:
- `transaction.atomic()` begins.
- The order row is locked or selected with a status transition check.
- The system verifies that the order is in a cancellable state (`pending`/`confirmed` for this phase).
- For each `OrderItem`, the corresponding `Product` row is locked with `select_for_update()` and `stock_quantity += item.quantity` is applied in the same transaction.
- Set the order status to `cancelled` in the same transaction only after all restoration operations succeed. A payment refund is a separate payment concern and must not itself restore stock.
- If fulfillment has started or the order is partially fulfilled, cancellation and partial restoration are rejected in this phase. Partial cancellation remains deferred until a reliable fulfillment ledger or equivalent per-line fulfilled quantity/event design exists.

The order-row lock serializes concurrent cancellation attempts. The service must re-check the status after obtaining the lock and restore stock only during the valid transition to `cancelled`; a replay sees the terminal status and performs no second restoration. If any operation fails, the whole transaction rolls back.

### Duplicate submission prevention
Use the persistent `CheckoutAttempt` lifecycle defined in section 4.3. Session signatures alone are not durable and do not protect concurrent or cross-device submissions. Bind a token to the authenticated customer and canonical cart digest; persist the attempt and all per-shop orders in one transaction; replay an already committed token by returning its existing orders; retain the session cart/token on transaction failure; and clear the cart only after commit succeeds.

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
- Shopkeeper route must resolve the order by `shop__owner=request.user`; `OrderItem` has no separate shop FK.
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

The live database observed in the latest read-only audit is `beni_db` on MySQL 8.0.46. It contains standard Django auth/contenttypes/admin/session tables, but does not contain `shops_shop` or `products_product`. Its migration recorder includes the built-in auth/contenttypes/admin/session migrations but not `shops.0001_initial` or `products.0001_initial`. Thus the repo graph and live database state are different: the shop/product migrations exist in source but are pending in this database.

The future `orders.0001_initial` should directly depend on both:
- `('products', '0001_initial')`, for Product and Shop references through the existing product dependency chain
- `migrations.swappable_dependency(settings.AUTH_USER_MODEL)`, because `Order` and `CheckoutAttempt` directly reference the configured user model

The direct auth dependency is required even though the products migration transitively depends on shops and auth. No Orders migration currently exists in the repo.

### Safe future order migration plan
If the design is approved, the first migration should create `CheckoutAttempt`, `Order`, and `OrderItem` together:
1. `orders.0001_initial`

It should use the direct dependencies stated above. Because the observed database has pending shop/product migrations, any later application of `orders.0001_initial` may also apply those prerequisites. Review the actual migration plan and obtain separate explicit database approval before applying anything.

### Migration sequence from a safe implementation perspective
1. Finalize and approve the `CheckoutAttempt`, `Order`, and `OrderItem` schema.
2. Create those models in `orders/models.py`.
2. Add model-level indexing, checks, and unique constraints.
3. Generate `orders.0001_initial` only after explicit approval.
4. Run only a focused migration and validate the resulting schema before checkout implementation continues.

## 10. Proposed `orders` app model file structure

The current `orders` app is empty and should remain empty until the migration is explicitly approved. Proposed files after approval:
- `orders/models.py` — `CheckoutAttempt`, `Order`, `OrderItem`
- `orders/services.py` — checkout idempotency, transaction, stock, and cancellation operations
- `orders/forms.py` — checkout and order status forms
- `orders/views.py` — customer checkout, order detail, shopkeeper order management
- `orders/urls.py` — customer and shopkeeper routes
- `orders/tests.py` — order creation, stock deduction, authorization, and status tests
- `orders/migrations/0001_initial.py` — to be generated only after approval

Integrate the order views through the existing customer/shopkeeper route modules where practical, preserving current route names (`customers:checkout`, `customers:orders`, `customers:order_detail`, and `shopkeeper_orders`) to avoid breaking templates and links.

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
- A checkout token is kept in the session for the active cart and persisted through `CheckoutAttempt` only as part of the all-or-nothing checkout transaction.
- The cart is cleared only after the transaction commits successfully; if any exception occurs, the cart remains available for retry.

### Data integrity safeguards
- `on_delete=PROTECT` prevents losing historical records when a customer, shop, product, or checkout attempt with related order history is deleted.
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
7. Validate the session token and canonical cart digest; resolve or create the persistent `CheckoutAttempt`.
8. Create `Order` rows for each shop in the same transaction, each attached to the attempt.
9. Create `OrderItem` rows with immutable snapshots for each product line.
10. Decrease each product `stock_quantity` by the ordered amount.
11. Save the order totals and commit the transaction.
12. Clear the session cart only after a successful commit.
13. Redirect to the customer order detail page.

### Multi-shop and rollback behavior
- The checkout is all-or-nothing across all shops. If any shop-specific order fails validation or insert, the transaction is rolled back.
- This prevents partial fulfillment and avoids inconsistent stock deductions across shops.
- Duplicate submission is blocked by the unique attempt token and unique `(checkout_attempt, shop)` constraint; a committed replay returns the existing orders.
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
