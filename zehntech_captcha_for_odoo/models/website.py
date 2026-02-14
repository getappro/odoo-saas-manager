from odoo import models, fields

class Website(models.Model):
    _inherit = 'website'
    
    captcha_enabled = fields.Boolean(string='Enable Captcha', default=False)
    captcha_type = fields.Selection([
        ('mathematical', 'Mathematical'),
        ('numeric_image', 'Numbers Image'),
        ('alphabetic_image', 'Alphabetic Image')
    ], string='Captcha Type', default='mathematical')
    
    algebraic_operations = fields.Selection([
        ('addition', 'Addition'),
        ('subtraction', 'Subtraction'),
        ('multiplication', 'Multiplication'),
        ('random', 'Random')
    ], string='Algebraic Operations', default='addition')
    
    rhs_digit_length = fields.Selection([
        ('0-9', '0-9'),
        ('0-99', '0-99')
    ], string='RHS Digit Length', default='0-9')
    
    include_symbols = fields.Boolean(string='Include Symbols')
    captcha_length = fields.Integer(string='Captcha Length', default=6)
    include_capital = fields.Boolean(string='Include Capital Letters') 