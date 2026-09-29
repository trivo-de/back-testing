const numeric = value => {
    if ((typeof value !== 'number' && typeof value !== 'string') || String(value).trim() === '' || !Number.isFinite(Number(value))) throw Error('Giá trị chart không hợp lệ.');
    return Number(value);
};
const day = value => {
    if (typeof value !== 'string' || !/^\d{4}-\d{2}-\d{2}$/.test(value) || !Number.isFinite(Date.parse(value)) || new Date(value).toISOString().slice(0, 10) !== value) throw Error('Ngày chart không hợp lệ.');
    return value;
};

export function relatedRows(run, fillId) {
    const all = {fills: run.fills, trades: run.trades, position: run.open_position ? [run.open_position] : [],
        signals: run.signals, orders: run.orders, equity: run.equity_history, selected: null};
    const selected = run.fills.find(fill => fill.fill_id === fillId);
    if (!selected) return all;
    const order = run.orders.find(item => item.order_id === selected.order_id);
    const exactEquity = run.equity_history.filter(point => point.trading_date === selected.fill_time);
    const sameDay = value => value?.slice(0, 10) === selected.fill_time.slice(0, 10);
    return {
        fills: run.fills.filter(fill => sameDay(fill.fill_time)),
        trades: run.trades.filter(trade => trade.entry_fill_id === fillId || trade.exit_fill_id === fillId),
        position: run.open_position?.entry_fill_id === fillId ? [run.open_position] : [],
        signals: run.signals.filter(signal => signal.signal_id === order?.signal_id),
        orders: order ? [order] : [],
        equity: exactEquity.length ? exactEquity : run.equity_history.filter(point => sameDay(point.trading_date)),
        selected,
    };
}

export function backtestData(run, payload) {
    if (run.schema_version === 2 || typeof payload.bars?.[0]?.time === 'number') return intradayData(run, payload);
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
            borderColor: {light: '#000', dark: '#fff'}, borderWidth: 1.5,
            color: fill.side === 'BUY' ? '#1565c0' : '#ef6c00'})),
    };
}

function intradayData(run, payload) {
    const intraday = payload.metadata?.resolution === '5';
    const keys = run.schema_version === 2 ? ['run_id', 'input_hash', 'policy_hash'] : ['run_id', 'dataset_version', 'content_hash'];
    for (const key of keys) if (!run.metadata[key] || run.metadata[key] !== payload.metadata[key]) throw Error('Chart và kết quả khác nguồn.');
    const timestamp = value => {
        const stamp = typeof value === 'number' ? value : Date.parse(value) / 1000;
        if (!Number.isFinite(stamp) || !Number.isInteger(stamp)) throw Error('Thời gian chart không hợp lệ.');
        return stamp;
    };
    const rows = values => {
        let previous = -Infinity;
        return values.map(row => {
            const time = timestamp(row.time);
            const [open, high, low, close] = ['open', 'high', 'low', 'close'].map(k => numeric(row[k]));
            if (time <= previous || low <= 0 || low > Math.min(open, close) || high < Math.max(open, close)) throw Error('OHLC không hợp lệ.');
            previous = time;
            return {time, open, high, low, close};
        });
    };
    const candles = rows(payload.bars);
    if (!candles.length) throw Error('Thiếu nến của lần chạy.');
    const dates = new Set(candles.map(b => b.time));
    const orders = new Map(run.orders.map(o => [o.order_id, o]));
    const signals = new Map(run.signals.map(s => [s.signal_id, s]));
    const ids = new Set();
    const fills = run.fills.map(fill => {
        const order = orders.get(fill.order_id), signal = signals.get(order?.signal_id);
        const chartTime = timestamp(fill.bar_time ?? fill.fill_time);
        if (!dates.has(chartTime) || !signal || order.status !== 'filled' || ids.has(fill.fill_id)
            || !['BUY', 'SELL', 'LONG', 'SHORT', 'CLOSE'].includes(fill.side) || numeric(fill.fill_price) <= 0) throw Error('Khớp lệnh không thuộc chart.');
        ids.add(fill.fill_id);
        return {...fill, chartTime, reason: signal.reason};
    });
    const volume = payload.bars.filter(b => b.volume !== null && b.volume !== undefined).map(b => {
        const value = numeric(b.volume);
        if (value < 0) throw Error('Khối lượng âm.');
        return {time: timestamp(b.time), value, color: numeric(b.close) >= numeric(b.open) ? '#269982' : '#d95866'};
    });
    let previous = -Infinity;
    const equity = run.equity_history.map(p => {
        const time = timestamp(p.trading_date);
        if (time <= previous) throw Error('Thứ tự vốn không hợp lệ.');
        previous = time;
        return {time, value: numeric(p.equity)};
    });
    if (!equity.length || equity.at(-1).value !== numeric(run.summary.final_equity)) throw Error('Vốn không khớp kết quả.');
    const market = rows(payload.market_bars ?? []).map(b => ({time: b.time, close: b.close}));
    const indicators = {};
    for (const row of run.evaluations ?? []) for (const [name, value] of Object.entries(row.indicators ?? {})) {
        if (value === null) continue;
        const points = indicators[name] ??= [];
        const point = {time: timestamp(row.indicator_times?.[name] ?? row.time), value: numeric(value)};
        if (!points.length || point.time > points.at(-1).time) points.push(point);
    }
    const markers = fills.map(fill => {
        const buying = ['BUY', 'LONG'].includes(fill.side) || (fill.side === 'CLOSE' && fill.direction === 'SHORT');
        return {id: fill.fill_id, time: fill.chartTime, price: numeric(fill.fill_price),
            position: buying ? 'atPriceBottom' : 'atPriceTop', shape: buying ? 'arrowUp' : 'arrowDown',
            color: buying ? '#1565c0' : '#ef6c00', size: .65, borderColor: {light: '#000', dark: '#fff'}, borderWidth: 1.5};
    }).sort((a, b) => a.time - b.time);
    return {candles, volume, fills, equity, market, markers, indicators, intraday};
}
