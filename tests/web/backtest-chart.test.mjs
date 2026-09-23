import test from 'node:test';
import assert from 'node:assert/strict';
import {backtestData, relatedRows} from '../../src/backtest_hpg/web/backtest-data.mjs';

test('exact executed markers, provenance and equity come from the same run', () => {
    const meta = {run_id: 'run', dataset_id: 'd', dataset_version: '1', content_hash: 'hash'};
    const config = {symbol: 'HPG', start_date: '2020-01-01', end_date: '2020-01-03'};
    const run = {metadata: {...meta, config},
        orders: [{order_id: 'o', signal_id: 's', status: 'filled'}],
        signals: [{signal_id: 's', reason: '<script>literal</script>'}],
        fills: [{fill_id: 'f', order_id: 'o', fill_time: '2020-01-03', signal_time: '2020-01-02', fill_price: '106', side: 'BUY'}],
        equity_history: [{trading_date: '2020-01-03', equity: '900'}], summary: {final_equity: '900'}};
    const payload = {metadata: {...meta, ...config, timeframe: '1D'},
        bars: [{time: '2020-01-03', open: '100', high: '105', low: '98', close: '103', volume: '0'}],
        market: [{time: '2020-01-03', close: '800', sma200: '750'}]};
    const mapped = backtestData(run, payload);
    assert.equal(mapped.markers[0].time, '2020-01-03');
    assert.equal(mapped.markers[0].price, 106); // Slippage outside the candle is preserved.
    assert.equal(mapped.markers[0].position, 'atPriceBottom');
    assert.equal(mapped.markers[0].size, 0.65);
    assert.deepEqual(mapped.markers[0].borderColor, {light: '#000', dark: '#fff'});
    assert.equal(mapped.markers[0].borderWidth, 1.5);
    assert.equal(mapped.markers[0].color, '#1565c0');
    assert.equal(mapped.markers[0].text, undefined);
    const sell = backtestData({...run, fills: [{...run.fills[0], side: 'SELL'}]}, payload).markers[0];
    assert.equal(sell.position, 'atPriceTop');
    assert.equal(sell.shape, 'arrowDown');
    assert.equal(sell.color, '#ef6c00');
    assert.equal(sell.price, 106);
    assert.equal(mapped.fills[0].reason, '<script>literal</script>');
    assert.equal(mapped.volume[0].value, 0);
    assert.equal(mapped.equity[0].value, 900);
    assert.deepEqual(mapped.market[0], {time: '2020-01-03', close: 800, sma200: 750});
    assert.deepEqual(backtestData({...run, fills: []}, payload).markers, []);
    for (const key of Object.keys(meta)) assert.throws(() => backtestData(run, {...payload, metadata: {...payload.metadata, [key]: 'different'}}));
    assert.throws(() => backtestData(run, {...payload, bars: []}));
    assert.throws(() => backtestData(run, {...payload, bars: [...payload.bars, ...payload.bars]}));
    assert.throws(() => backtestData(run, {...payload, bars: [{...payload.bars[0], high: null}]}));
    assert.throws(() => backtestData({...run, fills: [{...run.fills[0], fill_time: '2020-01-02'}]}, payload));
    assert.throws(() => backtestData({...run, orders: [{...run.orders[0], status: 'rejected'}]}, payload));
    assert.throws(() => backtestData({...run, summary: {final_equity: '901'}}, payload));
    assert.throws(() => backtestData(run, {...payload, market: []}));
    assert.throws(() => backtestData(run, {...payload, market: [{...payload.market[0], sma200: '-1'}]}));
});

test('selected fill filters related audit and portfolio rows', () => {
    const run = {
        fills: [
            {fill_id: 'buy', order_id: 'buy-order', fill_time: '2020-01-02T09:05:00+07:00', side: 'BUY'},
            {fill_id: 'same-day', order_id: 'same-day-order', fill_time: '2020-01-02T10:05:00+07:00', side: 'BUY'},
            {fill_id: 'sell', order_id: 'sell-order', fill_time: '2020-01-03', side: 'SELL'},
        ],
        orders: [
            {order_id: 'buy-order', signal_id: 'buy-signal'},
            {order_id: 'same-day-order', signal_id: 'same-day-signal'},
            {order_id: 'sell-order', signal_id: 'sell-signal'},
        ],
        signals: [{signal_id: 'buy-signal'}, {signal_id: 'same-day-signal'}, {signal_id: 'sell-signal'}],
        trades: [{trade_id: 'trade', entry_fill_id: 'buy', exit_fill_id: 'sell'}],
        open_position: {entry_fill_id: 'buy'},
        equity_history: [
            {trading_date: '2020-01-02T09:05:00+07:00', equity: '100'},
            {trading_date: '2020-01-02T10:05:00+07:00', equity: '101'},
            {trading_date: '2020-01-03', equity: '110'},
        ],
    };
    const selected = relatedRows(run, 'buy');
    assert.deepEqual(selected.fills.map(row => row.fill_id), ['buy', 'same-day']);
    assert.deepEqual(selected.orders.map(row => row.order_id), ['buy-order']);
    assert.deepEqual(selected.signals.map(row => row.signal_id), ['buy-signal']);
    assert.deepEqual(selected.trades.map(row => row.trade_id), ['trade']);
    assert.equal(selected.position[0].entry_fill_id, 'buy');
    assert.deepEqual(selected.equity.map(row => row.trading_date), ['2020-01-02T09:05:00+07:00']);
    assert.equal(relatedRows(run).fills.length, 3);
});
