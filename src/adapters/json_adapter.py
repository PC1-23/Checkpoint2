import json
from .registry import register_adapter

def parse_json(payload: bytes, content_type: str):
    data = json.loads(payload.decode('utf-8'))
    out = []
    for item in data:
        sku = str(item.get('sku') or item.get('id') or '').strip()
        name = str(item.get('name', '')).strip()
        price = item.get('price_cents') if item.get('price_cents') is not None else item.get('price', 0)
        if isinstance(price, int):
            price_cents = price
        elif isinstance(price, float):
            price_cents = int(round(price * 100))
        else:
            try:
                price_cents = int(price)
            except Exception:
                try:
                    price_cents = int(float(price) * 100)
                except Exception:
                    price_cents = 0
        out.append({
            'sku': sku,
            'name': name,
            'price_cents': price_cents,
            'stock': int(item.get('stock', 0)),
            'partner_id': item.get('partner_id', 'unknown'),
            'extra': item,
        })
    return out

register_adapter('application/json', parse_json)
