with base as (
    select * from {{ ref('stg_risk_metrics') }}
),

enriched as (
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
        total_volume,
        -- session high up to this window
        max(max_price) over (
            partition by symbol
            order by window_start
            rows between unbounded preceding and current row
        ) as session_high,
        -- drawdown from session high
        round(
            (max(max_price) over (
                partition by symbol
                order by window_start
                rows between unbounded preceding and current row
            ) - vwap)
            / nullif(max(max_price) over (
                partition by symbol
                order by window_start
                rows between unbounded preceding and current row
            ), 0) * 100
        , 4) as drawdown_pct,
        -- volatility rank across all symbols in this window
        rank() over (
            partition by window_start
            order by volatility desc
        ) as volatility_rank
    from base
)

select * from enriched
