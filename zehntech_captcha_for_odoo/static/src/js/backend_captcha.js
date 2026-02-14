import { _t } from "@web/core/l10n/translation";
import options from "@web_editor/js/editor/snippets.options";
import { rpc } from "@web/core/network/rpc";

/**
 * Captcha Options for Website Forms
 * Adds captcha functionality to standard Odoo website forms
 */
const WebsiteFormCaptcha = options.Class.extend({
    selector: '.s_website_form',

    start: function () {
        const result = this._super.apply(this, arguments);
        const snippetEditor = this.getParent();
        if (!snippetEditor || !snippetEditor.$target) {
            return result;
        }

        this.$target = snippetEditor.$target;
        this.$form = this.$target.find('form').first();

        if (!this.$form.length) {
            return result;
        }

        this._initializeCaptchaState();
        return result;
    },

    _initializeCaptchaState: function () {
        const hasCaptcha = this.$form.find('.s_website_form_captcha').length > 0;
        if (hasCaptcha) {
            this._syncCaptchaUI();
        }
    },

    _syncCaptchaUI: function () {
        const $captchaField = this.$form.find('.s_website_form_captcha');
        if ($captchaField.length) {
            const captcha_type = $captchaField.attr('data-captcha-type') || 'mathematical';
        }
    },

    /**
     * ONLY add captcha field - NO dialog
     */
    enableCaptcha: function (previewMode, widgetValue, params) {
        const $existingCaptcha = this.$form.find('.s_website_form_captcha');
        
        // If captcha already exists, do nothing
        if ($existingCaptcha.length > 0) {
            console.log('Captcha already enabled on this form');
            return;
        }

        // Add new captcha field
        this._addCaptchaField();
    },

    /**
     * Add captcha field to form
     */
    _addCaptchaField: function () {
        rpc('/website/captcha/get_config').then((config) => {
            const captcha_type = config.captcha_type || 'mathematical';

            const captchaFieldHtml = this._generateCaptchaFieldHtml(captcha_type, config);
            const $submitBtn = this.$form.find('button[type="submit"]');

            if ($submitBtn.length) {
                $(captchaFieldHtml).insertBefore($submitBtn.parent());
            } else {
                this.$form.append(captchaFieldHtml);
            }

            this.trigger_up('snippet_option_update', {
                onSuccess: () => {
                    console.log('Captcha field added successfully');
                }
            });
        });
    },

    /**
     * Generate captcha field HTML
     */
    _generateCaptchaFieldHtml: function (captcha_type, config) {
        let captchaContent = '';

        switch (captcha_type) {
            case 'mathematical':
                captchaContent = this._generateMathCaptcha(config);
                break;
            case 'numeric_image':
                captchaContent = this._generateNumericImageCaptcha(config);
                break;
            case 'alphabetic_image':
                captchaContent = this._generateAlphabeticImageCaptcha(config);
                break;
            default:
                captchaContent = this._generateMathCaptcha(config);
        }

        return `
            <div class="mb-3 s_website_form_field s_website_form_captcha s_website_form_required col-12" 
                 data-type="captcha" 
                 data-name="Captcha Field" 
                 data-captcha-type="${captcha_type}"
                 data-math-op="${config.algebraic_operations || 'addition'}"
                 data-math-rhs="${config.rhs_digit_length || '0-9'}"
                 data-num-symbols="${config.include_symbols || false}"
                 data-num-len="${config.captcha_length || 6}"
                 data-alpha-caps="${config.include_capital || false}">
                <label class="s_website_form_label" style="width: 200px">
                    <span class="s_website_form_label_content">Verification</span>
                    <span class="s_website_form_mark"> *</span>
                </label>
                <div class="captcha-container">
                    ${captchaContent}
                    <input type="text" 
                           class="form-control s_website_form_input mt-2" 
                           name="captcha_answer" 
                           required="1" 
                           placeholder="Enter your answer"
                           autocomplete="off" />
                    <input type="hidden" name="captcha_token" class="captcha-token" />
                </div>
            </div>
        `;
    },

    _generateMathCaptcha: function (config) {
        return `
            <div class="captcha-question mathematical-captcha">
                <span class="captcha-text">What is <strong class="captcha-equation">5 + 3</strong>?</span>
                <button type="button" class="btn btn-sm btn-link refresh-captcha" title="Refresh">
                    <i class="fa fa-refresh"></i>
                </button>
            </div>
        `;
    },

    _generateNumericImageCaptcha: function (config) {
        return `
            <div class="captcha-question numeric-image-captcha">
                <div class="captcha-image-placeholder" style="background: #f0f0f0; padding: 15px; border-radius: 4px; text-align: center; font-family: monospace; font-size: 24px; letter-spacing: 8px;">
                    <span class="captcha-code">8N4M2X</span>
                </div>
                <button type="button" class="btn btn-sm btn-link refresh-captcha mt-2" title="Refresh">
                    <i class="fa fa-refresh"></i> Refresh
                </button>
            </div>
        `;
    },

    _generateAlphabeticImageCaptcha: function (config) {
        return `
            <div class="captcha-question alphabetic-image-captcha">
                <div class="captcha-image-placeholder" style="background: #f0f0f0; padding: 15px; border-radius: 4px; text-align: center; font-family: monospace; font-size: 24px; letter-spacing: 8px;">
                    <span class="captcha-code">aBcDeF</span>
                </div>
                <button type="button" class="btn btn-sm btn-link refresh-captcha mt-2" title="Refresh">
                    <i class="fa fa-refresh"></i> Refresh
                </button>
            </div>
        `;
    },

    /**
     * Remove captcha field
     */
    removeCaptcha: function () {
        const $captchaField = this.$form.find('.s_website_form_captcha');
        if ($captchaField.length) {
            $captchaField.remove();
            this.trigger_up('snippet_option_update', {
                onSuccess: () => {
                    console.log('Captcha field removed');
                }
            });
        }
    }
});

/**
 * Captcha Field Options - For when user selects the captcha field
 */
const WebsiteFormCaptchaField = options.Class.extend({
    selector: '.s_website_form_captcha',

    start: function () {
        const result = this._super.apply(this, arguments);
        const snippetEditor = this.getParent();
        if (!snippetEditor || !snippetEditor.$target) {
            return result;
        }
        this.$captchaField = snippetEditor.$target;
        return result;
    },

    /**
     * Change captcha type
     */
    onCaptchaTypeChange: function (previewMode, widgetValue) {
        this.$captchaField.attr('data-captcha-type', widgetValue);
        this._regenerateCaptcha();
    },

    /**
     * Open settings wizard - ONLY for field-level configuration
     */
    openCaptchaSettings: function (previewMode) {
        const captcha_type = this.$captchaField.attr('data-captcha-type') || 'mathematical';
        
        this._openConfigDialog(captcha_type);
    },

    /**
     * Open configuration dialog
     */
    _openConfigDialog: function (captcha_type) {
        var refreshCallback = () => {
            this._regenerateCaptcha();
            this.trigger_up('snippet_option_update', {
                onSuccess: () => { console.log('Captcha configuration updated'); }
            });
        };

        try {
            const env = this.env || window.owl?.Component?.env;
            
            if (env && env.services && env.services.action) {
                env.services.action.doAction('zehntech_captcha_for_odoo.action_captcha_config_wizard', {
                    on_close: refreshCallback,
                    context: { default_captcha_type: this._mapCaptchaType(captcha_type) }
                });
                return;
            }

            var parent = (this.getParent && this.getParent()) || null;
            if (parent && typeof parent.do_action === 'function') {
                parent.do_action('zehntech_captcha_for_odoo.action_captcha_config_wizard', { 
                    on_close: refreshCallback,
                    context: { default_captcha_type: this._mapCaptchaType(captcha_type) }
                });
                return;
            }

            if (typeof this.do_action === 'function') {
                this.do_action('zehntech_captcha_for_odoo.action_captcha_config_wizard', { 
                    on_close: refreshCallback,
                    context: { default_captcha_type: this._mapCaptchaType(captcha_type) }
                });
                return;
            }
        } catch (err) {
            console.error('Error opening captcha config dialog:', err);
        }
    },

    /**
     * Map captcha type names
     */
    _mapCaptchaType: function (type) {
        const map = {
            'mathematical': 'math',
            'numeric_image': 'num',
            'alphabetic_image': 'alpha'
        };
        return map[type] || type;
    },

    /**
     * Regenerate captcha display
     */
    _regenerateCaptcha: function () {
        const captcha_type = this.$captchaField.attr('data-captcha-type') || 'mathematical';
        const config = {
            algebraic_operations: this.$captchaField.attr('data-math-op') || 'addition',
            rhs_digit_length: this.$captchaField.attr('data-math-rhs') || '0-9',
            include_symbols: this.$captchaField.attr('data-num-symbols') === 'true',
            captcha_length: parseInt(this.$captchaField.attr('data-num-len') || 6),
            include_capital: this.$captchaField.attr('data-alpha-caps') === 'true'
        };

        let captchaContent = '';
        switch (captcha_type) {
            case 'mathematical':
                captchaContent = this._generateMathCaptcha(config);
                break;
            case 'numeric_image':
                captchaContent = this._generateNumericImageCaptcha(config);
                break;
            case 'alphabetic_image':
                captchaContent = this._generateAlphabeticImageCaptcha(config);
                break;
        }

        this.$captchaField.find('.captcha-container').html(captchaContent + 
            `<input type="text" class="form-control s_website_form_input mt-2" name="captcha_answer" required="1" placeholder="Enter your answer" autocomplete="off" />
             <input type="hidden" name="captcha_token" class="captcha-token" />`);
    },

    _generateMathCaptcha: function (config) {
        return `
            <div class="captcha-question mathematical-captcha">
                <span class="captcha-text">What is <strong class="captcha-equation">5 + 3</strong>?</span>
                <button type="button" class="btn btn-sm btn-link refresh-captcha" title="Refresh">
                    <i class="fa fa-refresh"></i>
                </button>
            </div>
        `;
    },

    _generateNumericImageCaptcha: function (config) {
        return `
            <div class="captcha-question numeric-image-captcha">
                <div class="captcha-image-placeholder" style="background: #f0f0f0; padding: 15px; border-radius: 4px; text-align: center; font-family: monospace; font-size: 24px; letter-spacing: 8px;">
                    <span class="captcha-code">8N4M2X</span>
                </div>
                <button type="button" class="btn btn-sm btn-link refresh-captcha mt-2" title="Refresh">
                    <i class="fa fa-refresh"></i> Refresh
                </button>
            </div>
        `;
    },

    _generateAlphabeticImageCaptcha: function (config) {
        return `
            <div class="captcha-question alphabetic-image-captcha">
                <div class="captcha-image-placeholder" style="background: #f0f0f0; padding: 15px; border-radius: 4px; text-align: center; font-family: monospace; font-size: 24px; letter-spacing: 8px;">
                    <span class="captcha-code">aBcDeF</span>
                </div>
                <button type="button" class="btn btn-sm btn-link refresh-captcha mt-2" title="Refresh">
                    <i class="fa fa-refresh"></i> Refresh
                </button>
            </div>
        `;
    }
});

// Register options
options.registry.WebsiteFormCaptcha = WebsiteFormCaptcha;
options.registry.WebsiteFormCaptchaField = WebsiteFormCaptchaField;

export default { WebsiteFormCaptcha, WebsiteFormCaptchaField };