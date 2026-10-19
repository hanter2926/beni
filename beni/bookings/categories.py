REPAIR_CATEGORIES = (
    {
        'name': 'Mobile repair',
        'keywords': ('mobile', 'phone', 'smartphone'),
        'description': 'Screen, battery, charging, and other mobile device problems.',
    },
    {
        'name': 'Laptop repair',
        'keywords': ('laptop', 'notebook', 'computer'),
        'description': 'Hardware, performance, display, and software troubleshooting.',
    },
    {
        'name': 'Electronics repair',
        'keywords': ('electronics', 'electronic', 'tv', 'television'),
        'description': 'Help with household electronics and electronic devices.',
    },
    {
        'name': 'Other repairs',
        'keywords': ('appliance', 'repair', 'service'),
        'description': 'Describe your issue and BENI will route it to a suitable worker.',
    },
)

REPAIR_CATEGORY_CHOICES = tuple(
    (category['name'], category['name'])
    for category in REPAIR_CATEGORIES
)
