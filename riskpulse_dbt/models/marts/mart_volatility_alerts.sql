with windows as (
    select * from {{ ref('fct_vwap_windows') }}
),

latest as (
    select *,
        row_number() over (
            partition by symbol order by window_end desc
        ) as rn
    from windows
),

alerts as (
    select
        symbol,
        window_end                         as alert_time,
        vwap                               as current_vwap,
        session_high,
        round(drawdown_pct, 2)             as drawdown_pct,
        round(volatility, 6)               as volatility,
        volatility_rank,
        case
            when drawdown_pct > 3           then 'DRAWDOWN'
            when volatility_rank = 1        then 'HIGHEST_VOL'
            else                                 'WATCH'
        end                                as alert_type
    from latest
    where rn = 1
      and (drawdown_pct > 3 or volatility_rank <= 3)
)

select * from alerts
order by drawdown_pct desc nulls last, volatility desc
