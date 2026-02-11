import base64
import io

from odoo.service import common as service_common, db


def backup(master_pwd, db_name, backup_format='zip'):
    """Expose db.dump_db over RPC with super-admin check."""
    service_common.check_super(master_pwd)
    buffer = io.BytesIO()
    db.dump_db(db_name, buffer, backup_format=backup_format)
    buffer.seek(0)
    return base64.b64encode(buffer.read()).decode()


db.dispatch['backup'] = backup

