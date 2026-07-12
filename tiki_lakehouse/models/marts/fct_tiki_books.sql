with listing as (
    select * from {{ ref('stg_tiki_listing') }}
),

detail as (
    select * from {{ ref('stg_tiki_detail') }}
),

joined as (
    select
        -- identity
        l.product_id,
        l.sku,
        l.name,
        l.url_key,
        l.url_path,
        l.type,
        l.seller_id,
        l.seller_product_id,

        -- pricing
        l.price,
        l.list_price,
        l.original_price,
        l.discount,
        l.discount_rate,

        -- computed: discount percent từ list_price (chuẩn hơn dùng discount_rate raw)
        case
            when l.list_price is not null and l.list_price > 0
                then round((l.list_price - l.price) * 100.0 / l.list_price, 2)
            else 0
        end as discount_pct,

        -- ratings & engagement
        l.rating_average,
        l.review_count,
        l.order_count,
        l.favourite_count,
        l.quantity_sold,

        -- computed: có review chưa
        case
            when l.review_count is not null and l.review_count > 0 then true
            else false
        end as has_reviews,

        -- product attributes
        l.brand_name,
        l.book_cover,
        l.has_ebook,
        l.bundle_deal,
        l.shippable,
        l.is_visible,

        -- category
        l.primary_category_path,
        l.productset_id,
        l.productset_group_name,

        -- inventory
        l.availability,
        l.inventory,
        l.salable_type,

        -- media
        l.thumbnail_url,
        l.url_review,

        -- book specs (từ detail)
        d.short_description,
        d.spec_publisher_vn,
        d.spec_publication_date,
        d.spec_book_cover,
        d.spec_number_of_page,
        d.spec_language_book,
        d.spec_book_version,
        d.spec_isbn13,
        d.spec_brand,
        d.spec_origin,
        d.spec_dich_gia,
        d.spec_edition,
        d.spec_dimensions,
        d.inventory_status,
        d.categories,

        l.extracted_at

    from listing l
    left join detail d on l.product_id = d.product_id
)

select * from joined