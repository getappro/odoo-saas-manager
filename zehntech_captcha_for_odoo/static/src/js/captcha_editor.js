/** captcha_editor.js **/
import { _t } from "@web/core/l10n/translation";
import { registry } from "@web/core/registry";
import { Dialog } from "@web/core/dialog/dialog";
import { useService } from "@web/core/utils/hooks";
const { Component, onMounted, onWillStart, useState } = owl;

class CaptchaEditorDialog extends Component {
    static template = "zehntech_captcha_for_odoo.CaptchaEditorDialog";
    static props = { close: Function };
    setup() {
        this.rpc = useService("rpc");
        this.notification = useService("notification");
        this.state = useState({
            loading: true, saving: false,
            enabled: false, on_login: true, on_signup: true, on_reset: true,
            message: "Captcha not verified.", type: "math",
            math_operation: "rnd", math_rhs_len: "9",
            num_include_symbols: false, num_length: "5",
            alpha_include_caps: true, alpha_include_symbols: false, alpha_length: "5",
        });
        onWillStart(async () => {
            try {
                const cfg = await this.rpc("/captcha/site_config/get", {});
                Object.assign(this.state, cfg || {});
            } finally { this.state.loading = false; }
        });
    }
    async save() {
        this.state.saving = true;
        try {
            const payload = { ...this.state };
            delete payload.loading; delete payload.saving;
            await this.rpc("/captcha/site_config/set", payload);
            this.notification.add(_t("Captcha settings saved for this website."), { type: "success" });
            window.location.reload();
        } catch (e) {
            this.notification.add(_t("Could not save captcha settings."), { type: "danger" });
            this.state.saving = false;
        }
    }
}

function addButtonWhenEditorReady(dialogService) {
    const CANDIDATES = [
        ".o_we_website_tools",
        ".o_we_topbar_actions",
        ".o_website_editor_panel_top",
        ".o-we-toolbar .o-we-toolbar-actions",
    ];

    function ensureButton(toolbar) {
        if (!toolbar || toolbar.querySelector(".o_we_captcha_btn")) return;
        const btn = document.createElement("button");
        btn.type = "button";
        btn.className = "btn btn-secondary o_we_captcha_btn";
        btn.style.marginLeft = "6px";
        btn.innerHTML = `<i class="fa fa-shield"></i><span class="ms-1">Captcha</span>`;
        btn.addEventListener("click", () => {
            dialogService.add(CaptchaEditorDialog, { title: _t("Captcha (This Website)") });
        });
        toolbar.appendChild(btn);
    }

    function tryMount() {
        let toolbar = null;
        for (const sel of CANDIDATES) {
            toolbar = document.querySelector(sel);
            if (toolbar) break;
        }
        if (toolbar) { ensureButton(toolbar); return true; }
        return false;
    }

    if (tryMount()) return;

    const obs = new MutationObserver(() => { if (tryMount()) obs.disconnect(); });
    obs.observe(document.documentElement, { childList: true, subtree: true });
}

class CaptchaEditorBootstrap extends Component {
    setup() {
        const dialogService = this.env.services.dialog;
        onMounted(() => addButtonWhenEditorReady(dialogService));
    }
}
CaptchaEditorBootstrap.template = "zehntech_captcha_for_odoo.CaptchaEditorButton";

registry.category("webclient_hooks").add("zehntech_captcha_for_odoo.bootstrap", {
    start(env) {
        new CaptchaEditorBootstrap(null, { env }).mount(document.createElement("div"));
    },
});

export default { CaptchaEditorDialog, CaptchaEditorBootstrap };
