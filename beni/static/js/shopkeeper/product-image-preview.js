const imageInput = document.querySelector('#id_image');
const imagePreview = document.querySelector('[data-product-image-preview]');
const previewMessage = document.querySelector('#product-image-preview-message');
const clearPreviewButton = document.querySelector('[data-clear-product-image]');

if (imageInput instanceof HTMLInputElement && imagePreview instanceof HTMLImageElement && previewMessage) {
    const originalSource = imagePreview.dataset.originalSrc
        ? new URL(imagePreview.dataset.originalSrc, document.baseURI).href
        : '';
    const emptySource = imagePreview.dataset.emptySrc;
    let previewObjectUrl = '';
    let previewFileName = '';
    let originalImageAvailable = Boolean(
        originalSource
        && imagePreview.currentSrc === originalSource
        && imagePreview.complete
        && imagePreview.naturalWidth > 0
        && imagePreview.dataset.imageFallbackApplied !== 'true'
    );
    const releasePreviewUrl = () => {
        if (previewObjectUrl) {
            URL.revokeObjectURL(previewObjectUrl);
            previewObjectUrl = '';
        }
    };
    const restorePreview = () => {
        imagePreview.src = originalImageAvailable ? originalSource : emptySource;
    };
    const clearSelectedImage = () => {
        releasePreviewUrl();
        previewFileName = '';
        imageInput.value = '';
        imageInput.setCustomValidity('');
        restorePreview();
        previewMessage.classList.remove('is-error');
        previewMessage.textContent = 'A preview appears here when you choose an image.';
        if (clearPreviewButton) clearPreviewButton.hidden = true;
    };

    imagePreview.addEventListener('load', () => {
        if (previewObjectUrl && imagePreview.currentSrc === previewObjectUrl) {
            imageInput.setCustomValidity('');
            previewMessage.classList.remove('is-error');
            previewMessage.textContent = `Previewing ${previewFileName}. The image is saved only after you submit the form.`;
        } else if (!previewObjectUrl && imagePreview.currentSrc === originalSource) {
            originalImageAvailable = true;
        }
    });
    imagePreview.addEventListener('error', () => {
        if (previewObjectUrl && imagePreview.currentSrc === previewObjectUrl) {
            releasePreviewUrl();
            imagePreview.src = emptySource;
            imageInput.setCustomValidity('The selected file could not be read as an image. Choose a valid JPEG, PNG, or WebP image.');
            previewMessage.classList.add('is-error');
            previewMessage.textContent = imageInput.validationMessage;
        } else if (imagePreview.dataset.imageFallbackApplied === 'true'
            || imagePreview.currentSrc === originalSource) {
            originalImageAvailable = false;
            imagePreview.src = emptySource;
        }
    });
    delete imagePreview.dataset.fallbackSrc;
    if (imagePreview.dataset.imageFallbackApplied === 'true') {
        originalImageAvailable = false;
        imagePreview.src = emptySource;
    }

    imageInput.addEventListener('change', () => {
        const [file] = imageInput.files || [];
        releasePreviewUrl();
        imageInput.setCustomValidity('');

        if (!file) {
            clearSelectedImage();
            return;
        }

        previewMessage.classList.remove('is-error');
        const supportedExtension = /\.(jpe?g|png|webp)$/i.test(file.name);
        const supportedType = ['', 'image/jpeg', 'image/png', 'image/webp'].includes(file.type);
        if (!supportedExtension || !supportedType || file.size > 2 * 1024 * 1024) {
            imagePreview.src = emptySource;
            const message = file.size > 2 * 1024 * 1024
                ? 'Choose an image no larger than 2 MB.'
                : 'Choose a JPEG, PNG, or WebP image.';
            imageInput.setCustomValidity(message);
            previewMessage.classList.add('is-error');
            previewMessage.textContent = message;
            if (clearPreviewButton) clearPreviewButton.hidden = false;
            return;
        }

        previewObjectUrl = URL.createObjectURL(file);
        previewFileName = file.name;
        delete imagePreview.dataset.imageFallbackApplied;
        imagePreview.src = previewObjectUrl;
        previewMessage.textContent = `Loading preview for ${file.name}…`;
        if (clearPreviewButton) clearPreviewButton.hidden = false;
    });

    clearPreviewButton?.addEventListener('click', clearSelectedImage);
    imageInput.form?.addEventListener('submit', (event) => {
        if (!imageInput.checkValidity()) {
            event.preventDefault();
            imageInput.reportValidity();
        }
    });
    window.addEventListener('beforeunload', releasePreviewUrl, { once: true });
}
