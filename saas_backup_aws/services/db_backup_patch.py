import base64
import io

from odoo.service import db

_original_dispatch = db.dispatch


def _backup_rpc(params):
    # params: [master_pwd, db_name, backup_format?]
    passwd, db_name = params[0], params[1]
    backup_format = params[2] if len(params) > 2 else 'zip'
    db.check_super(passwd)
    buffer = io.BytesIO()
    db.dump_db(db_name, buffer, backup_format=backup_format)
    buffer.seek(0)
    return base64.b64encode(buffer.read()).decode()


def dispatch(method, params):
    if method == 'backup':
        return _backup_rpc(params)
    return _original_dispatch(method, params)


# monkey-patch
db.dispatch = dispatch
