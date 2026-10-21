// Same toggle pattern as theme.mjs, with an independent preview preference.
const storageKey = 'backtest-preview-theme';
/** Apply the preview theme and update accessible toggle labels. */
function setTheme(value) {
    const theme = value === 'dark' ? 'dark' : 'light';
    document.documentElement.dataset.theme = theme;
    document.querySelectorAll('[data-theme-toggle]').forEach(/* Update a preview theme button's icon and accessible state. */ button => {
        button.textContent = theme === 'dark' ? '☾' : '☀';
        button.setAttribute('aria-label', theme === 'dark' ? 'Chuyển sang giao diện sáng' : 'Chuyển sang giao diện tối');
        button.setAttribute('aria-pressed', String(theme === 'dark'));
    });
    window.dispatchEvent(new Event('themechange'));
}
let saved;
try { saved = localStorage.getItem(storageKey); } catch {}
setTheme(saved);
document.querySelectorAll('[data-theme-toggle]').forEach(/* Bind each preview theme toggle once. */ button => {
    if (button.dataset.themeBound) return;
    button.dataset.themeBound = 'true';
    button.addEventListener('click', /* Switch and persist the preview theme after a toggle click. */ () => {
        const theme = document.documentElement.dataset.theme === 'dark' ? 'light' : 'dark';
        try { localStorage.setItem(storageKey, theme); } catch {}
        setTheme(theme);
    });
});
window.addEventListener('storage', /* Synchronize preview theme changes received from storage events. */ event => {
    if (event.key === storageKey || event.key === null) setTheme(event.newValue);
});

/** Build chart colors from the active preview CSS properties. */
export function chartTheme() {
    const style = getComputedStyle(document.documentElement);
    /** Read and trim a preview theme color property. */
    const color = name => style.getPropertyValue(name).trim();
    return {
        layout: {background: {color: color('--surface')}, textColor: color('--text'), fontFamily: style.fontFamily},
        grid: {vertLines: {color: color('--grid')}, horzLines: {color: color('--grid')}},
        rightPriceScale: {borderColor: color('--border')},
        timeScale: {borderColor: color('--border')},
    };
}
