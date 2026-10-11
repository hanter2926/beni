const adminTabs = [...document.querySelectorAll('.admin-tabs [role="tab"]')];

function selectAdminTab(selectedTab, moveFocus = false) {
    adminTabs.forEach((tab) => {
        const selected = tab === selectedTab;
        tab.setAttribute('aria-selected', String(selected));
        tab.tabIndex = selected ? 0 : -1;
        document.getElementById(tab.getAttribute('aria-controls')).hidden = !selected;
    });
    if (moveFocus) selectedTab.focus();
}

adminTabs.forEach((tab, index) => {
    tab.addEventListener('click', () => selectAdminTab(tab));
    tab.addEventListener('keydown', (event) => {
        if (!['ArrowLeft', 'ArrowRight', 'Home', 'End'].includes(event.key)) return;
        event.preventDefault();
        const nextIndex = event.key === 'Home' ? 0
            : event.key === 'End' ? adminTabs.length - 1
                : (index + (event.key === 'ArrowRight' ? 1 : -1) + adminTabs.length) % adminTabs.length;
        selectAdminTab(adminTabs[nextIndex], true);
    });
});