// Same toggle pattern as theme.mjs, with an independent preview preference.
const storageKey = 'backtest-preview-theme';
function setTheme(value) {
    const theme = value === 'dark' ? 'dark' : 'light';
    document.documentElement.dataset.theme = theme;
    document.querySelectorAll('[data-theme-toggle]').forEach(button => {
        button.textContent = theme === 'dark' ? '☾' : '☀';
        button.setAttribute('aria-label', theme === 'dark' ? 'Chuyển sang giao diện sáng' : 'Chuyển sang giao diện tối');
        button.setAttribute('aria-pressed', String(theme === 'dark'));
    });
    window.dispatchEvent(new Event('themechange'));
}
let saved;
try { saved = localStorage.getItem(storageKey); } catch {}
setTheme(saved);
document.querySelectorAll('[data-theme-toggle]').forEach(button => {
    if (button.dataset.themeBound) return;
    button.dataset.themeBound = 'true';
    button.addEventListener('click', () => {
        const theme = document.documentElement.dataset.theme === 'dark' ? 'light' : 'dark';
        try { localStorage.setItem(storageKey, theme); } catch {}
        setTheme(theme);
    });
});
window.addEventListener('storage', event => {
    if (event.key === storageKey || event.key === null) setTheme(event.newValue);
});

export function chartTheme() {
    const style = getComputedStyle(document.documentElement);
    const color = name => style.getPropertyValue(name).trim();
    return {
        layout: {background: {color: color('--surface')}, textColor: color('--text'), fontFamily: style.fontFamily},
        grid: {vertLines: {color: color('--grid')}, horzLines: {color: color('--grid')}},
        rightPriceScale: {borderColor: color('--border')},
        timeScale: {borderColor: color('--border')},
    };
}
