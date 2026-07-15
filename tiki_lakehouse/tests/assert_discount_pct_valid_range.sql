select
    product_id,
    name,
    price,
    list_price,
    discount_pct
from {{ ref('fct_tiki_books') }}
where
    discount_pct < 0
    or discount_pct > 100