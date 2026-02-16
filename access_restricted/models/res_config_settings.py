from odoo import SUPERUSER_ID, api, models
from odoo.tools import ustr
from odoo.tools.translate import _


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    @api.model
    def _get_classified_fields(self, fnames=None):
        uid = self.env.uid
        classified = super(ResConfigSettings, self)._get_classified_fields(fnames)
        config = self.env.context.get("config")
        is_execute_stage = config and isinstance(config, models.Model)
        user = self.env.user
        if uid == SUPERUSER_ID or is_execute_stage:
            return classified

        allow_implied = user.has_group(
            "access_restricted.group_allow_add_implied_from_settings"
        )
        group = []
        for name, groups, implied_group in classified["group"]:
            if (implied_group and user.has_group(implied_group)) or allow_implied:
                group.append((name, groups, implied_group))
        classified["group"] = group
        return classified

    @api.model
    def fields_get(self, allfields=None, **kwargs):
        uid = self.env.uid
        user = self.env.user
        fields = super(ResConfigSettings, self).fields_get(allfields, **kwargs)

        if uid == SUPERUSER_ID:
            return fields

        allow_implied = user.has_group(
            "access_restricted.group_allow_add_implied_from_settings"
        )

        for name in fields:
            if not name.startswith("group_"):
                continue
            f = self._fields[name]
            implied_group = getattr(f, "implied_group", False)
            if implied_group and (user.has_group(implied_group) or allow_implied):
                continue

            fields[name].update(
                readonly=True,
                help=ustr(fields[name].get("help", ""))
                + _(
                    "\n\nYou don't have access to change this settings, because you administration rights are restricted"
                ),
            )
        return fields

    def execute(self):
        res = super(ResConfigSettings, self.with_context({"config": self})).execute()
        return res
