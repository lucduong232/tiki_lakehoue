
select
    -- identity
    product_id,
    sku,
    name,
    url_key,

    -- content
    short_description,
    description,
    images,
    categories,

    -- pricing (duplicate từ listing, giữ để self-contained)
    price,
    list_price,
    discount_rate,

    -- ratings
    rating_average,
    review_count,
    inventory_status,

    -- book specs
    spec_publisher_vn,
    spec_publication_date,
    spec_dimensions,
    spec_book_cover,
    spec_number_of_page,
    spec_manufacturer,
    spec_language_book,
    spec_book_version,
    spec_isbn13,
    spec_brand,
    spec_origin,
    spec_brand_country,
    spec_dich_gia,
    spec_edition,
    spec_material,

    -- service / warranty
    spec_seller_delivery_method,
    spec_is_warranty_applied,
    spec_bookcare_service,
    spec_warranty_form,
    spec_warranty_time_period,
    spec_organization_name,
    spec_organization_address,
    spec_service_highlight_2,
    spec_service_highlight_3,

    extracted_at

from {{ source ('silver', 'silver_detail')}}
where product_id is not null
