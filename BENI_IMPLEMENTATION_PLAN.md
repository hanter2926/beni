# BENI Implementation Checklist

Inventory date: 2026-10-18; implementation recheck: 2026-10-19
Scope: original project inventory plus subsequent approved database repairs and Orders/Checkout implementation. The payment migrations were generated, reviewed, explicitly approved, and applied to the configured MySQL database.

## Resume checklist — 2026-10-19

This recheck supersedes older “current” status statements below where they
conflict with the live migration recorder or current checkout. Historical
implementation notes are retained for context, not as proof of current state.

### Verified in this recheck

- [x] Project virtualenv is Python 3.14.6 / Django 5.2.18. `manage.py check
  --database default` passed, and `makemigrations --check --dry-run` reported
  no model/migration drift.
- [x] Port 8000 was listening and `/accounts/login/` returned HTTP 200. A
  fresh project-virtualenv server on 127.0.0.1:8001 also returned HTTP 200.
  The existing 8000 process uses system Python / Django 6.0.8; use the project
  virtualenv for reproducible development.
- [x] Read-only migration and schema inspection found the earlier account,
  booking, verification, wallet, and shop-image migrations applied, with
  `accounts.0002_profile_alternate_phone_profile_phone_and_more` and
  `bookings.0003_repairbooking_locality_and_more` pending.
- [x] After receiving explicit approval for those exact migrations on
  `beni_db`, applied each individually and verified its migration-recorder row.
  Read-only introspection now confirms all installed model tables/columns and
  both booking-support indexes are present.
- [x] Post-migration fresh-server smoke test: `/accounts/login/` and
  `/catalog/` returned HTTP 200; anonymous `/customer/orders/`, `/repairs/`,
  and `/accounts/profile/` returned the expected HTTP 302 login redirect.
  Authenticated live MySQL pages were not tested.
- [x] The full 115-test suite passed against an explicitly guarded in-memory
  SQLite database. The booking/verification subset also passed (20 tests).
  These runs did not use or modify the configured MySQL database and do not
  establish MySQL locking/concurrency behavior.
- [x] Implemented code-only Razorpay checkout and staff-reviewed paid-order
  cancellation. The latest 131-test suite passes against guarded in-memory
  SQLite with provider calls mocked. The payment migrations were applied to
  `beni_db` after separate approval and their tables/columns were verified.
- [x] `git diff --check` and `git diff --cached --check` passed. Existing
  worktree changes were left intact.

### Approval-gated and unfinished

- [x] Applied the explicitly approved `orders.0002_checkoutattempt_payment_method`
  and `payments.0001_initial` to `beni_db` in sequence; verified the recorder,
  `payment_method` column, all three tables, their required columns/indexes,
  and a clean Django database check.
- [ ] Configure Razorpay sandbox credentials in the private environment
  (`RAZORPAY_KEY_ID`, `RAZORPAY_KEY_SECRET`, `RAZORPAY_WEBHOOK_SECRET`), set
  the webhook URL to `/payments/webhook/razorpay/`, and test with the sandbox.
  No provider or browser checkout call has been made.
- [ ] Test authenticated profile, booking, and support-request workflows
  against approved test fixtures now that their schema is present; do not use
  real account credentials or live customer data.
- [ ] Reconcile remaining billing, review, withdrawal, and role dashboard
  requirements against current routes and code. Payment code is not yet
  sandbox- or production-verified.
- [ ] Verify real upload/storage and customer/shopkeeper/worker/admin
  workflows end-to-end; do not mark presentation-only controls as complete.
- [ ] Implement billing/digital bills: no billing route or bill workflow is
  currently wired into the root URL configuration.
- [x] Implement payment endpoints and mocked Razorpay checkout/webhook tests;
  checkout offers COD and online payment, webhook signatures and event
  idempotency are enforced, and paid-order cancellation requires staff review.
  COD is settled when the shopkeeper records delivery; refunds and
  multi-shop payouts remain manual.
- [ ] Implement reviews with verified-order ownership and moderation rules;
  no review model or routed review workflow is currently present.
- [ ] Extend the wallet ledger to withdrawal requests, authorization, and
  payout reconciliation; current wallet URLs expose role-specific wallet
  history, not a withdrawal workflow.
- [ ] Complete worker-specific profile/availability/dashboard workflows.
  Booking assignment and verification logic exist, but the `workers` app has
  no domain model or routed workflow of its own.
- [ ] Define API contracts and permissions before adding API endpoints; no API
  route is included in the current root URL configuration.

## 1. Executive summary

The 2026-10-19 recheck found working authentication, catalog, shop/product,
order, booking, verification, notification, and wallet source workflows. The
configured MySQL database has the order, booking, verification, wallet,
shop-image, and payment schema; the approved profile, repair-support, and
payment migrations have been applied and verified. The latest 131-test suite
passed using in-memory SQLite, but this does not verify MySQL locking or
authenticated live pages.
Billing/digital bills, reviews, wallet withdrawals, worker-specific
profile/availability workflows, and sandbox Razorpay verification remain
unfinished. Payment code and schema are present, but the provider has not
been exercised. Consult the resume checklist above;
the detailed inventory sections below are historical planning context and
must not override the current recheck.

The uppercase `Customer`, `Repair`, and `Dukandaar` directories are not
installed or routed; retain them until their future disposition is explicitly
decided.

## 2. Environment and database facts / blockers

### Confirmed in the repository virtual environment

- Project interpreter: `beni/venv/Scripts/python.exe`; Python 3.14.6.
- Project virtualenv Django: 5.2.18.
- `beni/requirements-before-fix.txt` pins Django 5.2.18, DRF 3.18.3, mysqlclient 2.3.0, and related dependencies. Its filename indicates a pre-fix list; no canonical current lock/requirements file was identified.
- The project settings comment says Django 6.0.8. The system Python at `C:\Users\Vikram\AppData\Local\Programs\Python\Python314\python.exe` resolves Django 6.0.8. Do not assume this is the project runtime.
- `python manage.py check` under the project virtualenv completed with no system-check issues.
- Settings configure MySQL (`django.db.backends.mysql`), database `beni_db`; read-only inspection using the project virtualenv connected to MySQL 8.0.46, default engine InnoDB, isolation `READ-COMMITTED`.
- The 2026-10-19 read-only inspection found `shops_shop`, `products_product`,
  and the order tables present. `orders.0001_initial` is recorded as applied.
  `accounts.0002` and `bookings.0003` are the only pending project migrations
  relevant to the observed profile/booking schema gaps.
- The configured test database name is `test_beni_db`; it already existed
  during the latest recheck. The passing 115-test run explicitly set Django's
  database to in-memory SQLite before setup and asserted `:memory:`; it did
  not use or modify `test_beni_db`.
- Settings do not define `DATABASES['default']['TEST']`, `DATABASE_ROUTERS`, or a custom test runner.

### Outstanding safety gates

- Preserve the selected project virtual environment (Python 3.14.6, Django 5.2.18); do not change the runtime or dependencies.
- The latest DB check found shop/product migrations already applied. Recheck before future schema actions; do not infer live schema state from this checklist.
- The user explicitly approved creation of `orders.0001_initial.py` only. Its dependency graph and dry-run plan are inspected; applying it to any persistent database still requires separate explicit approval.
- Test DB name `test_beni_db` was confirmed distinct from `beni_db` and absent before testing. The successful 26-test run used a transient, process-local `MIGRATION_MODULES` override setting all installed apps to unmigrated so Django synchronized their model tables only in the isolated test DB. This bypasses migrations and is for source-level tests only; never use it against the runtime database.

## 3. Feature status inventory

Classification definitions: **Implemented and tested** means source supports the behavior and a focused automated test exists; it does not imply tests were run during this inventory. **Implemented but incomplete** means some runtime behavior exists but the workflow is incomplete. **UI/template only** means a presentation exists without a connected workflow. **Placeholder or missing** means the app is scaffolded or lacks the requested functionality. **Blocked by database schema or unresolved dependency** means implementation/test execution depends on an unapplied migration, unresolved environment, or prerequisite design.

| Area / workflow | Classification | Evidence and gaps |
|---|---|---|
| Registration, login, logout | Implemented and tested | `accounts` uses Django auth forms/views; registration creates a default customer (ordinary user with no privileged group); login redirects by role; logout is POST-only. Focused account tests cover rendering, redirects, CSRF, logout, and role-group creation. |
| Role-based access | Implemented and tested | `accounts/roles.py` provides exact-name group decorators; dashboard tests cover role boundaries and case-variant groups. Shopkeeper and repair-worker groups are provisioned by a management command. |
| Customer catalog and product details | Implemented and tested | Active products from active shops are listed with search/category/pagination; detail hides inactive products. Shop/product tables and migrations were present and applied in the latest pre-implementation DB inspection. |
| Customer cart | Implemented; session-based | Existing add/update/remove routes remain; edits invalidate the active checkout token. Cart values are revalidated against current product/shop state and current price. |
| Checkout / order history / details | Implemented and schema applied | `Order`, `OrderItem`, and `CheckoutAttempt` models and transactional multi-shop checkout are live against the applied order schema. Each shop receives an independent order; stock is locked/deducted atomically; a database-backed attempt token prevents duplicate order sets; ownership-scoped history/detail and cancellation are present. |
| Shopkeeper shop management | Implemented and tested | CRUD with exact shopkeeper role gate and owner-filtered list/edit; latest DB inspection found the shop migration applied. |
| Shopkeeper product management / inventory | Implemented and tested; workflow incomplete | CRUD scoped to shops owned by the user; form shop choices are restricted to owned shops. Inventory is manually edited outside the atomic order reservation/cancellation service; no general stock ledger exists. |
| Shopkeeper order management | Implemented in source; blocked by Orders schema | Existing route name `shopkeeper_orders` is preserved. Persistent order lists are filtered by `shop__owner=request.user`; status transitions are restricted and validated in the service; no payment handling is provided. |
| Billing, payments, refunds, cancellations | Razorpay checkout implemented; refunds/payouts manual; billing missing | Payment choice, one aggregate Razorpay attempt per multi-shop checkout, signed callback/provider status checks, idempotent captured-payment webhook, and staff review for paid cancellation are implemented and tested with mocked provider requests. Payment migrations are applied. No live provider/browser verification has occurred; automatic refunds, shop payouts, and digital bills are not implemented. |
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
- `beni/products/{models.py,forms.py,views.py,urls.py,public_urls.py,tests.py,migrations/0001_initial.py,admin.py}` — preserve catalog and owner-scoped product CRUD; current Stage A adds only a model guard against moving products with order history to another shop.
- `beni/beni/{settings.py,urls.py}` — preserve current middleware, URL entry points, role apps, and DB settings; do not alter dependencies or database settings without approval.
- Existing auth, customer/catalog/shopkeeper templates and role CSS/JS listed above — reuse and extend rather than rewrite.

### Orders / checkout Stage A status and remaining work

Implemented in source (not yet usable against the configured runtime DB until a schema migration is approved/applied):

- `beni/orders/models.py` — `CheckoutAttempt`, `Order`, and `OrderItem` with unique order numbers, snapshots, constraints/indexes, and history-preserving `PROTECT` relationships.
- `beni/orders/services.py` — session cart digest/token replay, per-shop grouping, one atomic transaction for every order and stock deduction, product/shop row locks, order transition validation, and idempotent full cancellation/restoration.
- `beni/orders/forms.py` — server-validated checkout contact/address fields and shopkeeper status input. `beni/customers/forms.py` re-exports `CheckoutForm` for compatibility.
- `beni/orders/views.py` — customer checkout/history/detail/cancel and owner-scoped shopkeeper listing/status update.
- `beni/orders/admin.py` — read-only order monitoring; no direct status/payment/total editing.
- `beni/products/models.py` — blocks product shop reassignment after order items exist, preserving cancellation stock destination.
- `beni/customers/views.py` — retained cart actions, invalidated checkout token when cart changes, removed session-only order persistence, and improved malformed-cart feedback.
- `beni/customers/urls.py`, `beni/customers/shopkeeper_urls.py` — existing route names retained and mapped to persistent order views.
- `beni/orders/tests.py`, `beni/customers/tests.py` — success/multi-shop, stock/price validation, idempotent replay, rollback, cancellation, ownership, CSRF, and history-retention test cases.
- `beni/templates/customer/checkout.html`, `beni/templates/customer/orders/list.html`, `beni/templates/customer/orders/detail.html`, `beni/templates/shopkeeper/orders/list.html` — updated to render persistent model fields and CSRF-protected actions. Existing role CSS/JS is sufficient; no asset change is required.

Historical Orders-stage notes (the current payment status is recorded above):

- `beni/orders/migrations/0001_initial.py` — its original dependencies were `products.0001_initial`, `shops.0001_initial`, and `migrations.swappable_dependency(settings.AUTH_USER_MODEL)`; it is now recorded as applied.
- Run the test suite normally only after confirming test DB isolation; that will apply migrations to the disposable test DB. The earlier 26-test source run used a process-local override before this migration existed and did not test migration execution.
- Automated concurrency/oversell behavior still needs verification against MySQL/InnoDB. Unit-level tests cannot establish simultaneous request locking correctness by themselves.
- Dashboard copy remains unchanged; update `beni/templates/customer/dashboard.html` and `beni/templates/shopkeeper/dashboard.html` only if the completed persistent workflows need dashboard links/status copy.

### Billing / payments

- Razorpay code is in `beni/payments/` and customer order checkout. Set `RAZORPAY_KEY_ID`, `RAZORPAY_KEY_SECRET`, and `RAZORPAY_WEBHOOK_SECRET` only in the private environment; configure the webhook at `/payments/webhook/razorpay/` for `payment.authorized`, `payment.captured`, and `payment.failed`. Never commit credentials.
- `orders.0002_checkoutattempt_payment_method` and `payments.0001_initial` were generated, SQL-reviewed, approved for application, and applied to `beni_db`. Existing checkout attempts received COD as the default; the payment-attempt, webhook-event, and cancellation-review tables were empty when created.
- Automated tests mock Razorpay and do not verify hosted checkout, provider credentials, webhook delivery, MySQL concurrency, payouts, or actual refunds. Manual payout/refund reconciliation remains outside this integration. Billing and digital bills are still unimplemented.

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
2. **Database prerequisite review (complete at latest audit):** `shops.0001_initial` and `products.0001_initial` were applied and their InnoDB tables existed. Recheck before any future schema action.
3. **Persistent Orders / inventory (implemented):** `orders.0001_initial` is applied on the configured database. Multi-shop checkout remains one order per shop under one checkout attempt.
4. **Customer and shopkeeper order UX (implemented):** object-scoped history/details/status management uses the applied order schema. COD orders are settled when the shopkeeper records delivery.
5. **Online payment integration (code and schema implemented):** Razorpay checkout, server-side signature/provider status checks, captured-payment webhooks, and staff-reviewed paid cancellation are covered by mocked tests. The migrations are applied; sandbox/provider behavior remains unverified.
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

- The implementation used the repository virtual environment (Python 3.14.6/Django 5.2.18); no runtime/dependency changes are proposed.
- `orders.0001_initial` is recorded as applied. The payment migrations were generated and SQL-reviewed after authorization, then explicitly approved and applied in order: `orders.0002_checkoutattempt_payment_method` depends on `orders.0001_initial`; `payments.0001_initial` depends on it and the swappable user model.
- Read-only verification confirms both payment migration recorder entries, the checkout payment-method column, and all three payment tables with their required columns and indexes. `check --database default` passed; `makemigrations --check --dry-run` reports no drift.
- The selected schema uses checkout-attempt idempotency, UUID-based unique order numbers, `PROTECT` history links, and prohibits product shop reassignment after order history. These design decisions are implemented in source; request changes before approving migration if they are not acceptable.
- Full cancellation is allowed only before fulfillment; partial cancellation remains deferred until fulfillment tracking exists. No separate design decision remains for this stage.
- Test DB isolation for the latest 131-test run used process-local in-memory SQLite, not `test_beni_db` or `beni_db`. Provider requests were mocked; Razorpay sandbox behavior and MySQL concurrency remain unverified.
- The gateway is Razorpay. Checkout signature verification, raw-body webhook verification/idempotency, and manual refund/payout policies are implemented. Configure and test sandbox credentials before any production use.
- Before bookings/worker flows: select repair request, assignment, scheduling and verification policies.
- Before wallets/payouts: define ledger/accounting, earnings ownership, withdrawal authorization and reconciliation.
- Decide future disposition of the uppercase scaffold directories separately; this plan does not merge or delete them.

## 9. Inventory and Stage A validation record

- Inspected `INSTALLED_APPS`, settings, root URL configuration, domain models/forms/views/routes/tests/admin/migration files for the requested apps, plus template/static inventories and relevant base/role templates and JavaScript.
- Inspected uppercase scaffold modules and verified they are absent from `INSTALLED_APPS` and current URL includes.
- Ran the original read-only `manage.py check` and comprehensive inventory before implementation.
- Stage A later ran `manage.py check` successfully; `showmigrations` marks `shops.0001_initial` and `products.0001_initial` applied and `orders.0001_initial` unapplied. `migrate --plan` lists only `orders.0001_initial`.
- Read-only runtime inspection confirmed MySQL 8.0.46, `beni_db`, InnoDB shop/product tables, no Orders tables, and no remaining `test_beni_db`.
- The 26 tests in `orders.tests`, `customers.tests`, and `products.tests` passed with a process-local migration override before the Orders migration file was created. The runner dropped the isolated test DB afterward. This does not test migration behavior or concurrent database locking.
- Stage A changed application/order templates, product shop-reassignment validation, and related design/checklist documents. The approved Orders migration file exists but has not been applied; no live database schema or data was altered.
