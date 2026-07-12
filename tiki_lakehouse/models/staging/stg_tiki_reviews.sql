
select
    review_id,
    product_id,
    rating,
    title,
    content,
    thank_count,
    reviewer_name,
    reviewer_purchased,
    created_at,
    extracted_at

from {{source ('silver', 'silver_reviews')}}
where review_id is not null
    and product_id is not null

