from odoo import api, fields, models
from io import BytesIO
import base64
import random
from types import SimpleNamespace
import string

try:
    from PIL import Image, ImageDraw, ImageFont, ImageFilter
except Exception:
    Image = None


def _website_param_key(website, suffix):
    """Generate website-specific parameter key."""
    return f"website_captcha.{website.id}.{suffix}"


def _load_font(size):
    """Load font with fallback chain for better compatibility."""
    font_names = ("DejaVuSans-Bold.ttf", "arialbd.ttf", "Arial.ttf", "arial.ttf")
    for name in font_names:
        try:
            return ImageFont.truetype(name, size)
        except Exception:
            continue
    return ImageFont.load_default()


def _measure(draw, font, text):
    """Version-safe text size measurement (Pillow ≥10 removed font.getsize)."""
    try:
        l, t, r, b = draw.textbbox((0, 0), text, font=font)
        return (r - l, b - t)
    except Exception:
        # Fallback for older Pillow versions
        w = int(draw.textlength(text, font=font)) if hasattr(draw, "textlength") else 0
        if hasattr(font, "getmetrics"):
            a, d = font.getmetrics()
            h = a + d
        else:
            h = font.size if hasattr(font, "size") else 32
        return (w, h)


def _make_preview_image(sample_text: str) -> bytes:
    """Generate high-quality, clear PNG bytes for the preview using the provided text."""
    # Increased size for better visibility
    IMG_W, IMG_H = 250, 100
    BG = (255, 255, 255)
    FG = (20, 20, 20)  # Darker for better contrast
    NOISE = (200, 200, 200)  # Lighter noise for clearer image

    img = Image.new("RGB", (IMG_W, IMG_H), BG)
    draw = ImageDraw.Draw(img)
    # Larger font for better clarity
    font = _load_font(56)

    # Calculate total width for centering
    total_w = sum(_measure(draw, font, ch)[0] for ch in sample_text) + (len(sample_text) - 1) * 6
    x = max(20, (IMG_W - total_w) // 2)
    _, H = _measure(draw, font, "H")
    y_base = (IMG_H - H) // 2

    # Render each character with less rotation for clarity
    for ch in sample_text:
        cw, chh = _measure(draw, font, ch)
        tile = Image.new("RGBA", (cw + 40, chh + 40), (0, 0, 0, 0))
        td = ImageDraw.Draw(tile)
        # Thicker stroke for better readability
        td.text(
            (20, 12), ch, font=font, fill=FG,
            stroke_width=3, stroke_fill=(255, 255, 255)
        )
        # Less rotation for clarity
        angle = random.randint(-12, 12)
        tile = tile.rotate(angle, resample=Image.BICUBIC, expand=True)
        y = y_base - random.randint(0, 8)
        img.paste(tile, (x, y), tile)
        x += cw + random.randint(4, 8)

    # Reduced noise for clearer image
    # Fewer lines
    for _ in range(6):
        x1, y1 = random.randint(0, IMG_W), random.randint(0, IMG_H)
        x2, y2 = random.randint(0, IMG_W), random.randint(0, IMG_H)
        draw.line((x1, y1, x2, y2), fill=NOISE, width=1)
    # Fewer points
    for _ in range(50):
        draw.point((random.randint(0, IMG_W - 1), random.randint(0, IMG_H - 1)), fill=NOISE)

    # Less aggressive filter for sharper image
    img = img.filter(ImageFilter.SMOOTH_MORE)

    buf = BytesIO()
    img.save(buf, format="PNG", optimize=True)
    return buf.getvalue()


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    website_id = fields.Many2one(
        'website', string="Website",
        default=lambda self: self.env['website'].get_current_website()
    )
    captcha_enabled = fields.Boolean("Enable Captcha")
    captcha_on_login = fields.Boolean("Login Form")
    captcha_on_signup = fields.Boolean("Signup Form")
    captcha_on_reset = fields.Boolean("Password Reset Form")
    captcha_not_verified_message = fields.Char(
        "Not Verified Message", default="Captcha not verified."
    )
    captcha_type = fields.Selection([
        ('math', 'Mathematical'),
        ('num', 'Numbers Image'),
        ('alpha', 'Alphabetic Image'),
    ], string="Captcha Type", default='math')

    # Mathematical
    math_operation = fields.Selection([
        ('add', 'Addition'), ('sub', 'Subtraction'),
        ('mul', 'Multiplication'), ('rnd', 'Random'),
    ], default='rnd', string="Algebraic Operation")
    math_rhs_len = fields.Selection([('9', '0–9'), ('99', '0–99')],
                                    default='9', string="RHS Digit Length")

    # Numbers Image
    num_include_symbols = fields.Boolean("Include Symbols (!@#$%^&=)")
    num_length = fields.Selection(
        [('4','4'),('5','5'),('6','6'),('7','7')], default='5',
        string="Captcha Length (Numbers)"
    )

    # Alphabetic Image
    alpha_include_caps = fields.Boolean("Include Capital Letters")
    alpha_include_symbols = fields.Boolean("Include Symbols")
    alpha_length = fields.Selection(
        [('4','4'),('5','5'),('6','6'),('7','7')], default='5',
        string="Captcha Length (Alphabetic)"
    )

    # Preview fields (computed, not stored)
    captcha_preview_text = fields.Char(
        readonly=True,
        compute="_compute_captcha_preview",
        help="Preview text that matches the preview image"
    )
    captcha_preview_image = fields.Binary(
        readonly=True,
        compute="_compute_captcha_preview",
        attachment=False,
        help="Preview image that matches the preview text"
    )
    captcha_preview_nonce = fields.Integer(
        default=0,
        help="Nonce to force recompute when refresh button is clicked"
    )

    # ---------- load/save (per-website via ICP) ----------
    @api.model
    def get_values(self):
        res = super().get_values()
        website = self.env['website'].get_current_website()
        ICP = self.env['ir.config_parameter'].sudo()

        def g(suffix, default=None):
            return ICP.get_param(_website_param_key(website, suffix), default)

        res.update(
            captcha_enabled=g('enabled', 'False') == 'True',
            captcha_on_login=g('on_login', 'True') == 'True',
            captcha_on_signup=g('on_signup', 'True') == 'True',
            captcha_on_reset=g('on_reset', 'True') == 'True',
            captcha_not_verified_message=g('message', "Captcha not verified."),
            captcha_type=g('type', 'math'),
            math_operation=g('math_operation', 'rnd'),
            math_rhs_len=g('math_rhs_len', '9'),
            num_include_symbols=g('num_include_symbols', 'False') == 'True',
            num_length=g('num_length', '5'),
            alpha_include_caps=g('alpha_include_caps', 'True') == 'True',
            alpha_include_symbols=g('alpha_include_symbols', 'False') == 'True',
            alpha_length=g('alpha_length', '5'),
        )
        return res

    def set_values(self):
        super().set_values()
        self.ensure_one()
        website = self.website_id or self.env['website'].get_current_website()
        ICP = self.env['ir.config_parameter'].sudo()

        def s(suffix, val):
            ICP.set_param(_website_param_key(website, suffix), str(val))

        s('enabled', self.captcha_enabled)
        s('on_login', self.captcha_on_login)
        s('on_signup', self.captcha_on_signup)
        s('on_reset', self.captcha_on_reset)
        s('message', self.captcha_not_verified_message or "Captcha not verified.")
        s('type', self.captcha_type or 'math')
        s('math_operation', self.math_operation or 'rnd')
        s('math_rhs_len', self.math_rhs_len or '9')
        s('num_include_symbols', self.num_include_symbols)
        s('num_length', self.num_length or '5')
        s('alpha_include_caps', self.alpha_include_caps)
        s('alpha_include_symbols', self.alpha_include_symbols)
        s('alpha_length', self.alpha_length or '5')

    @api.depends(
        'captcha_type', 'math_operation', 'math_rhs_len',
        'num_include_symbols', 'num_length',
        'alpha_include_caps', 'alpha_include_symbols', 'alpha_length',
        'captcha_preview_nonce'
    )
    def _compute_captcha_preview(self):
        """Compute preview text and image - both always show the same value."""
        for rec in self:
            # Reset preview fields
            rec.captcha_preview_text = False
            rec.captcha_preview_image = False

            # Use nonce as seed for deterministic random generation
            # This ensures same nonce always generates same values (no double computation issue)
            seed_value = hash((rec.id or 0, rec.captcha_preview_nonce or 0, 
                              rec.captcha_type or '', rec.math_operation or '',
                              rec.num_length or '', rec.alpha_length or ''))
            # Use local Random instance to avoid affecting global random state
            local_random = random.Random(seed_value)

            # Math Captcha (text only, no image)
            if rec.captcha_type == 'math':
                a = local_random.randint(1, 9)
                op_map = {
                    'add': '+',
                    'sub': '-',
                    'mul': '×',
                    'rnd': local_random.choice(['+', '-', '×']),
                }
                op = op_map.get(rec.math_operation or 'rnd', '+')
                b_max = 9 if (rec.math_rhs_len or '9') == '9' else 99
                b = local_random.randint(0, b_max)
                rec.captcha_preview_text = f"{a} {op} {b} = ?"
                continue

            # Image captchas require Pillow
            if Image is None:
                rec.captcha_preview_text = "Pillow not installed (no image preview)."
                continue

            # Generate the captcha text based on type
            if rec.captcha_type == 'num':
                pool = string.digits
                if rec.num_include_symbols:
                    pool += "!@#$%^&="
                length = int(rec.num_length or '5')
            else:  # alpha
                pool = string.ascii_lowercase
                if rec.alpha_include_caps:
                    pool += string.ascii_uppercase
                if rec.alpha_include_symbols:
                    pool += "!@#$%^&="
                length = int(rec.alpha_length or '5')

            # Generate the same text for both preview fields (using deterministic seed)
            # This ensures that even if compute is called multiple times, same nonce = same values
            preview_text = ''.join(local_random.choice(pool) for _ in range(max(1, length)))

            # Generate image from the same text to ensure synchronization
            png_bytes = _make_preview_image(preview_text)
            rec.captcha_preview_text = preview_text
            rec.captcha_preview_image = base64.b64encode(png_bytes).decode('ascii')


    def action_refresh_preview(self):
        """Refresh preview by incrementing nonce and computing synchronously."""
        self.ensure_one()
        # Increment nonce to trigger recompute
        self.captcha_preview_nonce += 1
        # Invalidate cache to ensure fresh computation
        self.invalidate_recordset(['captcha_preview_text', 'captcha_preview_image'])
        # Force immediate compute to ensure values are ready
        self._compute_captcha_preview()
        # Get the computed values (they should be fresh now)
        preview_text = self.captcha_preview_text or ''
        preview_image = self.captcha_preview_image or ''
        # Return preview values directly to avoid second RPC call
        return {
            'type': 'ir.actions.client',
            'tag': 'captcha_preview_update',
            'context': {
                'preview_text': preview_text,
                'preview_image': preview_image,
            }
        }

    def get_preview_values(self):
        """Return current preview values - ensure compute happens first."""
        self.ensure_one()
        # Force compute to ensure we have fresh values
        self._compute_captcha_preview()
        return {
            'preview_text': self.captcha_preview_text or '',
            'preview_image': self.captcha_preview_image or '',
        }

    # ---------- helper for controllers/templates ----------
    @api.model
    def get_site_config(self, website):
        ICP = self.env['ir.config_parameter'].sudo()

        def _get(suffix, default=None):
            return ICP.get_param(_website_param_key(website, suffix), default)

        def _to_bool(val):
            if val is None:
                return False
            if isinstance(val, bool):
                return val
            return str(val).strip().lower() in ('1', 'true', 't', 'yes', 'y', 'on')

        data = {
            'enabled': _to_bool(_get('enabled', False)),
            'on_login': _to_bool(_get('on_login', False)),
            'on_signup': _to_bool(_get('on_signup', False)),
            'on_reset': _to_bool(_get('on_reset', False)),
            'message': _get('message', "Captcha not verified."),
            'type': _get('type', 'math'),
            'math_operation': _get('math_operation', 'rnd'),
            'math_rhs_len': _get('math_rhs_len', '9'),
            'num_include_symbols': _to_bool(_get('num_include_symbols', False)),
            'num_length': _get('num_length', '5'),
            'alpha_include_caps': _to_bool(_get('alpha_include_caps', False)),
            'alpha_include_symbols': _to_bool(_get('alpha_include_symbols', False)),
            'alpha_length': _get('alpha_length', '5'),
        }
        return SimpleNamespace(**data)

    def action_configure_captcha(self):
        """Open the captcha configuration wizard."""
        return {
            'name': 'Configure Captcha',
            'type': 'ir.actions.act_window',
            'res_model': 'captcha.config.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_captcha_type': self.captcha_type,
                'default_math_operation': self.math_operation,
                'default_math_rhs_len': self.math_rhs_len,
                'default_num_include_symbols': self.num_include_symbols,
                'default_num_length': self.num_length,
                'default_alpha_include_caps': self.alpha_include_caps,
                'default_alpha_include_symbols': self.alpha_include_symbols,
                'default_alpha_length': self.alpha_length,
            }
        }


class CaptchaConfigWizard(models.TransientModel):
    _name = 'captcha.config.wizard'
    _description = 'Captcha Configuration Wizard'

    captcha_type = fields.Selection([
        ('math', 'Mathematical'),
        ('num', 'Numbers Image'),
        ('alpha', 'Alphabetic Image'),
    ], string="Captcha Type", required=True)

    # Mathematical Captcha fields
    math_operation = fields.Selection([
        ('add', 'Addition'), ('sub', 'Subtraction'),
        ('mul', 'Multiplication'), ('rnd', 'Random'),
    ], default='rnd', string="Algebraic Operation")
    math_rhs_len = fields.Selection([('9', '0–9'), ('99', '0–99')],
                                   default='9', string="RHS Digit Length")

    # Numbers Image fields
    num_include_symbols = fields.Boolean("Include Symbols (!@#$%^&=)")
    num_length = fields.Selection(
        [('4','4'),('5','5'),('6','6'),('7','7')], default='5',
        string="Captcha Length (Numbers)"
    )

    # Alphabetic Image fields
    alpha_include_caps = fields.Boolean("Include Capital Letters")
    alpha_include_symbols = fields.Boolean("Include Symbols")
    alpha_length = fields.Selection(
        [('4','4'),('5','5'),('6','6'),('7','7')], default='5',
        string="Captcha Length (Alphabetic)"
    )

    @api.onchange('captcha_type')
    def _onchange_captcha_type(self):
        """Update wizard fields based on captcha type"""
        if self.captcha_type == 'math':
            # Set defaults for math
            if not self.math_operation:
                self.math_operation = 'rnd'
            if not self.math_rhs_len:
                self.math_rhs_len = '9'
        elif self.captcha_type == 'num':
            # Set defaults for numbers
            if not self.num_length:
                self.num_length = '5'
        elif self.captcha_type == 'alpha':
            # Set defaults for alphabetic
            if not self.alpha_length:
                self.alpha_length = '5'

    def action_save_config(self):
        """Save the configuration and close wizard."""
        # Get or create the current settings record
        settings = self.env['res.config.settings'].search([], limit=1)
        if not settings:
            settings = self.env['res.config.settings'].create({})

        # Update the settings based on wizard values
        settings.write({
            'captcha_type': self.captcha_type,
            'math_operation': self.math_operation,
            'math_rhs_len': self.math_rhs_len,
            'num_include_symbols': self.num_include_symbols,
            'num_length': self.num_length,
            'alpha_include_caps': self.alpha_include_caps,
            'alpha_include_symbols': self.alpha_include_symbols,
            'alpha_length': self.alpha_length,
        })

        # Save the settings
        settings.set_values()

        return {'type': 'ir.actions.act_window_close'}
