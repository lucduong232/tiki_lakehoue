select
    product_id,
    name,
    review_count,
    has_reviews
from {{ ref('fct_tiki_books') }}
where
    (has_reviews = true  and (review_count is null or review_count = 0))
    or (has_reviews = false and review_count > 0)