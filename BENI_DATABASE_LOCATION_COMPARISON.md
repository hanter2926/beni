# BENI SQL Dump vs Current Project: Database and Location Comparison

**Audit date:** 2026-10-21
**Project:** `C:\Users\Vikram\Documents\Repositories\beni\beni`
**Dump inspected:** [`beni_db_before_orders.sql`](./beni/beni_db_before_orders.sql), described as a MySQL 8.0.46 `beni_db` dump from 2026-10-18.

## Scope and safety

This was a read-only source comparison. The SQL file was inspected as text: table names/column names were read from `CREATE TABLE` statements and migration names from the `django_migrations` insert statement. No SQL from the dump was executed. In particular, no `DROP`, `DELETE`, `TRUNCATE`, or data-bearing `INSERT` statements were executed, and row data/password hashes/session data were not inspected or printed. No connection was made to the configured database. No code, database, migration, dependency, or other project file was changed except this report.

## Executive summary

The supplied dump is an older, pre-orders schema snapshot, not evidence of the current configured database. It contains 12 tables: Django core tables plus `products_product` and `shops_shop`. Its `django_migrations` recorder has the initial `shops.0001_initial` and `products.0001_initial` entries, but no later BENI app migrations.

The current project has many additional registered apps, models, admin registrations, and migration files. In particular, current source defines bookings, checkout/orders, payments, reviews, wallets, profile, shop gallery/bank details, and product gallery models that are not represented by tables in this dump. The dump's `shops_shop` does include latitude/longitude, but it predates the later shop image and bank/photo additions in the current source.

**Current configured database state is not established by this comparison.** [`beni/settings.py`](./beni/beni/settings.py) configures MySQL using environment values, which were not read; no connection or database introspection was performed. [`BENI_DATABASE_AUDIT.md`](./beni/BENI_DATABASE_AUDIT.md) and [`BENI_CURRENT_STATUS_AUDIT.md`](./BENI_CURRENT_STATUS_AUDIT.md) contain earlier claims of read-only checks on a later database state. Those are prior reports, not a fresh verification in this task, and must not be conflated with the 2026-10-18 dump.

## Current Django project and Admin

[`beni/settings.py`](./beni/beni/settings.py) installs Django Admin and the project apps `accounts`, `Dukandaar`, `Repair`, `Customer`, `customers`, `shops`, `products`, `orders`, `workers`, `bookings`, `billing`, `wallets`, `payments`, `reviews`, `notifications`, `verification`, `dashboard`, and `repair_guides`.

Current Admin registration source includes:

- Accounts/Profile: [`accounts/admin.py`](./beni/accounts/admin.py)
- Bookings/support requests: [`bookings/admin.py`](./beni/bookings/admin.py)
- Orders/checkout attempts: [`orders/admin.py`](./beni/orders/admin.py)
- Payment attempts/webhook events/cancellation requests: [`payments/admin.py`](./beni/payments/admin.py)
- Products: [`products/admin.py`](./beni/products/admin.py)
- Repair guide/Q&A moderation/content models: [`repair_guides/admin.py`](./beni/repair_guides/admin.py)
- Reviews: [`reviews/admin.py`](./beni/reviews/admin.py)
- Shops: [`shops/admin.py`](./beni/shops/admin.py)
- Wallet accounts/ledger entries: [`wallets/admin.py`](./beni/wallets/admin.py)

Admin registration proves only that code registers a model with Django Admin; it does not prove the backing table exists in the supplied dump or the currently configured database. The uppercase facade apps `Customer`, `Dukandaar`, and `Repair` do not define the corresponding customer/shop/booking data models; the canonical models live in lower-case/domain apps.

## Dump inventory and recorder

Tables found in `CREATE TABLE` statements:

`auth_group`, `auth_group_permissions`, `auth_permission`, `auth_user`, `auth_user_groups`, `auth_user_user_permissions`, `django_admin_log`, `django_content_type`, `django_migrations`, `django_session`, `products_product`, `shops_shop`.

Project-app migration entries recorded in the supplied dump:

- `shops.0001_initial`
- `products.0001_initial`

The remaining recorder entries are Django core migrations (`contenttypes`, `auth`, `admin`, `sessions`). The dump does not record migrations for accounts, bookings, orders, payments, reviews, wallets, or the other current domain apps.

For `shops_shop`, the dump contains the initial address fields and `latitude`/`longitude`. It does not contain the current model's `logo_image`/`cover_image` columns; the dump also has no `shops_shopphoto` or `shops_shopbankdetails` tables. Those later additions are defined by `shops.0002_shop_cover_image_shop_logo_image` and `shops.0003_shopbankdetails_shopphoto`, neither recorded in this dump.

For `products_product`, the dump contains the base product table, but no `products_productimage` table; current project migration `products.0002_alter_product_image_productimage` creates that gallery model and is not recorded in the dump.

## Feature comparison

“Dump state” refers only to the supplied SQL snapshot. “Current database” refers to the environment configured by current settings and is marked unverified unless a fresh check is performed. A migration file's presence does not imply its application.

| Feature | Model in current code | Migration file(s) | Evidence in supplied dump | Current status | Next action |
|---|---|---|---|---|---|
| Customer reusable addresses | **No address model.** `Profile` has no address/location fields; checkout orders store delivery-address snapshots. See [`accounts/models.py`](./beni/accounts/models.py), [`orders/models.py`](./beni/orders/models.py), and the empty [`customers/models.py`](./beni/customers/models.py). | `accounts.0001_initial` and `accounts.0002_profile_alternate_phone_profile_phone_and_more` exist; none creates a customer address model. `orders.0001_initial` creates order address snapshots. | No `accounts_profile`, `orders_order`, or customer-address table. No accounts/orders migration recorded. | **Absent in dump; reusable address absent from code; current database not checked.** | Decide whether reusable addresses are required. If yes, approve an address model/table and migrations separately; do not infer customer addresses from order snapshots. |
| Shop address and coordinates | `shops.Shop` includes postal address, optional `latitude`/`longitude`, validators and DB range checks. See [`shops/models.py`](./beni/shops/models.py). | `shops.0001_initial.py` defines address/coordinates; `shops.0002...` adds logo/cover; `shops.0003...` adds photo/bank models. | `shops_shop` exists and `shops.0001_initial` is recorded. Dump schema contains address and coordinates. It omits current image columns and the photo/bank tables; migrations 0002/0003 are not recorded. | **Base shop location present in dump; dump schema is behind current source; current database not checked.** | If comparing the live instance, perform an approved read-only schema/recorder check and compare expected shop columns/tables with current models. Do not apply migrations as part of that check. |
| Shop photos and bank details | `ShopPhoto` and `ShopBankDetails` exist in [`shops/models.py`](./beni/shops/models.py). | `shops.0003_shopbankdetails_shopphoto.py` exists, depends on 0002. | Neither corresponding table is present; 0003 is not recorded. | **Models/migrations exist; absent in dump; current database not checked.** | Confirm table/recorder state with read-only introspection before any deployment decision. |
| Worker service area | No structured worker-area model. `workers/models.py` is empty; profile `service_details` is free text. | `workers` contains only `migrations/__init__.py`; no worker-area migration. | No worker/service-area table or migration entry. | **Not implemented in code or dump; current database not checked.** | Define area semantics and separately approve a model/migration before implementation. |
| Worker live GPS | No worker live-position model or GPS field in current source. | No worker live-location migration. | No worker location table or migration entry. | **Not implemented in code or dump; current database not checked.** | Do not collect or store live location without explicit consent, access/retention policy, and approved schema. |
| Repair bookings and service address | `bookings.RepairBooking` stores customer, optional assigned worker, text `service_address` and locality; it has no coordinates. See [`bookings/models.py`](./beni/bookings/models.py). | `bookings.0001_initial`, `0002_repairbookingimage`, `0003_repairbooking_locality_and_more` exist. | No `bookings_repairbooking`, assignment, support, or image tables; no bookings migration recorded. | **Model/migrations exist; absent in dump; current database not checked.** | Read-only check on the actual configured DB if current booking-table state must be confirmed. |
| Orders and checkout address snapshots | `orders.Order` stores customer/shop FKs and delivery address snapshot; `CheckoutAttempt` and `OrderItem` are also modeled. See [`orders/models.py`](./beni/orders/models.py). | `orders.0001_initial` and `orders.0002_checkoutattempt_payment_method` exist. | No order/checkout/item tables; no orders migration recorded. | **Models/migrations exist; absent in dump; current database not checked.** | Verify current database through approved read-only schema inspection; do not restore the dump over it. |
| Payments | `PaymentAttempt`, `WebhookEvent`, and `OrderCancellationRequest` exist. See [`payments/models.py`](./beni/payments/models.py). | `payments.0001_initial.py` exists and depends on orders migration 0002. | No payment tables; no payments migration recorded. | **Models/migration exist; absent in dump; current database not checked.** | Confirm actual current payment tables/recorder only via read-only database check when authorized. |
| Reviews | `reviews.Review` can relate to exactly one order or repair booking. See [`reviews/models.py`](./beni/reviews/models.py). | `reviews.0001_initial.py` exists. | No `reviews_review` table and no reviews migration recorded. | **Model/migration exist; absent in dump; current database not checked.** | Read-only verify current review table and migration recorder if required. |
| Wallets | `WalletAccount` and immutable `WalletLedgerEntry` exist. See [`wallets/models.py`](./beni/wallets/models.py). | `wallets.0001_initial.py` exists. | No wallet tables and no wallets migration recorded. | **Models/migration exist; absent in dump; current database not checked.** | Read-only verify actual current wallet tables before any schema change or deployment claim. |
| Accounts/Profile | `accounts.Profile` exists and stores user/profile image, phone, verification, and service details, but no address. See [`accounts/models.py`](./beni/accounts/models.py). | `accounts.0001_initial.py` and `0002...py` exist. | No `accounts_profile` table and no accounts migration recorded. | **Model/migrations exist; absent in dump; current database not checked.** | Compare current DB's profile table/columns using approved read-only inspection. |
| Product gallery (relevant dump/source discrepancy) | `ProductImage` exists beside `Product`. See [`products/models.py`](./beni/products/models.py). | `products.0001_initial.py`, `products.0002_alter_product_image_productimage.py` exist. | `products_product` exists and 0001 is recorded; `products_productimage` is absent and 0002 not recorded. | **Base product present in dump; gallery addition absent in dump; current database not checked.** | Verify product table columns and gallery table on current DB before drawing a deployment conclusion. |
| Notifications, verification, repair guides, billing, and other project apps | Current models are defined for notifications, verification, and repair guides; `billing` has no persisted domain model. | Migration files exist for notifications, verification, and repair guides; billing has only the empty migration package. | No tables or app migration entries for these domains in dump. | **Mixed model/migration presence in code; absent in dump; current database not checked.** | Treat each app independently in an approved current-schema comparison; do not infer from Admin modules or screenshots. |

## Explicit discrepancies

1. **The dump is not the current checked-in project schema.** It is named `beni_db_before_orders.sql`, and its recorder has only the initial shops/products app migrations. The current tree includes later shop/product migrations and complete bookings, orders, payments, reviews, wallets, profiles, notifications, verification, and repair-guide model/migration code.
2. **Shop coordinate presence is confirmed only in the dump and source definition.** `shops_shop.latitude` and `shops_shop.longitude` appear in the dump and `shops.0001_initial`; their presence in today's configured DB was not independently queried.
3. **Dump shop/product schemas lag later checked-in migrations.** Shop logo/cover fields and shop photo/bank tables are omitted; product gallery table is omitted. The dump migration recorder lacks the corresponding 0002/0003 records.
4. **The Admin screenshots are not evidence of physical tables.** Registrations in current `admin.py` files account for the additional Admin modules. They prove source registration only, not that all tables existed in the dump or exist in the currently configured DB.
5. **The current configured database is a separate evidence question.** `settings.py` uses MySQL and environment-provided connection values. No credentials were read and no database connection was made. Existing [`BENI_DATABASE_AUDIT.md`](./beni/BENI_DATABASE_AUDIT.md) documents later read-only checks and claims multiple migrations/tables were verified on `beni_db`; this comparison has not repeated those checks. The supplied 2026-10-18 dump cannot establish the 2026-10-21 database state.

## Smallest safe next step

If the goal is to reconcile the current deployment, first authorize a **read-only** inspection of the configured database that retrieves only (a) table names, (b) column names/types for expected tables, and (c) app/migration names from `django_migrations`. Do not run migrations or restore/execute this dump. Compare that output to the checked-in models/migrations and record any missing tables/columns; decide on schema changes only after reviewing the exact discrepancy and deployment target.

## Summary: confirmed vs not confirmed

- **Confirmed from the dump text:** MySQL 8.0.46 metadata; the listed 12 tables; `shops_shop` and `products_product` schema; shop latitude/longitude columns; migration recorder entries including `shops.0001_initial` and `products.0001_initial`; absence from the dump of the listed current domain tables.
- **Confirmed from current project source:** installed apps and MySQL configuration pattern; current models, migration files, and Admin registrations; customer address is not a reusable address model; shop coordinates exist in source; worker service area/live GPS are not modeled; bookings/orders/payments/reviews/wallet models and migrations exist in source.
- **Requires a read-only check of the current configured database:** whether any expected current table/column exists today and which migrations are currently recorded there. This task intentionally did not connect to that database.
