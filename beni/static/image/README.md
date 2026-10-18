# BENI image asset manifest

No approved image files or generated image sheet were present in the repository
when this manifest was prepared. The entries below are requested filenames and
intended purposes, not files currently available. Do not reference a missing
file from a template.

## Hero images

| Filename | Intended purpose | Existing page/template | Status |
| --- | --- | --- | --- |
| `hero/home-hero.webp` | Public marketplace hero. | No public homepage exists; `/` redirects to login in `beni/urls.py`. | Missing; page integration requires a separate homepage decision. |
| `hero/customer-hero.webp` | Customer marketplace introduction. | `templates/customer/dashboard.html` | Missing; current hero is CSS artwork. |
| `hero/shop-hero.webp` | Shopkeeper introduction. | `templates/shopkeeper/dashboard.html` | Missing; current workspace uses CSS styling. |
| `hero/repair-hero.webp` | Repair-service introduction. | `templates/customer/repairs/form.html` | Missing; no repair hero image exists. |

## Category illustrations

These are generic illustrations, not proof of inventory or supported fixed
categories. `Product.category` is free text and the catalog selector is
database-driven; confirm the actual category taxonomy before presenting these
as selectable categories.

| Filename | Intended purpose | Existing page/template | Status |
| --- | --- | --- | --- |
| `categories/hardware.webp` | Generic hardware category illustration. | `templates/customer/catalog/list.html` (no category tiles) | Missing; category taxonomy needs confirmation. |
| `categories/electrical.webp` | Generic electrical category illustration. | `templates/customer/catalog/list.html` (no category tiles) | Missing; category taxonomy needs confirmation. |
| `categories/plumbing.webp` | Generic plumbing category illustration. | `templates/customer/catalog/list.html` (no category tiles) | Missing; category taxonomy needs confirmation. |
| `categories/tools.webp` | Generic tools category illustration. | `templates/customer/catalog/list.html` (no category tiles) | Missing; category taxonomy needs confirmation. |
| `categories/appliances.webp` | Generic appliances category illustration. | `templates/customer/catalog/list.html` (no category tiles) | Missing; category taxonomy needs confirmation. |
| `categories/home-repair.webp` | Generic home-repair category illustration. | `templates/customer/catalog/list.html` (no category tiles) | Missing; category taxonomy needs confirmation. |
| `categories/painting.webp` | Generic painting category illustration. | `templates/customer/catalog/list.html` (no category tiles) | Missing; category taxonomy needs confirmation. |
| `categories/carpentry.webp` | Generic carpentry category illustration. | `templates/customer/catalog/list.html` (no category tiles) | Missing; category taxonomy needs confirmation. |

## Product images

These names describe specific product types, but must not be used as if they
were photographs of actual available inventory. Product cards, details, and
cart items must continue to use Shopkeeper-uploaded product images; a neutral
placeholder may be used only after it is supplied and reviewed.

| Filename | Intended purpose | Existing page/template | Status |
| --- | --- | --- | --- |
| `products/smartphone.webp` | Product-type artwork only, not an inventory photo. | `templates/customer/catalog/list.html`, `templates/customer/catalog/detail.html` | Missing; do not substitute for uploaded item images. |
| `products/headphones.webp` | Product-type artwork only, not an inventory photo. | Catalog list/detail | Missing; do not substitute for uploaded item images. |
| `products/laptop.webp` | Product-type artwork only, not an inventory photo. | Catalog list/detail | Missing; do not substitute for uploaded item images. |
| `products/smartwatch.webp` | Product-type artwork only, not an inventory photo. | Catalog list/detail | Missing; do not substitute for uploaded item images. |
| `products/powerbank.webp` | Product-type artwork only, not an inventory photo. | Catalog list/detail | Missing; do not substitute for uploaded item images. |
| `products/toolkit.webp` | Product-type artwork only, not an inventory photo. | Catalog list/detail | Missing; do not substitute for uploaded item images. |
| `products/water-bottle.webp` | Product-type artwork only, not an inventory photo. | Catalog list/detail | Missing; do not substitute for uploaded item images. |
| `products/backpack.webp` | Product-type artwork only, not an inventory photo. | Catalog list/detail | Missing; do not substitute for uploaded item images. |

## Shops, workers, and repairs

| Filename | Intended purpose | Existing page/template | Status |
| --- | --- | --- | --- |
| `shops/local-shop.webp` | Generic local shop illustration, not a specific merchant. | `templates/shopkeeper/shops/list.html` | Missing; current cards are text-based. |
| `shops/shopkeeper.webp` | Generic shopkeeper introduction illustration, not a real person. | `templates/shopkeeper/dashboard.html` | Missing. |
| `workers/repair-worker.webp` | Generic Repair Worker introduction illustration, not a real person. | `templates/repair_worker/dashboard.html`, `templates/customer/repairs/detail.html` | Missing. |
| `workers/technician.webp` | Generic technician illustration, not a real person. | Existing repair pages; no profile-photo component found. | Missing; no individual profile-photo use should be implied. |
| `repairs/workshop.webp` | Generic workshop illustration. | `templates/customer/repairs/form.html`, `templates/customer/repairs/detail.html` | Missing. |

## Banners, placeholders, and errors

| Filename | Intended purpose | Existing page/template | Status |
| --- | --- | --- | --- |
| `banners/secure-payment.webp` | Decorative payment-related banner only after payment behavior and placement are approved. | No payment page or payment workflow found. | Missing; do not imply secure/verified payment processing. |
| `banners/delivery.webp` | Decorative delivery illustration, not proof of delivery. | `templates/customer/orders/detail.html` | Missing; delivery completion is not customer-confirmed in current source. |
| `banners/special-deals.webp` | Promotion artwork for a real approved promotion. | No promotion page/section found. | Missing; no offer or pricing claim may be invented. |
| `banners/no-image.webp` | Neutral missing-image placeholder. | Existing product-image fallback locations after review. | Missing; existing CSS/text fallbacks remain. |
| `placeholders/empty-cart.webp` | Decorative empty-cart illustration. | `templates/customer/cart.html` | Missing; existing text/CSS empty state remains. |
| `placeholders/empty-orders.webp` | Decorative empty-orders illustration. | `templates/customer/orders/list.html` | Missing; existing text/CSS empty state remains. |
| `placeholders/empty-notifications.webp` | Decorative empty-notifications illustration. | `templates/notifications/inbox.html` | Missing; existing text/CSS empty state remains. |
| `errors/404.webp` | Decorative not-found illustration. | No custom 404 template found. | Missing; no custom error page to integrate. |

## Current project integration facts

- `beni/settings.py` configures `STATIC_URL = "static/"` and
  `STATICFILES_DIRS = [BASE_DIR / "static"]`; this supports paths such as
  `{% static 'image/hero/customer-hero.webp' %}` once an asset exists.
- The project root route redirects to `accounts:login`; there is no standalone
  public homepage template to receive `home-hero.webp`.
- The product catalog and detail templates display uploaded product images
  from media storage when available and use existing non-image fallbacks
  otherwise. Preserve this database-driven behavior.
- No review page, public worker profile page, payment workflow, promotion
  section, or custom 404 page was found in the inspected templates/routes.
- `static/image/` directories are source-controlled with `.gitkeep` markers.
  These markers and this manifest are not image assets.
- No image generation capability or approved local image asset was available
  during this task. No image files were generated, copied, or downloaded.
