const menuToggle = document.querySelector('.menu-toggle');
const roleNavigation = document.querySelector('#role-navigation');
const navigationBackdrop = document.querySelector('.navigation-backdrop');
const accountMenus = [...document.querySelectorAll('.account-menu')];

if (menuToggle && !roleNavigation) {
    menuToggle.remove();
}

if (menuToggle && roleNavigation) {
    const navigationLinks = roleNavigation.querySelectorAll('a');
    const closeNavigation = () => {
        menuToggle.setAttribute('aria-expanded', 'false');
        menuToggle.setAttribute('aria-label', 'Open workspace navigation');
        roleNavigation.classList.remove('is-open');
        if (navigationBackdrop) navigationBackdrop.hidden = true;
    };

    menuToggle.addEventListener('click', () => {
        const isExpanded = menuToggle.getAttribute('aria-expanded') === 'true';
        menuToggle.setAttribute('aria-expanded', String(!isExpanded));
        menuToggle.setAttribute('aria-label', isExpanded ? 'Open workspace navigation' : 'Close workspace navigation');
        roleNavigation.classList.toggle('is-open', !isExpanded);
        if (navigationBackdrop) navigationBackdrop.hidden = isExpanded;
        if (!isExpanded) navigationLinks[0]?.focus();
    });

    roleNavigation.addEventListener('click', (event) => {
        if (event.target instanceof Element && event.target.closest('a')) {
            closeNavigation();
        }
    });

    document.addEventListener('keydown', (event) => {
        if (event.key === 'Escape' && menuToggle.getAttribute('aria-expanded') === 'true') {
            closeNavigation();
            menuToggle.focus();
        }
    });

    document.addEventListener('click', (event) => {
        if (
            menuToggle.getAttribute('aria-expanded') === 'true'
            && event.target instanceof Node
            && !roleNavigation.contains(event.target)
            && !menuToggle.contains(event.target)
        ) {
            closeNavigation();
        }
    });

    navigationBackdrop?.addEventListener('click', () => {
        closeNavigation();
        menuToggle.focus();
    });

    window.matchMedia('(min-width: 1024px)').addEventListener('change', (event) => {
        if (event.matches) closeNavigation();
    });
}

document.addEventListener('keydown', (event) => {
    if (event.key !== 'Escape') return;
    const openMenu = accountMenus.find((menu) => menu.open);
    if (openMenu) {
        openMenu.open = false;
        openMenu.querySelector('summary')?.focus();
    }
});

document.addEventListener('click', (event) => {
    accountMenus.forEach((menu) => {
        if (event.target instanceof Node && !menu.contains(event.target)) {
            menu.open = false;
        }
    });
});