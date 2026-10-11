const menuToggle = document.querySelector('.menu-toggle');
const roleNavigation = document.querySelector('#role-navigation');

if (menuToggle && roleNavigation) {
    menuToggle.addEventListener('click', () => {
        const isExpanded = menuToggle.getAttribute('aria-expanded') === 'true';
        const sideRail = roleNavigation.closest('.side-rail');
        menuToggle.setAttribute('aria-expanded', String(!isExpanded));
        sideRail?.classList.toggle('is-open', !isExpanded);
    });

    roleNavigation.addEventListener('click', (event) => {
        if (event.target instanceof Element && event.target.closest('a')) {
            menuToggle.setAttribute('aria-expanded', 'false');
            roleNavigation.closest('.side-rail')?.classList.remove('is-open');
        }
    });
}