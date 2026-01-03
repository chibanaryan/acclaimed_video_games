/**
 * Live markdown preview and Cloudinary image upload for Django admin.
 * Uses iframe to isolate site styles from admin styles.
 */
document.addEventListener("DOMContentLoaded", function() {
    const contentField = document.querySelector("#id_content");
    if (!contentField) return;

    // Find the parent .form-row for the content field
    const contentRow = contentField.closest(".form-row");
    if (!contentRow) return;

    // Add "Insert Image" button as its own form row above the content row
    const toolbarRow = document.createElement("div");
    toolbarRow.className = "form-row article-toolbar-row";
    toolbarRow.innerHTML = `
        <div>
            <label>&nbsp;</label>
            <button type="button" class="insert-image-btn" title="Upload and insert image">
                + Insert Image
            </button>
        </div>
    `;
    contentRow.parentNode.insertBefore(toolbarRow, contentRow);

    // Create preview row with iframe for style isolation
    const previewRow = document.createElement("div");
    previewRow.className = "form-row field-preview";
    previewRow.innerHTML = `
        <div>
            <label>Preview:</label>
            <iframe class="article-preview-frame" frameborder="0"></iframe>
        </div>
    `;
    contentRow.parentNode.insertBefore(previewRow, contentRow.nextSibling);

    // Cloudinary Upload Widget
    const insertImageBtn = toolbarRow.querySelector(".insert-image-btn");
    let cloudinaryWidget = null;

    function loadCloudinaryWidget() {
        if (window.cloudinary) return Promise.resolve();
        return new Promise((resolve) => {
            const script = document.createElement("script");
            script.src = "https://upload-widget.cloudinary.com/global/all.js";
            script.onload = resolve;
            document.head.appendChild(script);
        });
    }

    function insertAtCursor(text) {
        const start = contentField.selectionStart;
        const end = contentField.selectionEnd;
        const before = contentField.value.substring(0, start);
        const after = contentField.value.substring(end);
        contentField.value = before + text + after;
        contentField.selectionStart = contentField.selectionEnd = start + text.length;
        contentField.focus();
        // Trigger preview update
        contentField.dispatchEvent(new Event("input"));
    }

    insertImageBtn.addEventListener("click", async function() {
        await loadCloudinaryWidget();

        if (!cloudinaryWidget) {
            cloudinaryWidget = window.cloudinary.createUploadWidget({
                cloudName: "dpl7qh1gp",
                uploadPreset: "articles",      // Unsigned upload preset
                sources: ["local", "url", "camera"],
                multiple: true,
                maxFileSize: 10000000,  // 10MB
                folder: "articles",
                resourceType: "image",
                clientAllowedFormats: ["png", "jpg", "jpeg", "gif", "webp"],
            }, (error, result) => {
                if (!error && result && result.event === "success") {
                    const url = result.info.secure_url;
                    const alt = result.info.original_filename || "image";
                    insertAtCursor(`![${alt}](${url})\n`);
                }
            });
        }

        cloudinaryWidget.open();
    });

    const iframe = previewRow.querySelector(".article-preview-frame");

    // Initialize iframe with site styles - matches article_detail.html structure
    function initIframe() {
        const doc = iframe.contentDocument;
        doc.open();
        doc.write(`
            <!DOCTYPE html>
            <html data-theme="forest">
            <head>
                <link rel="stylesheet" href="/static/css/dist/styles.css">
                <style>
                    body { margin: 0; padding: 16px; }
                    .article-container {
                        background: var(--color-base-100);
                        border: 1px solid var(--color-base-300);
                        border-radius: 8px;
                    }
                </style>
            </head>
            <body class="bg-base-200">
                <div class="article-container">
                    <article class="max-w-3xl mx-auto px-4 py-8">
                        <div class="prose prose-lg prose-invert max-w-none" id="content">
                            <p class="text-base-content/50 italic">Start typing to see preview...</p>
                        </div>
                    </article>
                </div>
            </body>
            </html>
        `);
        doc.close();
    }

    initIframe();

    // Load marked.js for markdown rendering
    function loadMarked(callback) {
        if (typeof marked !== "undefined") {
            callback();
            return;
        }
        const script = document.createElement("script");
        script.src = "https://cdn.jsdelivr.net/npm/marked/marked.min.js";
        script.onload = callback;
        document.head.appendChild(script);
    }

    function renderPreview() {
        if (typeof marked === "undefined") return;

        const content = contentField.value.trim();
        const target = iframe.contentDocument.getElementById("content");
        if (!target) return;

        if (content) {
            target.innerHTML = marked.parse(content);
        } else {
            target.innerHTML = "<p class='text-base-content/50 italic'>Start typing to see preview...</p>";
        }

        // Auto-resize iframe to content height
        iframe.style.height = iframe.contentDocument.body.scrollHeight + "px";
    }

    // Load marked and render initial preview
    loadMarked(function() {
        // Small delay to let iframe CSS load
        setTimeout(renderPreview, 100);
    });

    // Update preview on input (debounced)
    let timeout;
    contentField.addEventListener("input", function() {
        clearTimeout(timeout);
        timeout = setTimeout(renderPreview, 150);
    });
});
