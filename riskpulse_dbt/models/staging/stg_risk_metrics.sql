with source as (
    select * from read_parquet('../data/risk_metrics/**/*.parquet')
),

cleaned as (
    select
        symbol,
        window_start::timestamp as window_start,
        window_end::timestamp   as window_end,
        vwap,
        min_price,
        max_price,
        volatility,
        price_range,
        trade_count,
        total_volume,
        -- deduplicate on symbol + window_start
        row_number() over (
            partition by symbol, window_start
            order by window_end desc
        ) as rn
    from source
)

select
    symbol,
    window_start,
    window_end,
    vwap,
    min_price,
    max_price,
    volatility,
    price_range,
    trade_count,
    total_volume
from cleaned
where rn = 1
