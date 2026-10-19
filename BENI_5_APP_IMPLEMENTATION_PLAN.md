# BENI Five-App Integration Plan

Audit date: 2026-10-19
Project: `beni/`

## Verified architecture and findings

| Requested app | Registered/routed today? | Existing state and source of truth |
|---|---|---|
| `Dukandaar` | Initially absent from `INSTALLED_APPS` and root URLs; now installed and routed as a facade. | Facade routes reuse the existing role-protected dashboard, shop/product/order views, shopkeeper wallet, and shop verification view. Shop ownership remains `Shop.owner`; no duplicate shop/product/order models or business logic were added. |
| `Repair` | Initially absent from `INSTALLED_APPS` and root URLs; now installed and routed as a facade. | Facade routes reuse customer, verified-worker, staff assignment, status, support, and private-image views in `bookings`. Existing booking model and authorization remain canonical. The customer booking category choices now match the repair categories already presented on the customer dashboard. |
| `Customer` | Initially absent from `INSTALLED_APPS` and root URLs; now installed and routed as a facade. | Facade routes reuse the existing customer dashboard/cart, checkout, and order views. Catalog, payments, and bookings remain in their existing canonical apps. |
| `billing` | Initially installed but had no root URLconf inclusion, models, migrations, forms, or workflow; now has a route and read-only order receipt. | The receipt derives from immutable order/item snapshots and payment fields already stored in `orders`/`payments`. It does not claim tax-invoice status and is visible only to the order customer, owning shopkeeper, or staff. No `billing_*` schema was added. |
| `reviews` | Initially installed but empty/unrouted; now routed and implemented. | `reviews.Review` and `reviews.0001_initial` are applied. Routes support customer submission, shop/worker review lists, and staff moderation. |

Uppercase folder names are distinct Python packages from lowercase apps. The
user confirmed that these must remain facades, so `Dukandaar`, `Repair`, and
`Customer` are now registered as empty-model apps and route to the same
lowercase views. Existing canonical URL names remain available. Existing
shop/product/order/booking migrations are recorded as applied on the inspected
database. `billing` still has no migrations. `reviews.0001_initial` was
generated after explicit approval, then applied after separate approval.

Existing UI assets include customer/shopkeeper/repair-worker/admin templates,
role-specific CSS and JavaScript, and repair/shop/product image assets. The
uppercase placeholders contain only app config, empty model/view/admin/test
modules, and an empty migrations package; they have no presentation or
business logic of their own.

## Implementation sequence

1. Preserve the existing lowercase apps as the sources of truth. Completed:
   registered the uppercase apps as facades and added routes that dispatch to
   canonical views without duplicating models or authorization.
2. Completed safe repair-catalog integration by sharing the dashboard's
   existing category catalog with the booking form; no field/database schema
   change was made.
3. Completed read-only order receipts derived from stored order snapshots,
   with customer/shop-owner/staff access checks and customer/shopkeeper
   navigation links.
4. Reviews code and the approved migration are applied. Persistent review
   submission, moderation, and ratings are enabled; full authenticated browser
   verification remains pending.
5. Repair invoices remain blocked because `RepairBooking` stores no price,
   quote, tax, invoice number, or payment record. Do not invent amounts.
6. Keep adding focused authorization/integration tests. Never create or apply
   migrations, or modify persistent data, without explicit approval.

## Current implementation status

- [x] Inspected settings, installed apps, root URLs, app configs, models,
  views, forms/URLconf/migration inventory, admin and tests for all five
  requested apps.
- [x] Inspected active shop/product/order/booking models and relevant routes,
  templates, role checks, upload/storage paths, static assets, and database
  migration/table state using read-only commands.
- [x] User confirmed that uppercase packages should be thin facades over the
  live lowercase domain apps, not replacements or duplicate systems.
- [x] Registered the uppercase facade apps and wired shopkeeper, customer, and
  repair URLs directly to canonical role-protected views.
- [x] Connected the existing repair categories to the booking form, retaining
  the existing free-text database field and booking lifecycle.
- [x] Added a printable digital order receipt based only on persisted order
  snapshots. Customer and owning shopkeeper order pages link to it; the
  receipt view returns 404 for an unrelated user.
- [x] Added tests proving facade routes resolve to canonical views and billing
  receipts are restricted to the order customer/shop owner (or staff); invoice
  content is rendered from stored order values.
- [x] After explicit approval, implemented persisted order/shop and repair
  worker reviews with delivered/completed ownership checks, one review per
  target, staff-only moderation, customer notifications, shopkeeper/worker
  review lists, and public display of moderated shop ratings.
- [x] Generated and SQL-reviewed `reviews.0001_initial.py` after explicit
  approval. After separate explicit approval, applied it to `beni_db` and
  verified the migration recorder, all fields, unique target constraints,
  MySQL DDL, and that the new table is empty.
- [ ] Implement repair invoices after an approved pricing/quote/payment model
  exists; current repair booking data has no billable amounts.
- [ ] Run a real authenticated browser/upload/payment workflow in a
  non-production environment; current verification is automated only.

### Reviews migration — generated, reviewed, and applied after approval

Reviews persist in one `reviews_review` table supporting both shop and
repair-worker reviews without duplicating review systems. The user separately
approved migration generation and application. It has been applied to
`beni_db`:

- `id`: auto-increment primary key.
- `customer_id`: non-null FK to `AUTH_USER_MODEL`, `PROTECT`.
- `order_id`: nullable, unique FK to `orders_order`, `PROTECT`.
- `booking_id`: nullable, unique FK to `bookings_repairbooking`, `PROTECT`.
- `rating`: non-null unsigned small integer, constrained to 1 through 5.
- `body`: non-null text, blank allowed, validated to at most 2,000 characters.
- `status`: non-null `varchar(10)`, choices `pending`, `published`, `rejected`;
  default `pending`.
- `moderator_id`: nullable FK to `AUTH_USER_MODEL`, `SET_NULL`.
- `moderation_note`: non-null text, blank allowed, max 2,000 characters.
- `created_at`, `updated_at`: non-null timestamps.
- Database check: exactly one of `order_id` or `booking_id` must be non-null.
- Unique nullable target FKs enforce at most one review per order or booking.
- Review target is derived from the order's shop or the completed booking's
  assigned worker. Services must verify customer ownership and delivered/
  completed status before submission; only staff may moderate.
- Migration dependencies: `orders.0002_checkoutattempt_payment_method`,
  `bookings.0003_repairbooking_locality_and_more`, and
  `migrations.swappable_dependency(settings.AUTH_USER_MODEL)`.

The applied `reviews.0001_initial` depends on the specified orders and
bookings migrations plus the swappable user model. SQL review confirms it
creates the single table with its two nullable unique target FKs, three user
FKs, rating/source check constraints, and moderation index. It does not
rewrite existing data; the table is empty and no historical reviews are
backfilled. Review text and moderation state are new personal data; access is
restricted to the customer, reviewed target owner, and staff, and publication
is staff-moderated. Read-only verification confirmed the created table is
empty and the recorder row is present.

### Repair invoice blocker

Existing repair booking rows contain no quote, charge, tax, or payment amount,
and the worker wallet is not linked to completed booking charges. A repair
invoice cannot be truthfully generated from current data. A possible exact
schema proposal, pending business-policy decisions, is:

- Create `billing_repairinvoice`: auto id; `booking_id` unique `PROTECT` FK
  to `bookings_repairbooking`; unique `invoice_number` varchar(40);
  `status` varchar(10) (`draft`, `issued`, `void`); `currency` char(3)
  default `INR`; `subtotal`, `tax_amount`, and `total` decimal(12,2);
  nullable `created_by_id` FK to `AUTH_USER_MODEL` with `SET_NULL`;
  nullable `issued_at`; `created_at` and `updated_at`; checks that amounts are
  nonnegative and total equals subtotal plus tax.
- Create `billing_repairinvoiceline`: auto id; `invoice_id` cascading FK with
  related name `lines`; description varchar(255); positive quantity;
  unit price and line total decimal(12,2); positive display position.
- Dependencies: `bookings.0003_repairbooking_locality_and_more` and
  `migrations.swappable_dependency(settings.AUTH_USER_MODEL)`.
- This creates two empty tables and does not rewrite existing bookings.
  Payment capture, refunds, quote acceptance, tax calculation, and shop/worker
  settlement are deliberately excluded until their policies are defined.

No invoice schema/model/migration has been generated. Before proceeding,
define who may issue a quote/invoice (worker or staff), whether the customer
must accept the quote, applicable tax treatment, and whether/how payments and
refunds are recorded. The current commerce/order invoice is a digital receipt,
not a tax invoice.

### Verification results for the current code-only phase

- Guarded in-memory SQLite tests: **159 passed** after all current code
  changes, including migration execution in the ephemeral test database. The
  focused review run passed **10 tests**; the prior integration run passed
  **27 tests** across bookings, dashboard, billing, and all three facades.
- `manage.py check`: passed.
- `makemigrations --check --dry-run`: no changes detected; the generated
  reviews model and migration are in sync.
- `git diff --check`: passed.
- `reviews.0001_initial` was applied to MySQL only after separate explicit
  approval; preflight verified the exact target `beni_db` and absent table.
  Postflight confirmed the table, columns, unique order/booking targets,
  empty row count, recorder entry, successful database check, and SQL output.
  No other application migration was run.
