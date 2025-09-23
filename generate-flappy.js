/**
 * generate-flappy.js
 * Generate an animated SVG "Flappy Bird" rendered over your GitHub contribution grid.
 *
 * Usage (in Actions): GITHUB_USER set via env (github.repository_owner)
 * Output: ./dist/flappy-contribution-graph.svg
 *
 * Notes:
 * - Uses simple parsing of GitHub contributions SVG (rect[data-date][fill]).
 * - Heuristik: very-light fill (#ebedf0) = empty, others = filled => obstacle.
 * - If GitHub markup changes, parser may need updates; see "Alternatif" di README.
 */

import fs from "fs";
import fetch from "node-fetch";
import { parse } from "node-html-parser";

const USER = process.env.GITHUB_USER || process.argv[2] || "MHFADev";
const OUT_DIR = "dist";
const OUT_FILE = `${OUT_DIR}/flappy-contribution-graph.svg`;

// ensure output dir
function ensureOut() {
  if (!fs.existsSync(OUT_DIR)) fs.mkdirSync(OUT_DIR, { recursive: true });
}

// fetch contributions SVG from GitHub user page
async function fetchContributionSvg(user) {
  const url = `https://github.com/users/${user}/contributions`;
  const res = await fetch(url, { headers: { "User-Agent": "github-actions" } });
  if (!res.ok) throw new Error(`Failed to fetch contributions page: ${res.status}`);
  const text = await res.text();
  const root = parse(text);
  const svgEl = root.querySelector("svg.js-calendar-graph-svg") || root.querySelector("svg");
  if (!svgEl) throw new Error("Contribution SVG not found. Check username or page structure.");
  return svgEl.toString();
}

// parse rect entries -> array of rect objects, preserve DOM order
function parseGridFromSvg(svgHtml) {
  const rectMatches = [...svgHtml.matchAll(/<rect[^>]*data-date="([^"]+)"[^>]*fill="([^"]+)"[^>]*>/g)];
  const cells = rectMatches.map(m => ({ date: m[1], fill: m[2] }));
  // GitHub orders rects by week columns (left-to-right), each week up to 7 rects.
  const weeks = [];
  for (let i = 0; i < cells.length; i += 7) {
    weeks.push(cells.slice(i, i + 7));
  }
  // pad incomplete weeks
  weeks.forEach(w => { while (w.length < 7) w.push(null); });
  return weeks; // weeks[col][row]
}

// produce SVG content
function createFlappySvg(weeks, username) {
  const cols = weeks.length;
  const rows = 7;
  const cellSize = 12;
  const gutter = 4;
  const leftOffset = 20;
  const topOffset = 30;
  const width = leftOffset * 2 + cols * (cellSize + gutter);
  const height = topOffset + rows * (cellSize + gutter) + 40;

  // obstacle map: true => blocked
  const obstacleCols = weeks.map(col => col.map(cell => {
    if (!cell) return true;
    const hex = (cell.fill || "").toLowerCase();
    return !(hex === "#ebedf0" || hex === "#ebedf0ff" || hex === "rgba(0,0,0,0)");
  }));

  // animation duration scales with columns (keeps visual pleasant)
  const duration = Math.max(8, Math.round(Math.max(8, cols / 6)));

  // build SVG
  let svg = `<?xml version="1.0" encoding="UTF-8"?>\n`;
  svg += `<svg xmlns="http://www.w3.org/2000/svg" width="${width}" height="${height}" viewBox="0 0 ${width} ${height}">\n`;
  svg += `<style>
    .bg { fill: #071022; }
    .cell { rx:2; }
    .pipe { fill: #0f9d58; }
    .bird { fill: #ffdd57; stroke:#d08f00; stroke-width:0.8; }
    .wing { fill: #ffb347; }
    .label { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial; font-size:11px; fill:#9fb1c8; }
  </style>\n`;

  svg += `<rect class="bg" x="0" y="0" width="${width}" height="${height}" rx="10"/>\n`;

  // grid cells (use original fill when available)
  for (let c = 0; c < cols; c++) {
    for (let r = 0; r < rows; r++) {
      const x = leftOffset + c * (cellSize + gutter);
      const y = topOffset + r * (cellSize + gutter);
      const cell = weeks[c][r];
      const fill = (cell && cell.fill) ? cell.fill : "#223044";
      svg += `<rect class="cell" x="${x}" y="${y}" width="${cellSize}" height="${cellSize}" fill="${fill}"/>\n`;
    }
  }

  // draw pipes (blocked cells)
  for (let c = 0; c < cols; c++) {
    for (let r = 0; r < rows; r++) {
      if (obstacleCols[c][r]) {
        const x = leftOffset + c * (cellSize + gutter) - 1;
        const y = topOffset + r * (cellSize + gutter) - 1;
        svg += `<rect class="pipe" x="${x}" y="${y}" width="${cellSize+2}" height="${cellSize+2}" rx="2"/>\n`;
      }
    }
  }

  // Bird group: animate translate across canvas with subtle vertical motion pattern
  const birdStartX = leftOffset - 12;
  const birdStartY = topOffset + Math.floor(rows/2)*(cellSize + gutter);
  svg += `<g id="bird" transform="translate(${birdStartX}, ${birdStartY})">\n`;
  svg += `  <circle class="bird" cx="0" cy="0" r="7"/>\n`;
  svg += `  <path class="wing" d="M-2 0 q6 -6 12 0 q-6 3 -12 0" transform="translate(-4,1) rotate(-15)"/>\n`;
  // horizontal travel using animateTransform (SMIL)
  svg += `  <animateTransform attributeName="transform" type="translate"\n`;
  svg += `    values="${birdStartX} ${birdStartY}; ${Math.round(width - 100)} ${birdStartY}"\n`;
  svg += `    dur="${duration}s" repeatCount="indefinite" />\n`;
  // subtle up/down motion overlay (keyTimes)
  svg += `  <animate attributeName="cy" xlink:href="#bird" dur="${Math.max(2, duration/2)}s" values="0;-8;6;0" repeatCount="indefinite"/>\n`;
  svg += `</g>\n`;

  // footer label
  svg += `<text x="${12}" y="${height - 14}" class="label">flappy contribution graph — generated for ${username}</text>\n`;

  svg += `</svg>\n`;
  return svg;
}

async function main() {
  try {
    console.log("Fetching contribution SVG for", USER);
    const svgHtml = await fetchContributionSvg(USER);
    console.log("Parsing grid...");
    const weeks = parseGridFromSvg(svgHtml);
    console.log(`Parsed ${weeks.length} weeks.`);
    console.log("Generating flappy SVG...");
    ensureOut();
    const out = createFlappySvg(weeks, USER);
    fs.writeFileSync(OUT_FILE, out, "utf8");
    console.log("Done. Wrote", OUT_FILE);
  } catch (err) {
    console.error("ERROR:", err.message);
    process.exit(1);
  }
}

main();