select
    product_id,
    name,
    brand_name, 
    price,
    discount_rate, 
    -- Metadata từ dbt snapshot
    dbt_valid_from                                          as valid_from,
    coalesce(dbt_valid_to, current_timestamp)              as valid_to,
    dbt_valid_to is null                                    as is_current,
 
    -- Tính số ngày giữ nguyên mức giá này
    datediff(
        'day',
        dbt_valid_from,
        coalesce(dbt_valid_to, current_timestamp)
    )                                                       as days_at_price
 
{# from {{ source('snapshots', 'scd_tiki_book_prices') }} #}
from {{ ref('scd_tiki_book_prices')}}