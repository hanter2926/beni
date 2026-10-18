# BENI image asset inventory

The `beni_separate_images/` tree contains 66 readable JPEG/PNG images in 10
subfolders (plus the directory root). Every image was decoded and visually
reviewed. No corrupt or unsupported image files were found; all are RGB.

The organized subfolder path is preferred in templates. Flat root files are
legacy aliases or alternate versions and are preserved in place. The paths
below include every file in the asset tree.

## Inventory

| Relative path(s) | Type and dimensions | Likely purpose |
| --- | --- | --- |
| `banner_deals.jpg`; `banners/deals.jpg` | JPEG, 330 x 107 | Promotional artwork; not used because its discount claim is not verified. |
| `banner_delivery.jpg`; `banners/delivery.jpg` | JPEG, 294 x 107 | Delivery artwork; not used because delivery claims are not verified. |
| `banner_payment.jpg`; `banners/payment.jpg` | JPEG, 284 x 107 | Payment artwork; not used because it implies secure payment behavior that is not implemented. |
| `category_appliances.png`; `category/appliances.png` | PNG, 193 x 156 | Appliance category tile; organized image used in the catalog. |
| `category_beauty.png`; `category/beauty.png` | PNG, 174 x 156 | Beauty category tile; organized image used in the catalog. |
| `category_ecommerce.png`; `category/ecommerce.png` | PNG, 170 x 156 | Generic marketplace/category fallback; used for other free-text catalog categories and registration artwork. |
| `category_electronics.png`; `category/electronics.png` | PNG, 171 x 156 | Electronics category tile; organized image used in the catalog. |
| `category_fashion.png`; `category/fashion.png` | PNG, 173 x 156 | Fashion category tile; organized image used in the catalog. |
| `category_home.png`; `category/home.png` | PNG, 190 x 156 | Home category tile; organized image used in the catalog. |
| `category_sports.png`; `category/sports.png` | PNG, 176 x 156 | Sports category tile; organized image used in the catalog. |
| `category_tools.png`; `category/tools.png` | PNG, 172 x 156 | Tools category tile; organized image used in the catalog. |
| `error_404.png`; `errors/404.png` | PNG, 285 x 107 | Not-found page illustration; organized image used by the custom 404 template. |
| `hero_admin_banner.jpg`; `hero/admin-banner.jpg` | JPEG, 323 x 250 | Administration dashboard artwork; organized image used on the admin dashboard. |
| `hero_home_banner.jpg`; `hero/home-banner.jpg` | JPEG, 462 x 250 | Marketplace artwork; organized image used on the customer dashboard and sign-in page. |
| `hero_repair_banner.jpg`; `hero/repair-banner.jpg` | JPEG, 284 x 250 | Repair-service banner; organized image used on the customer repair request form beside the existing booking workflow. |
| `hero_shop_banner.jpg`; `hero/shop-banner.jpg` | JPEG, 416 x 250 | Shopkeeper dashboard artwork; organized image used on that dashboard. |
| `icon_like.png`; `icons/like.png` | PNG, 158 x 130 | Like/favorite icon; not used because no matching favorite workflow is established. |
| `icon_notification.png`; `icons/notification.png` | PNG, 157 x 130 | Notification icon with a baked-in count; not used for live notification counts. |
| `icon_secure.png`; `icons/secure.png` | PNG, 149 x 130 | Security/payment icon; not used to imply unimplemented payment security. |
| `icon_star.png`; `icons/star.png` | PNG, 128 x 130 | Rating icon; not used as a live rating indicator. |
| `placeholder_no_image.png`; `placeholders/no-image.png` | PNG, 251 x 107 | Missing-product-image placeholder; organized image used wherever an uploaded product image is absent. |
| `product_backpack.jpg`; `product/backpack.jpg` | JPEG, 183 x 150 | Backpack example image; not assigned to inventory records. |
| `product_headphones.jpg`; `product/headphones.jpg` | JPEG, 182 x 150 | Headphones example image; not assigned to inventory records. |
| `product_laptop.jpg`; `product/laptop.jpg` | JPEG, 208 x 150 | Laptop example image; not assigned to inventory records. |
| `product_powerbank.jpg`; `product/powerbank.jpg` | JPEG, 176 x 150 | Power-bank example image; not assigned to inventory records. |
| `product_shoes.jpg`; `product/shoes.jpg` | JPEG, 186 x 150 | Shoes example image; not assigned to inventory records. |
| `product_smartphone.jpg`; `product/smartphone.jpg` | JPEG, 176 x 150 | Smartphone example image; not assigned to inventory records. |
| `product_smartwatch.jpg`; `product/smartwatch.jpg` | JPEG, 175 x 150 | Smartwatch example image; not assigned to inventory records. |
| `product_waterbottle.jpg`; `product/waterbottle.jpg` | JPEG, 128 x 150 | Water-bottle example image; not assigned to inventory records. |
| `repair_workshop.png`; `repair/workshop.jpg` | PNG and JPEG, 173 x 145 | Workshop/repair illustration; organized image used on customer repair pages. |
| `shop_shop.png`; `shops/shop.jpg` | PNG and JPEG, 244 x 145 | Generic storefront illustration; organized image used on the shopkeeper's shops page. |
| `worker_technician.png`; `workers/technician.jpg` | PNG and JPEG, 201 x 145 | Generic technician illustration; organized image used on the Repair Worker dashboard. |
| `worker_worker.png`; `workers/worker.jpg` | PNG and JPEG, 188 x 145 | Generic repair-worker illustration; organized image used on repair details and worker job pages. |

## Duplicate and variant notes

SHA-256 comparison found 14 exact duplicate pairs: the eight category pairs,
the 404 pair, four icon pairs, and the no-image placeholder pair. The
organized and flat versions of the banner and product images are visually
similar but are not byte-identical; the repair, shop, and worker flat files
are PNG variants of their organized JPEG counterparts. Keep all originals.

## Integration status

The 18 distinct files referenced by templates are:

- `category/appliances.png`, `category/beauty.png`,
  `category/ecommerce.png`, `category/electronics.png`,
  `category/fashion.png`, `category/home.png`, `category/sports.png`,
  `category/tools.png`
- `errors/404.png`
- `hero/admin-banner.jpg`, `hero/home-banner.jpg`,
  `hero/repair-banner.jpg`, `hero/shop-banner.jpg`
- `placeholders/no-image.png`
- `repair/workshop.jpg`, `shops/shop.jpg`
- `workers/technician.jpg`, `workers/worker.jpg`

The remaining 48 files are preserved but intentionally not referenced:

- The 8 flat category PNGs, `error_404.png`, and
  `placeholder_no_image.png` are exact duplicates of their organized-folder
  counterparts.
- `banner_deals.jpg`, `banner_delivery.jpg`, `banner_payment.jpg` and the
  corresponding three files in `banners/` contain unverified promotion,
  delivery, or secure-payment claims.
- The four flat `hero_*_banner.jpg` files are alternate versions of the four
  organized hero images; the organized versions are used instead.
- All 8 root icon PNGs and all 4 `icons/` PNGs are intentionally unused:
  the notification bell has a fixed baked-in count, while like, star, and
  secure-payment symbols would imply features not established by the site.
- The 8 `product/` JPGs and their 8 flat counterparts are product examples,
  not confirmed photos of database inventory. Uploaded shopkeeper images
  remain authoritative; otherwise the neutral placeholder is shown.
- `repair_workshop.png`, `shop_shop.png`, `worker_technician.png`, and
  `worker_worker.png` are alternate-format variants; the corresponding
  organized JPEG assets are used.

## Integration notes

- Static references use paths relative to `static/`, for example
  `{% static 'image/beni_separate_images/category/appliances.png' %}`.
- Catalog categories are free text. Known category names get their matching
  illustration; unrecognized names use the generic marketplace image without
  changing the category filter behavior.
- Shopkeeper-uploaded product images remain authoritative in catalog, detail,
  cart, checkout, and shopkeeper product views. The neutral placeholder is
  shown if an upload is absent. Example product images are not assigned to
  database records without a verified product-image association.
- Category artwork is decorative alongside the category label. Other
  informative images have descriptive alternative text.
- The repair banner's baked-in booking prompt is artwork, not a clickable
  control; the actual repair request form remains the working booking action.
  Other banner artwork contains unverified discount, delivery, and secure
  payment claims and is not used.
- `static/image/` may also contain `.gitkeep` markers and this manifest; they
  are not image assets.
