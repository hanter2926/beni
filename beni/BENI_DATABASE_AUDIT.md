# BENI Database Schema Audit

## Current recheck — 2026-10-19

This recheck supersedes the historical “Current state after approved
migrations” and verification statements below where they differ. The initial
comparison was read-only against the configured MySQL database `beni_db`.
The user-approved account and booking operations below were applied
individually and verified. The payment migrations described below were
subsequently generated, explicitly approved for application, applied in
dependency order, and verified on `beni_db`.

- `accounts.0001_initial`, `bookings.0001_initial`,
  `bookings.0002_repairbookingimage`, `bookings.0003_repairbooking_locality_and_more`,
  `accounts.0002_profile_alternate_phone_profile_phone_and_more`, `shops.0002`,
  `verification.0001_initial`, `wallets.0001_initial`, and the previously
  applied product/order/notification migrations are now recorded as applied.
- Before approval, `accounts_profile` lacked `phone`, `alternate_phone`,
  `phone_verified`, and `service_details`; `bookings_repairbooking` lacked
  `locality` and `preferred_contact_method`; and
  `bookings_bookingsupportrequest` was absent. After both migrations,
  read-only introspection confirmed all installed model tables and columns
  match, and both expected support-request indexes are present.
- The project virtualenv reports Python 3.14.6 / Django 5.2.18. Its database
  system check passed; `makemigrations --check --dry-run` reported no changes.
  The earlier full 115-test suite and focused booking/verification run passed
  against guarded in-memory SQLite, not MySQL. After payment implementation,
  all 131 tests passed against guarded in-memory SQLite with provider calls
  mocked.
- `orders.0002_checkoutattempt_payment_method` and `payments.0001_initial`
  were generated and SQL-reviewed, then applied after explicit approval.
  Read-only verification confirmed both recorder entries, the
  `orders_checkoutattempt.payment_method` column, all three payment tables,
  required columns, unique fields, and the payment-attempt index.
- After migration application, `manage.py check --database default` passed,
  `showmigrations orders payments` marks all three migrations applied, and
  `makemigrations --check --dry-run` reports no changes.
- For the 2026-10-19 shopkeeper workflow, generated and SQL-reviewed
  `shops.0003_shopbankdetails_shopphoto` and
  `verification.0002_alter_verificationapplication_status_and_more` after
  explicit approval. They created empty shop photo/bank details tables and
  added the `info_needed` verification choice to the two existing status
  fields (SQL no-ops). Both migration-recorder entries and affected schema
  were verified on `beni_db`; no existing rows were rewritten or deleted.
  The full 141-test suite passed on guarded in-memory SQLite.
- One earlier test-isolation attempt in this recheck configured SQLite too
  late and attempted to create `test_beni_db`; MySQL rejected the create
  because that database already exists, and the runner exited at its
  confirmation prompt. No deletion, recreation, migration, or test-data
  operation occurred in that attempt. The successful test runs set SQLite
  before Django setup and asserted `:memory:` before starting.
- The listener on port 8000 and fresh project-virtualenv server on port 8001
  both returned HTTP 200 for `/accounts/login/`. After the migrations, the
  fresh server also returned HTTP 200 for `/catalog/` and HTTP 302 for the
  anonymous protected order, repair, and profile routes. No startup traceback
  was observed. The original refused-connection event was not reproducible.

### Shopkeeper schema extensions — applied after approval

The user explicitly approved applying these migrations to `beni_db`. Each was
applied individually, with checks before proceeding to the next migration.

| Migration | Dependency | Operations / affected schema | Data impact and risk |
|---|---|---|---|
| `shops.0003_shopbankdetails_shopphoto` | `shops.0002_shop_cover_image_shop_logo_image` (applied) | Create `shops_shopbankdetails` with one-to-one `shop_id`, account holder name, account number, IFSC code, and timestamps. Create `shops_shopphoto` with `shop_id`, image path, alt text, ordering, and creation time. | Both tables start empty. No existing shop rows are changed. Account details are owner-scoped in the application and not field-encrypted by this migration; application/database access must remain restricted. |
| `verification.0002_alter_verificationapplication_status_and_more` | `verification.0001_initial` (applied) | Add `info_needed` (“Additional information required”) to `status` choices on `verification_verificationapplication` and `verification_verificationdecision`. Existing `varchar(12)` columns fit the 11-character value; `sqlmigrate` emitted no-op operations. | Existing statuses are unchanged. No data is rewritten or deleted. New status values become available only after application code is deployed. |

`showmigrations shops verification` reports both as applied on `beni_db`.
Read-only introspection confirmed the two new shop tables, required columns,
and the two verification `status` columns remain `varchar(12)`. The migration
changes no existing records. The 141-test run also exercised migrations on
guarded in-memory SQLite. No migration was faked.

### Payment implementation checkpoint

Razorpay checkout is implemented as one platform payment per multi-shop
checkout. Provider order creation, server-side checkout-signature verification,
provider payment status/amount/currency verification, captured-payment webhook
handling, and webhook event idempotency are covered with mocked provider tests.
Cash on delivery remains available and is marked paid when the shopkeeper
records delivery. Paid-order cancellation creates a staff-review request;
approving it restores reserved stock but does not issue a refund. Shop payouts
and refunds remain manual.

No Razorpay credentials were read or printed, no provider request or hosted
checkout was made, and no live webhook was delivered. Set
`RAZORPAY_KEY_ID`, `RAZORPAY_KEY_SECRET`, and `RAZORPAY_WEBHOOK_SECRET` only in
the private environment before a separate sandbox validation. The configured
webhook endpoint is `/payments/webhook/razorpay/`.

#### Approved payment migration plan and execution

| Migration | Dependency | Exact operations / affected tables | Data impact and risk |
|---|---|---|---|
| `orders.0002_checkoutattempt_payment_method` | `orders.0001_initial` (already applied) | Add `orders_checkoutattempt.payment_method`, `varchar(12)`, choices `cod` / `razorpay`, default `cod`. | Existing checkout-attempt rows receive COD as the additive-column default. No orders, payment status, inventory, or other business data are rewritten or deleted. MySQL requires an `ALTER TABLE` and may briefly lock the table. |
| `payments.0001_initial` | `orders.0002_checkoutattempt_payment_method` and swappable auth-user dependency | Create `payments_paymentattempt` (checkout FK, amount/currency/status, unique nullable provider order/payment IDs, timestamps, checkout/created index); `payments_webhookevent` (unique event ID, event type, timestamp); and `payments_ordercancellationrequest` (one-to-one order FK, reason/status, optional staff reviewer/notes, requested/reviewed timestamps). | New tables start empty; no existing order or payment row is copied or deleted. MySQL DDL can hold metadata/table locks. Reversing this migration drops these newly created tables and any records subsequently written to them. |

The files were inspected with `sqlmigrate`. After separate explicit approval,
the following commands were run individually, checking state after each:

1. `.\venv\Scripts\python.exe manage.py migrate orders 0002_checkoutattempt_payment_method`
2. Verified the migration recorder and `orders_checkoutattempt.payment_method`
   column.
3. `.\venv\Scripts\python.exe manage.py migrate payments 0001_initial`
4. Verified the migration recorder and all three payment tables, required
   columns, unique constraints, and payment-attempt index.

Both commands completed with `OK`. No fake migration, data reset, row deletion,
or live Razorpay request was performed.

### Approved migration operations and data-risk record

| Migration | Dependency | Operations / affected schema | Data risk |
|---|---|---|---|
| `accounts.0002_profile_alternate_phone_profile_phone_and_more` | `accounts.0001_initial` (applied) | On `accounts_profile`, add `alternate_phone` and `phone` (`CharField`, max 30, blank), `phone_verified` (`BooleanField`, default false), and `service_details` (`TextField`, blank). | Existing rows receive blank strings and `false`; no existing values are rewritten or deleted. |
| `bookings.0003_repairbooking_locality_and_more` | `bookings.0002_repairbookingimage` (applied) and the swappable auth-user dependency | On `bookings_repairbooking`, add `locality` (max 120, blank/default empty) and `preferred_contact_method` (phone/WhatsApp, default phone); alter `status` from max length 20 to 24 with the current choices; create `bookings_bookingsupportrequest` with booking/reporter `PROTECT` foreign keys, request type, description, open/resolved status, creation time, and `(booking, created_at)` / `(status, created_at)` indexes. | Existing booking values are retained; the new columns use their declared defaults. The new support table starts empty. No data-deletion or data-copy operation exists. MySQL DDL can hold metadata/table locks and may not be transactionally reversible; use a verified backup and inspect state after each migration before continuing. |

The user explicitly approved these exact operations. The controlled commands
were executed in this order:

1. `.\venv\Scripts\python.exe manage.py migrate accounts 0002_profile_alternate_phone_profile_phone_and_more`
2. Verified `accounts.0002` and all four profile columns before continuing.
3. `.\venv\Scripts\python.exe manage.py migrate bookings 0003_repairbooking_locality_and_more`
4. Verified `bookings.0003`, both booking columns, the support-request table,
   and its two indexes.

Both commands completed with `OK`. No data-deletion or data-copy operation was
run; no remaining approval is needed for these two completed migrations.

## Scope and safety

The original comparison of Django models, migration recorder, and live MySQL
schema was read-only. After explicit user approval, the reviewed pending
migrations were applied to the primary MySQL database. The bookings index
name was shortened consistently in the model and its unapplied initial
migration, and a wallet initial migration was generated from the models after
repository history inspection found no prior wallet migration file. Secrets
were not read out or reported.

The active connection resolved from `beni.settings` is MySQL database
`beni_db`, host `127.0.0.1`, port `3306`, alias `default`. `INSTALLED_APPS`
contains the project apps and standard Django apps listed below.
`DATABASE_ROUTERS` is empty. Model table names use Django's default naming;
no project `db_table` or app-label override was found. The project `.env`
contains the expected database variable names, and `settings.py` loads it
before reading required database settings. This confirms the current runtime
target, not which database a previous server process was using.

The project virtual environment reports Django 5.2.18, matching the inspected
requirements snapshot. The server already listening on port 8000 is using
system Python with Django 6.0.8. Both environments passed Django checks after
the index-name correction; the version difference should be reconciled when
restarting the server using the project virtual environment.

During verification, an initial test command intended to use SQLite did not
replace Django's already-cached MySQL connection. Django therefore removed
the existing `test_beni_db`, recreated it, ran tests, then removed it. This
was not the primary `beni_db`; read-only verification afterward confirmed
`beni_db` still has its existing tables and contents were not queried. The
test database `test_beni_db` is currently absent. Subsequent tests explicitly
asserted and used in-memory SQLite.

## Current state after approved migrations

The user-approved `manage.py migrate --noinput` completed successfully. It
applied `accounts.0001_initial`, `bookings.0001_initial`,
`bookings.0002_repairbookingimage`,
`products.0002_alter_product_image_productimage`,
`shops.0002_shop_cover_image_shop_logo_image`, `verification.0001_initial`,
and `wallets.0001_initial`. Read-only introspection confirmed the previously
missing account, booking, gallery, verification, and wallet tables, and the
`shops_shop.logo_image` and `shops_shop.cover_image` columns. The notification
table remains present. All migrations are now applied.

`/accounts/login/` and `/catalog/` each returned HTTP 200 from the running
server. Anonymous requests to `/customer/orders/`, `/repairs/`, and
`/accounts/profile/` returned HTTP 302 to login as intended. Authenticated
live MySQL rendering for those three endpoints was not directly exercised.

## Original findings for reported errors

The following table records causes before migrations were applied. See
“Approved migration plan” for current schema status and runtime checks.

| URL / reported error | Model or query | Evidence and root cause | Risk / approval |
|---|---|---|---|
| `/catalog/` — missing `verification_verificationapplication` | `products.public_catalog` → `public_products()` → `marketable_products()` → `eligible_shop_verifications()` | The catalog intentionally includes only active products from active shops whose verification is approved, phone is verified, and Aadhaar or PAN is verified. This is an existing marketplace rule, not an unnecessary catalog query. The verification table is absent and `verification.0001_initial` is unapplied; that migration depends on unapplied `shops.0002`. Do not bypass the verification query. | High. Requires approved schema migration(s). |
| `/customer/orders/` — unknown `shops_shop.logo_image` | `orders.views.order_history` uses `select_related('shop')`; order templates consume shop data | The current `shops_shop` table exists but lacks both `logo_image` and `cover_image`, which are added by unapplied `shops.0002_shop_cover_image_shop_logo_image`. This is schema drift caused by an unapplied existing migration, not an incorrect field or table name. | High. Requires approval to add two columns. |
| `/repairs/` — missing `bookings_repairbooking` | Booking views/models | `RepairBooking` and `BookingAssignmentEvent` tables are absent. `bookings.0001_initial` and dependent `bookings.0002_repairbookingimage` are unapplied. | High. Requires approval to create booking tables and indexes. |
| `/accounts/profile/` — missing `accounts_profile` | `accounts.views.profile` reads `Profile` | `accounts_profile` is absent and `accounts.0001_initial` is unapplied. The view's optional `.filter(...).first()` still requires the table to exist; suppressing the database error would hide the schema defect. | High. Requires approval to create the profile table. |
| Previous customer dashboard — missing `notifications_notification` | `notifications.Notification` | The current database contains this table with all model columns; its `notifications.0001_initial` migration is recorded as applied. The prior error is not reproducible from the present schema evidence. It may predate the migration application or have come from a different runtime connection, but the available evidence cannot establish which. | Low for the current schema; investigate the old process/connection if it recurs. |

The missing tables/columns were not hidden by code fallbacks. Code-level
defects found during implementation were fixed: the bookings index name now
fits Django's backend limit, and verification submission notifications now
link staff to the admin review inbox.

The prior `models.E034` blocker was resolved by renaming the index to
`booking_customer_created_idx` in both `bookings/models.py` and
`bookings/migrations/0001_initial.py`. This migration is unapplied on the
observed database snapshot before approval; the database-aware check passed
after the correction, and the migration was subsequently applied.

## Pre-migration model-to-database inventory

The following inventory is the pre-migration snapshot. Column lists below are
database column names as reported by Django model
metadata and MySQL introspection. A missing table means all expected columns
are absent. For existing tables, “matches” means all model columns are
present; this column comparison does not independently certify indexes,
constraints, defaults, or data integrity.

| App / model | Expected table and columns | Live table / columns | Migration state | Risk / recommendation |
|---|---|---|---|---|
| `accounts.Profile` | `accounts_profile`: `id`, `image`, `user_id` | Table absent | `accounts.0001_initial` unapplied | High — create table after approval. |
| `bookings.RepairBooking` | `bookings_repairbooking`: `id`, `customer_id`, `assigned_worker_id`, `service_category`, `problem_description`, `service_address`, `preferred_at`, `status`, `created_at`, `updated_at` | Table absent | `bookings.0001_initial` unapplied | High — create table and declared indexes after approval. |
| `bookings.BookingAssignmentEvent` | `bookings_bookingassignmentevent`: `id`, `booking_id`, `assigned_worker_id`, `previous_worker_id`, `assigned_by_id`, `created_at` | Table absent | `bookings.0001_initial` unapplied | High — create table and declared indexes after approval. |
| `bookings.RepairBookingImage` | `bookings_repairbookingimage`: `id`, `booking_id`, `image`, `image_type`, `uploaded_by_id`, `created_at` | Table absent | `bookings.0002_repairbookingimage` unapplied | High — create private booking-image table and index after approval. |
| `shops.Shop` | `shops_shop`: `id`, `owner_id`, `name`, `description`, `category`, `phone`, `address`, `city`, `state`, `postal_code`, `latitude`, `longitude`, `opening_hours`, `logo_image`, `cover_image`, `is_active`, `created_at`, `updated_at` | Table exists; all columns match except `logo_image`, `cover_image` are absent | `shops.0001_initial` applied; `shops.0002_shop_cover_image_shop_logo_image` unapplied | High — add the two image columns after approval. |
| `products.Product` | `products_product`: `id`, `shop_id`, `name`, `description`, `category`, `sku`, `price`, `stock_quantity`, `image`, `is_active`, `created_at`, `updated_at` | Table exists; columns match | `products.0001_initial` applied | Low — no column drift found. |
| `products.ProductImage` | `products_productimage`: `id`, `product_id`, `image`, `alt_text`, `sort_order`, `created_at` | Table absent | `products.0002_alter_product_image_productimage` unapplied | Medium — create gallery table after approval. This migration also changes the `Product.image` upload path in migration state; that `upload_to` change does not itself require a database column alteration. |
| `orders.CheckoutAttempt` | `orders_checkoutattempt`: `id`, `token`, `cart_digest`, `created_at`, `customer_id` | Table exists; columns match | `orders.0001_initial` applied | Low — no column drift found. |
| `orders.Order` | `orders_order`: `id`, `order_number`, `status`, `payment_status`, `contact_name`, `contact_phone`, `address_line1`, `city`, `state`, `postal_code`, `delivery_notes`, `subtotal`, `delivery_fee`, `service_fee`, `total`, `created_at`, `updated_at`, `checkout_attempt_id`, `customer_id`, `shop_id` | Table exists; columns match | `orders.0001_initial` applied | Low — no column drift found. |
| `orders.OrderItem` | `orders_orderitem`: `id`, `product_name`, `product_category`, `product_sku`, `unit_price`, `quantity`, `line_total`, `created_at`, `order_id`, `product_id` | Table exists; columns match | `orders.0001_initial` applied | Low — no column drift found. |
| `notifications.Notification` | `notifications_notification`: `id`, `event_key`, `title`, `message`, `destination_url`, `created_at`, `read_at`, `recipient_id` | Table exists; columns match | `notifications.0001_initial` applied | Low — no current schema gap. |
| `verification.VerificationApplication` | `verification_verificationapplication`: `id`, `applicant_id`, `shop_id`, `worker_application_key`, `application_type`, `status`, `phone_status`, `aadhaar_status`, `pan_status`, `bank_status`, `face_status`, `decision_reason`, `reviewed_by_id`, `created_at`, `updated_at` | Table absent | `verification.0001_initial` unapplied; depends on `shops.0002` | High — create after approval and after its shop dependency. |
| `verification.VerificationDecision` | `verification_verificationdecision`: `id`, `application_id`, `reviewer_id`, `status`, `phone_status`, `aadhaar_status`, `pan_status`, `bank_status`, `face_status`, `reason`, `created_at` | Table absent | `verification.0001_initial` unapplied | High — created by the same verification migration. |
| `verification.VerificationDocument` | `verification_verificationdocument`: `id`, `application_id`, `file`, `document_type`, `uploaded_by_id`, `uploaded_at` | Table absent | `verification.0001_initial` unapplied | High — created by the same migration; file storage is configured private. |
| `wallets.WalletAccount` | `wallets_walletaccount`: `id`, `owner_id`, `role`, `created_at` | Table absent | `wallets.0001_initial` generated from current models, unapplied | High — creates table and `wallet_owner_role_unique` after approval. |
| `wallets.WalletLedgerEntry` | `wallets_walletledgerentry`: `id`, `wallet_id`, `entry_type`, `amount_minor`, `reference_key`, `actor_id`, `created_at` | Table absent | `wallets.0001_initial` generated from current models, unapplied | High — creates table, two indexes, unique reference and nonzero amount constraints after approval. |

At the time of the original schema comparison, the project apps
`billing`, `customers`, `dashboard`, `payments`, `reviews`, and `workers`
had no model tables to compare. Since then, `payments` gained the three models
and routed workflows described in the current payment checkpoint above; its
tables are now present in `beni_db`. `billing` and `reviews` remain
unimplemented; the `workers` app still has no models, views, or URL routes of
its own (worker workflow code is in bookings and verification).

## Remaining current database tables

All standard Django tables are present, and their columns match the installed
Django model metadata: `auth_group`, `auth_group_permissions`,
`auth_permission`, `auth_user`, `auth_user_groups`,
`auth_user_user_permissions`, `django_admin_log`, `django_content_type`,
`django_migrations`, and `django_session`.

The complete live table set is those standard tables plus the present project
tables `notifications_notification`, `orders_checkoutattempt`, `orders_order`,
`orders_orderitem`, `products_product`, and `shops_shop`. No other live
project-app tables were found.

## Pre-migration recorder and operation review

Project migrations recorded as applied before the follow-up migration run:

- `notifications.0001_initial`
- `orders.0001_initial`
- `products.0001_initial`
- `shops.0001_initial`

Project migrations that were pending before the follow-up migration run:

- `accounts.0001_initial`
- `bookings.0001_initial`
- `bookings.0002_repairbookingimage` (depends on `bookings.0001_initial`)
- `products.0002_alter_product_image_productimage` (depends on `products.0001_initial`)
- `shops.0002_shop_cover_image_shop_logo_image` (depends on `shops.0001_initial`)
- `verification.0001_initial` (depends on `shops.0002_shop_cover_image_shop_logo_image`)
- `wallets.0001_initial` (generated from current wallet models; depends on the swappable user model)

Those migrations contained model/table creation, two shop image-field
additions, and declared indexes. No `RunSQL`, `RunPython`, fake
migration, or data-deletion operation was found in these migrations.
Read-only plans confirmed: accounts creates `Profile`; shops adds the two
image fields; bookings creates `RepairBooking`, `BookingAssignmentEvent`,
their indexes, and `RepairBookingImage`; products alters the `image` field
state and creates `ProductImage`; verification creates its three models. The
bookings index name was shortened to `booking_customer_created_idx` in both
the model and initial migration before the approved migration run.

Repository history contains no earlier wallet migration. A new
`wallets.0001_initial` was generated from the current `WalletAccount` and
`WalletLedgerEntry` models and applied during the approved migration run. Other
installed model apps without migration files have no models and therefore no
detected migration gap.

## Approved migration plan

The plan below was reviewed and explicitly approved. It creates missing
tables and constraints/indexes and adds two shop image columns; it contains no
`RunSQL`, `RunPython`, fake migration, or data-deletion operation.

1. `python manage.py migrate accounts 0001_initial` — create
   `accounts_profile`.
2. `python manage.py migrate shops 0002_shop_cover_image_shop_logo_image` —
   add `logo_image` and `cover_image` to `shops_shop`.
3. `python manage.py migrate bookings 0002_repairbookingimage` — create
   `bookings_repairbooking`, `bookings_bookingassignmentevent`, and
   `bookings_repairbookingimage` (plus their declared indexes).
4. `python manage.py migrate products 0002_alter_product_image_productimage`
   — create `products_productimage`; update `Product.image` upload-path
   migration state.
5. `python manage.py migrate verification 0001_initial` — create the three
   verification tables. The target includes the prerequisite shop-image
   migration if it has not already been applied.
6. `python manage.py migrate wallets 0001_initial` — create
   `wallets_walletaccount` and `wallets_walletledgerentry`, their foreign keys,
   uniqueness/check constraints, and indexes.

The plan was rechecked immediately before execution and applied with
`venv\\Scripts\\python.exe manage.py migrate --noinput`. All seven project
migrations in that earlier, approved set completed with `OK`. The subsequently generated and explicitly approved
`orders.0002_checkoutattempt_payment_method` and `payments.0001_initial` were
applied afterward and are verified in the current recheck above.

## Verification performed

- `venv\\Scripts\\python.exe manage.py check --database default` — passed
  before and after the approved migrations; the system-Python server
  environment also passed its database-aware check.
- `venv\\Scripts\\python.exe manage.py showmigrations --list` — confirmed all
  project migrations are applied except apps without migrations/models.
- `venv\\Scripts\\python.exe manage.py makemigrations --check --dry-run` —
  passed (`No changes detected`).
- `venv\\Scripts\\python.exe manage.py migrate --noinput` — all seven
  approved migrations completed with `OK`.
- Full tests — ran against asserted in-memory SQLite; all 112 tests passed.
  The cart test setup now retains one session-store instance when saving, and
  the ineligible-product test consumes the add-to-cart redirect before
  asserting the later cart response.
- Template static-reference scan — all 132 literal references resolved; no
  missing static files found.
- Browser/HTTP verification — `/accounts/login/` and `/catalog/` returned
  HTTP 200 on the server listening at `127.0.0.1:8000`; protected pages
  redirected anonymous requests to login.
- Read-only Django/MySQL introspection — confirmed the active database name,
  full live table set, columns, expected model tables/columns, and applied
  migration recorder rows. It did not read database records.

The login and public catalog URLs were verified. The authenticated
database-backed `/customer/orders/`, `/repairs/`, and `/accounts/profile/`
pages were not directly tested against live accounts; the isolated full test
suite passed after the schema was applied.
