const storageKey = 'backtest-theme';
/** Read the operating system's preferred color scheme. */
const systemTheme = () => matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
/** Apply the saved or system theme and notify mounted charts. */
function setTheme(value) {
    const theme = value === 'dark' || value === 'light' ? value : systemTheme();
    document.documentElement.dataset.theme = theme;
    document.querySelectorAll('[data-theme-toggle]').forEach(/* Update a theme button's icon and accessible label. */ button => {
        button.textContent = theme === 'dark' ? '☾' : '☀';
        button.setAttribute('aria-label', theme === 'dark' ? 'Chuyển sang giao diện sáng' : 'Chuyển sang giao diện tối');
    });
    window.dispatchEvent(new Event('themechange'));
}
let saved;
try { saved = localStorage.getItem(storageKey); } catch {}
setTheme(saved);
document.querySelectorAll('[data-theme-toggle]').forEach(/* Bind each theme toggle once. */ button => {
    if (button.dataset.themeBound) return;
    button.dataset.themeBound = 'true';
    button.addEventListener('click', /* Switch and persist the theme after a toggle click. */ () => {
        const theme = document.documentElement.dataset.theme === 'dark' ? 'light' : 'dark';
        try { localStorage.setItem(storageKey, theme); } catch {}
        setTheme(theme);
    });
});
window.addEventListener('storage', /* Synchronize theme changes received from storage events. */ event => {
    if (event.key === storageKey || event.key === null) setTheme(event.newValue);
});
/** Build chart colors from the active CSS theme properties. */
export function chartTheme() {
    const style = getComputedStyle(document.documentElement);
    /** Read and trim a theme color property. */
    const color = name => style.getPropertyValue(name).trim();
    return {
        layout: {background: {color: color('--surface')}, textColor: color('--text')},
        grid: {vertLines: {color: color('--grid')}, horzLines: {color: color('--grid')}},
        rightPriceScale: {borderColor: color('--border')},
        timeScale: {borderColor: color('--border')},
    };
}
