/**
 * Start-up and error screens, shown before the dashboard can load. Bilingual (Mongolian first) because
 * they appear before the user's language choice is known. Rendered from a data: URL, so no files.
 */
const page = (body: string) =>
  `data:text/html;charset=utf-8,${encodeURIComponent(`<!doctype html><html lang="mn"><head><meta charset="utf-8">
<meta http-equiv="Content-Security-Policy" content="default-src 'none'; style-src 'unsafe-inline'">
<style>
  html,body{height:100%;margin:0}
  body{display:grid;place-items:center;background:#020617;color:#e2e8f0;font:15px/1.5 system-ui,-apple-system,"Segoe UI",sans-serif}
  main{max-width:34rem;padding:2rem;text-align:center}
  h1{font-size:1.15rem;margin:0 0 .25rem}
  p{margin:.25rem 0;color:#94a3b8}
  code{display:block;margin-top:1rem;padding:.5rem;border-radius:.375rem;background:#0f172a;color:#cbd5e1;font-size:12px;word-break:break-all;text-align:left}
  .spin{width:28px;height:28px;margin:0 auto 1rem;border:3px solid #155e75;border-top-color:#22d3ee;border-radius:50%;animation:s 1s linear infinite}
  @keyframes s{to{transform:rotate(360deg)}}
  @media (prefers-reduced-motion:reduce){.spin{animation:none}}
</style></head><body><main>${body}</main></body></html>`)}`

export const startingScreen = () =>
  page(`<div class="spin" role="status" aria-label="Loading"></div>
<h1>Эрэмбэлэх системийг эхлүүлж байна…</h1>
<p>Starting the triage engine…</p>
<p>Анх асаахад хэдэн арван секунд болж магадгүй. · The first start can take a minute.</p>`)

export const failedScreen = (message: string, logFile: string) =>
  page(`<h1>Эрэмбэлэх систем эхэлсэнгүй · The triage engine did not start</h1>
<p>${escapeHtml(message)}</p>
<p>Програмыг хаагаад дахин нээнэ үү. Асуудал давтагдвал доорх бүртгэлийн файлыг техникийн ажилтанд өгнө үү.</p>
<p>Close and reopen the app. If it keeps happening, send this log file to technical support:</p>
<code>${escapeHtml(logFile)}</code>`)

function escapeHtml(text: string) {
  return text.replace(/[&<>"']/g, (c) => `&#${c.charCodeAt(0)};`)
}
