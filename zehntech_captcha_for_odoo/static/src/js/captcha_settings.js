/** @odoo-module */

import { registry } from "@web/core/registry";
import { rpc } from "@web/core/network/rpc";

// Register client action to handle preview update
registry.category("actions").add("captcha_preview_update", async (env, action) => {
    const context = action.context || {};
    const previewText = context.preview_text || '';
    const previewImage = context.preview_image || '';
    
    // Use setTimeout to ensure DOM is ready
    setTimeout(() => {
        // Find all possible form views
        const formViews = document.querySelectorAll('.o_form_view');
        
        formViews.forEach(formView => {
            // Update ALL preview text fields (there are two - one for math, one for image)
            const textFields = formView.querySelectorAll('[name="captcha_preview_text"]');
            textFields.forEach(textField => {
                // Try multiple ways to find the input element
                let input = textField.querySelector('input');
                if (!input) {
                    input = textField.querySelector('.o_field_char');
                }
                if (!input) {
                    input = textField;
                }
                
                if (input) {
                    if (input.tagName === 'INPUT') {
                        input.value = previewText;
                    } else {
                        input.textContent = previewText;
                    }
                    // Trigger multiple events
                    ['input', 'change', 'blur'].forEach(eventType => {
                        input.dispatchEvent(new Event(eventType, { bubbles: true, cancelable: true }));
                    });
                }
            });
            
            // Update preview image field
            if (previewImage) {
                const imageField = formView.querySelector('[name="captcha_preview_image"]');
                if (imageField) {
                    // Update hidden input
                    const hiddenInput = imageField.querySelector('input[type="hidden"]');
                    if (hiddenInput) {
                        hiddenInput.value = previewImage;
                        ['input', 'change'].forEach(eventType => {
                            hiddenInput.dispatchEvent(new Event(eventType, { bubbles: true, cancelable: true }));
                        });
                    }
                    
                    // Update all image elements
                    const imageContainer = imageField.closest('.o_field_image') || imageField.parentElement;
                    if (imageContainer) {
                        const imgElements = imageContainer.querySelectorAll('img');
                        imgElements.forEach(img => {
                            img.src = 'data:image/png;base64,' + previewImage;
                            img.style.display = 'block';
                        });
                    }
                }
            }
        });
    }, 100);
});

registry.category("web.View").add("form", {
    selector: ".o_form_view",
    do: (view) => {
        // Handle captcha type changes in settings
        view.el.addEventListener('change', (event) => {
            if (event.target.name === 'captcha_type') {
                const captcha_type = event.target.value;
                updateCaptchaSettingsVisibility(view.el, captcha_type);
            }
        });

        // Handle refresh preview button click
        view.el.addEventListener('click', async (event) => {
            const button = event.target.closest('button[name="action_refresh_preview"]');
            if (button && !button.disabled) {
                event.preventDefault();
                event.stopPropagation();
                
                // Get record ID from the form
                const form = view.el.closest('form') || view.el.querySelector('form');
                if (!form) return;
                
                // Try to get resId from various possible locations
                let resId = null;
                const idInput = form.querySelector('input[name="id"]');
                if (idInput) {
                    resId = parseInt(idInput.value);
                }
                if (!resId) {
                    // Try alternative: get from data attributes or form action
                    const formAction = form.action;
                    if (formAction) {
                        const match = formAction.match(/\/\d+/);
                        if (match) {
                            resId = parseInt(match[0].substring(1));
                        }
                    }
                }
                
                if (!resId) return;
                
                // Disable button
                button.disabled = true;
                const originalText = button.textContent;
                button.textContent = 'Refreshing...';
                
                try {
                    // Call refresh action which returns client action with preview values
                    const result = await rpc('/web/dataset/call_kw', {
                        model: 'res.config.settings',
                        method: 'action_refresh_preview',
                        args: [[resId]],
                        kwargs: {},
                    });
                    
                    // Extract preview values from result
                    let previewText = '';
                    let previewImage = '';
                    
                    if (result && result.context) {
                        previewText = result.context.preview_text || '';
                        previewImage = result.context.preview_image || '';
                    }
                    
                    // If we have values, update directly as fallback
                    if (previewText || previewImage) {
                        // Update ALL preview text fields (there are two - one for math, one for image)
                        if (previewText) {
                            const textFields = form.querySelectorAll('[name="captcha_preview_text"]');
                            textFields.forEach(textField => {
                                // Try multiple ways to find the input element
                                let input = textField.querySelector('input');
                                if (!input) {
                                    input = textField.querySelector('.o_field_char');
                                }
                                if (!input) {
                                    input = textField;
                                }
                                
                                if (input) {
                                    if (input.tagName === 'INPUT') {
                                        input.value = previewText;
                                    } else {
                                        input.textContent = previewText;
                                    }
                                    // Trigger events to notify Odoo
                                    ['input', 'change', 'blur'].forEach(eventType => {
                                        input.dispatchEvent(new Event(eventType, { bubbles: true, cancelable: true }));
                                    });
                                }
                            });
                        }
                        
                        // Update preview image
                        if (previewImage) {
                            const imageField = form.querySelector('[name="captcha_preview_image"]');
                            if (imageField) {
                                // Update hidden input
                                const hiddenInput = imageField.querySelector('input[type="hidden"]');
                                if (hiddenInput) {
                                    hiddenInput.value = previewImage;
                                    hiddenInput.dispatchEvent(new Event('input', { bubbles: true }));
                                    hiddenInput.dispatchEvent(new Event('change', { bubbles: true }));
                                }
                                
                                // Update image display
                                const imgElements = form.querySelectorAll('[name="captcha_preview_image"] img');
                                imgElements.forEach(img => {
                                    img.src = 'data:image/png;base64,' + previewImage;
                                    img.style.display = 'block';
                                });
                            }
                        }
                    }
                    
                    // Also try to execute client action if available
                    if (result && result.tag === 'captcha_preview_update') {
                        const actionService = view.env?.services?.action;
                        if (actionService) {
                            await actionService.doAction(result);
                        }
                    }
                } catch (error) {
                    console.error('Error refreshing preview:', error);
                } finally {
                    button.disabled = false;
                    button.textContent = originalText;
                }
            }
        });

        // Initial visibility update
        const captcha_typeField = view.el.querySelector('[name="captcha_type"]');
        if (captcha_typeField) {
            updateCaptchaSettingsVisibility(view.el, captcha_typeField.value);
        }
    }
});

function updateCaptchaSettingsVisibility(formEl, captcha_type) {
    // Hide all captcha setting groups first
    const mathGroup = formEl.querySelector('[data-string="Mathematical Captcha Settings"]');
    const numGroup = formEl.querySelector('[data-string="Numbers Image Settings"]');
    const alphaGroup = formEl.querySelector('[data-string="Alpha Captcha Settings"]');

    if (mathGroup) {
        const mathContainer = mathGroup.closest('.o_group');
        if (mathContainer) mathContainer.style.display = captcha_type === 'math' ? '' : 'none';
    }
    if (numGroup) {
        const numContainer = numGroup.closest('.o_group');
        if (numContainer) numContainer.style.display = captcha_type === 'num' ? '' : 'none';
    }
    if (alphaGroup) {
        const alphaContainer = alphaGroup.closest('.o_group');
        if (alphaContainer) alphaContainer.style.display = captcha_type === 'alpha' ? '' : 'none';
    }
}