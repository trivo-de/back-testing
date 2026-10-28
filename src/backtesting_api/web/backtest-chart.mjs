import {createChart, CandlestickSeries, HistogramSeries, LineSeries, createSeriesMarkers} from './vendor/lightweight-charts.standalone.production.mjs';
import {chartTheme} from './theme.mjs?v=20260918';

let priceChart, marketChart, equityChart, markerOutline;
/** Find a chart-related page element. */
const $ = selector => document.querySelector(selector);
window.addEventListener('themechange', /* Apply changed theme colors to every mounted chart and marker outline. */ () => {
    for (const chart of [priceChart, marketChart, equityChart]) chart?.applyOptions(chartTheme());
    markerOutline?.redraw();
});
/** Constrain a drawing dimension to the supplied bounds. */
const clamp = (value, min, max) => Math.min(max, Math.max(min, value));
/** Attach a chart primitive that outlines fill markers at their price coordinates. */
const markerOutlinePrimitive = (series, chart, markers) => {
    /** Ignore redraw requests until the primitive is attached. */
    let requestUpdate = () => {};
    /** Draw a marker arrow outline using bitmap pixel ratios. */
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
    const renderer = {/* Render marker outlines in the chart's bitmap coordinate space. */ draw(target) {
        target.useBitmapCoordinateSpace(/* Project each visible marker into bitmap drawing coordinates. */ ({context, horizontalPixelRatio, verticalPixelRatio}) => {
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
        /** Retain the redraw callback supplied when the primitive is attached. */
        attached({requestUpdate: update}) { requestUpdate = update; },
        /** Disable redraw requests when the primitive is detached. */
        detached() { requestUpdate = /* Ignore redraw requests after detachment. */ () => {}; },
        paneViews: /* Expose the marker outline renderer as a pane view. */ () => [{renderer: /* Return the pane's marker outline renderer. */ () => renderer}],
        /** Keep no cached view state because drawing reads current coordinates. */
        updateAllViews() {},
    };
    series.attachPrimitive(primitive);
    return {redraw: /* Request a redraw through the primitive's current attachment. */ () => requestUpdate()};
};
/** Remove mounted charts and clear tooltip and metadata state. */
export function clearCharts() {
    priceChart?.remove(); marketChart?.remove(); equityChart?.remove();
    priceChart = marketChart = equityChart = markerOutline = undefined;
    $('#fill-tooltip').replaceChildren();
    $('#fill-tooltip').hidden = true;
    $('#chart-metadata').textContent = '';
}

/** Render saved price, volume, market, and equity data with fill selection. */
export function renderCharts(data, metadata, onFillSelect = /* Ignore fill selection when no selection callback was supplied. */ () => {}) {
    clearCharts();
    const theme = chartTheme();
    /** Format chart times in the run's configured timezone. */
    const localTime = value => typeof value === 'number' ? new Intl.DateTimeFormat('vi-VN', {timeZone: metadata.timezone || 'Asia/Ho_Chi_Minh', month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit', hourCycle: 'h23'}).format(new Date(value * 1000)) : String(value);
    const options = {autoSize: true, ...theme, localization: {timeFormatter: localTime}, timeScale: {...theme.timeScale, minBarSpacing: data.intraday ? 0.05 : 1, timeVisible: !!data.intraday, ...(data.intraday ? {tickMarkFormatter: localTime} : {})}};
    priceChart = createChart($('#price-chart'), options);
    const candles = priceChart.addSeries(CandlestickSeries, {
        upColor: '#269982', downColor: '#d95866', borderVisible: false,
        wickUpColor: '#269982', wickDownColor: '#d95866',
        priceFormat: {type: 'price', precision: data.intraday ? 1 : 6, minMove: data.intraday ? .1 : .000001},
        autoscaleInfoProvider: /* Extend the visible price range to include fill marker prices. */ original => {
            const info = original();
            const range = priceChart.timeScale().getVisibleLogicalRange();
            const start = range ? data.candles[Math.max(0, Math.floor(range.from))]?.time : undefined;
            const end = range ? data.candles[Math.min(data.candles.length - 1, Math.ceil(range.to))]?.time : undefined;
            const visible = data.markers.filter(/* Keep markers within the visible time range. */ marker => (!start || marker.time >= start) && (!end || marker.time <= end));
            if (info && visible.length) {
                info.priceRange.minValue = Math.min(info.priceRange.minValue, ...visible.map(/* Read a marker's price for the lower scale bound. */ marker => marker.price));
                info.priceRange.maxValue = Math.max(info.priceRange.maxValue, ...visible.map(/* Read a marker's price for the upper scale bound. */ marker => marker.price));
            }
            return info;
        },
    });
    candles.setData(data.candles);
    const auctionIds = new Set(data.fills.filter(/* Identify fills produced by auction orders. */ fill => ['ATO', 'ATC'].includes(fill.order_type)).map(/* Read an auction fill identifier. */ fill => fill.fill_id));
    createSeriesMarkers(candles, data.markers.filter(/* Keep continuous-session markers on the candle series. */ marker => !auctionIds.has(marker.id)), {autoScale: true});
    if (auctionIds.size) {
        // Auction markers need real price points; whitespace candles alone cannot host them.
        const auctionSeries = priceChart.addSeries(LineSeries, {lineVisible: false, pointMarkersVisible: false,
            lastValueVisible: false, priceLineVisible: false, crosshairMarkerVisible: false});
        auctionSeries.setData(data.fills.filter(/* Select auction fills for the dedicated price series. */ fill => auctionIds.has(fill.fill_id))
            .map(/* Project an auction fill onto its chart time and price. */ fill => ({time: fill.chartTime, value: Number(fill.fill_price)})));
        createSeriesMarkers(auctionSeries, data.markers.filter(/* Keep auction markers on the dedicated auction series. */ marker => auctionIds.has(marker.id)), {autoScale: true});
    }
    markerOutline = markerOutlinePrimitive(candles, priceChart, data.markers);
    priceChart.addSeries(HistogramSeries, {priceFormat: {type: 'volume'}}, 1).setData(data.volume);
    priceChart.panes()[1].setHeight(100);
    $('#market-panel').hidden = !data.market.length;
    $('#market-chart').style.height = '240px';
    if (data.market.length) {
        marketChart = createChart($('#market-chart'), options);
        marketChart.addSeries(LineSeries, {color: '#667085', title: 'Market Close'}).setData(data.market.map(/* Project market observations onto the market close series. */ point => ({time: point.time, value: point.close})));
        if (!data.intraday) marketChart.addSeries(LineSeries, {color: '#b54708', lineWidth: 2, title: 'SMA200'}).setData(data.market.filter(/* Keep observations with an available SMA200 value. */ point => point.sma200 != null).map(/* Project available SMA200 values onto the indicator series. */ point => ({time: point.time, value: point.sma200})));
    }
    const panes = new Map([['trade_data:volume', 1]]);
    const colors = ['#b54708', '#245ea8', '#9c27b0', '#269982'];
    let color = 0;
    for (const [name, points] of Object.entries(data.indicators || {})) {
        const spec = metadata.indicator_specs?.[name.split('.')[0]];
        if (!spec) continue;
        const chart = spec.source.startsWith('market_data') ? marketChart : priceChart;
        if (!chart) continue;
        let pane = 0;
        const oscillator = ['MACD', 'MFI'].includes(spec.type);
        const volume = !oscillator && spec.source.endsWith('.volume');
        if (oscillator || volume) {
            const key = spec.source.split('.')[0] + ':' + (volume ? 'volume' : spec.type);
            if (!panes.has(key)) panes.set(key, chart.panes().length);
            pane = panes.get(key);
        }
        chart.addSeries(LineSeries, {title: name, color: colors[color++ % colors.length], lineWidth: 1, ...(volume ? {priceFormat: {type: 'volume'}} : {})}, pane).setData(points);
        if (pane) chart.panes()[pane].setHeight(120);
    }
    if (marketChart) $('#market-chart').style.height = `${240 + (marketChart.panes().length - 1) * 120}px`;
    equityChart = createChart($('#equity-chart'), options);
    equityChart.addSeries(LineSeries, {color: '#245ea8', title: data.priceOnly ? 'Lãi/lỗ (điểm × lượng)' : 'Vốn theo đơn vị gốc'}).setData(data.equity);
    /** Hide the fill tooltip. */
    const hideTooltip = () => { $('#fill-tooltip').hidden = true; };
    /** Show details for a fill at the supplied chart point. */
    const showTooltip = (id, point) => {
        const fill = data.fills.find(/* Find the fill selected by its identifier. */ item => item.fill_id === id);
        if (!fill || !point) { hideTooltip(); return null; }
        const tooltip = $('#fill-tooltip');
        const title = document.createElement('strong'); title.textContent = `${fill.side} đã khớp`;
        const details = document.createElement('dl');
        for (const [label, value] of [['Ngày khớp', fill.fill_time], ['Giá', fill.fill_price], ['Số lượng', fill.quantity], ...(data.priceOnly ? [] : [['Phí', fill.fee]]), ['Tín hiệu', fill.signal_time ?? fill.decision_time], ['Lý do', fill.reason]]) {
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
    priceChart.subscribeClick(/* Select the fill under a chart click or clear the selection. */ event => onFillSelect(showTooltip(event.hoveredObjectId, event.point)?.fill_id));
    priceChart.subscribeCrosshairMove(/* Update the tooltip as the chart crosshair moves. */ event => showTooltip(event.hoveredObjectId, event.point));
    $('#chart-metadata').textContent = JSON.stringify(metadata, null, 2);
    $('#chart-status').textContent = `${metadata.symbol || 'Giá giao dịch'} · ${metadata.resolution || metadata.timeframe || ''} · ${data.candles.filter(/* Count actual OHLC candles without auction whitespace points. */ bar => bar.open !== undefined).length} nến · ${data.markers.length} lần khớp · Mua ↑ / Bán ↓`;
    /** Fit all mounted charts to the saved run's time range. */
    const fitRun = () => {priceChart.timeScale().fitContent(); marketChart?.timeScale().fitContent(); equityChart.timeScale().fitContent();};
    $('#fit-run').onclick = fitRun;
    if (data.candles.length > 250) {
        const last = data.candles.length - 1;
        priceChart.timeScale().setVisibleLogicalRange({from: last - 249, to: last});
        marketChart?.timeScale().setVisibleLogicalRange({from: Math.max(0, data.market.length - 250), to: data.market.length - 1});
        equityChart.timeScale().setVisibleLogicalRange({from: Math.max(0, data.equity.length - 250), to: data.equity.length - 1});
    } else fitRun();
}
