function replaceImageWithFallback(image) {
    if (!image.dataset.fallbackSrc) return;
    image.src = image.dataset.fallbackSrc;
    if (image.dataset.fallbackAlt) image.alt = image.dataset.fallbackAlt;
    image.dataset.imageFallbackApplied = 'true';
    image.classList.add('image-fallback');
    delete image.dataset.fallbackSrc;
}

document.addEventListener('error', (event) => {
    const image = event.target;
    if (image instanceof HTMLImageElement) replaceImageWithFallback(image);
}, true);

document.querySelectorAll('img[data-fallback-src]').forEach((image) => {
    if (image.complete && image.naturalWidth === 0) {
        replaceImageWithFallback(image);
    }
});
