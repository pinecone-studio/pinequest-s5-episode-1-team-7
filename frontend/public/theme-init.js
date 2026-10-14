// Applies the saved appearance before first paint so a dark page never flashes white; src/app/theme.ts
// keeps it in sync afterwards. A separate file rather than an inline script, so the desktop CSP allows it.
try {
  var theme = localStorage.getItem('pathtriage.theme')
  if (theme === 'dark' || (theme !== 'light' && matchMedia('(prefers-color-scheme: dark)').matches))
    document.documentElement.classList.add('dark')
} catch {}
