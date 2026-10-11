const customerTabs = [...document.querySelectorAll('.customer-tabs [role="tab"]')];

function selectCustomerTab(selectedTab, moveFocus = false) {
    customerTabs.forEach((tab) => {
        const selected = tab === selectedTab;
        tab.setAttribute('aria-selected', String(selected));
        tab.tabIndex = selected ? 0 : -1;
        document.getElementById(tab.getAttribute('aria-controls')).hidden = !selected;
    });
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