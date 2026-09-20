import {createChart, CandlestickSeries, HistogramSeries, LineSeries, createSeriesMarkers} from './vendor/lightweight-charts.standalone.production.mjs';
import {chartTheme} from './theme.mjs?v=20260918';

let priceChart, marketChart, equityChart;
const $ = selector => document.querySelector(selector);
window.addEventListener('themechange', () => {
    for (const chart of [priceChart, marketChart, equityChart]) chart?.applyOptions(chartTheme());
});
export function clearCharts() {
    priceChart?.remove(); marketChart?.remove(); equityChart?.remove();
    priceChart = marketChart = equityChart = undefined;
    $('#fill-tooltip').replaceChildren();
    $('#fill-tooltip').hidden = true;
    $('#chart-metadata').textContent = '';
}

export function renderCharts(data, metadata) {
    clearCharts();
    const theme = chartTheme();
    const options = {autoSize: true, ...theme, timeScale: {...theme.timeScale, minBarSpacing: 0.05}};
    priceChart = createChart($('#price-chart'), options);
    const candles = priceChart.addSeries(CandlestickSeries, {
        upColor: '#269982', downColor: '#d95866', borderVisible: false,
        wickUpColor: '#269982', wickDownColor: '#d95866',
        priceFormat: {type: 'price', precision: 6, minMove: 0.000001},
        autoscaleInfoProvider: original => {
            const info = original();
            const range = priceChart.timeScale().getVisibleLogicalRange();
            const start = range ? data.candles[Math.max(0, Math.floor(range.from))]?.time : undefined;
            const end = range ? data.candles[Math.min(data.candles.length - 1, Math.ceil(range.to))]?.time : undefined;
            const visible = data.markers.filter(marker => (!start || marker.time >= start) && (!end || marker.time <= end));
            if (info && visible.length) {
                info.priceRange.minValue = Math.min(info.priceRange.minValue, ...visible.map(marker => marker.price));
                info.priceRange.maxValue = Math.max(info.priceRange.maxValue, ...visible.map(marker => marker.price));
            }
            return info;
        },
    });
    candles.setData(data.candles);
    createSeriesMarkers(candles, data.markers, {autoScale: true});
    priceChart.addSeries(HistogramSeries, {priceFormat: {type: 'volume'}, priceScaleId: ''}, 1).setData(data.volume);
    priceChart.panes()[1].setHeight(100);
    marketChart = createChart($('#market-chart'), options);
    marketChart.addSeries(LineSeries, {color: '#667085', title: 'VN-Index Close'}).setData(data.market.map(point => ({time: point.time, value: point.close})));
    marketChart.addSeries(LineSeries, {color: '#b54708', lineWidth: 2, title: 'SMA200'}).setData(data.market.filter(point => point.sma200 !== null).map(point => ({time: point.time, value: point.sma200})));
    equityChart = createChart($('#equity-chart'), options);
    equityChart.addSeries(LineSeries, {color: '#245ea8'}).setData(data.equity);
    const hideTooltip = () => { $('#fill-tooltip').hidden = true; };
    const showTooltip = (id, point) => {
        const fill = data.fills.find(item => item.fill_id === id);
        if (!fill || !point) { hideTooltip(); return; }
        const tooltip = $('#fill-tooltip');
        const title = document.createElement('strong'); title.textContent = `${fill.side} đã khớp`;
        const details = document.createElement('dl');
        for (const [label, value] of [['Ngày khớp', fill.fill_time], ['Giá', fill.fill_price], ['Số lượng', fill.quantity], ['Phí', fill.fee], ['Signal', fill.signal_time], ['Lý do', fill.reason]]) {
            const term = document.createElement('dt'); term.textContent = label;
            const description = document.createElement('dd'); description.textContent = value;
            details.append(term, description);
        }
        tooltip.replaceChildren(title, details);
        tooltip.hidden = false;
        const bounds = $('#price-chart-wrap').getBoundingClientRect();
        tooltip.style.left = `${Math.max(8, Math.min(point.x + 12, bounds.width - tooltip.offsetWidth - 8))}px`;
        tooltip.style.top = `${Math.max(8, Math.min(point.y + 12, bounds.height - tooltip.offsetHeight - 8))}px`;
    };
    priceChart.subscribeClick(event => showTooltip(event.hoveredObjectId, event.point));
    priceChart.subscribeCrosshairMove(event => showTooltip(event.hoveredObjectId, event.point));
    $('#chart-metadata').textContent = JSON.stringify(metadata, null, 2);
    $('#chart-status').textContent = `${data.candles.length} nến HPG · ${data.markers.length} fills · BUY ↑ / SELL ↓ · SMA200 thuộc VN-Index`;
    $('#fit-run').onclick = () => {priceChart.timeScale().fitContent(); marketChart.timeScale().fitContent(); equityChart.timeScale().fitContent();};
    $('#fit-run').click();
}
