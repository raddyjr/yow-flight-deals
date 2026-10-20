// Shared helpers for the YOW Flight Deals blog (home, post and admin pages).

const REGIONS = [
  { id: "sun", name: "Sun & Beach", icon: "🏝️" },
  { id: "europe", name: "Europe", icon: "🏰" },
  { id: "canada-us", name: "Canada & US", icon: "🍁" },
  { id: "asia", name: "Asia", icon: "🏯" },
  { id: "middle-east", name: "Middle East", icon: "🕌" },
  { id: "south-america", name: "South America", icon: "🌎" },
  { id: "other", name: "Anywhere", icon: "✈️" },
];
const regionOf = (id) => REGIONS.find((r) => r.id === id) || REGIONS[REGIONS.length - 1];

const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) =>
  ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));

function fmtMoney(n, cur) {
  if (n === "" || n == null || isNaN(n)) return "";
  return new Intl.NumberFormat("en-CA", { style: "currency", currency: cur || "CAD", maximumFractionDigits: 0 }).format(n);
}

function fmtDate(s, opts) {
  if (!s) return "";
  return new Date(s + "T12:00:00").toLocaleDateString("en-CA", opts || { month: "short", day: "numeric", year: "numeric" });
}

function todayStr() {
  const d = new Date();
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
}

const isExpired = (p) => p.expired || (p.expires && p.expires < todayStr());

function savingsPct(p) {
  return p.usual_price && p.price && p.usual_price > p.price
    ? Math.round((1 - p.price / p.usual_price) * 100) : 0;
}

// Only allow http(s) links so a post can never inject a javascript: URL.
function safeUrl(u) {
  try { const x = new URL(u, location.href); return /^https?:$/.test(x.protocol) ? x.href : "#"; }
  catch { return "#"; }
}

// Tiny Markdown: paragraphs, - bullet lists, **bold**, *italic*, [text](url).
function renderMarkdown(src) {
  const inline = (t) => esc(t)
    .replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>")
    .replace(/\*(.+?)\*/g, "<em>$1</em>")
    .replace(/\[([^\]]+)\]\(([^)\s]+)\)/g, (_, text, url) =>
      `<a href="${esc(safeUrl(url.replace(/&amp;/g, "&")))}" target="_blank" rel="noopener">${text}</a>`);
  const isBullet = (l) => /^\s*[-*]\s+/.test(l);
  return String(src || "").trim().split(/\n\s*\n/).map((block) => {
    // Split each paragraph into runs of plain lines and runs of bullet lines.
    const runs = [];
    for (const line of block.split("\n")) {
      const bullet = isBullet(line);
      if (!runs.length || runs[runs.length - 1].bullet !== bullet) runs.push({ bullet, lines: [] });
      runs[runs.length - 1].lines.push(bullet ? line.replace(/^\s*[-*]\s+/, "") : line);
    }
    return runs.map((r) => r.bullet
      ? `<ul>${r.lines.map((l) => `<li>${inline(l)}</li>`).join("")}</ul>`
      : `<p>${r.lines.map(inline).join("<br>")}</p>`).join("");
  }).join("");
}

async function loadPosts() {
  const r = await fetch(`posts.json?v=${Date.now()}`, { cache: "no-store" });
  if (!r.ok) throw new Error(`posts.json: ${r.status}`);
  const data = await r.json();
  return (data.posts || []).sort((a, b) => (b.published_at || "").localeCompare(a.published_at || ""));
}
