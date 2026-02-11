# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

import logging
import secrets
import datetime
from urllib.parse import urljoin, urlencode

import jwt
from odoo import http, fields
from odoo.http import request

_logger = logging.getLogger(__name__)


class SaaSAgentController(http.Controller):
    """Endpoints exposés au master pour contrôle SaaS."""

    def _get_agent_secret(self):
        secret = request.env['ir.config_parameter'].sudo().get_param('saas_agent.secret')
        if not secret:
            _logger.warning('Missing saas_agent.secret')
        return secret

    def _get_token_from_request(self):
        auth_header = request.httprequest.headers.get('Authorization', '')
        if auth_header.startswith('Bearer '):
            return auth_header.split(' ', 1)[1]
        body = request.jsonrequest or {}
        return body.get('token')

    def _decode_token(self, token, action):
        secret = self._get_agent_secret()
        if not secret:
            _logger.warning('Missing saas_agent.secret')
            return None, 'Missing agent secret'
        if not token:
            return None, 'Missing token'
        try:
            payload = jwt.decode(token, secret, algorithms=['HS256'], options={'verify_aud': False})
            if payload.get('action') != action:
                raise jwt.InvalidTokenError('Invalid action')
            if payload.get('db') and payload['db'] != request.env.cr.dbname:
                raise jwt.InvalidTokenError('DB mismatch')
            return payload, None
        except jwt.ExpiredSignatureError:
            _logger.warning('Expired JWT for action %s', action)
            return None, 'Token expired'
        except jwt.InvalidTokenError as exc:
            _logger.warning('Invalid JWT: %s', exc)
            return None, str(exc)

    def _json_error(self, message):
        return {'success': False, 'error': message}

    @http.route('/saas/set_user_limit', type='json', auth='public', csrf=False, methods=['POST'])
    def set_user_limit(self, **_kwargs):
        token = self._get_token_from_request()
        payload, err = self._decode_token(token, 'set_user_limit') if token else (None, None)
        if not payload:
            return self._json_error(err or 'Unauthorized')

        user_limit = payload.get('user_limit')
        if user_limit is None:
            return self._json_error('Missing user_limit')

        ICP = request.env['ir.config_parameter'].sudo()
        ICP.set_param('saas_agent.user_limit', int(user_limit))
        ICP.set_param('saas_agent.instance_uuid', payload.get('instance_uuid') or '')
        return {'success': True}

    @http.route('/saas/get_users_count', type='json', auth='public', csrf=False, methods=['POST'])
    def get_users_count(self, **_kwargs):
        token = self._get_token_from_request()
        payload, err = self._decode_token(token, 'get_users_count') if token else (None, None)
        if not payload:
            return self._json_error(err or 'Unauthorized')

        helper = request.env['saas.user.limit.helper']
        count = helper.count_billable_users()
        return {'success': True, 'current_users': count}

    @http.route('/saas/set_expiration', type='json', auth='public', csrf=False, methods=['POST'])
    def set_expiration(self, **_kwargs):
        token = self._get_token_from_request()
        payload, err = self._decode_token(token, 'set_expiration') if token else (None, None)
        if not payload:
            return self._json_error(err or 'Unauthorized')

        ICP = request.env['ir.config_parameter'].sudo()
        expiration = payload.get('expiration_date')
        suspended = payload.get('suspended')
        ICP.set_param('saas_agent.expiration_date', expiration or '')
        ICP.set_param('saas_agent.suspended', '1' if str(suspended).lower() in ('1', 'true', 'yes', 'on') else '0')
        return {'success': True}

    def _find_target_user(self, payload):
        sudo_env = request.env['res.users'].sudo()
        user_id = payload.get('user_id')
        if user_id:
            return sudo_env.browse(int(user_id))

        login = payload.get('user_login')
        if login:
            user = sudo_env.search([('login', '=', login)], limit=1)
            if user:
                return user

        config_user_id = request.env['ir.config_parameter'].sudo().get_param('saas_agent.impersonate_user_id')
        if config_user_id:
            return sudo_env.browse(int(config_user_id))

        return sudo_env.browse(2)

    def _build_login_url(self, token_record, redirect):
        base = request.httprequest.url_root.rstrip('/') + '/'
        params = {'token': token_record.token}
        if redirect:
            params['next'] = redirect
        return urljoin(base, 'saas/sso/login?' + urlencode(params))

    @http.route('/saas/sso/request', type='json', auth='public', csrf=False, methods=['POST'])
    def request_sso(self, **_kwargs):
        token = self._get_token_from_request()
        payload, err = self._decode_token(token, 'sso')
        if not payload:
            _logger.warning('SSO request rejected: %s', err or 'Unauthorized')
            return self._json_error(err or 'Unauthorized')

        target_user = self._find_target_user(payload)
        if not target_user or not target_user.exists():
            _logger.warning('SSO target user not found: payload=%s', payload)
            return self._json_error('User not found')

        exp_ts = payload.get('exp')
        if not exp_ts:
            _logger.warning('SSO request missing exp: payload=%s', payload)
            return self._json_error('Missing exp')

        expire_at = datetime.datetime.utcfromtimestamp(exp_ts)
        if expire_at <= datetime.datetime.utcnow():
            _logger.warning('SSO request expired: exp=%s now=%s', expire_at, datetime.datetime.utcnow())
            return self._json_error('Token expired')

        AgentToken = request.env['saas.agent.token'].sudo()
        login_token = AgentToken.create({
            'token': secrets.token_urlsafe(32),
            'user_id': target_user.id,
            'expire_at': expire_at,
            'redirect_url': payload.get('redirect') or '/web',
        })

        login_url = self._build_login_url(login_token, payload.get('redirect'))
        _logger.info('SSO token created for user %s exp=%s', target_user.id, expire_at)
        return {
            'success': True,
            'login_url': login_url,
            'expire_at': fields.Datetime.to_string(expire_at),
        }

    @http.route('/saas/sso/login', type='http', auth='public', csrf=False, methods=['GET'])
    def sso_login(self, token=None, next=None, **_kwargs):
        if not token:
            _logger.warning('SSO login missing token')
            return http.Response('Missing token', status=400)

        Token = request.env['saas.agent.token'].sudo()
        record = Token.search([('token', '=', token)], limit=1)
        if not record or record.state != 'new':
            _logger.warning('SSO login invalid token=%s', token)
            return http.Response('Invalid token', status=400)

        now = fields.Datetime.now()
        if record.expire_at and record.expire_at < now:
            record.write({'state': 'expired'})
            _logger.warning('SSO login expired token=%s exp=%s now=%s', token, record.expire_at, now)
            return http.Response('Token expired', status=400)

        user = record.user_id
        if not user or not user.active:
            record.write({'state': 'expired'})
            _logger.warning('SSO login inactive user for token=%s user_id=%s', token, user.id if user else None)
            return http.Response('User inactive', status=400)

        request.session.uid = user.id
        request.session.login = user.login
        request.session.session_token = user._compute_session_token(request.session.sid)
        request.session.context = dict(request.session.context or {}, uid=user.id)
        request.update_env(user=user)

        record.write({'state': 'used', 'last_used': now})
        _logger.info('SSO login successful token=%s user_id=%s redirect=%s', token, user.id, next or record.redirect_url)

        redirect_url = next or record.redirect_url or '/web'
        return request.redirect(redirect_url)

