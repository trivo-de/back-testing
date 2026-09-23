import {createChart, CandlestickSeries, HistogramSeries, LineSeries, createSeriesMarkers} from './vendor/lightweight-charts.standalone.production.mjs';
import {chartTheme} from './theme.mjs?v=20260918';

let priceChart, marketChart, equityChart, markerOutline;
const $ = selector => document.querySelector(selector);
window.addEventListener('themechange', () => {
    for (const chart of [priceChart, marketChart, equityChart]) chart?.applyOptions(chartTheme());
    markerOutline?.redraw();
});
const clamp = (value, min, max) => Math.min(max, Math.max(min, value));
const markerOutlinePrimitive = (series, chart, markers) => {
    let requestUpdate = () => {};
    const drawArrow = (context, marker, x, priceY, horizontalRatio, verticalRatio, barSpacing) => {
        const base = Math.ceil(clamp(barSpacing, 12, 30));
        const markerSize = (base % 2 ? base - 1 : base) * marker.size;
        const shapeSize = clamp(markerSize, 12, 30);
        const half = (shapeSize - 1) / 2;
        const wing = (Math.ceil(shapeSize / 2) - 1) / 2;
        const centerY = priceY + (marker.shape === 'arrowUp' ? markerSize / 2 : -markerSize / 2);
        const px = x * horizontalRatio, py = centerY * verticalRatio;
        const hx = half * horizontalRatio, hy = half * verticalRatio;
        const wx = wing * horizontalRatio;
        context.beginPath();
        context.moveTo(px - hx, py);
        context.lineTo(px, py + (marker.shape === 'arrowUp' ? -hy : hy));
        context.lineTo(px + hx, py);
        context.lineTo(px + wx, py);
        context.lineTo(px + wx, py + (marker.shape === 'arrowUp' ? hy : -hy));
        context.lineTo(px - wx, py + (marker.shape === 'arrowUp' ? hy : -hy));
        context.lineTo(px - wx, py);
        context.closePath();
        context.strokeStyle = marker.borderColor[document.documentElement.dataset.theme] ?? marker.borderColor.light;
        context.lineWidth = marker.borderWidth * Math.max(horizontalRatio, verticalRatio);
        context.lineJoin = 'round';
        context.stroke();
    };
    const renderer = {draw(target) {
        target.useBitmapCoordinateSpace(({context, horizontalPixelRatio, verticalPixelRatio}) => {
            const barSpacing = chart.timeScale().options().barSpacing;
            context.save();
            for (const marker of markers) {
                const x = chart.timeScale().timeToCoordinate(marker.time);
                const y = series.priceToCoordinate(marker.price);
                if (x !== null && y !== null) drawArrow(context, marker, x, y, horizontalPixelRatio, verticalPixelRatio, barSpacing);
            }
            context.restore();
        });
    }};
    const primitive = {
        attached({requestUpdate: update}) { requestUpdate = update; },
        detached() { requestUpdate = () => {}; },
        paneViews: () => [{renderer: () => renderer}],
        updateAllViews() {},
    };
    series.attachPrimitive(primitive);
    return {redraw: () => requestUpdate()};
};
export function clearCharts() {
    priceChart?.remove(); marketChart?.remove(); equityChart?.remove();
    priceChart = marketChart = equityChart = markerOutline = undefined;
    $('#fill-tooltip').replaceChildren();
    $('#fill-tooltip').hidden = true;
    $('#chart-metadata').textContent = '';
}

export function renderCharts(data, metadata, onFillSelect = () => {}) {
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
    markerOutline = markerOutlinePrimitive(candles, priceChart, data.markers);
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
        if (!fill || !point) { hideTooltip(); return null; }
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
        return fill;
    };
    priceChart.subscribeClick(event => onFillSelect(showTooltip(event.hoveredObjectId, event.point)?.fill_id));
    priceChart.subscribeCrosshairMove(event => showTooltip(event.hoveredObjectId, event.point));
    $('#chart-metadata').textContent = JSON.stringify(metadata, null, 2);
    $('#chart-status').textContent = `${data.candles.length} nến HPG · ${data.markers.length} fills · BUY ↑ / SELL ↓ · SMA200 thuộc VN-Index`;
    $('#fit-run').onclick = () => {priceChart.timeScale().fitContent(); marketChart.timeScale().fitContent(); equityChart.timeScale().fitContent();};
    $('#fit-run').click();
}
