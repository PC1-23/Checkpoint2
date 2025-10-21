import csv
from io import StringIO
from .registry import register_adapter

def parse_csv(payload: bytes, content_type: str):
    s = payload.decode('utf-8')
    reader = csv.DictReader(StringIO(s))
    out = []
    for row in reader:
        price = row.get('price_cents') or row.get('price') or '0'
        try:
            price_cents = int(price)
        except Exception:
            try:
                price_cents = int(float(price) * 100)
            except Exception:
                price_cents = 0
        sku = str(row.get('sku') or row.get('id') or '').strip()
        name = str(row.get('name', '')).strip()
        out.append({
            'sku': sku,
            'name': name,
            'price_cents': price_cents,
            'stock': int(row.get('stock', 0)),
            'partner_id': row.get('partner_id', 'unknown'),
            'extra': row,
        })
    return out

register_adapter('text/csv', parse_csv)
