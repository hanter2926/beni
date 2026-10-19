const customerTabs = [...document.querySelectorAll('.customer-tabs [role="tab"]')];

function selectCustomerTab(selectedTab, moveFocus = false) {
    customerTabs.forEach((tab) => {
        const selected = tab === selectedTab;
        tab.setAttribute('aria-selected', String(selected));
        tab.tabIndex = selected ? 0 : -1;
        const panelId = tab.getAttribute('aria-controls');
        const panel = panelId ? document.getElementById(panelId) : null;
        if (panel) panel.hidden = !selected;
    });
    const selectedPanel = document.getElementById(
        selectedTab.getAttribute('aria-controls'),
    );
    if (selectedPanel && selectedPanel.id === 'panel-shops') {
        const loading = selectedPanel.querySelector('[data-shop-loading]');
        if (loading) loading.hidden = true;
        selectedPanel.removeAttribute('aria-busy');
    }
    const url = new URL(window.location.href);
    url.searchParams.set('tab', selectedTab.id.replace('tab-', ''));
    window.history.replaceState({}, '', url);
    if (moveFocus) selectedTab.focus();
}

customerTabs.forEach((tab, index) => {
    tab.addEventListener('click', () => selectCustomerTab(tab));
    tab.addEventListener('keydown', (event) => {
        if (!['ArrowLeft', 'ArrowRight', 'Home', 'End'].includes(event.key)) return;
        event.preventDefault();
        const nextIndex = event.key === 'Home' ? 0
            : event.key === 'End' ? customerTabs.length - 1
                : (index + (event.key === 'ArrowRight' ? 1 : -1) + customerTabs.length) % customerTabs.length;
        selectCustomerTab(customerTabs[nextIndex], true);
    });
});

const shopSearch = document.querySelector('[data-shop-search]');
if (shopSearch) {
    shopSearch.addEventListener('submit', () => {
        const loading = shopSearch.querySelector('[data-shop-loading]');
        if (loading) loading.hidden = false;
        const panel = document.getElementById('panel-shops');
        if (panel) panel.setAttribute('aria-busy', 'true');
    });
}

document.querySelectorAll('[data-repair-category]').forEach((button) => {
    button.addEventListener('click', () => {
        const repairTab = document.getElementById('tab-repair');
        const categoryField = document.getElementById('id_service_category');
        if (repairTab) selectCustomerTab(repairTab);
        if (categoryField) categoryField.value = button.dataset.repairCategory || '';
        document.getElementById('repair-request')?.scrollIntoView({
            behavior: 'smooth',
            block: 'start',
        });
        if (categoryField) categoryField.focus({ preventScroll: true });
    });
});