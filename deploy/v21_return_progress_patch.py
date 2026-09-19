"""Show completion only after receipt and refund completion are both confirmed."""
from pathlib import Path
from shutil import copyfile

source = Path(__file__).resolve().parent / 'v21_ui/static/assets/return-progress.js'
copyfile(source, Path('static/assets/return-progress.js'))

for page, script in (('mypage', 'mypage-returns'), ('return-request', 'return-request')):
    path = Path('static') / (page + '.html')
    text = path.read_text()
    old = f'<script src="assets/{script}.js"></script>'
    assert text.count(old) == 1, (page, old)
    new = '<script src="assets/return-progress.js?v=21-receipt-2"></script>' + f'<script src="assets/{script}.js?v=21-receipt-2"></script>'
    path.write_text(text.replace(old, new))

path = Path('app/returns.py')
text = path.read_text()
old = '        "refundStatus": r.refund_status,'
assert text.count(old) == 1
text = text.replace(old, old + '''
        "receiptConfirmed": bool(r.received_at),
        "refundCompleted": bool(r.request_type == "RETURN" and r.received_at
                                and r.status in {"REFUNDED", "COMPLETED"}
                                and r.refund_status in {"COMPLETED", "MANUAL_COMPLETED"}),''')
path.write_text(text)
print('V21 customer return completion now requires confirmed receipt and refund')
