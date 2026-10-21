# BENI Current Status Audit

**Audit date:** 2026-10-21  
**Project:** `beni/` Django project  
**Audit type:** Fresh, read-only implementation and database status review

## Scope and verification boundary

This review checked the registered apps and root URL configuration; domain models,
views, URLconfs, forms, templates, services, JavaScript, CSS, tests, and migration
files; plus migration-recorder and table state in the configured `beni_db`.
Database inspection consisted of read-only migration, schema-introspection, and
aggregate-count queries.

No application code, settings, dependencies, migrations, or existing records were
changed. No migration or test suite was run. Test files were inspected, but their
assertions are evidence of intended coverage, not fresh passing results. No browser,
real upload, Razorpay sandbox, live payment, or staging deployment workflow was
exercised. `.env` values and customer/document contents were not read.

The classifications below are deliberately conservative: a named route resolving
and source code existing do not establish that a full authenticated workflow works
end to end. No complete feature is classified **Working and verified** in this
fresh audit because feature workflows and tests were not executed.

## Evidence index

The inspected implementation surfaces used for the findings below:

| Feature | Models / services / views / routes | Forms / templates / tests / migrations |
|---|---|---|
| App registration and common routes | [settings.py](./beni/beni/settings.py), [urls.py](./beni/beni/urls.py), [accounts/roles.py](./beni/accounts/roles.py) | [accounts/tests.py](./beni/accounts/tests.py) |
| Dukandaar | [Dukandaar/urls.py](./beni/Dukandaar/urls.py), [shops/views.py](./beni/shops/views.py), [products/views.py](./beni/products/views.py), [orders/views.py](./beni/orders/views.py), [wallets/views.py](./beni/wallets/views.py), [verification/views.py](./beni/verification/views.py) | [Dukandaar/models.py](./beni/Dukandaar/models.py), [Dukandaar/tests.py](./beni/Dukandaar/tests.py), [templates/shopkeeper/](./beni/templates/shopkeeper/) |
| Repair | [Repair/urls.py](./beni/Repair/urls.py), [bookings/models.py](./beni/bookings/models.py), [bookings/services.py](./beni/bookings/services.py), [bookings/views.py](./beni/bookings/views.py) | [bookings/forms.py](./beni/bookings/forms.py), [bookings/tests.py](./beni/bookings/tests.py), [bookings/migrations/](./beni/bookings/migrations/), [templates/customer/repairs/](./beni/templates/customer/repairs/), [templates/repair_worker/repairs/](./beni/templates/repair_worker/repairs/) |
| Customer | [Customer/urls.py](./beni/Customer/urls.py), [customers/views.py](./beni/customers/views.py), [orders/views.py](./beni/orders/views.py) | [customers/tests.py](./beni/customers/tests.py), [Customer/tests.py](./beni/Customer/tests.py), [templates/customer/](./beni/templates/customer/) |
| Billing | [billing/urls.py](./beni/billing/urls.py), [billing/views.py](./beni/billing/views.py), [billing/models.py](./beni/billing/models.py) | [billing/tests.py](./beni/billing/tests.py), [templates/billing/order_invoice.html](./beni/templates/billing/order_invoice.html), [billing/migrations/](./beni/billing/migrations/) |
| Reviews | [reviews/models.py](./beni/reviews/models.py), [reviews/services.py](./beni/reviews/services.py), [reviews/views.py](./beni/reviews/views.py), [reviews/urls.py](./beni/reviews/urls.py) | [reviews/forms.py](./beni/reviews/forms.py), [reviews/tests.py](./beni/reviews/tests.py), [reviews/migrations/](./beni/reviews/migrations/), [templates/reviews/](./beni/templates/reviews/) |
| Orders and checkout | [orders/models.py](./beni/orders/models.py), [orders/services.py](./beni/orders/services.py), [orders/views.py](./beni/orders/views.py), [customers/urls.py](./beni/customers/urls.py) | [orders/forms.py](./beni/orders/forms.py), [orders/tests.py](./beni/orders/tests.py), [orders/migrations/](./beni/orders/migrations/), [templates/customer/checkout.html](./beni/templates/customer/checkout.html), [templates/customer/orders/](./beni/templates/customer/orders/) |
| Payments and refunds | [payments/models.py](./beni/payments/models.py), [payments/gateway.py](./beni/payments/gateway.py), [payments/services.py](./beni/payments/services.py), [payments/views.py](./beni/payments/views.py), [payments/urls.py](./beni/payments/urls.py) | [payments/forms.py](./beni/payments/forms.py), [payments/tests.py](./beni/payments/tests.py), [payments/migrations/](./beni/payments/migrations/), [payments/templates/](./beni/payments/templates/) |
| Wallets and payouts | [wallets/models.py](./beni/wallets/models.py), [wallets/views.py](./beni/wallets/views.py), [wallets/urls.py](./beni/wallets/urls.py) | [wallets/tests.py](./beni/wallets/tests.py), [wallets/migrations/](./beni/wallets/migrations/), [templates/wallets/account.html](./beni/templates/wallets/account.html) |
| Verification | [verification/models.py](./beni/verification/models.py), [verification/services.py](./beni/verification/services.py), [verification/views.py](./beni/verification/views.py), [verification/urls.py](./beni/verification/urls.py) | [verification/forms.py](./beni/verification/forms.py), [verification/tests.py](./beni/verification/tests.py), [verification/migrations/](./beni/verification/migrations/), [verification/storage.py](./beni/verification/storage.py), [templates/admin_panel/verification/](./beni/templates/admin_panel/verification/) |
| Notifications | [notifications/models.py](./beni/notifications/models.py), [notifications/services.py](./beni/notifications/services.py), [notifications/views.py](./beni/notifications/views.py), [notifications/urls.py](./beni/notifications/urls.py) | [notifications/tests.py](./beni/notifications/tests.py), [notifications/migrations/](./beni/notifications/migrations/), [templates/notifications/](./beni/templates/notifications/) |
| Repair guides and Q&A | [repair_guides/models.py](./beni/repair_guides/models.py), [repair_guides/forms.py](./beni/repair_guides/forms.py), [repair_guides/permissions.py](./beni/repair_guides/permissions.py), [repair_guides/services.py](./beni/repair_guides/services.py), [repair_guides/views.py](./beni/repair_guides/views.py), [repair_guides/urls.py](./beni/repair_guides/urls.py) | [repair_guides/tests.py](./beni/repair_guides/tests.py), [repair_guides/migrations/](./beni/repair_guides/migrations/), [templates/repair_guides/](./beni/templates/repair_guides/) |
| Frontend, uploads, testing and deployment | [upload_validation.py](./beni/beni/upload_validation.py), [upload_forms.py](./beni/beni/upload_forms.py), [private_files.py](./beni/beni/private_files.py), [upload_paths.py](./beni/beni/upload_paths.py), [upload_signals.py](./beni/beni/upload_signals.py), [file_lifecycle.py](./beni/beni/file_lifecycle.py) | [templates/base/base.html](./beni/templates/base/base.html), [static/css/](./beni/static/css/), [static/js/](./beni/static/js/), [requirements-before-fix.txt](./beni/requirements-before-fix.txt) |

## Executive status

| # | Feature | Classification | Current finding |
|---|---|---|---|
| 1 | Dukandaar | Partially implemented | Registered facade routes resolve to existing shopkeeper views and inherit their role/ownership checks. The app has no separate domain model or workflow. |
| 2 | Repair | Partially implemented | Booking, assignment, status, support, and private-image code exists with applied schema. Worker availability, quotes, repair pricing, invoices, and payment remain absent. |
| 3 | Customer | Partially implemented | Customer account/profile, catalog, session cart, order checkout/history, and repair booking paths exist. The uppercase `Customer` app is only a facade; no end-to-end flow was run. |
| 4 | billing | Partially implemented | A scoped digital order receipt exists. There is no billing model/migration/table, tax invoice, or repair invoice. Repair invoicing is blocked by missing quote/amount/tax/payment data and policy. |
| 5 | reviews | Partially implemented | Persisted order/shop and repair-worker reviews, ownership checks, moderation, and published shop ratings exist; migration is applied. The database currently contains zero reviews. |
| 6 | orders and checkout | Partially implemented | Transactional multi-shop orders, item snapshots, stock updates, idempotent checkout attempts, and scoped order views exist; migrations are applied. MySQL concurrency and authenticated checkout were not exercised. |
| 7 | payments and refunds | Partially implemented | Razorpay order creation, signature/provider verification, webhook idempotency, and staff-reviewed cancellation exist. **Refund execution and persisted refund lifecycle are missing.** |
| 8 | wallets and payouts | Partially implemented | Owner/role-scoped read-only wallet history and immutable ledger foundations exist. **Earning-credit production, withdrawal requests, payout processing, and reconciliation are missing.** |
| 9 | verification | Partially implemented | Shopkeeper/worker document submission, private storage, staff decisions, and eligibility checks exist. External/automated identity checks are not integrated. |
| 10 | notifications | Partially implemented | Persistent in-app inbox, unread counts, idempotent transactional events, and POST-only read actions exist. Email, SMS, push, and realtime delivery are absent. |
| 11 | iFixit-inspired repair guides, categories, parts and Q&A | Partially implemented | Category, guide, step, resource/part, product relation, Q&A, votes, reports, and moderation code/schema exist. The database has categories but no guide/Q&A content; FAQ and expert availability are absent. |
| 12 | Frontend, CSS, JavaScript, uploads, testing and deployment | Partially implemented | Templates and role assets exist; upload validation/private-file handling is implemented. Browser/upload acceptance is unverified, tests were not run, and active deployment checks report six warnings. |

## Findings by feature

### 1. Dukandaar

- `INSTALLED_APPS` registers `Dukandaar.apps.DukandaarConfig`; the root URLconf
  includes `Dukandaar.urls` at `/dukandaar/`.
- Runtime resolution confirmed names including `Dukandaar:dashboard`,
  `Dukandaar:shop_create`, `Dukandaar:product_create`, `Dukandaar:orders`, and
  `Dukandaar:wallet`. The facade callbacks resolve to
  `dashboard.views.shopkeeper_dashboard`, `shops.views.shop_create`,
  `products.views.product_create`, `orders.views.shopkeeper_order_list`, and
  `wallets.views.shopkeeper_wallet`.
- The facade URLconf also maps shop edit, product edit/order detail/status, and
  shop verification routes to the existing canonical app views. Shop and product
  records remain related through `Shop.owner` and `Product.shop`; order lists and
  details filter by `shop__owner=request.user`.
- `Dukandaar.models` and `Dukandaar.views` are placeholders. This is consistent
  with the existing integration plan's stated facade architecture, not a separate
  Dukandaar data model. The facade route test exists but was not run.
- **Remaining:** authenticated CRUD, bank-detail/gallery uploads, verification,
  order, and wallet pages need a controlled browser/staging run. No standalone
  shopkeeper earnings or payout feature is provided by this facade.

### 2. Repair

- `/repair-service/` is the `Repair` facade over `bookings`; the canonical
  `/repairs/` URLconf is also registered. Runtime resolution confirmed
  `Repair:customer_list`, `Repair:customer_create`, and `Repair:worker_list`
  dispatch to `bookings.views`.
- `RepairBooking` relates a customer and optional assigned worker to the request;
  related records include booking images, assignment history, and support requests.
  `bookings.services` enforces staff assignment to an active, verified worker and
  a defined worker status transition sequence. Customer and worker views scope
  records to the customer or assigned worker; admin assignment is staff-only.
- Creating a request requires a verified customer phone. Worker queue/status
  access requires a verified worker. Booking images are served through a private
  view to the customer, assigned worker, or staff.
- The schema has no quote, accepted price, labor/parts charge, tax calculation,
  invoice, or booking payment record. There is no worker availability/scheduling
  directory or matching algorithm; a preferred time is stored and staff manually
  assigns a worker. A support/dispute path exists but is not a priced repair
  settlement flow.
- **Remaining:** define worker availability and quote/acceptance rules; add
  repair pricing and settlement only after those rules and payment/refund
  dependencies are decided. Repair invoices cannot be derived truthfully from
  current booking rows.

### 3. Customer

- Both `/customer-space/` (`Customer` facade) and `/customer/` (`customers`)
  are registered. The uppercase facade routes dashboard/cart/checkout/order
  pages to `dashboard`, `customers`, and `orders` views. Runtime resolution
  confirmed `Customer:dashboard`, `Customer:cart`, `Customer:checkout`, and
  `Customer:orders`.
- Customer identity uses Django's configured user model and `accounts.Profile`.
  The cart is session-backed and associated with the current customer; cart
  entries are revalidated against active, marketable products, stock, and current
  prices. Checkout is customer-only (not staff, shopkeeper, or repair worker).
- There is no standalone `Customer` model in the uppercase app or custom
  `customers` app. This is consistent with the current implementation: orders
  persist a user FK and the cart is session data. The uppercase model/view
  modules are placeholders, not independent functionality.
- **Remaining:** run authenticated registration/profile/cart/checkout/order and
  repair-request flows in a disposable staging environment. Current cart and
  checkout UI are not evidence of a full customer acceptance run.

### 4. billing

- `/billing/orders/<order_number>/` is named `billing:order_invoice`. The view
  requires login and restricts the order to its customer, owning shopkeeper, or
  staff; an unrelated user cannot retrieve it.
- The template presents order/item snapshots and stored payment status/reference,
  provides print behavior, and explicitly states that it is a digital order
  receipt, not a tax invoice. It does not invent tax or discount line items.
- `billing.models` is empty; the app has no billing migration or billing table.
  The receipt is rendered from `orders.Order`, `OrderItem`, and, when captured,
  `payments.PaymentAttempt`; therefore the current digital receipt does not
  require a separate billing table.
- **Missing / blocked by database/schema and policy:** repair invoices. Booking
  rows do not contain amounts, accepted quotes, tax, or repair-payment records.
  A schema should not be invented until quote authority, customer acceptance,
  tax treatment, and payment/refund recording are defined.

### 5. reviews

- `/reviews/` exposes `reviews:customer_list`, `reviews:submit_order`,
  `reviews:submit_repair`, `reviews:shopkeeper_list`, `reviews:worker_list`,
  `reviews:moderation_queue`, and `reviews:moderate`.
- `Review` has a customer FK and exactly one of a one-to-one order or booking
  target, 1–5 rating validation/check, pending/published/rejected moderation
  state, and moderator metadata. Submission service requires the requesting
  customer to own a delivered order or a completed repair with an assigned
  worker; duplicate reviews are rejected. Staff-only moderation is required.
  Shopkeepers see published reviews for their own shop; workers need verified
  worker status to view their published repair reviews. Public product details
  calculate displayed published shop rating/count.
- `reviews.0001_initial` is applied and `reviews_review` exists. The database
  count is currently zero. Focused tests for ownership, delivery/completion,
  moderation, publication, and permissions are present but were not run.
- **Remaining:** test actual customer-to-moderation-to-public-display workflows;
  decide whether review editing, removal/appeals, or broader public repair-worker
  rating display are required.

### 6. orders and checkout

- Customer URL names include `customers:cart`, `customers:cart_add`,
  `customers:cart_update`, `customers:cart_remove`, `customers:checkout`,
  `customers:orders`, `customers:order_detail`, and `customers:order_cancel`.
  Shopkeeper order pages use the canonical owner-scoped order views and the
  `Dukandaar` facade routes.
- `CheckoutAttempt` belongs to a customer and stores a unique token/cart digest
  and payment method. `Order` belongs to customer, shop, and checkout attempt;
  `OrderItem` belongs to an order and retains product name/category/SKU/price
  snapshots. The schema has checks/indexes and protected relationships for
  commerce history.
- Checkout groups items by shop, locks/revalidates product rows, writes all
  per-shop orders/items and stock deductions in one atomic transaction, and
  persists idempotency tokens. Customer and shopkeeper order views enforce
  object ownership. Cancellation/restoration is transition-checked and
  transactional. Existing tests cover replay, stock validation, rollback,
  ownership, CSRF, and cancellation idempotency; none was run in this audit.
- `orders.0001_initial` and `orders.0002_checkoutattempt_payment_method` are
  applied. This fresh audit did not reproduce MySQL contention or run concurrent
  checkout requests. Delivery and service fees are currently zero in checkout;
  the customer-entered address/contact is stored on each per-shop order.
- **Remaining:** execute checkout and order lifecycle acceptance tests against
  isolated staging fixtures; verify MySQL/InnoDB concurrent stock behavior.
  Do not treat a source-level `select_for_update()` as empirical concurrency
  verification.

### 7. payments and refunds

- Registered payment routes include `payments:attempt`, `payments:verify`,
  `payments:start`, `payments:razorpay_webhook`,
  `payments:cancellation_queue`, and `payments:review_cancellation`.
  The resolved webhook URL is `/payments/webhook/razorpay/`.
- `PaymentAttempt` is linked to a checkout attempt and records amount/currency,
  pending/authorized/captured/failed status, and unique provider IDs.
  `payments.gateway` calls Razorpay for order creation/payment fetch and verifies
  checkout and webhook HMAC signatures. The service checks provider amount,
  currency, order identity, and event ID; captured status synchronizes linked
  orders. Customer payment pages are customer-scoped; cancellation review is
  staff-only.
- Paid cancellation creates a staff-review request. Approving it transitions
  the order to cancelled and sends a notification; it does **not** call a refund
  API. The order view explicitly tells customers a refund is not issued
  automatically. Payment status choices do not include a refund state, and no
  refund model/service/provider operation exists. The `refunded` order/payment
  enum values are not a refund workflow.
- `payments.0001_initial` and the order payment-method migration are applied.
  Payment tests use mocked provider calls and explicitly cover cancellation
  without refund. No provider credentials were read, no network/provider call was
  made, and no sandbox test was run.
- **Missing:** persisted refund requests/results, provider refund execution,
  webhook/event reconciliation for refunds, and operational/manual reconciliation
  states. Define who can authorize refunds and how partial/multi-shop refunds
  work before implementation.

### 8. wallets and payouts

- `/wallets/shopkeeper/` (`wallets:shopkeeper`) and
  `/wallets/repair-worker/` (`wallets:repair_worker`) are role-gated. Each view
  loads only the current user's wallet for that role.
- `WalletAccount` is unique per owner and role. `WalletLedgerEntry` has
  immutable-queryset/model protections, unique per-wallet reference keys, and
  entry types that anticipate credits/reservations/debits. These are ledger
  foundations only: there is no wallet service, withdrawal request model/form,
  payout endpoint, external payout integration, or reconciliation workflow.
  Repository search found no production code writing ledger entries.
- The wallet template explicitly says earnings and withdrawals are not enabled
  and does not calculate available funds. The wallet tables are applied; current
  read-only counts are zero accounts and zero entries.
- **Missing:** earning attribution/crediting, balance derivation rules,
  withdrawal authorization, payout execution/status, failed-payout handling,
  and reconciliation. These depend on payment/refund, commission, settlement,
  and bank-detail policies.

### 9. verification

- Routes are named `verification:shopkeeper_application`,
  `verification:worker_application`, `verification:admin_list`,
  `verification:admin_document`, and `verification:admin_review`.
- Applications relate to an applicant and optionally a shop; documents relate to
  an application and uploader; decisions persist reviewer/status/check fields.
  Shopkeeper application lookup is owner-scoped, worker submission requires the
  worker role, and staff-only views handle decisions and private document
  downloads. The private storage rejects direct URLs and is configured outside
  the public media root.
- Shop listing eligibility requires an approved application, verified phone,
  and approved Aadhaar or PAN status. Worker eligibility requires approved
  worker status, verified phone, and verified face status. Review is a manual
  staff-entered decision; no phone OTP, Aadhaar/PAN authority, bank validation,
  or face-matching provider is integrated. The statuses are recorded assertions,
  not external identity verification.
- `verification.0001_initial` and `0002` are applied. Tests exist for private
  document access, owner scoping, phone verification, staff review, and
  notifications, but were not run.
- **Remaining:** define which checks are manual versus provider-backed, then
  test evidence upload/review/resubmission in staging. Avoid presenting
  staff-entered check statuses as third-party verified identity.

### 10. notifications

- Routes are `notifications:inbox`, `notifications:mark_read`, and
  `notifications:mark_all_read`. Inbox and updates are authenticated and
  recipient-scoped; read mutations require POST.
- `Notification` has recipient, unique per-recipient event key, destination,
  created/read timestamps, and an inbox index. `create_notification` requires
  an enclosing transaction, allowlists route destinations/argument counts, and
  resolves local route names; business events call it from order, booking,
  verification, payment-cancellation, and review workflows. The context
  processor supplies unread count.
- The database migration is applied. The implementation is in-app only; there
  is no email/SMS/push delivery adapter, retry queue, or realtime delivery.
  Tests exist for ownership, idempotency, POST/CSRF, unread count, and
  transaction requirements, but were not run.

### 11. iFixit-inspired repair guides, categories, parts and Q&A

- `/repair-guides/` provides named home/category/guide/question/answer/report/
  moderation routes. Models cover categories/subcategories, guides and ordered
  steps, guide resources (tool/part/material) with an optional FK to
  `products.Product`, feedback, questions, answers, votes, reports, and
  moderation events.
- Published-content checks and staff moderation are implemented. Guide
  contribution requires an active user in the `Repair Guide Contributor` group
  or staff; unpublished content is restricted to the owner/staff. Resource and
  question product choices are filtered to marketable, in-stock products.
  Product association does not establish device/part compatibility; the model's
  compatibility flag defaults false.
- `repair_guides.0001_initial` is applied, and the live database has 16
  categories but zero guides, questions, and answers. Thus route/schema support
  exists, but there is no authored guide or community content available to a
  customer now. Repair Guides tests exist for routes, search, permissions,
  moderation, and Q&A behaviors; they were not run.
- **Missing:** persisted FAQ content and a browsable expert/worker availability
  directory. Compatibility certification and a curated parts catalogue are not
  established by the present product FK.

### 12. Frontend, CSS, JavaScript, uploads, testing and deployment

- Inventory found 57 HTML templates (including the two payment templates), 14
  CSS files, and 10 JavaScript files. `base/base.html` provides responsive
  viewport metadata, role navigation, skip link, shared navigation/media
  scripts, and per-page asset blocks. Role styles exist for customer,
  shopkeeper, repair worker, admin, reviews, billing, and repair guides.
  Feature JavaScript includes navigation/tabs, catalog discovery, image
  previews/fallbacks, and print receipt. The repair-guide and commerce pages are
  templated, but no browser rendering or accessibility acceptance run was done.
- Upload forms validate decoded JPEG/PNG/WebP images, size, dimensions and
  animation; document validation allows bounded PDF or supported images.
  Templates use multipart forms and connect the upload-preview script.
  Verification documents and booking/profile images use private storage and
  authenticated authorization views. Shop/product media uses public media
  configuration; upload lifecycle signals schedule replaced/deleted file
  cleanup on transaction commit. No live file-storage/upload/delete workflow
  was exercised.
- Test modules exist across accounts, bookings, orders, billing, payments,
  reviews, wallets, verification, notifications, and repair guides; facade
  route tests exist for `Customer`, `Repair`, and `Dukandaar`. Tests were
  inspected but not executed under the no-database-change requirement.
- Fresh validation: `manage.py check` passed with no issues;
  `manage.py check --database default` passed with no issues; and
  `makemigrations --check --dry-run` reported **No changes detected**.
  `manage.py showmigrations --plan` showed no pending migrations. These checks
  do not substitute for the test suite or browser workflows.
- `manage.py check --deploy` completed with six deployment warnings:
  `security.W004` (no HSTS seconds), `W008` (SSL redirect not enabled),
  `W009` (configured `SECRET_KEY` fails Django's strength check), `W012`
  (session cookie not secure), `W016` (CSRF cookie not secure), and `W018`
  (`DEBUG=True` in the active environment). The key value was not displayed or
  read directly.
- Project settings define a static source directory but no `STATIC_ROOT` was
  found. The project directory has `requirements-before-fix.txt`, but no
  canonical `requirements.txt`/lock, Docker/Compose file, or `Procfile` was
  found. No deployment pipeline or production static/media/web-server
  configuration was verified.
- **Remaining:** resolve deployment warnings for the intended HTTPS topology,
  establish supported dependency/deployment configuration, configure static
  collection and media/private-media storage, then run browser, upload, and
  provider acceptance tests in a dedicated staging environment.

## Database and migration status

Read-only commands used the configured database named `beni_db`. The migration
plan showed all 37 recorded migrations applied, including:

- `accounts.0001_initial`, `accounts.0002_profile_alternate_phone_profile_phone_and_more`
- `bookings.0001_initial` through `bookings.0003_repairbooking_locality_and_more`
- `notifications.0001_initial`
- `shops.0001_initial` through `shops.0003_shopbankdetails_shopphoto`
- `products.0001_initial`, `products.0002_alter_product_image_productimage`
- `orders.0001_initial`, `orders.0002_checkoutattempt_payment_method`
- `payments.0001_initial`
- `repair_guides.0001_initial`
- `reviews.0001_initial`
- `verification.0001_initial`, `verification.0002_alter_verificationapplication_status_and_more`
- `wallets.0001_initial`
- Django auth, contenttypes, admin, and sessions migrations.

The configured database reported 47 tables. The domain table inventory included
the booking, notification, shop, product, order, payment, repair-guide, review,
verification, and wallet tables. No `billing_*` table exists because billing has
no models/migration; no `workers_*` table exists because `workers` has no domain
model. The uppercase facade apps and custom `customers` app also have no
domain-specific migration tables.

**Schema conclusion:** no pending migration was reported, Django found no
model-to-migration drift, and the configured-database system check passed.
Existing applied schema supports the current persisted workflows. New repair
invoice/refund/payout workflows are not presently represented by a complete
schema. No schema was changed during this audit.

### Stale-document conflict

Some implementation notes dated 2026-10-19 describe the repair-guide migration
as pending and/or reflect earlier app-registration states. The fresh live
recorder now reports `repair_guides.0001_initial` applied, the guide tables are
present, and the uppercase facades are installed and route-resolved. This report
records the fresh observations; older statements should not be treated as current
database evidence.

## Errors, blockers, and unverified claims

1. **Production readiness blocker:** six `check --deploy` warnings listed above,
   notably the active `DEBUG=True` and `SECRET_KEY` strength warning.
2. **Refund blocker:** staff approval cancels a paid order but does not return
   funds; no refund API or persisted refund lifecycle is present.
3. **Payout blocker:** the wallet is a read-only ledger foundation; the UI
   explicitly disables earnings and withdrawals.
4. **Repair invoice blocker:** booking data has no amount/quote/tax/payment
   basis, and no repair invoice schema exists.
5. **Content readiness gap:** 16 repair-guide categories exist, but guides,
   questions, and answers are empty in the inspected database.
6. **Unverified runtime behavior:** tests, authenticated workflows, MySQL
   concurrency, real uploads, Razorpay sandbox/webhooks, and browser
   presentation were not run. No conclusion that these end-to-end workflows
   work should be inferred from templates, source code, or test names.

## Recommended implementation order

1. **Make a safe staging/deployment baseline.** Resolve runtime deployment
   settings against the intended HTTPS/reverse-proxy topology, use a strong
   private secret, set production `DEBUG=False`, configure secure cookies/HSTS
   only after HTTPS is confirmed, and define static/private-media handling and
   dependency installation.  
   **Dependencies:** none; do this before public deployment or live acceptance.

2. **Define and implement refund lifecycle.** Set cancellation/refund policy
   (full/partial, per-order/per-checkout, authorization and timing); persist
   refund request/provider results; add idempotent provider operation and
   webhook/reconciliation handling. Keep staff cancellation review separate
   from a claimed refund until the provider confirms it.  
   **Dependencies:** existing orders/payment attempts; provider sandbox
   configuration and agreed refund policy.

3. **Implement earning settlement and payouts.** Define commissions, when
   shop/worker earnings become payable, reserve/release rules, payout state,
   failed payouts, and reconciliation; then add write-side wallet services and
   authorized payout workflows on the immutable ledger.  
   **Dependencies:** payment/refund accounting from task 2, approved earning
   rules, and a secure bank-details/payout-data policy.

4. **Design and implement priced repair quotes and repair invoices.** Specify
   who can quote, customer acceptance, labor/parts, tax, disputes, payment,
   cancellation, and refund behavior. Only then add repair quote/invoice
   schema and views tied to bookings and the payment/refund lifecycle.  
   **Dependencies:** existing booking workflow plus agreed pricing/tax rules
   and payment/refund decisions from task 2; review each migration before
   applying it.

5. **Run isolated end-to-end acceptance and concurrency verification.** Use a
   disposable database/staging deployment to exercise customer, shopkeeper,
   repair-worker, staff, verification, private upload, order, payment, refund,
   wallet, and guide flows; run targeted/full tests and MySQL concurrency checks
   without production credentials or data.  
   **Dependencies:** staging baseline from task 1; tasks 2–4 for their new
   financial/repair paths. Existing-source smoke tests can be scheduled earlier
   in a disposable environment, but must not target `beni_db`.

**Audit boundary maintained:** no application code, migration, dependency,
settings, or database changes were made. The only requested deliverable from this
audit is this status report.
