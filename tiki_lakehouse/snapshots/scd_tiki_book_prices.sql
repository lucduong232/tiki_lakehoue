{% snapshot scd_tiki_book_prices%}

{{ 
    config(
      target_schema='snapshots',
      unique_key='product_id',
      strategy='check',
      check_cols=['price', 'discount_rate'],
      hard_deletes='invalidate'
    ) 
}}

select
    product_id,
    name,
    price,
    original_price,
    discount_rate,
    brand_name,
    extracted_at   
from {{ ref('fct_tiki_books') }}
 
{% endsnapshot %}