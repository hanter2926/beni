# BENI Project Audit Report

Date: 2026-10-18
Scope: read-only repository audit of the existing Django project. No migrations, database resets, schema changes, or destructive commands were run.

## Executive summary

This repository is a partially implemented Django marketplace/repair platform. The project has a working foundation for authentication, basic role-based dashboards, shop ownership, and public product catalog browsing. However, the broader BENI business workflow described in the project brief is not yet implemented: the order, cart, checkout, payment, wallet, repair booking, verification, review, notification, and admin management modules remain largely scaffolded or empty.

Evidence from the codebase and test run:
- `python manage.py test --verbosity 1` executed successfully.
- Result: 32 tests ran and passed (`OK`).
- This confirms the implemented baseline features are working, but it does not indicate the full Phase II–VIII product requirements are complete.

## 1. Existing working features

### Authentication and access control
- `beni/beni/settings.py` registers the Django auth stack and BENI apps.
- `beni/accounts/urls.py` includes `login`, `register`, and `logout` routes.
- `beni/accounts/views.py` implements registration and redirect logic.
- `beni/accounts/roles.py` defines role checks using Django groups:
  - `Shopkeeper`
  - `Repair Worker`
- `beni/accounts/management/commands/create_role_groups.py` creates the required groups and refuses case-colliding duplicates.
- `beni/dashboard/views.py` enforces login and role-based access for:
  - customer workspace
  - shopkeeper workspace
  - repair worker workspace
  - admin workspace
- Route permissions and redirect behavior are covered in `beni/dashboard/tests.py` and `beni/accounts/tests.py`.

### Shop and product domain
- `beni/shops/models.py` defines a `Shop` model with ownership, geolocation validation, and DB constraints.
- `beni/products/models.py` defines a `Product` model with price and stock validation and per-shop SKU uniqueness.
- `beni/shops/views.py` provides shop list/create/update with owner scoping.
- `beni/products/views.py` provides product list/create/update scoped to the signed-in shop owner.
- `beni/shops/forms.py` and `beni/products/forms.py` style and validate fields for shop/product management.
- `beni/products/public_urls.py` exposes a public product catalog and product detail route.
- `beni/products/views.py` includes public catalog filtering by search and category.

### UI/workspace scaffolding
- `beni/templates/base/base.html` provides the shared shell navigation and layout.
- Templates exist for:
  - auth login/register
  - customer dashboard
  - shopkeeper dashboard
  - admin panel dashboard
  - shopkeeper product/shop management
  - customer catalog pages
- `beni/static/css` and `beni/static/js` include starter assets for these views.

### Existing test coverage
The repository includes app-level tests for:
- auth flows, redirects, and CSRF behavior
- dashboard access permissions
- shop ownership and coordinate validation
- product validation and owner-scoped access
- public catalog visibility and filtering

## 2. Missing features

The project brief includes many missing or not-yet-wired features across the platform. The following major areas are not implemented or only scaffolded:

### Core commerce lifecycle
- `beni/orders/models.py` is empty.
- `beni/orders/views.py` is empty.
- No cart, checkout, order items, order status transitions, invoice generation, or order history exists.
- No order-number generation or order-price snapshot logic.

### Payment and billing
- `beni/payments/models.py` is empty.
- `beni/payments/views.py` is empty.
- `beni/billing/models.py` is empty.
- `beni/billing/views.py` is empty.
- No payment gateway integration, webhook handling, idempotency, or duplicate-payment prevention is present.

### Wallet and financial ledger
- `beni/wallets/models.py` is empty.
- `beni/wallets/views.py` is empty.
- No immutable or auditable wallet ledger, withdrawal flow, transaction references, or balance reconciliation is implemented.

### Repair and booking workflows
- `beni/bookings/models.py` is empty.
- `beni/bookings/views.py` is empty.
- `beni/workers/models.py` is empty.
- `beni/workers/views.py` is empty.
- No worker profile, skill set, availability, repair booking accept/reject workflow, inspection reports, or completion lifecycle is implemented.

### Reviews, notifications, verification
- `beni/reviews/models.py` is empty.
- `beni/reviews/views.py` is empty.
- `beni/notifications/models.py` is empty.
- `beni/notifications/views.py` is empty.
- `beni/verification/models.py` is empty.
- `beni/verification/views.py` is empty.
- No review editing window or verification workflows exist.

### Customer profile / account settings
- `beni/accounts/models.py` is empty.
- No profile models or account settings pages exist.
- The app relies on the default Django user model and role groups, not on a richer customer profile model.

## 3. Partially implemented features

These areas exist but are not complete enough for the full platform brief:

### Dashboard UX
The role dashboards in `beni/templates/customer/dashboard.html`, `beni/templates/shopkeeper/dashboard.html`, and `beni/templates/admin_panel/dashboard.html` are mostly placeholders. They describe future features such as:
- product/order workflow
- repair workflow
- review workflow
- admin operations

The templates explicitly say that these areas are “not connected” or “pending”.

### Public catalog
The public catalog works for active shops/products, but it is a narrow storefront layer only. It does not include:
- cart
- checkout
- favorites
- customer order history
- review display
- category filters beyond simple list views

### Shopkeeper product management
This area is functional for a basic CRUD workflow, but it does not include:
- inventory validation beyond model checks
- stock adjustments history
- order fulfillment integration
- customer feedback or shop rating surfaces

## 4. Bugs and security risks

### Security and configuration issues
- `beni/beni/settings.py` uses `DEBUG = True`.
- `SECRET_KEY` is hard-coded in source.
- `ALLOWED_HOSTS = []` leaves the app unprepared for deployment.
- Database credentials are embedded in `settings.py` (`root` / password string), which is a security risk if this file is committed or shared.
- Media uploads are enabled without any evidence of validation or access restrictions.

### Architectural and maintenance risks
- The repo contains multiple legacy or duplicated app folders such as:
  - `beni/Customer/`
  - `beni/Dukandaar/`
  - `beni/Repair/`
  These are not registered in `INSTALLED_APPS`, which makes them dead or legacy code paths.
- Multiple installed apps are present but empty or nearly empty (`customers`, `orders`, `workers`, `billing`, `wallets`, `payments`, `reviews`, `notifications`, `verification`), indicating incomplete domain modeling.
- `beni/beni/urls.py` includes only a subset of project routes. There are no order, payment, wallet, booking, review, or verification URLs wired into the main URLConf.
- Several apps still have placeholder files with `# Create your models here.` or `# Create your views here.` comments.

### Data integrity/security concerns for the future
- No custom user profile model or restricted account model is present.
- No explicit wallet ledger immutability strategy is implemented.
- No payment-handoff or webhook validation flow is present.
- No consent or location privacy safeguards are present for repair workers or customers.
- No role-scoped data isolation beyond basic group checks is implemented for the missing modules.

## 5. Database and migration discrepancies

### Actual migration state
The following app-level migrations exist:
- `beni/shops/migrations/0001_initial.py`
- `beni/products/migrations/0001_initial.py`

### Missing schema coverage
The following major domains do not have migrations in the repository, despite being listed in `INSTALLED_APPS`:
- `accounts`
- `customers`
- `orders`
- `workers`
- `bookings`
- `billing`
- `wallets`
- `payments`
- `reviews`
- `notifications`
- `verification`
- `dashboard`

This means the schema for the platform’s critical business functions is not yet defined in the database layer. In a real production setup, this would require a controlled migration plan before feature work begins.

## 6. Dependencies between incomplete features

The missing features are tightly coupled:
- Order creation depends on product stock and cart logic.
- Payment processing depends on order state and wallet or payment-transactions models.
- Wallet changes depend on immutable ledger entries and reconciliation.
- Repair worker workflow depends on booking + worker + verification + notification models.
- Review flows depend on order or booking completion and user identity checks.
- Admin monitoring depends on orders, wallets, verification, and review records.

The implementation order matters: without the data model and state machine for orders and payments, the rest of the workflow cannot safely be built.

## 7. Recommended implementation order

1. Finalize the data model and migration plan
   - accounts/customer profile
   - shops/products
   - orders/order items
   - wallets and ledger
   - payments/billing
   - repair bookings and workers
   - verification and reviews
   - notifications

2. Implement core state machines and integrity rules
   - order statuses
   - payment statuses
   - wallet balances and ledger immutability
   - repair lifecycle transitions

3. Build checkout and payment flow
   - cart
   - order creation
   - price snapshots
   - tax and delivery calculations
   - payment transaction record creation
   - idempotent webhook handling

4. Implement repair workflows
   - booking requests and status transitions
   - worker scheduling and skill matching
   - arrival and inspection workflow
   - bill approval/dispute process

5. Add verification and notification layers
   - phone verification
   - shop and worker verification
   - notification event publishing and delivery

6. Implement admin and moderation views
   - user management
   - verification queues
   - orders and disputes
   - wallet reviews and withdrawals
   - reporting and audit log surfaces

7. Polish and harden the app
   - responsive UI
   - API/admin review security
   - audit trail
   - safe configuration for deployment

## 8. Exact files likely to require changes for the next implementation phase

### Core project config
- `beni/beni/settings.py`
- `beni/beni/urls.py`

### Authentication and access
- `beni/accounts/models.py`
- `beni/accounts/views.py`
- `beni/accounts/forms.py`
- `beni/accounts/roles.py`
- `beni/accounts/management/commands/create_role_groups.py`

### Shop and product domain
- `beni/shops/models.py`
- `beni/shops/views.py`
- `beni/shops/forms.py`
- `beni/products/models.py`
- `beni/products/views.py`
- `beni/products/forms.py`
- `beni/products/public_urls.py`

### Missing domain modules
- `beni/orders/models.py`
- `beni/orders/views.py`
- `beni/payments/models.py`
- `beni/payments/views.py`
- `beni/billing/models.py`
- `beni/billing/views.py`
- `beni/wallets/models.py`
- `beni/wallets/views.py`
- `beni/bookings/models.py`
- `beni/bookings/views.py`
- `beni/workers/models.py`
- `beni/workers/views.py`
- `beni/reviews/models.py`
- `beni/reviews/views.py`
- `beni/notifications/models.py`
- `beni/notifications/views.py`
- `beni/verification/models.py`
- `beni/verification/views.py`

### Templates and frontend
- `beni/templates/base/base.html`
- `beni/templates/auth/login.html`
- `beni/templates/auth/register.html`
- `beni/templates/customer/dashboard.html`
- `beni/templates/shopkeeper/dashboard.html`
- `beni/templates/admin_panel/dashboard.html`
- `beni/templates/customer/catalog/list.html`
- `beni/templates/customer/catalog/detail.html`
- `beni/static/css/**`
- `beni/static/js/**`

## Final assessment

The repository is in a strong partial-start state for a Django marketplace product, with working role access and foundational shop/product logic. The core project foundation is in place, and the baseline test suite passes. However, the full BENI platform described in the brief is not yet implemented. The main missing work is not a bug in the current skeleton; it is a large set of business domains that are still unmodeled or unconnected.

Recommended next step: treat this as a staged implementation project, starting with the data model and migration plan for orders, wallet/payment, repair workflows, verification, notifications, and admin operational records before building the rest of the user-facing workflows.
