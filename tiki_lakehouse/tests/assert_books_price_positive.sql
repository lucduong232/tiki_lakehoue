select 
    product_id,
    name,
    price
from {{ ref("fct_tiki_books")}}
where price < 0