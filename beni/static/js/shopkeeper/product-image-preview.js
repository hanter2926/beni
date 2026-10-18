const imageInput = document.querySelector('#id_image');
const imagePreview = document.querySelector('[data-product-image-preview]');
const previewMessage = document.querySelector('#product-image-preview-message');
const clearPreviewButton = document.querySelector('[data-clear-product-image]');

if (imageInput instanceof HTMLInputElement && imagePreview instanceof HTMLImageElement && previewMessage) {
    const initialSource = imagePreview.src;
    const emptySource = imagePreview.dataset.emptySrc || initialSource;
    let previewObjectUrl = '';
    const clearSelectedImage = () => {
        if (previewObjectUrl) {
            URL.revokeObjectURL(previewObjectUrl);
            previewObjectUrl = '';
        }
        imageInput.value = '';
        imagePreview.src = imagePreview.dataset.imageFallbackApplied === 'true'
            ? emptySource
            : initialSource;
        previewMessage.textContent = 'A preview appears here when you choose an image.';
        if (clearPreviewButton) clearPreviewButton.hidden = true;
    };

    imageInput.addEventListener('change', () => {
        const [file] = imageInput.files || [];
        if (previewObjectUrl) {
            URL.revokeObjectURL(previewObjectUrl);
            previewObjectUrl = '';
        }

        if (!file) {
            clearSelectedImage();
            return;
        }

        const allowedTypes = ['image/jpeg', 'image/png', 'image/webp'];
        if (!allowedTypes.includes(file.type) || file.size > 2 * 1024 * 1024) {
            imagePreview.src = emptySource;
            previewMessage.textContent = file.size > 2 * 1024 * 1024
                ? 'Choose an image no larger than 2 MB.'
                : 'Choose a JPEG, PNG, or WebP image.';
            if (clearPreviewButton) clearPreviewButton.hidden = false;
            return;
        }

        previewObjectUrl = URL.createObjectURL(file);
        imagePreview.src = previewObjectUrl;
        previewMessage.textContent = `Previewing ${file.name}. The image is saved only after you submit the form.`;
        if (clearPreviewButton) clearPreviewButton.hidden = false;
    });

    clearPreviewButton?.addEventListener('click', clearSelectedImage);
}
