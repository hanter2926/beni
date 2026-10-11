const firstInvalidField = document.querySelector('[aria-invalid="true"]');

if (firstInvalidField instanceof HTMLElement) {
    firstInvalidField.focus({ preventScroll: true });
}