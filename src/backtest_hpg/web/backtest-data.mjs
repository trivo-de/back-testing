const numeric = value => {
    if ((typeof value !== 'number' && typeof value !== 'string') || String(value).trim() === '' || !Number.isFinite(Number(value))) throw Error('Giá trị chart không hợp lệ.');
    return Number(value);
};
const day = value => {
    if (typeof value !== 'string' || !/^\d{4}-\d{2}-\d{2}$/.test(value) || !Number.isFinite(Date.parse(value)) || new Date(value).toISOString().slice(0, 10) !== value) throw Error('Ngày chart không hợp lệ.');
    return value;
};

export function backtestData(run, payload) {
    for (const key of ['run_id', 'dataset_id', 'dataset_version', 'content_hash']) {
        if (!run.metadata[key] || run.metadata[key] !== payload.metadata[key]) throw Error('Chart và result không cùng run/dataset.');
    }
    if (payload.metadata.symbol !== run.metadata.config.symbol || payload.metadata.timeframe !== '1D') throw Error('Sai symbol/timeframe.');
    for (const key of ['start_date', 'end_date']) {
        if (payload.metadata[key] !== run.metadata.config[key]) throw Error('Sai kỳ backtest.');
    }
    let previous = '';
    const candles = payload.bars.map(bar => {
        const time = day(bar.time);
        const [open, high, low, close, volume] = ['open', 'high', 'low', 'close', 'volume'].map(key => numeric(bar[key]));
        if (time <= previous || time < payload.metadata.start_date || time > payload.metadata.end_date || Math.min(open, high, low, close) <= 0 || volume < 0 || low > Math.min(open, close) || high < Math.max(open, close)) throw Error('OHLCV không nhất quán.');
        previous = time;
        return {time, open, high, low, close};
    });
    if (!candles.length) throw Error('Thiếu nến của run.');
    const dates = new Set(candles.map(bar => bar.time));
    const orders = new Map(run.orders.map(order => [order.order_id, order]));
    const signals = new Map(run.signals.map(signal => [signal.signal_id, signal]));
    const ids = new Set();
    previous = '';
    const fills = run.fills.map(fill => {
        const time = day(fill.fill_time), price = numeric(fill.fill_price);
        const order = orders.get(fill.order_id), signal = signals.get(order?.signal_id);
        if (!fill.fill_id || ids.has(fill.fill_id) || !dates.has(time) || time < previous || price <= 0 || !['BUY', 'SELL'].includes(fill.side) || !signal || order.status !== 'filled') throw Error('Fill không khớp chart hoặc audit.');
        ids.add(fill.fill_id); previous = time;
        return {...fill, reason: signal.reason};
    });
    previous = '';
    const equity = run.equity_history.map(point => {
        const time = day(point.trading_date), value = numeric(point.equity);
        if (!dates.has(time) || time <= previous) throw Error('Equity không khớp chart.');
        previous = time;
        return {time, value};
    });
    if (!equity.length || equity.at(-1).value !== numeric(run.summary.final_equity)) throw Error('Equity không khớp summary.');
    if (!Array.isArray(payload.market) || payload.market.length !== candles.length) throw Error('Thiếu VN-Index cho SMA200.');
    previous = '';
    const market = payload.market.map(point => {
        const time = day(point.time), close = numeric(point.close);
        const sma200 = point.sma200 === null ? null : numeric(point.sma200);
        if (time <= previous || !dates.has(time) || close <= 0 || (sma200 !== null && sma200 <= 0)) throw Error('VN-Index/SMA200 không nhất quán.');
        previous = time;
        return {time, close, sma200};
    });
    return {candles, fills, equity, market,
        volume: payload.bars.map(bar => ({time: bar.time, value: numeric(bar.volume), color: numeric(bar.close) >= numeric(bar.open) ? '#269982' : '#d95866'})),
        markers: fills.map(fill => ({id: fill.fill_id, time: fill.fill_time, price: numeric(fill.fill_price),
            position: fill.side === 'BUY' ? 'atPriceBottom' : 'atPriceTop',
            shape: fill.side === 'BUY' ? 'arrowUp' : 'arrowDown', size: 0.65,
            color: fill.side === 'BUY' ? '#1565c0' : '#ef6c00'})),
    };
}
