with reviews as (
    select * from {{ ref('stg_tiki_reviews') }}
),

books as (
    select
        product_id,
        name,
        primary_category_path,
        brand_name,
        price,
        discount_pct,
        rating_average,
        spec_publisher_vn,
        spec_language_book,
        spec_isbn13
    from {{ ref('fct_tiki_books') }}
),

joined as (
    select
        -- review fields
        r.review_id,
        r.product_id,
        r.rating,
        r.title,
        r.content,
        r.thank_count,
        r.reviewer_name,
        r.reviewer_purchased,
        r.created_at,

        -- book context
        b.name                  as product_name,
        b.primary_category_path,
        b.brand_name,
        b.price,
        b.discount_pct,
        b.rating_average,
        b.spec_publisher_vn,
        b.spec_language_book,
        b.spec_isbn13,

        r.extracted_at

    from reviews r
    left join books b on r.product_id = b.product_id
)

select * from joined