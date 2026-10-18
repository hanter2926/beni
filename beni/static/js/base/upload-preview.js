document.addEventListener('DOMContentLoaded', () => {
    document.querySelectorAll('[data-image-preview-input]').forEach((input) => {
        const field = input.closest('.form-field, .management-field');
        const previewList = field && field.querySelector('[data-image-preview-list]');
        if (!previewList) {
            return;
        }

        let objectUrls = [];
        input.addEventListener('change', () => {
            objectUrls.forEach((url) => URL.revokeObjectURL(url));
            objectUrls = [];
            previewList.replaceChildren();

            Array.from(input.files || []).forEach((file) => {
                const item = document.createElement('div');
                item.className = 'upload-preview-item';
                if (file.type.startsWith('image/')) {
                    const image = document.createElement('img');
                    image.src = URL.createObjectURL(file);
                    image.alt = '';
                    image.loading = 'lazy';
                    objectUrls.push(image.src);
                    item.append(image);
                }
                const name = document.createElement('span');
                name.textContent = file.name;
                item.append(name);
                previewList.append(item);
            });

            if (!input.files || !input.files.length) {
                const emptyState = document.createElement('span');
                emptyState.textContent = 'No new files selected.';
                previewList.append(emptyState);
            }
        });
    });
});
