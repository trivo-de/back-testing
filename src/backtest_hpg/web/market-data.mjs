// Preserve Unix seconds; timezone conversion is presentation only.
export const timeLabel = time => new Intl.DateTimeFormat('vi-VN', {
    timeZone: 'Asia/Ho_Chi_Minh', day: '2-digit', month: '2-digit', year: 'numeric',
    hour: '2-digit', minute: '2-digit', hourCycle: 'h23',
}).format(new Date(time * 1000));

export function chartData(payload) {
    const {metadata, bars} = payload;
    if (metadata?.symbol !== 'VN30F1M' || metadata.timeframe !== '5m' ||
        metadata.timezone !== 'Asia/Ho_Chi_Minh' || !Array.isArray(bars)) {
        throw Error('Metadata chart không hợp lệ.');
    }
    let previous = -1;
    for (const bar of bars) {
        const {time, open, high, low, close, volume} = bar;
        if (!Number.isSafeInteger(time) || time <= previous ||
            ![open, high, low, close, volume].every(Number.isFinite) ||
            Math.min(open, high, low, close) <= 0 || volume < 0 ||
            low > Math.min(open, close) || high < Math.max(open, close)) {
            throw Error('OHLCV không nhất quán; không thể vẽ chart.');
        }
        previous = time;
    }
    return {
        candles: bars.map(({time, open, high, low, close}) => ({time, open, high, low, close})),
        volume: bars.map(({time, volume, open, close}) => ({time, value: volume,
            color: close >= open ? '#29a38a' : '#e36978'})),
    };
}
