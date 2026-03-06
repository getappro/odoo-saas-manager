# -*- coding: utf-8 -*-
from odoo import fields, models
from odoo.http import request


class SaaSExpirationHelper(models.AbstractModel):
    _name = 'saas.expiration.helper'
    _description = 'SaaS Expiration Helper'

    def _get_expiration(self):
        icp = self.env['ir.config_parameter'].sudo()
        raw_date = icp.get_param('saas_agent.expiration_date') or None
        raw_suspended = icp.get_param('saas_agent.suspended')
        suspended = str(raw_suspended).lower() in ('1', 'true', 'yes', 'on')
        expiration_dt = fields.Datetime.from_string(raw_date) if raw_date else None
        return expiration_dt, suspended

    def is_access_blocked(self):
        expiration_dt, suspended = self._get_expiration()
        if suspended:
            return True
        if expiration_dt and fields.Datetime.now() >= expiration_dt:
            return True
        return False

    def is_allowed_request(self):
        path = (request.httprequest.path or '').lower() if request and request.httprequest else ''
        return path.startswith('/saas/')

    def build_block_response(self):
        from odoo import http
        if request and request.httprequest:
            path = request.httprequest.path or ''
            ctype = (request.httprequest.content_type or '').lower()
            if path.endswith('/jsonrpc') or 'json' in path or 'application/json' in ctype:
                return http.Response(
                    headers={'Content-Type': 'application/json'},
                    status=403,
                    response='{"error":"Instance suspended or expired"}',
                )
        return http.Response(
            status=403,
            content_type='text/html',
            response=(
                "<!doctype html>"\
                "<html lang='fr'>"\
                "<head>"\
                "<meta charset='utf-8'>"\
                "<meta name='viewport' content='width=device-width,initial-scale=1'>"\
                "<title>Instance suspendue</title>"\
                "<style>"\
                "body{margin:0;font-family:Arial,Helvetica,sans-serif;background:#0f172a;color:#e2e8f0;display:flex;align-items:center;justify-content:center;height:100vh;}"\
                ".card{background:#111827;border:1px solid #1f2937;border-radius:12px;padding:32px;box-shadow:0 15px 40px rgba(0,0,0,0.35);max-width:520px;text-align:center;}"\
                ".title{font-size:22px;font-weight:700;margin-bottom:12px;color:#fbbf24;}"\
                ".subtitle{font-size:15px;margin-bottom:20px;color:#cbd5e1;}"\
                ".cta{display:inline-block;margin-top:10px;padding:10px 18px;border-radius:8px;background:#2563eb;color:#e2e8f0;text-decoration:none;font-weight:600;}"\
                "</style>"\
                "</head>"\
                "<body>"\
                "  <div class='card'>"\
                "    <div class='title'>Instance suspendue</div>"\
                "    <div class='subtitle'>Cette instance est suspendue ou expirée. Contactez votre administrateur ou votre support pour rétablir l'accès.</div>"\
                "    <a class='cta' href='mailto:support@deepcode.ma'>Contacter le support</a>"\
                "  </div>"\
                "</body>"\
                "</html>"
            ),
        )
