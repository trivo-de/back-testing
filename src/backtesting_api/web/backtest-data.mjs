/** Require a finite chart number without accepting blank values. */
const numeric = value => {
    if ((typeof value !== 'number' && typeof value !== 'string') || String(value).trim() === '' || !Number.isFinite(Number(value))) throw Error('Giá trị chart không hợp lệ.');
    return Number(value);
};
/** Require a canonical and valid calendar date. */
const day = value => {
    if (typeof value !== 'string' || !/^\d{4}-\d{2}-\d{2}$/.test(value) || !Number.isFinite(Date.parse(value)) || new Date(value).toISOString().slice(0, 10) !== value) throw Error('Ngày chart không hợp lệ.');
    return value;
};

/** Select result rows related to a fill, or return all rows without a selection. */
export function relatedRows(run, fillId) {
    const positions = run.open_positions ?? (run.open_position ? [run.open_position] : []);
    const points = run.schema_version === 3 ? run.pnl_history : run.equity_history;
    const pointTime = point => point.time ?? point.trading_date;
    const all = {fills: run.fills, trades: run.trades, position: positions,
        signals: run.signals, orders: run.orders, equity: points, selected: null};
    const selected = run.fills.find(/* Find the selected fill by its identifier. */ fill => fill.fill_id === fillId);
    if (!selected) return all;
    const order = run.orders.find(/* Find the order that produced the selected fill. */ item => item.order_id === selected.order_id);
    const exactEquity = points.filter(/* Select recorded points at the exact fill time. */ point => pointTime(point) === selected.fill_time);
    /** Compare a timestamp's date with the selected fill date. */
    const sameDay = value => value?.slice(0, 10) === selected.fill_time.slice(0, 10);
    return {
        fills: run.fills.filter(/* Select fills on the selected fill date. */ fill => sameDay(fill.fill_time)),
        trades: run.trades.filter(/* Select trades linked to the selected entry or exit fill. */ trade => trade.entry_fill_id === fillId || trade.entry_fill_ids?.includes(fillId) || trade.exit_fill_id === fillId),
        position: positions.filter(/* Select open positions linked to the selected entry fill. */ position => position.entry_fill_id === fillId || position.entry_fill_ids?.includes(fillId) || (run.schema_version === 3 && position.position_id === selected.position_id)),
        signals: run.signals.filter(/* Select the signal that produced the selected order. */ signal => signal.signal_id === order?.signal_id),
        orders: order ? [order] : [],
        equity: exactEquity.length ? exactEquity : points.filter(/* Select recorded points on the fill date when no exact time matches. */ point => sameDay(pointTime(point))),
        selected,
    };
}

/** Validate saved result and chart identities before building chart series. */
export function backtestData(run, payload) {
    if ([2, 3].includes(run.schema_version) || typeof payload.bars?.[0]?.time === 'number') return intradayData(run, payload);
    for (const key of ['run_id', 'dataset_id', 'dataset_version', 'content_hash']) {
        if (!run.metadata[key] || run.metadata[key] !== payload.metadata[key]) throw Error('Chart và result không cùng run/dataset.');
    }
    if (payload.metadata.symbol !== run.metadata.config.symbol || payload.metadata.timeframe !== '1D') throw Error('Sai symbol/timeframe.');
    for (const key of ['start_date', 'end_date']) {
        if (payload.metadata[key] !== run.metadata.config[key]) throw Error('Sai kỳ backtest.');
    }
    let previous = '';
    const candles = payload.bars.map(/* Validate and convert a daily candle for chart display. */ bar => {
        const time = day(bar.time);
        const [open, high, low, close, volume] = ['open', 'high', 'low', 'close', 'volume'].map(/* Read and validate a candle price or volume column. */ key => numeric(bar[key]));
        if (time <= previous || time < payload.metadata.start_date || time > payload.metadata.end_date || Math.min(open, high, low, close) <= 0 || volume < 0 || low > Math.min(open, close) || high < Math.max(open, close)) throw Error('OHLCV không nhất quán.');
        previous = time;
        return {time, open, high, low, close};
    });
    if (!candles.length) throw Error('Thiếu nến của run.');
    const dates = new Set(candles.map(/* Read a candle's chart date. */ bar => bar.time));
    const orders = new Map(run.orders.map(/* Index orders by their identifiers. */ order => [order.order_id, order]));
    const signals = new Map(run.signals.map(/* Index signals by their identifiers. */ signal => [signal.signal_id, signal]));
    const ids = new Set();
    previous = '';
    const fills = run.fills.map(/* Validate a daily fill against its order, signal, and chart date. */ fill => {
        const time = day(fill.fill_time), price = numeric(fill.fill_price);
        const order = orders.get(fill.order_id), signal = signals.get(order?.signal_id);
        if (!fill.fill_id || ids.has(fill.fill_id) || !dates.has(time) || time < previous || price <= 0 || !['BUY', 'SELL'].includes(fill.side) || !signal || order.status !== 'filled') throw Error('Fill không khớp chart hoặc audit.');
        ids.add(fill.fill_id); previous = time;
        return {...fill, reason: signal.reason};
    });
    previous = '';
    const equity = run.equity_history.map(/* Validate daily equity order and convert equity values for display. */ point => {
        const time = day(point.trading_date), value = numeric(point.equity);
        if (!dates.has(time) || time <= previous) throw Error('Equity không khớp chart.');
        previous = time;
        return {time, value};
    });
    if (!equity.length || equity.at(-1).value !== numeric(run.summary.final_equity)) throw Error('Equity không khớp summary.');
    if (!Array.isArray(payload.market) || payload.market.length !== candles.length) throw Error('Thiếu VN-Index cho SMA200.');
    previous = '';
    const market = payload.market.map(/* Validate market dates, close values, and optional SMA200 values. */ point => {
        const time = day(point.time), close = numeric(point.close);
        const sma200 = point.sma200 === null ? null : numeric(point.sma200);
        if (time <= previous || !dates.has(time) || close <= 0 || (sma200 !== null && sma200 <= 0)) throw Error('VN-Index/SMA200 không nhất quán.');
        previous = time;
        return {time, close, sma200};
    });
    return {candles, fills, equity, market,
        volume: payload.bars.map(/* Build a colored volume point from a source candle. */ bar => ({time: bar.time, value: numeric(bar.volume), color: numeric(bar.close) >= numeric(bar.open) ? '#269982' : '#d95866'})),
        markers: fills.map(/* Build a directional marker from a saved fill. */ fill => ({id: fill.fill_id, time: fill.fill_time, price: numeric(fill.fill_price),
            position: fill.side === 'BUY' ? 'atPriceBottom' : 'atPriceTop',
            shape: fill.side === 'BUY' ? 'arrowUp' : 'arrowDown', size: 0.65,
            borderColor: {light: '#000', dark: '#fff'}, borderWidth: 1.5,
            color: fill.side === 'BUY' ? '#1565c0' : '#ef6c00'})),
    };
}

/** Validate intraday chart sources, fills, and timing without recomputing results. */
function intradayData(run, payload) {
    const intraday = payload.metadata?.resolution === '5';
    const keys = [2, 3].includes(run.schema_version) ? ['run_id', 'input_hash', 'policy_hash'] : ['run_id', 'dataset_version', 'content_hash'];
    for (const key of keys) if (!run.metadata[key] || run.metadata[key] !== payload.metadata[key]) throw Error('Chart và kết quả khác nguồn.');
    /** Convert a supplied timestamp to validated Unix seconds. */
    const timestamp = value => {
        const stamp = typeof value === 'number' ? value : Date.parse(value) / 1000;
        if (!Number.isFinite(stamp) || !Number.isInteger(stamp)) throw Error('Thời gian chart không hợp lệ.');
        return stamp;
    };
    /** Validate and convert an ordered OHLC source series. */
    const rows = values => {
        let previous = -Infinity;
        return values.map(/* Validate one source candle and its chronological order. */ row => {
            const time = timestamp(row.time);
            const [open, high, low, close] = ['open', 'high', 'low', 'close'].map(/* Read and validate a source candle price column. */ k => numeric(row[k]));
            if (time <= previous || low <= 0 || low > Math.min(open, close) || high < Math.max(open, close)) throw Error('OHLC không hợp lệ.');
            previous = time;
            return {time, open, high, low, close};
        });
    };
    const sourceBars = new Map(payload.bars.map(/* Index source candles by their Unix timestamp. */ row => [timestamp(row.time), row]));
    const candles = rows(payload.bars);
    if (!candles.length) throw Error('Thiếu nến của lần chạy.');
    const dates = new Set(candles.map(/* Read an intraday candle's chart timestamp. */ b => b.time));
    const auctions = new Map((payload.auctions ?? []).map(/* Index auction observations by their match timestamp. */ a => [timestamp(a.time), a]));
    // A whitespace point reserves auction time without inventing an OHLC candle.
    for (const time of auctions.keys()) if (!dates.has(time)) candles.push({time});
    candles.sort(/* Sort candle and auction whitespace points chronologically. */ (a, b) => a.time - b.time);
    const orders = new Map(run.orders.map(/* Index intraday orders by their identifiers. */ o => [o.order_id, o]));
    const signals = new Map(run.signals.map(/* Index intraday signals by their identifiers. */ s => [s.signal_id, s]));
    const ids = new Set();
    const fills = run.fills.map(/* Validate an intraday fill against its order, signal, and source observation. */ fill => {
        fill = {...fill, fill_price: fill.fill_price ?? fill.price};
        const order = orders.get(fill.order_id), signal = signals.get(order?.signal_id);
        const chartTime = timestamp(fill.bar_time ?? fill.fill_time);
        const auction = auctions.get(chartTime);
        const sourceBar = sourceBars.get(chartTime), auctionType = ['ATO', 'ATC'].includes(fill.order_type);
        const auctionFill = auctionType && ((auction?.status === 'matched'
            && auction.contract_code === fill.contract_code && numeric(auction.price) === numeric(fill.fill_price))
            || (sourceBar?.contract_code === fill.contract_code
                && numeric(sourceBar[fill.order_type === 'ATO' ? 'open' : 'close']) === numeric(fill.fill_price)));
        const orderHasFill = order?.status?.toLowerCase() === 'filled' || Number(order?.filled_quantity) > 0;
        if ((!dates.has(chartTime) && !auctionFill) || (auctionType && !auctionFill)
            || !signal || !orderHasFill || ids.has(fill.fill_id)
            || !['BUY', 'SELL', 'LONG', 'SHORT', 'CLOSE'].includes(fill.side) || numeric(fill.fill_price) <= 0) throw Error('Khớp lệnh không thuộc chart.');
        ids.add(fill.fill_id);
        return {...fill, chartTime, signal_time: fill.signal_time ?? signal.decision_time ?? signal.signal_time, reason: signal.reason};
    });
    const volume = payload.bars.filter(/* Keep candles with an explicitly supplied volume. */ b => b.volume !== null && b.volume !== undefined).map(/* Validate and color a supplied intraday volume point. */ b => {
        const value = numeric(b.volume);
        if (value < 0) throw Error('Khối lượng âm.');
        return {time: timestamp(b.time), value, color: numeric(b.close) >= numeric(b.open) ? '#269982' : '#d95866'};
    });
    let previous = -Infinity;
    const priceOnly = run.schema_version === 3;
    const equity = (priceOnly ? run.pnl_history : run.equity_history).map(/* Read the stored P&L or equity series without recalculating it. */ p => {
        const time = timestamp(p.time ?? p.trading_date);
        if (time <= previous) throw Error('Thứ tự vốn không hợp lệ.');
        previous = time;
        return {time, value: numeric(priceOnly ? p.total_pnl : p.equity)};
    });
    if (!equity.length || equity.at(-1).value !== numeric(priceOnly ? run.summary.total_pnl : run.summary.final_equity)) throw Error('Đường tích lũy không khớp kết quả.');
    const market = rows(payload.market_bars ?? []).map(/* Project market candles onto the market close series. */ b => ({time: b.time, close: b.close}));
    const indicators = {};
    for (const row of run.evaluations ?? []) for (const [name, value] of Object.entries(row.indicators ?? {})) {
        if (value === null) continue;
        const points = indicators[name] ??= [];
        const point = {time: timestamp(row.indicator_times?.[name] ?? row.time), value: numeric(value)};
        if (!points.length || point.time > points.at(-1).time) points.push(point);
    }
    const markers = fills.map(/* Build an intraday fill marker using its action and position direction. */ fill => {
        const buying = ['BUY', 'LONG'].includes(fill.side) || (fill.side === 'CLOSE' && fill.direction === 'SHORT');
        return {id: fill.fill_id, time: fill.chartTime, price: numeric(fill.fill_price),
            position: buying ? 'atPriceBottom' : 'atPriceTop', shape: buying ? 'arrowUp' : 'arrowDown',
            color: buying ? '#1565c0' : '#ef6c00', size: .65, borderColor: {light: '#000', dark: '#fff'}, borderWidth: 1.5};
    }).sort(/* Sort fill markers chronologically. */ (a, b) => a.time - b.time);
    return {candles, volume, fills, equity, market, markers, indicators, intraday, priceOnly};
}
