with actual_counts as (
    select
        product_id,
        count(*) as crawled_review_count
    from {{ ref('fct_tiki_reviews') }}
    group by product_id
)
 
select
    b.product_id,
    b.name,
    b.review_count      as reported_review_count,
    a.crawled_review_count
from {{ ref('fct_tiki_books') }} b
join actual_counts a on b.product_id = a.product_id
where a.crawled_review_count > b.review_count