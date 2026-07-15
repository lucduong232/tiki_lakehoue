select
    product_id,
    name,
    rating_average,
    review_count
from {{ ref('fct_tiki_books') }}
where
    review_count > 0
    and (
        rating_average < 1.0
        or rating_average > 5.0
    )