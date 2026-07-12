
select
    -- identity
    id                      as product_id,
    sku,
    name,
    url_key,
    url_path,
    type,
    seller_id,
    seller_product_id,

    -- pricing
    price,
    list_price,
    original_price,
    discount,
    discount_rate,

    -- ratings & engagement
    rating_average,
    review_count,
    order_count,
    favourite_count,
    quantity_sold,

    -- product attributes
    brand_name,
    book_cover,
    has_ebook,
    bundle_deal,
    shippable,
    is_visible,
    is_flower,
    is_gift_card,

    -- inventory & availability
    availability,
    inventory,
    salable_type,
    stock_item,

    -- category
    primary_category_path,
    productset_id,
    productset_group_name,

    -- media
    thumbnail_url,
    thumbnail_width,
    thumbnail_height,

    -- misc
    url_review,
    extracted_at

from {{source ('silver', 'silver_listing')}}
where id is not null