# BENI Database Schema Audit

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

The project apps `billing`, `customers`, `dashboard`, `payments`, `reviews`,
and `workers` currently define no Django models and have no migration files.
Their current app directories therefore have no expected app model tables to
compare. This is not evidence of lost schema for those apps; it reflects their
current code state. Billing, payments, and reviews have placeholder
views/tests and no routed workflows; the workers app has no models, views, or
URL routes of its own (worker workflow code is in bookings and verification).
Real payment, bill, and review flows require business/schema decisions and
migrations; no fake transaction behavior was added.

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
migrations completed with `OK`; they are no longer pending on the observed
database.

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
