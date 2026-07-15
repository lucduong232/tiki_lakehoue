{% test assert_not_null_when(model, column_name, when_column, when_value) %}
select {{ column_name }}, {{ when_column }}
from {{ model }}
where
    {{ when_column }} = '{{ when_value }}'
    and {{ column_name }} is null

{% endtest %}