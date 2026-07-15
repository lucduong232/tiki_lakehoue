select
    product_id,
    name,
    price,
    list_price,
    discount_pct
from {{ ref('fct_tiki_books') }}
where
    list_price is not null
    and list_price < price