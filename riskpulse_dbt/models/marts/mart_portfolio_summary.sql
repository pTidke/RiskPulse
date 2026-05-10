with windows as (
    select * from {{ ref('fct_vwap_windows') }}
),

summary as (
    select
        symbol,
        count(*)                          as total_windows,
        round(avg(vwap), 2)               as avg_vwap,
        round(min(min_price), 2)          as session_low,
        round(max(max_price), 2)          as session_high,
        round(max(max_price) - min(min_price), 2) as session_range,
        round(avg(volatility), 6)         as avg_volatility,
        round(max(volatility), 6)         as peak_volatility,
        sum(trade_count)                  as total_trades,
        round(sum(total_volume), 0)       as total_volume,
        round(max(drawdown_pct), 2)       as max_drawdown_pct,
        min(window_start)                 as session_start,
        max(window_end)                   as last_updated
    from windows
    group by symbol
)

select
    *,
    case
        when avg_volatility > 0.05  then 'HIGH'
        when avg_volatility > 0.015 then 'MEDIUM'
        else                             'LOW'
    end as volatility_regime
from summary
order by avg_volatility desc
