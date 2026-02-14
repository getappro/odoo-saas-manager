from odoo import http
from odoo.http import request
import io
import random
import string
from PIL import Image, ImageDraw, ImageFont, ImageFilter

try:
    RESAMPLE_LANCZOS = Image.Resampling.LANCZOS
    RESAMPLE_BICUBIC = Image.Resampling.BICUBIC
except Exception:
    # Older Pillow fallback
    RESAMPLE_LANCZOS = getattr(Image, 'LANCZOS', Image.ANTIALIAS)
    RESAMPLE_BICUBIC = getattr(Image, 'BICUBIC', Image.BILINEAR)


# -----------------------
# Utility helpers
# -----------------------
def _rand_chars(alpha=False, length=5, include_caps=True, include_symbols=False, numbers_only=False):
    letters = string.ascii_lowercase
    if include_caps:
        letters += string.ascii_uppercase
    digits = string.digits
    symbols = "!@#$%^&=" if include_symbols else ""
    if numbers_only:
        pool = digits + symbols
    elif alpha:
        pool = letters + symbols
    else:
        pool = letters + digits + symbols
    return ''.join(random.choice(pool) for _ in range(length))


def _gen_math_expr(op='rnd', rhs_len='9'):
    a = random.randint(0, 9 if rhs_len == '9' else 99)
    b = random.randint(1, 9 if rhs_len == '9' else 99)
    op = random.choice(['add', 'sub', 'mul']) if op == 'rnd' else op
    if op == 'add':
        q = f"{a} + {b} = ?"
        ans = str(a + b)
    elif op == 'sub':
        q = f"{a} - {b} = ?"
        ans = str(a - b)
    else:
        q = f"{a} × {b} = ?"
        ans = str(a * b)
    return q, ans


def _draw_captcha(text, width=180, height=56):
    """High-contrast, readable captcha with light noise and outline text."""
    scale = 2
    W, H = width * scale, height * scale
    bg = (250, 250, 250)
    fg = (20, 20, 20)
    stroke = (255, 255, 255)

    img = Image.new('RGB', (W, H), bg)
    draw = ImageDraw.Draw(img)

    font = None
    for fname, size in [
        ("DejaVuSans-Bold.ttf", 44 * scale // 2),
        ("arialbd.ttf",         40 * scale // 2),
        ("Arial.ttf",           40 * scale // 2),
    ]:
        try:
            font = ImageFont.truetype(fname, size)
            break
        except Exception:
            continue
    if font is None:
        font = ImageFont.load_default()

    for _ in range(2):
        x1 = random.randint(0, W // 3)
        y1 = random.randint(0, H)
        x2 = random.randint(W // 2, W)
        y2 = random.randint(0, H)
        draw.line((x1, y1, x2, y2), fill=(200, 200, 200), width=2 * scale)

    x = 12 * scale
    for ch in text:
        tile = Image.new('RGBA', (int(40 * scale), int(40 * scale)), (0, 0, 0, 0))
        td = ImageDraw.Draw(tile)
        td.text(
            (6 * scale, 4 * scale), ch, font=font, fill=fg,
            stroke_width=2 * scale, stroke_fill=stroke
        )
        angle = random.randint(-6, 6)
        tile = tile.rotate(angle, resample=RESAMPLE_BICUBIC, expand=1)
        y = random.randint(6 * scale, 14 * scale)
        img.paste(tile, (x, y), tile)
        x += int(22 * scale)

    img = img.filter(ImageFilter.SMOOTH)
    img = img.resize((width, height), RESAMPLE_LANCZOS)
    return img


# -----------------------
# Controller
# -----------------------

class CaptchaController(http.Controller):
    
    @http.route('/website/captcha/get_config', type='json', auth='user', website=True)
    def get_captcha_config(self, **kwargs):
        website = request.website
        return {
            'captcha_enabled': website.captcha_enabled or False,
            'captcha_type': website.captcha_type or 'mathematical',
            'algebraic_operations': website.algebraic_operations or 'addition',
            'rhs_digit_length': website.rhs_digit_length or '0-9',
            'include_symbols': website.include_symbols or False,
            'captcha_length': website.captcha_length or 6,
            'include_capital': website.include_capital or False,
        } 

    @http.route(['/captcha/preview'], type='json', auth='user', website=True)
    def captcha_preview(self, **kw):
        """Generate a preview for admin UI (not session-bound)."""
        website = request.website
        config = request.env['res.config.settings'].sudo().get_site_config(website)
        if config.type == 'math':
            q, _ans = _gen_math_expr(config.math_operation, config.math_rhs_len)
            text = q
        elif config.type == 'num':
            text = _rand_chars(
                alpha=False, length=int(config.num_length), include_caps=False,
                include_symbols=config.num_include_symbols, numbers_only=True
            )
        else:
            text = _rand_chars(
                alpha=True, length=int(config.alpha_length),
                include_caps=config.alpha_include_caps, include_symbols=config.alpha_include_symbols
            )
        return {"preview": text}

    @http.route(['/captcha/new'], type='json', auth='public', website=True, csrf=False)
    def captcha_new(self, form_context=None, **kw):
        website = request.website
        cfg = request.env['res.config.settings'].sudo().get_site_config(website)
        if not cfg.enabled:
            return {"enabled": False}

        ctx = form_context or {}
        # Effective config = per-form override if provided else global
        ctype = (ctx.get('type') or cfg.type)
        num_len = int((ctx.get('len') or (cfg.num_length if ctype == 'num' else cfg.alpha_length)))
        include_symbols = (bool(ctx.get('symbols')) if ctx.get('symbols') is not None
                           else (cfg.num_include_symbols if ctype == 'num' else cfg.alpha_include_symbols))
        include_caps = (bool(ctx.get('caps')) if ctx.get('caps') is not None else cfg.alpha_include_caps)
        math_op = (ctx.get('op') or cfg.math_operation)
        math_rhs = (ctx.get('rhs') or cfg.math_rhs_len)

        token = ''.join(random.choice(string.ascii_letters + string.digits) for _ in range(24))

        if ctype == 'math':
            q, ans = _gen_math_expr(math_op, math_rhs)
            render_text, solution, prompt = q, ans, q
            request.session[f"captcha:q:{token}"] = q
        elif ctype == 'num':
            render_text = _rand_chars(alpha=False, length=num_len, include_caps=False,
                                      include_symbols=include_symbols, numbers_only=True)
            solution, prompt = render_text, None
        else:
            render_text = _rand_chars(alpha=True, length=num_len,
                                      include_caps=include_caps, include_symbols=include_symbols)
            solution, prompt = render_text, None

        request.session[f"captcha:{token}"] = solution
        request.session.modified = True
        return {"enabled": True, "token": token, "image": f"/captcha/image/{token}.png", "prompt": prompt}

    @http.route(['/captcha/image/<string:token>.png'], type='http', auth='public', website=True, csrf=False)
    def captcha_image(self, token=None, **kw):
        try:
            website = request.website
            config = request.env['res.config.settings'].sudo().get_site_config(website)
            if not config.enabled:
                return request.not_found()

            sess = request.session
            solution = sess.get(f"captcha:{token}") or "00000"
            render_text = solution if config.type != 'math' else (sess.get(f"captcha:q:{token}") or "Solve:")

            img = _draw_captcha(render_text)
            buf = io.BytesIO()
            img.save(buf, format='PNG')
            buf.seek(0)
            return request.make_response(buf.read(), headers=[('Content-Type', 'image/png')])

        except Exception:
            # tiny 1x1 PNG fallback so UI non-blocking rahe
            return request.make_response(
                b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x02\x00\x00\x00\x90wS\xde\x00\x00\x00\nIDATx\x9cc``\x00\x00\x00\x02\x00\x01E\x9c\xbb\x7f\x00\x00\x00\x00IEND\xaeB`\x82',
                headers=[('Content-Type', 'image/png')]
            )


def _check_and_pop_captcha(token, value):
    sess = request.session
    key = f"captcha:{token}"
    solution = sess.get(key)
    if solution is None:
        return False
    ok = str(value or "").strip() == str(solution).strip()
    if ok:
        sess.pop(key, None)
        request.session.modified = True
    return ok

from odoo.addons.web.controllers.home import Home as WebHome
from odoo.addons.auth_signup.controllers.main import AuthSignupHome

class WebHomeCaptcha(WebHome):

    @http.route(['/web/login'], type='http', auth='public', website=True, sitemap=False, csrf=False, methods=['GET', 'POST'])
    def web_login(self, *args, **kw):
        website = request.website
        config = request.env['res.config.settings'].sudo().get_site_config(website)

        # Verify captcha BEFORE calling super()
        if request.httprequest.method == 'POST' and config.enabled and config.on_login:
            token = kw.get('captcha_token') or request.params.get('captcha_token')
            value = kw.get('captcha_value') or request.params.get('captcha_value')
            if not (token and _check_and_pop_captcha(token, value)):
                message = config.message or "Captcha not verified."
                return request.render('web.login', {'error': message})

        return super(WebHomeCaptcha, self).web_login(*args, **kw)

class AuthSignupHomeCaptcha(AuthSignupHome):

    @http.route(['/web/signup'], type='http', auth='public', website=True, sitemap=False, csrf=False, methods=['GET', 'POST'])
    def web_auth_signup(self, *args, **kw):
        website = request.website
        config = request.env['res.config.settings'].sudo().get_site_config(website)
        if request.httprequest.method == 'POST' and config.enabled and config.on_signup:
            token = kw.get('captcha_token')
            value = kw.get('captcha_value')
            if not (token and _check_and_pop_captcha(token, value)):
                message = config.message or "Captcha not verified."
                qcontext = self.get_auth_signup_qcontext()
                qcontext['error'] = message
                return request.render('auth_signup.signup', qcontext)
        return super(AuthSignupHomeCaptcha, self).web_auth_signup(*args, **kw)

    @http.route(['/web/reset_password'], type='http', auth='public', website=True, sitemap=False, csrf=False, methods=['GET', 'POST'])
    def web_auth_reset_password(self, *args, **kw):
        website = request.website
        config = request.env['res.config.settings'].sudo().get_site_config(website)
        if request.httprequest.method == 'POST' and config.enabled and config.on_reset:
            token = kw.get('captcha_token')
            value = kw.get('captcha_value')
            if not (token and _check_and_pop_captcha(token, value)):
                message = config.message or "Captcha not verified."
                qcontext = self.get_auth_signup_qcontext()
                qcontext['error'] = message
                return request.render('auth_signup.reset_password', qcontext)
        return super(AuthSignupHomeCaptcha, self).web_auth_reset_password(*args, **kw)


# Optional integration for legacy 'website_form' addon (if present)
try:
    from odoo.addons.website_form.controllers.main import WebsiteForm

    class WebsiteFormCaptcha(WebsiteForm):
        @http.route(['/website_form/<string:model_name>'], type='http', auth='public', methods=['POST'], website=True, csrf=False)
        def website_form(self, model_name, **kwargs):
            website = request.website
            config = request.env['res.config.settings'].sudo().get_site_config(website)
            if config.enabled:
                token = kwargs.get('captcha_token')
                value = kwargs.get('captcha_value')
                captcha_on_form = kwargs.get('captcha_enabled') or request.params.get('captcha_enabled')
                if captcha_on_form and not (token and _check_and_pop_captcha(token, value)):
                    message = config.message or "Captcha not verified."
                    ref = request.httprequest.referrer or '/'
                    sep = '&' if ('?' in ref) else '?'
                    return request.redirect_with_hash(f"{ref}{sep}captcha_error=1", message=message, code=303)

            return super().website_form(model_name, **kwargs)
except Exception:
    pass
