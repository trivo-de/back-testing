import test from 'node:test';
import assert from 'node:assert/strict';
import {chartData, timeLabel} from '../../src/backtest_hpg/web/market-data.mjs';

test('chart mapping preserves Unix time, prices, UTC+7 and zero volume', () => {
    const payload = {
        metadata: {symbol: 'VN30F1M', timeframe: '5m', timezone: 'Asia/Ho_Chi_Minh'},
        bars: [{time: 1773626400, open: 100, high: 103, low: 99, close: 102, volume: 0}],
    };
    const result = chartData(payload);
    assert.equal(result.candles[0].time, payload.bars[0].time);
    assert.equal(result.candles[0].close, 102);
    assert.equal(result.volume[0].value, 0);
    assert.match(timeLabel(1773626400), /09:00/);
    assert.deepEqual(chartData({...payload, bars: []}), {candles: [], volume: []});
    for (const override of [{high: 90}, {volume: -1}, {open: null}, {close: NaN}, {time: '1773626400'}]) {
        assert.throws(() => chartData({...payload, bars: [{...payload.bars[0], ...override}]}));
    }
    assert.throws(() => chartData({...payload, bars: [...payload.bars, ...payload.bars]}));
    assert.throws(() => chartData({...payload, metadata: {...payload.metadata, symbol: 'HPG'}}));
});
