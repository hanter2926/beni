const repairTabs = [...document.querySelectorAll('.repair-tabs [role="tab"]')];

function selectRepairTab(selectedTab, moveFocus = false) {
    repairTabs.forEach((tab) => {
        const selected = tab === selectedTab;
        tab.setAttribute('aria-selected', String(selected));
        tab.tabIndex = selected ? 0 : -1;
        const panelId = tab.getAttribute('aria-controls');
        const panel = panelId ? document.getElementById(panelId) : null;
        if (panel) panel.hidden = !selected;
    });
    if (moveFocus) selectedTab.focus();
}

repairTabs.forEach((tab, index) => {
    tab.addEventListener('click', () => selectRepairTab(tab));
    tab.addEventListener('keydown', (event) => {
        if (!['ArrowLeft', 'ArrowRight', 'Home', 'End'].includes(event.key)) return;
        event.preventDefault();
        const nextIndex = event.key === 'Home' ? 0
            : event.key === 'End' ? repairTabs.length - 1
                : (index + (event.key === 'ArrowRight' ? 1 : -1) + repairTabs.length) % repairTabs.length;
        selectRepairTab(repairTabs[nextIndex], true);
    });
});