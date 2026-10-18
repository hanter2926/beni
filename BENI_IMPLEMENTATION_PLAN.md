# BENI Implementation Checklist

Inventory date: 2026-10-18  
Scope: read-only repository, configuration, route, and database inventory. No application code, dependencies, migrations, or database data/schema were changed as part of this inventory. The only intended deliverable is this checklist.

## 1. Executive summary

BENI has a functional Django authentication/role foundation, customer-facing product catalog, shopkeeper shop and product CRUD, and a session-backed cart/checkout/order prototype. The latter is not a persistent order system: orders remain in the browser session, stock is checked but never deducted, checkout is not atomic, and shopkeeper order display is read-only. Existing auth, role-isolation, shop, product, catalog, cart, and session-order behaviors have focused tests in source, but no tests were run in this inventory because the configured database/test database isolation has not been approved.

Orders, payments, billing, bookings, workers, verification, wallets, reviews, and notifications are mostly empty Django app scaffolds. Repair-worker and admin areas currently have presentation-only dashboards. The uppercase `Customer`, `Repair`, and `Dukandaar` directories are not installed or routed and contain scaffolds; retain them until their future disposition is explicitly decided.

## 2. Environment and database facts / blockers

### Confirmed in the repository virtual environment

- Project interpreter: `beni/venv/Scripts/python.exe`; Python 3.14.6.
- Project virtualenv Django: 5.2.18.
- `beni/requirements-before-fix.txt` pins Django 5.2.18, DRF 3.18.3, mysqlclient 2.3.0, and related dependencies. Its filename indicates a pre-fix list; no canonical current lock/requirements file was identified.
- The project settings comment says Django 6.0.8. The system Python at `C:\Users\Vikram\AppData\Local\Programs\Python\Python314\python.exe` resolves Django 6.0.8. Do not assume this is the project runtime.
- `python manage.py check` under the project virtualenv completed with no system-check issues.
- Settings configure MySQL (`django.db.backends.mysql`), database `beni_db`; read-only inspection using the project virtualenv connected to MySQL 8.0.46, default engine InnoDB, isolation `READ-COMMITTED`.
- Existing configured database tables are only Django core tables (`auth_*`, `django_*`, `django_session`). `shops_shop` and `products_product` do not exist.
- Migration records show Django contenttypes/auth/admin/sessions applied. `shops.0001_initial` and `products.0001_initial` are present in source but unapplied to this database. No Orders or domain-app migrations exist other than `shops` and `products`.
- Settings do not define `DATABASES['default']['TEST']`, `DATABASE_ROUTERS`, or a custom test runner.

### Before implementation or testing

- Select and document the intended Python/Django environment. Reconcile the virtualenv (5.2.18), system interpreter (6.0.8), settings comment, and pre-fix dependency manifest without changing dependencies until approved.
- Confirm the target database is the intended development/test target; the source settings currently connect directly to `beni_db`.
- Review the exact migration plan before applying anything. Applying an Orders migration can first apply pending shop/product migrations; these create tables in the configured DB.
- Do not run Django tests against the current default configuration until the test database name, test settings, and database privileges are verified. `manage.py test` may create/drop a MySQL test database.
- Safe preflight (read-only): inspect `settings.DATABASES['default'].get('TEST')`, `DATABASE_ROUTERS`, and `connection.creation._get_test_db_name()` without calling test database setup. Then explicitly confirm the derived name is a disposable isolated database, not `beni_db` or any shared/production database. Actual test execution requires a separate approved isolated database and credentials.

## 3. Feature status inventory

Classification definitions: **Implemented and tested** means source supports the behavior and a focused automated test exists; it does not imply tests were run during this inventory. **Implemented but incomplete** means some runtime behavior exists but the workflow is incomplete. **UI/template only** means a presentation exists without a connected workflow. **Placeholder or missing** means the app is scaffolded or lacks the requested functionality. **Blocked by database schema or unresolved dependency** means implementation/test execution depends on an unapplied migration, unresolved environment, or prerequisite design.

| Area / workflow | Classification | Evidence and gaps |
|---|---|---|
| Registration, login, logout | Implemented and tested | `accounts` uses Django auth forms/views; registration creates a default customer (ordinary user with no privileged group); login redirects by role; logout is POST-only. Focused account tests cover rendering, redirects, CSRF, logout, and role-group creation. |
| Role-based access | Implemented and tested | `accounts/roles.py` provides exact-name group decorators; dashboard tests cover role boundaries and case-variant groups. Shopkeeper and repair-worker groups are provisioned by a management command. |
| Customer catalog and product details | Implemented and tested | Active products from active shops are listed with search/category/pagination; detail hides inactive products. Product tests cover these behaviors. Runtime DB currently lacks shops/products tables. |
| Customer cart | Implemented but incomplete; blocked by database availability | Session-backed add/update/remove with CSRF forms; checks product/shop activity, stock, and price when resolving cart. No reservation, durable cart, or atomic inventory operation. Cart URLs are `customers:cart`, `cart_add`, `cart_update`, `cart_remove`. |
| Checkout / order history / details | Implemented but incomplete; blocked by schema | Session-backed checkout creates one mixed-shop order dict and stores it in `beni_orders`; signatures are session-only and stock is not deducted. No `Order`/`OrderItem` tables, per-shop orders, database idempotency, transactional rollback, or cancellation. Existing `order_detail` raises an `HttpResponseBadRequest` object instead of returning it, so a missing order may produce an error. |
| Shopkeeper shop management | Implemented and tested | CRUD with exact shopkeeper role gate and owner-filtered list/edit; tests include foreign-owner rejection. Shop migration is not applied to current configured database. |
| Shopkeeper product management / inventory | Implemented and tested; workflow incomplete | CRUD scoped to shops owned by the user; form shop choices are restricted to their shops; tests cover ownership, validation, product uniqueness, public catalog, and availability. Inventory is manually edited; no stock ledger or reservation workflow. |
| Shopkeeper order management | Implemented but incomplete | Session-based list filters lines by owned shop and role; no persistent order data, details, status updates, or per-shop persistent orders. Existing list displays the overall order total even if showing only a subset of that order's items. Dashboard still describes order workflow as not connected. |
| Billing, payments, refunds, cancellations | Placeholder or missing; blocked by Orders schema/integration | Apps contain only scaffold files; no billing/payment models, views, URLs, forms, migrations, gateway client, webhook, or UI. No real payment processing or cancellation/refund implementation. |
| Repair requests and bookings | Placeholder or missing; UI/template only | `bookings` has no models/views/forms/URLs/tests/migrations; repair-worker dashboard is an empty UI mock. No customer request, worker assignment, inspection, scheduling, completion, or service billing workflow. |
| Worker profiles/assignment | Placeholder or missing | `workers` app has no domain model or workflow. Repair-worker group access and dashboard exist, but do not constitute worker assignment or verification. |
| Shopkeeper and worker verification | Placeholder or missing | `verification` app has no models/views/forms/URLs/tests/migrations/templates. Role membership is not a verification process. |
| Wallet ledger, balances, withdrawals, payouts | Placeholder or missing; depends on accounting/payment decisions | `wallets` has no domain implementation. No ledger, balance, withdrawal, payout, provider integration, or reconciliation. |
| Customer reviews / shop feedback | Placeholder or missing; depends on order identity | `reviews` has no domain implementation. No verified-purchase rule, review CRUD, moderation, rating aggregation, or feedback UI. |
| Notifications / admin monitoring | Placeholder or UI only | `notifications` has no implementation. Admin dashboard is a UI shell; it explicitly says operations metrics are not connected. Django admin remains available, but only Shop and Product have custom `ModelAdmin` registrations. |

## 4. Existing architecture, route names, and reusable components

### Root and routes

Current route configuration:

- `/` redirects to `accounts:login`.
- `/admin/` is Django admin.
- `/accounts/login/`, `/accounts/register/`, `/accounts/logout/`.
- `/customer/cart/`, `/customer/cart/add/<product_id>/`, `/customer/cart/update/<product_id>/`, `/customer/cart/remove/<product_id>/`, `/customer/checkout/`, `/customer/orders/`, `/customer/orders/<order_number>/`.
- `/catalog/` and `/catalog/<product_id>/`.
- `/workspace/customer/`, `/workspace/shopkeeper/`, `/workspace/repair-worker/`, `/workspace/admin/`.
- `/workspace/shopkeeper/shops/` and `/workspace/shopkeeper/products/`.
- `/workspace/shopkeeper/orders/` routes to `customers.shopkeeper_urls`.

Preserve existing route names where possible: `accounts:*`, `customers:cart`, `customers:checkout`, `customers:orders`, `customers:order_detail`, `catalog:*`, `shops:*`, `products:*`, `dashboard:*`, and `shopkeeper_orders`.

### Reusable controls and domain behavior

- Django authentication/session/messages and CSRF middleware are configured.
- `accounts.roles.role_group_required` is the shared login + exact group authorization helper.
- `Shop.owner=request.user` and `Product.shop__owner=request.user` are established object-level ownership patterns.
- `ProductForm` limits shops to those owned by the current user.
- `Product` uses a Shop foreign key (`CASCADE`), decimal price, integer stock, active flag, price/stock checks, and unique `(shop, sku)`.
- `Shop.owner` is a user FK (`CASCADE`); Shop has coordinate checks and active flag.
- `shops.0001_initial` depends on the swappable auth user; `products.0001_initial` depends on `shops.0001_initial`.
- There are no external payment, messaging, booking, or verification integrations in the inspected app source.
- `accounts`, `customers`, `dashboard`, and all scaffold apps have no domain migrations; `orders`, payments/billing/etc. have only migration package initializers.

### Template inheritance and static assets

All current role templates extend `templates/base/base.html`. The base provides the shared shell, messages, responsive role nav, sign-in/out, static base CSS, and POST/CSRF logout.

Existing template groups:

- Auth: `templates/auth/login.html`, `templates/auth/register.html`.
- Customer: `templates/customer/dashboard.html`, `templates/customer/catalog/list.html`, `templates/customer/catalog/detail.html`, `templates/customer/cart.html`, `templates/customer/checkout.html`, `templates/customer/orders/list.html`, `templates/customer/orders/detail.html`.
- Shopkeeper: `templates/shopkeeper/dashboard.html`, `templates/shopkeeper/_management_nav.html`, `templates/shopkeeper/shops/list.html`, `templates/shopkeeper/shops/form.html`, `templates/shopkeeper/products/list.html`, `templates/shopkeeper/products/form.html`, `templates/shopkeeper/orders/list.html`.
- Repair worker and staff: `templates/repair_worker/dashboard.html`, `templates/admin_panel/dashboard.html`.

Existing CSS is role/layout/presentation support, not business logic:

- `static/css/base/tokens.css`, `static/css/base/shell.css`
- `static/css/auth/auth.css`
- `static/css/customer/dashboard.css`, `static/css/customer/catalog.css`
- `static/css/shopkeeper/dashboard.css`, `static/css/shopkeeper/management.css`
- `static/css/repair_worker/dashboard.css`
- `static/css/admin_panel/dashboard.css`

Existing JavaScript only supports nav/tab interaction or auth focus:

- `static/js/base/navigation.js`, `static/js/auth/auth.js`
- `static/js/customer/discovery.js`, `static/js/shopkeeper/store-tabs.js`
- `static/js/repair_worker/work-queue.js`, `static/js/admin_panel/overview.js`

There are no dedicated payment, booking, wallet, review, verification, notification, or order-management assets. Cart/checkout/order templates exist, but are presentation for the current session prototype.

## 5. File-by-file gap checklist

All paths below are relative to the repository root.

### Existing features to preserve

- `beni/accounts/{forms.py,roles.py,views.py,urls.py,tests.py}` — preserve auth flows and add only narrow changes if later requirements demand them.
- `beni/accounts/management/commands/create_role_groups.py` — keep exact role group provisioning.
- `beni/dashboard/{views.py,urls.py,tests.py}` — keep role-separated routes; connect the current placeholder dashboards only when their corresponding workflows exist.
- `beni/shops/{models.py,forms.py,views.py,urls.py,tests.py,migrations/0001_initial.py,admin.py}` — preserve shop CRUD, ownership and validation.
- `beni/products/{models.py,forms.py,views.py,urls.py,public_urls.py,tests.py,migrations/0001_initial.py,admin.py}` — preserve catalog and owner-scoped product CRUD; extend inventory only when a stock-ledger design is approved.
- `beni/beni/{settings.py,urls.py}` — preserve current middleware, URL entry points, role apps, and DB settings; do not alter dependencies or database settings without approval.
- Existing auth, customer/catalog/shopkeeper templates and role CSS/JS listed above — reuse and extend rather than rewrite.

### Orders / checkout implementation still required

- Modify `beni/orders/models.py`: add persistent `Order` and `OrderItem`; finalize monetary snapshots, statuses, FKs, constraints, indexes, and deletion behavior.
- Create `beni/orders/migrations/0001_initial.py` only after explicit schema approval. It will need direct dependencies on `products.0001_initial` and `migrations.swappable_dependency(settings.AUTH_USER_MODEL)`. The live DB has pending `shops` and `products` migrations, so the application plan must account for them.
- Create `beni/orders/services.py`: cart revalidation, per-shop grouping, single atomic checkout transaction, lock/recheck/deduct stock, durable duplicate-submit protection, order state transitions, and full pre-fulfillment cancellation/restoration.
- Create `beni/orders/forms.py` for order-status input if the status action is form-based.
- Modify `beni/orders/views.py`: customer checkout/history/detail and owner-scoped shopkeeper order list/detail/status actions.
- Create `beni/orders/urls.py` or continue including views through existing route modules; preserve current names.
- Modify `beni/customers/views.py`, `beni/customers/urls.py`, and `beni/customers/shopkeeper_urls.py`: retain session cart endpoints, replace session-only order creation/history with persisted Orders while preserving names.
- Expand `beni/orders/tests.py` and `beni/customers/tests.py`: multi-shop order grouping, price/activity/stock validation, CSRF, duplicate concurrent/replay behavior, full transaction rollback, stock locks/oversell, customer ownership, shopkeeper own-shop scope, status transitions, cancellation exactly once, historical snapshots, and product/shop retention.
- Update `beni/templates/customer/checkout.html`, `beni/templates/customer/orders/list.html`, `beni/templates/customer/orders/detail.html`, and `beni/templates/shopkeeper/orders/list.html` to use persisted data and scoped per-shop totals. Add order-specific CSS/JS only if behavior cannot be handled accessibly with existing forms/styles.
- Update `beni/templates/customer/dashboard.html` and `beni/templates/shopkeeper/dashboard.html` only to replace the currently disconnected copy when persistent workflows are implemented.
- Ensure CSRF tokens on every state-changing form; all lookup querysets must enforce customer or shop ownership in the query itself.

### Billing / payments

- Implement in `beni/billing/models.py`, `views.py`, forms (new), `urls.py` (new), `tests.py`, migrations (new), and a role-scoped billing template only after order totals and payment responsibility are approved.
- Implement in `beni/payments/models.py`, `views.py`, forms (new), `urls.py` (new), `tests.py`, migrations (new), and provider integration modules (new) only after choosing a payment provider and webhook contract.
- Create payment/refund templates and provider CSS/JS only if required; do not trust browser redirect state. Webhook signature verification, idempotency, reconciliation, and secrets management are required before claiming payments work.

### Repairs, bookings, workers, verification

- Implement `beni/bookings/models.py`, `views.py`, forms (new), `urls.py` (new), `tests.py`, migration, and customer booking templates for repair requests and scheduling.
- Implement `beni/workers/models.py`, `views.py`, forms (new), `urls.py` (new), `tests.py`, migration, and repair-worker queue/detail templates for worker profiles, availability, assignment, inspection, status and completion.
- Implement `beni/verification/models.py`, `views.py`, forms (new), `urls.py` (new), `tests.py`, migration, and separated shopkeeper/worker/admin templates for review/approval, evidence access, audit trail, and permission boundaries.
- Connect `beni/dashboard/views.py` / `urls.py` and `templates/repair_worker/dashboard.html` only after the workflows and ownership model exist.
- Add role-specific CSS/JS only where necessary; current repair-worker CSS/JS only styles and switches a mock tabbed dashboard.

### Wallets, reviews, notifications, admin monitoring

- Implement `beni/wallets/models.py`, `views.py`, forms (new), `urls.py` (new), `tests.py`, migration, templates and any narrowly scoped assets for an immutable ledger, derived balance, withdrawal requests, payout state, and reconciliation. Depends on approved worker/shop earnings and payment/refund rules.
- Implement `beni/reviews/models.py`, `views.py`, forms (new), `urls.py` (new), `tests.py`, migration, templates, and optional styling. Depends on persisted order/item identity and verified-purchase/one-review rules.
- Implement `beni/notifications/models.py`, `views.py`, `urls.py` (new), `tests.py`, migration, templates and delivery adapter only after choosing in-app/email/SMS channels. Notification events should be emitted from committed domain transitions, not before transaction commit.
- Replace placeholder metrics in `templates/admin_panel/dashboard.html` and connect `beni/dashboard/views.py` only after reliable order, booking, payment and verification sources exist; keep Django admin available.
- Register new models with app `admin.py` only where administration is authorized and appropriate; currently only Shop and Product have custom admin registration.

### Uppercase directories — preserve; usage not established

- `beni/Customer/{apps.py,models.py,views.py,tests.py,admin.py,migrations/}`.
- `beni/Repair/{apps.py,models.py,views.py,tests.py,admin.py,migrations/}`.
- `beni/Dukandaar/{apps.py,models.py,views.py,tests.py,admin.py,migrations/}`.

They are not listed in `INSTALLED_APPS`, are not referenced by root URL configuration, and contain placeholder model/view/test modules with only migration initializers. They appear unused by the current runtime, but do not delete, rename, install, or merge them during feature implementation without a separate decision.

## 6. Dependencies and recommended staged implementation order

1. **Environment and safe baseline (prerequisite):** agree on the intended interpreter/Django version; confirm the target development DB; confirm an isolated test DB is available. Preserve the working auth, catalog, shop, and product surfaces.
2. **Database prerequisite review:** inspect migration plan; `shops.0001_initial` and `products.0001_initial` are source-present but unapplied to `beni_db`. Obtain explicit approval before applying them or any new schema.
3. **Persistent Orders / inventory:** approve and create Orders schema, then implement the transactional service and focused tests. No real payments. Keep all multi-shop orders all-or-nothing. Use one independent order per shop.
4. **Customer and shopkeeper order UX:** replace session order persistence with database-backed, object-scoped history/details/management; preserve named routes and role-specific templates.
5. **Billing and payment integration:** only after totals, provider, refunds and payout responsibilities are approved. No real payment feature is delivered by the Orders stage.
6. **Booking and worker workflow:** define request states, eligibility, schedule and ownership; implement booking then worker assignment/inspection/completion.
7. **Verification:** build shopkeeper/worker verification and admin review before exposing unverified workspaces or payouts.
8. **Wallets/payouts:** implement only after payment, accounting ownership, ledger immutability and reconciliation policy are decided.
9. **Reviews and notifications:** reviews depend on completed/persisted purchases; notifications depend on committed events and a chosen delivery channel.
10. **Admin monitoring:** connect live metrics after domain records and staff permissions exist; do not represent placeholders as working operations.

## 7. Test and security checklist

- Auth: existing registration/login/logout/CSRF/role redirect and cross-role isolation tests continue to pass.
- Catalog/shops/products: existing inactive filtering, validation, owner-scope, and foreign-object 404 tests continue to pass.
- Orders: multi-shop session grouping to per-shop DB orders; authoritative server prices/totals; inactive/missing item rejection; insufficient stock; two simultaneous checkouts; transaction rollback on any failure; duplicate POST/replay; no cart clearing before commit; customer-only detail; shopkeeper own-shop-only visibility and mutation; valid state transitions; full cancellation/restoration once; partial cancellation blocked; historical name/price/category/SKU snapshots.
- Billing/payments: tampered totals, unauthorized payment-status changes, duplicate callbacks, signature verification, replay prevention, refund state and reconciliation. Do not test against live payment services without a separate approved sandbox.
- Bookings/workers: customer ownership, worker assignment eligibility, schedule conflicts, role scope, allowed state transitions, inspection/completion audit trail.
- Verification: applicant/object privacy, reviewer authorization, decision immutability/audit, no unverified privilege escalation.
- Wallets: ledger append-only behavior, atomic balance calculations, idempotent postings, withdrawal/payout authorization, no negative/unbalanced accounting.
- Reviews: verified purchase, ownership, duplicates, moderation and unauthorized edits.
- Notifications/admin: event delivery only after commit, recipient scope, staff-only monitoring, no sensitive cross-user data leakage.
- Run CSRF-enforcing client tests on state-changing endpoints; test unauthenticated and wrong-role paths and cross-owner IDs.
- Run tests only on the confirmed isolated test database. Include concurrency tests against MySQL/InnoDB (not SQLite substitutes) for row-lock behavior.

## 8. Approval gates and unresolved decisions

- Choose the actual development/test interpreter and Django version; reconcile the 5.2.18 venv with system 6.0.8 and the pre-fix dependency file.
- Approve any database migration. The configured database currently lacks shop/product tables; migration execution may create those before Orders.
- Approve final persistent order schema, including checkout idempotency model/key, order number approach, product/shop/customer deletion policy, and whether product reassignment is allowed after order history.
- Approve the cancellation boundary (this plan recommends full cancellation only before fulfillment; partial cancellation waits for fulfillment tracking).
- Confirm test database isolation and authorization before running Django tests.
- Before payments: select a gateway, webhook verification, sandbox, refund contract and ownership of payment/billing records.
- Before bookings/worker flows: select repair request, assignment, scheduling and verification policies.
- Before wallets/payouts: define ledger/accounting, earnings ownership, withdrawal authorization and reconciliation.
- Decide future disposition of the uppercase scaffold directories separately; this plan does not merge or delete them.

## 9. Inventory validation record

- Inspected `INSTALLED_APPS`, settings, root URL configuration, domain models/forms/views/routes/tests/admin/migration files for the requested apps, plus template/static inventories and relevant base/role templates and JavaScript.
- Inspected uppercase scaffold modules and verified they are absent from `INSTALLED_APPS` and current URL includes.
- Ran read-only `manage.py check` using the project virtualenv: no issues reported.
- Queried the configured MySQL DB and migration recorder read-only using the project virtualenv; no test database was created and no migration was run.
- Did not run tests because their setup may create/drop a MySQL test database and test DB isolation is not configured or confirmed.
- No application source, models, templates, static assets, dependencies, migrations, or database state were changed for this inventory.
