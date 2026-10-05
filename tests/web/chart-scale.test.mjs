import {readFileSync} from 'node:fs';
import {runInNewContext} from 'node:vm';
import assert from 'node:assert/strict';
import test from 'node:test';

test('volume indicators never scale candles, for daily and intraday runs', () => {
    const source = readFileSync(new URL('../../src/backtest_hpg/web/backtest-chart.mjs', import.meta.url), 'utf8')
        .replace(/^import .*;\r?\n/gm, '').replace(/export function /g, 'function ');
    for (const intraday of [false, true]) {
        const charts = [];
        const elements = new Map();
        const context = {
            window: {addEventListener() {}},
            document: {querySelector(key) {
                if (!elements.has(key)) elements.set(key, {style: {}, replaceChildren() {}});
                return elements.get(key);
            }},
            chartTheme: () => ({}), CandlestickSeries: 'candle', HistogramSeries: 'volume', LineSeries: 'line',
            createSeriesMarkers() {},
            createChart() {
                const panes = [{setHeight() {}}], series = [];
                const chart = {series, panes: () => panes, remove() {},
                    timeScale: () => ({fitContent() {}}), subscribeClick() {}, subscribeCrosshairMove() {},
                    addSeries(type, options, pane = 0) {
                        while (panes.length <= pane) panes.push({setHeight() {}});
                        const item = {type, options, pane, setData(data) {this.data = data;}, attachPrimitive() {}};
                        series.push(item); return item;
                    }};
                charts.push(chart); return chart;
            },
        };
        runInNewContext(source, context);
        const specs = {
            renamed_volume: {source: 'trade_data.volume', type: 'SMA'},
            pivot: {source: 'trade_data.high', type: 'HIGHEST'},
            market_volume: {source: 'market_data.volume', type: 'EMA'},
            momentum: {source: 'trade_data.volume', type: 'MACD'},
            flow: {source: 'trade_data.close', type: 'MFI'},
        };
        const time = intraday ? 1774404900 : '2023-01-03';
        const points = [{time, value: 30000000}];
        context.renderCharts({intraday, candles: [{time, open: 16, high: 20, low: 15, close: 19}],
            volume: points, market: [{time, close: 1000}], markers: [], fills: [], equity: [],
            indicators: Object.fromEntries(Object.keys(specs).map(name => [name, points]))}, {indicator_specs: specs});
        const price = charts[0].series, market = charts[1].series;
        const volume = price.find(s => s.options.title === 'renamed_volume');
        const histogram = price.find(s => s.type === 'volume');
        assert.equal(volume.pane, histogram.pane);
        assert.equal(volume.options.priceScaleId ?? 'right', histogram.options.priceScaleId ?? 'right');
        assert.equal(volume.options.priceFormat.type, 'volume');
        assert.equal(price.find(s => s.options.title === 'pivot').pane, 0);
        assert.ok(market.find(s => s.options.title === 'market_volume').pane > 0);
        for (const name of ['momentum', 'flow']) assert.ok(price.find(s => s.options.title === name).pane > 1);
        assert.equal(volume.data, points);
    }
});
