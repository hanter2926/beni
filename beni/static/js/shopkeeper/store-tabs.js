const storeTabs = [...document.querySelectorAll('.shopkeeper-tabs [role="tab"]')];

function selectStoreTab(selectedTab, moveFocus = false) {
    storeTabs.forEach((tab) => {
        const selected = tab === selectedTab;
        tab.setAttribute('aria-selected', String(selected));
        tab.tabIndex = selected ? 0 : -1;
        document.getElementById(tab.getAttribute('aria-controls')).hidden = !selected;
    });
    if (moveFocus) selectedTab.focus();
}

storeTabs.forEach((tab, index) => {
    tab.addEventListener('click', () => selectStoreTab(tab));
    tab.addEventListener('keydown', (event) => {
        if (!['ArrowLeft', 'ArrowRight', 'Home', 'End'].includes(event.key)) return;
        event.preventDefault();
        const nextIndex = event.key === 'Home' ? 0
            : event.key === 'End' ? storeTabs.length - 1
                : (index + (event.key === 'ArrowRight' ? 1 : -1) + storeTabs.length) % storeTabs.length;
        selectStoreTab(storeTabs[nextIndex], true);
    });
});