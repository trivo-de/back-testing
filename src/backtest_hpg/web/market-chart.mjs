import {createChart, CandlestickSeries, HistogramSeries, TickMarkType} from './vendor/lightweight-charts.standalone.production.mjs';
import {chartData, timeLabel} from './market-data.mjs';
import {chartTheme} from './theme.mjs?v=20260918';

const $ = selector => document.querySelector(selector);
const status = $('#status');
let chart;
window.addEventListener('themechange', () => chart?.applyOptions(chartTheme()));
let request = 0;
let controller;
let loadedBars = [];
const detail = bar => `${timeLabel(bar.time)} · O ${bar.open}  H ${bar.high}  L ${bar.low}  C ${bar.close} · V ${bar.volume}`;
const dateTick = new Intl.DateTimeFormat('vi-VN', {timeZone: 'Asia/Ho_Chi_Minh', day: '2-digit', month: '2-digit'});
const timeTick = new Intl.DateTimeFormat('vi-VN', {timeZone: 'Asia/Ho_Chi_Minh', hour: '2-digit', minute: '2-digit', hourCycle: 'h23'});

function clear() {
    chart?.remove();
    chart = undefined;
    loadedBars = [];
    $('#bars').replaceChildren();
    $('#metadata').textContent = '';
    $('#ohlcv').textContent = 'Di chuyển con trỏ trên nến để xem OHLCV.';
    $('#fit').disabled = true;
}

function renderTable() {
    const fragment = document.createDocumentFragment();
    for (const bar of loadedBars) {
        const row = document.createElement('tr');
        for (const value of [timeLabel(bar.time), bar.open, bar.high, bar.low, bar.close, bar.volume]) {
            const cell = document.createElement('td');
            cell.textContent = value;
            row.append(cell);
        }
        fragment.append(row);
    }
    $('#bars').replaceChildren(fragment);
}

async function load() {
    const start = $('#start').value, end = $('#end').value;
    const sequence = ++request;
    controller?.abort();
    controller = new AbortController();
    clear();
    if (start > end) {
        status.className = 'error';
        status.textContent = 'Ngày bắt đầu phải trước hoặc bằng ngày kết thúc.';
        return;
    }
    status.className = '';
    status.textContent = 'Đang tải snapshot…';
    try {
        const response = await fetch(`/api/market-chart?${new URLSearchParams({start, end})}`, {signal: controller.signal});
        const payload = await response.json();
        if (sequence !== request) return;
        if (!response.ok) throw Error(typeof payload.detail === 'string' ? payload.detail : 'Không tải được snapshot.');
        const data = chartData(payload);
        $('#metadata').textContent = JSON.stringify(payload.metadata, null, 2);
        if (!data.candles.length) {
            status.textContent = 'Không có nến trong khoảng ngày đã chọn.';
            return;
        }
        const theme = chartTheme();
        chart = createChart($('#chart'), {
            autoSize: true,
            ...theme,
            localization: {locale: 'vi-VN', timeFormatter: timeLabel},
            timeScale: {...theme.timeScale, timeVisible: true, secondsVisible: false, minBarSpacing: 0.05, tickMarkFormatter: (time, type) =>
                (type === TickMarkType.Time || type === TickMarkType.TimeWithSeconds ? timeTick : dateTick).format(new Date(time * 1000))},
        });
        const candles = chart.addSeries(CandlestickSeries, {
            upColor: '#29a38a', downColor: '#e36978', borderVisible: false,
            wickUpColor: '#29a38a', wickDownColor: '#e36978',
            priceFormat: {type: 'price', precision: 1, minMove: 0.1},
        });
        const volume = chart.addSeries(HistogramSeries, {priceFormat: {type: 'volume'}, priceScaleId: ''}, 1);
        candles.setData(data.candles);
        volume.setData(data.volume);
        chart.panes()[1].setHeight(110);
        chart.timeScale().fitContent();
        loadedBars = payload.bars;
        const byTime = new Map(loadedBars.map(bar => [bar.time, bar]));
        $('#ohlcv').textContent = detail(loadedBars.at(-1));
        chart.subscribeCrosshairMove(event => {
            const bar = byTime.get(event.time);
            if (bar) $('#ohlcv').textContent = detail(bar);
        });
        $('#fit').disabled = false;
        $('#table-caption').textContent = `${loadedBars.length.toLocaleString('vi-VN')} nến trong khoảng đã chọn`;
        if ($('#bars').closest('details').open) renderTable();
        status.textContent = `Đã tải ${loadedBars.length.toLocaleString('vi-VN')} / ${payload.metadata.total_bars.toLocaleString('vi-VN')} nến · VN30F1M · 5 phút · UTC+7`;
    } catch (error) {
        if (sequence !== request || error.name === 'AbortError') return;
        clear();
        status.className = 'error';
        status.textContent = error.message;
    }
}

$('#range-form').addEventListener('submit', event => { event.preventDefault(); load(); });
$('#all').addEventListener('click', () => {
    $('#start').value = '2026-03-16'; $('#end').value = '2026-09-15'; load();
});
$('#fit').addEventListener('click', () => chart?.timeScale().fitContent());
$('#bars').closest('details').addEventListener('toggle', event => {
    if (event.target.open && !$('#bars').children.length) renderTable();
});
load();
