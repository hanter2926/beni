document.addEventListener('click', (event) => {
    if (event.target.closest('[data-print-invoice]')) {
        window.print();
    }
});
