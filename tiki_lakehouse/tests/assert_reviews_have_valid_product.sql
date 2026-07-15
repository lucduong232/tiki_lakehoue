select
    r.review_id,
    r.product_id,
    r.reviewer_name
from {{ ref('fct_tiki_reviews') }} r
left join {{ ref('fct_tiki_books') }} b on r.product_id = b.product_id
where b.product_id is null