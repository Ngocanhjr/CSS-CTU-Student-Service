import fs from "node:fs";
import path from "node:path";

const dir = path.dirname(new URL(import.meta.url).pathname.replace(/^\/(.:)/, "$1"));
const requestedFiles = process.argv.slice(2);
const files = fs.readdirSync(dir).filter((name) => name.endsWith(".mmd") && (!requestedFiles.length || requestedFiles.includes(name))).sort();
const outputDir = process.env.EXCALIDRAW_OUTPUT_DIR || dir;
fs.mkdirSync(outputDir, { recursive: true });
const palette = {
  process: ["#1e3a5f", "#dbeafe"], decision: ["#92400e", "#fef3c7"],
  terminal: ["#166534", "#dcfce7"], database: ["#6b21a8", "#f3e8ff"],
  note: ["#9a3412", "#ffedd5"]
};

const clean = (text) => text.replace(/<br\s*\/?\s*>/gi, "\n").replace(/&gt;/g, ">").replace(/&lt;/g, "<").trim();
const wrap = (text, max = 27) => text.split("\n").flatMap((part) => {
  const words = part.split(/\s+/).flatMap((word) => {
    if (word.length <= max) return [word];
    const pieces = word.split(/(?<=[_.:/-])/); const chunks = []; let chunk = "";
    for (const piece of pieces) {
      if (chunk && (chunk + piece).length > max) { chunks.push(chunk); chunk = piece; }
      else chunk += piece;
    }
    if (chunk) chunks.push(chunk);
    return chunks.flatMap((value) => value.length <= max ? [value] : value.match(new RegExp(`.{1,${max}}`, "g")));
  });
  const lines = []; let line = "";
  for (const word of words) {
    if (!line || `${line} ${word}`.length <= max) line = line ? `${line} ${word}` : word;
    else { lines.push(line); line = word; }
  }
  lines.push(line); return lines;
}).join("\n");
const base = (id, type, x, y, width, height, index, colors) => ({
  id, type, x, y, width, height, angle: 0, strokeColor: colors[0], backgroundColor: colors[1],
  fillStyle: "solid", strokeWidth: 2, strokeStyle: "solid", roughness: 1, opacity: 100,
  groupIds: [], frameId: null, roundness: type === "rectangle" ? { type: 3 } : null,
  seed: index + 101, version: 1, versionNonce: index + 1001, isDeleted: false,
  boundElements: [], updated: 1783699200000, link: null, locked: false
});

function parse(source) {
  const orientation = source.match(/^flowchart\s+(\w+)/m)?.[1] || "TD";
  const nodes = new Map(); const edges = []; const groups = []; let currentGroup = null;
  const declaration = /\b([A-Za-z][A-Za-z0-9_]*)\s*(\(\[([^]*?)\]\)|\[\(([^]*?)\)\]|\{\{([^]*?)\}\}|\{([^]*?)\}|\[([^]*?)\])/g;
  const lines = source.split(/\r?\n/).filter((line) => !line.trim().startsWith("%%"));
  for (const line of lines) {
    const subgraph = line.match(/^\s*subgraph\s+(.+)$/);
    if (subgraph) { currentGroup = { label: clean(subgraph[1].replaceAll("_", " ")), members: [] }; groups.push(currentGroup); continue; }
    if (/^\s*end\s*$/.test(line)) { currentGroup = null; continue; }
    if (/^\s*flowchart\b/.test(line)) continue;
    let normalized = line; declaration.lastIndex = 0; let match;
    while ((match = declaration.exec(line))) {
      const raw = match[2]; let kind = "process";
      if (raw.startsWith("([")) kind = "terminal";
      else if (raw.startsWith("[(")) kind = "database";
      else if (raw.startsWith("{{")) kind = "note";
      else if (raw.startsWith("{")) kind = "decision";
      nodes.set(match[1], { id: match[1], label: clean(match[3] ?? match[4] ?? match[5] ?? match[6] ?? match[7]), kind });
      if (currentGroup && !currentGroup.members.includes(match[1])) currentGroup.members.push(match[1]);
      normalized = normalized.replace(match[0], match[1]);
    }
    const bareMember = normalized.trim().match(/^([A-Za-z][A-Za-z0-9_]*)$/)?.[1];
    if (currentGroup && bareMember && !currentGroup.members.includes(bareMember)) currentGroup.members.push(bareMember);
    let rest = normalized.trim();
    const edgePattern = /\b([A-Za-z][A-Za-z0-9_]*)\s+(-\..*?\.->|-->)\s*(?:\|([^|]+)\|)?\s*([A-Za-z][A-Za-z0-9_]*)/;
    while ((match = edgePattern.exec(rest))) {
      const dotted = match[2] !== "-->";
      const connectorLabel = dotted ? match[2].replace(/^-\.|\.->$/g, "").trim() : "";
      edges.push({ from: match[1], to: match[4], label: clean(match[3] || connectorLabel), dotted });
      rest = match[4] + rest.slice(match.index + match[0].length);
    }
  }
  return { orientation, nodes, edges, groups };
}

const manualRows = {
  "00_unified_chunking_retrieval_flow.mmd": [
    ["A", "B", "C", "D", "E"],
    ["K", "I", "H", "G", "F"],
    ["M", "N", "O"],
    ["U", "T", "S", "R", "Q", "P"],
    ["V", "W"],
    ["X", "Y", "Z"],
    ["ZA", "AA", "AB"],
    ["AF", "AE", "AD", "AC"]
  ],
  "07_13_ingestion_pipeline_publish_modes_flow.mmd": [
    ["A", "B", "C", "D", "E"],
    ["G", "F", "H", "I"],
    ["J", "K", "L", "M"],
    ["S", "R", "Q", "P", "O", "N"]
  ],
  "08_chunk_key_db_qdrant_contract_flow.mmd": [
    ["A", "B", "C", "D", "E"],
    ["F", "G", "H"],
    ["I", "J", "K", "L", "M"],
    ["P", "Q", "R", "S"]
  ],
  "09a_pre_chunk_parsing_normalization_flow.mmd": [
    ["A", "B", "C", "D", "E"],
    ["J", "I", "H", "G", "F"],
    ["L", "N", "O"],
    ["P", "Q", "R", "S", "T", "U"]
  ],
  "10_structural_parent_child_flow.mmd": [
    ["A", "B"],
    ["C", "G", "BA", "L", "P"],
    ["D", "H", "BB", "M", "Q"],
    ["E", "I", "BC", "N", "R"],
    ["F", "J", "BD", "O", "S"],
    ["K", "T", "U"],
    ["V", "W", "X", "Y", "Z"],
    ["AA", "AB", "AC"]
  ],
  "14_15_embedding_qdrant_indexing_flow.mmd": [
    ["A", "B", "C", "D", "E"],
    ["I", "H", "G", "F"],
    ["J", "K", "L", "M", "N"],
    ["P", "O", "Q", "R", "S"],
    ["T"]
  ],
  "16_retrieval_citation_flow.mmd": [
    ["A", "B", "C", "D", "E"],
    ["F", "G", "H", "I"],
    ["J", "K", "L"],
    ["LA", "M", "N"],
    ["P", "Q", "R", "S", "O"],
    ["T", "U", "V", "W", "X"],
    ["Y", "Z"]
  ],
  "16a_hybrid_retrieval_sequence_flow.mmd": [
    ["A", "B"],
    ["E", "C"],
    ["D", "F"],
    ["I", "H", "G"],
    ["J", "K"],
    ["L", "M", "N"],
    ["S", "R", "Q", "P", "O"],
    ["T", "U", "V", "W", "X"]
  ],
  "17_validation_golden_tests_flow.mmd": [
    ["A", "B", "C", "D"],
    ["E", "F", "G", "H", "I"],
    ["K", "L", "M", "N", "O", "P"],
    ["Q", "R", "S"],
    ["J"]
  ]
};

function layout(name, nodes, edges, orientation) {
  const ids = [...nodes.keys()]; const order = new Map(ids.map((id, i) => [id, i]));
  if (manualRows[name]) {
    const positions = new Map(); const rows = manualRows[name]; const max = Math.max(...rows.map((row) => row.length));
    rows.forEach((row, r) => row.forEach((id, i) => positions.set(id, {
      x: 140 + (max - row.length) * 160 + i * 320, y: 160 + r * 210, rank: r
    })));
    return positions;
  }
  const rank = new Map(ids.map((id) => [id, 0]));
  // Mermaid source order identifies loop-back edges. Ignore those while assigning layers,
  // then route them around the outside of the diagram below.
  const forward = edges.filter((edge) => (order.get(edge.to) ?? 0) > (order.get(edge.from) ?? 0));
  for (let pass = 0; pass < ids.length; pass++) {
    let changed = false;
    for (const edge of forward) {
      const next = Math.min(ids.length, (rank.get(edge.from) || 0) + 1);
      if (next > (rank.get(edge.to) || 0)) { rank.set(edge.to, next); changed = true; }
    }
    if (!changed) break;
  }
  const groups = new Map();
  for (const id of ids) { const r = rank.get(id); if (!groups.has(r)) groups.set(r, []); groups.get(r).push(id); }
  const positions = new Map(); const horizontal = orientation === "LR" || orientation === "RL";
  const maxLaneCount = Math.max(...[...groups.values()].map((group) => group.length));
  for (const [r, group] of [...groups].sort((a, b) => a[0] - b[0])) group.forEach((id, i) => {
    const laneOffset = (maxLaneCount - group.length) * 160;
    positions.set(id, horizontal
      ? { x: 140 + r * 390, y: 160 + laneOffset / 2 + i * 210, rank: r }
      : { x: 140 + laneOffset + i * 320, y: 160 + r * 210, rank: r });
  });
  return positions;
}

const between = (value, a, b) => value >= Math.min(a, b) && value <= Math.max(a, b);
const segments = (points) => points.slice(1).map((point, i) => [points[i], point]);
const pathLength = (points) => segments(points).reduce((sum, [a, b]) => sum + Math.abs(a[0] - b[0]) + Math.abs(a[1] - b[1]), 0);
const compress = (points) => points.filter((point, i) => {
  if (i === 0 || i === points.length - 1) return true;
  const prev = points[i - 1], next = points[i + 1];
  return !((prev[0] === point[0] && point[0] === next[0]) || (prev[1] === point[1] && point[1] === next[1]));
});

function segmentHitsBox([a, b], box, margin = 14) {
  const left = box.x - margin, right = box.x + box.width + margin;
  const top = box.y - margin, bottom = box.y + box.height + margin;
  if (a[0] === b[0]) return between(a[0], left, right) && Math.max(Math.min(a[1], b[1]), top) <= Math.min(Math.max(a[1], b[1]), bottom);
  if (a[1] === b[1]) return between(a[1], top, bottom) && Math.max(Math.min(a[0], b[0]), left) <= Math.min(Math.max(a[0], b[0]), right);
  return true;
}

function sharedLength(first, second) {
  if (first[0][0] === first[1][0] && second[0][0] === second[1][0] && first[0][0] === second[0][0]) {
    return Math.max(0, Math.min(Math.max(first[0][1], first[1][1]), Math.max(second[0][1], second[1][1])) - Math.max(Math.min(first[0][1], first[1][1]), Math.min(second[0][1], second[1][1])));
  }
  if (first[0][1] === first[1][1] && second[0][1] === second[1][1] && first[0][1] === second[0][1]) {
    return Math.max(0, Math.min(Math.max(first[0][0], first[1][0]), Math.max(second[0][0], second[1][0])) - Math.max(Math.min(first[0][0], first[1][0]), Math.min(second[0][0], second[1][0])));
  }
  return 0;
}

function routeDashed(a, b, edgeIndex, bounds, boxes, edge, usedSegments) {
  const obstacles = boxes.filter((box) => box.id !== a.id && box.id !== b.id);
  const startOffset = Math.max(-a.height / 2 + 18, Math.min(a.height / 2 - 18, edge.startOffset || 0));
  const endOffset = Math.max(-b.height / 2 + 18, Math.min(b.height / 2 - 18, edge.endOffset || 0));
  const verticalStartOffset = Math.max(-a.width / 2 + 24, Math.min(a.width / 2 - 24, edge.startOffset || 0));
  const verticalEndOffset = Math.max(-b.width / 2 + 24, Math.min(b.width / 2 - 24, edge.endOffset || 0));
  const candidates = [];
  const add = (points) => {
    points = compress(points);
    if (segments(points).some((segment) => obstacles.some((box) => segmentHitsBox(segment, box)))) return;
    const overlap = segments(points).reduce((sum, segment) => sum + usedSegments.reduce((inner, used) => inner + sharedLength(segment, used), 0), 0);
    if (overlap > 1) return;
    candidates.push({ points, score: pathLength(points) });
  };

  const goRight = b.x + b.width / 2 >= a.x + a.width / 2;
  const hs = [a.x + (goRight ? a.width : 0), a.y + a.height / 2 + startOffset];
  const he = [b.x + (goRight ? 0 : b.width), b.y + b.height / 2 + endOffset];
  const xCandidates = [(hs[0] + he[0]) / 2, bounds.left - 50 - edgeIndex * 8, bounds.right + 50 + edgeIndex * 8];
  for (const box of obstacles) xCandidates.push(box.x - 28, box.x + box.width + 28);
  for (const x of xCandidates) add([hs, [x, hs[1]], [x, he[1]], he]);

  const goDown = b.y + b.height / 2 >= a.y + a.height / 2;
  const vs = [a.x + a.width / 2 + verticalStartOffset, a.y + (goDown ? a.height : 0)];
  const ve = [b.x + b.width / 2 + verticalEndOffset, b.y + (goDown ? 0 : b.height)];
  const yCandidates = [(vs[1] + ve[1]) / 2, bounds.top - 50 - edgeIndex * 8, bounds.bottom + 50 + edgeIndex * 8];
  for (const box of obstacles) yCandidates.push(box.y - 28, box.y + box.height + 28);
  for (const y of yCandidates) add([vs, [vs[0], y], [ve[0], y], ve]);

  // Perimeter candidates handle dense rows where every direct dogleg is blocked.
  const topY = bounds.top - 70 - edgeIndex * 10, bottomY = bounds.bottom + 70 + edgeIndex * 10;
  const leftX = bounds.left - 70 - edgeIndex * 10, rightX = bounds.right + 70 + edgeIndex * 10;
  const sourceTop = [a.x + a.width / 2 + verticalStartOffset, a.y];
  const sourceBottom = [a.x + a.width / 2 + verticalStartOffset, a.y + a.height];
  const targetLeft = [b.x, b.y + b.height / 2 + endOffset];
  const targetRight = [b.x + b.width, b.y + b.height / 2 + endOffset];
  add([sourceTop, [sourceTop[0], topY], [leftX, topY], [leftX, targetLeft[1]], targetLeft]);
  add([sourceTop, [sourceTop[0], topY], [rightX, topY], [rightX, targetRight[1]], targetRight]);
  add([sourceBottom, [sourceBottom[0], bottomY], [leftX, bottomY], [leftX, targetLeft[1]], targetLeft]);
  add([sourceBottom, [sourceBottom[0], bottomY], [rightX, bottomY], [rightX, targetRight[1]], targetRight]);

  let selected = candidates.sort((x, y) => x.score - y.score)[0];
  if (!selected) {
    const sx = a.x; const sy = a.y + a.height / 2 + startOffset; const ex = b.x; const ey = b.y + b.height / 2 + endOffset;
    const channel = bounds.left - 70 - edgeIndex * 14;
    selected = { points: [[sx, sy], [channel, sy], [channel, ey], [ex, ey]] };
  }
  usedSegments.push(...segments(selected.points));
  const start = selected.points[0], end = selected.points[selected.points.length - 1];
  return { start, end, points: selected.points.map(([x, y]) => [x - start[0], y - start[1]]) };
}

function route(a, b, orientation, edgeIndex, bounds, dotted = false, boxes = [], edge = {}, usedSegments = []) {
  return routeDashed(a, b, edgeIndex, bounds, boxes, edge, usedSegments);
}

const rectsOverlap = (a, b, gap = 0) => a.x < b.x + b.width + gap && a.x + a.width + gap > b.x && a.y < b.y + b.height + gap && a.y + a.height + gap > b.y;
const segmentIntersectsRect = (segment, rect, gap = 0) => segmentHitsBox(segment, rect, gap);

function placeEdgeLabel(text, routed, boxes, allSegments, placedLabels) {
  const display = wrap(text, 22); const lines = display.split("\n").length;
  const width = Math.max(90, Math.min(190, Math.max(...display.split("\n").map((line) => line.length)) * 8 + 20));
  const height = Math.max(36, lines * 18 + 12);
  const absolute = routed.points.map(([x, y]) => [routed.start[0] + x, routed.start[1] + y]);
  const routeSegments = segments(absolute).sort((a, b) => pathLength(b) - pathLength(a));
  const candidates = [];
  const add = (x, y, distance) => {
    const rect = { x, y, width, height };
    const nodeHits = boxes.filter((box) => rectsOverlap(rect, box, 8)).length;
    const labelHits = placedLabels.filter((other) => rectsOverlap(rect, other, 10)).length;
    const lineHits = allSegments.filter((segment) => segmentIntersectsRect(segment, rect, 3)).length;
    candidates.push({ rect, score: nodeHits * 1000000 + labelHits * 500000 + lineHits * 10000 + distance });
  };
  routeSegments.forEach(([a, b], segmentIndex) => {
    const distance = segmentIndex * 20;
    for (const fraction of [0.5, 0.25, 0.75]) {
      const midX = a[0] + (b[0] - a[0]) * fraction, midY = a[1] + (b[1] - a[1]) * fraction;
      if (a[1] === b[1]) {
        add(midX - width / 2, midY - height - 12, distance);
        add(midX - width / 2, midY + 12, distance + 2);
        add(midX - width / 2, midY - height - 36, distance + 6);
        add(midX - width / 2, midY + 36, distance + 8);
      } else {
        add(midX - width - 12, midY - height / 2, distance);
        add(midX + 12, midY - height / 2, distance + 2);
        add(midX - width - 36, midY - height / 2, distance + 6);
        add(midX + 36, midY - height / 2, distance + 8);
      }
    }
  });
  const centerX = absolute.reduce((sum, point) => sum + point[0], 0) / absolute.length;
  const centerY = absolute.reduce((sum, point) => sum + point[1], 0) / absolute.length;
  for (let radius = 80; radius <= 400; radius += 40) {
    for (let offset = -radius; offset <= radius; offset += 40) {
      add(centerX + offset - width / 2, centerY - radius - height / 2, 200 + radius + Math.abs(offset));
      add(centerX + offset - width / 2, centerY + radius - height / 2, 202 + radius + Math.abs(offset));
      add(centerX - radius - width / 2, centerY + offset - height / 2, 204 + radius + Math.abs(offset));
      add(centerX + radius - width / 2, centerY + offset - height / 2, 206 + radius + Math.abs(offset));
    }
  }
  const selected = candidates.sort((a, b) => a.score - b.score)[0];
  placedLabels.push(selected.rect);
  return { ...selected.rect, display };
}

function convert(name, source) {
  const { orientation, nodes, edges, groups } = parse(source); const positions = layout(name, nodes, edges, orientation);
  const elements = []; let index = 0;
  const title = wrap(name.replace(/\.mmd$/, "").replaceAll("_", " "), 60);
  elements.push({ ...base("diagram-title", "text", 100, 45, 900, 45, index++, ["#1e3a5f", "transparent"]),
    backgroundColor: "transparent", strokeWidth: 1, text: title, fontSize: 28, fontFamily: 1,
    textAlign: "left", verticalAlign: "top", baseline: 34, containerId: null, originalText: title,
    autoResize: true, lineHeight: 1.25 });
  for (const node of nodes.values()) {
    const pos = positions.get(node.id); const label = wrap(node.label); const lines = label.split("\n").length;
    const width = node.kind === "decision" ? 250 : 260; const height = Math.max(86, 28 + lines * 22);
    const shapeType = node.kind === "decision" ? "diamond" : node.kind === "terminal" ? "ellipse" : "rectangle";
    const shape = base(`node-${node.id}`, shapeType, pos.x, pos.y, width, height, index++, palette[node.kind]);
    shape.boundElements = [{ type: "text", id: `text-${node.id}` }]; elements.push(shape);
    elements.push({ ...base(`text-${node.id}`, "text", pos.x + 14, pos.y + 12, width - 28, height - 24, index++, [palette[node.kind][0], "transparent"]),
      backgroundColor: "transparent", strokeWidth: 1, text: label, fontSize: 17, fontFamily: 1,
      textAlign: "center", verticalAlign: "middle", baseline: 20, containerId: `node-${node.id}`,
      originalText: node.label, autoResize: true, lineHeight: 1.25 });
    node.box = { id: node.id, ...pos, width, height }; node.shape = shape;
  }
  const boxes = [...nodes.values()].map((node) => node.box);
  const bounds = {
    left: Math.min(...boxes.map((box) => box.x)), top: Math.min(...boxes.map((box) => box.y)),
    right: Math.max(...boxes.map((box) => box.x + box.width)), bottom: Math.max(...boxes.map((box) => box.y + box.height))
  };
  groups.forEach((group, groupIndex) => {
    const label = `${group.label}\n\n${group.members.map((id) => `• ${nodes.get(id)?.label || id}`).join("\n")}`;
    const display = wrap(label, 30); const height = 50 + display.split("\n").length * 20;
    const x = bounds.right + 130, y = 160 + groupIndex * (height + 40);
    const shape = base(`group-${groupIndex}`, "rectangle", x, y, 310, height, index++, ["#475569", "#f8fafc"]);
    shape.strokeStyle = "dashed"; shape.boundElements = [{ type: "text", id: `group-text-${groupIndex}` }]; elements.push(shape);
    elements.push({ ...base(`group-text-${groupIndex}`, "text", x + 16, y + 16, 278, height - 32, index++, ["#334155", "transparent"]),
      backgroundColor: "transparent", strokeWidth: 1, text: display, fontSize: 16, fontFamily: 1,
      textAlign: "left", verticalAlign: "top", baseline: 19, containerId: shape.id,
      originalText: label, autoResize: true, lineHeight: 1.25 });
  });
  const routedEdges = edges;
  const assignFan = (key, property) => {
    const grouped = new Map();
    for (const edge of routedEdges) { const value = edge[key]; if (!grouped.has(value)) grouped.set(value, []); grouped.get(value).push(edge); }
    for (const group of grouped.values()) group.forEach((edge, i) => { edge[property] = (i - (group.length - 1) / 2) * 10; });
  };
  assignFan("from", "startOffset"); assignFan("to", "endOffset");
  const usedSegments = []; const pendingLabels = [];
  for (const [edgeIndex, edge] of edges.entries()) {
    const a = nodes.get(edge.from)?.box; const b = nodes.get(edge.to)?.box; if (!a || !b) continue;
    const routed = route(a, b, orientation, edgeIndex, bounds, edge.dotted, boxes, edge, usedSegments);
    const absolutePoints = routed.points.map(([x, y]) => [routed.start[0] + x, routed.start[1] + y]);
    const minX = Math.min(...absolutePoints.map(([x]) => x)); const minY = Math.min(...absolutePoints.map(([, y]) => y));
    const maxX = Math.max(...absolutePoints.map(([x]) => x)); const maxY = Math.max(...absolutePoints.map(([, y]) => y));
    const arrow = base(`edge-${index}`, "arrow", minX, minY, maxX - minX, maxY - minY, index++, ["#475569", "transparent"]);
    Object.assign(arrow, { backgroundColor: "transparent", strokeStyle: edge.dotted ? "dashed" : "solid",
      points: absolutePoints.map(([x, y]) => [x - minX, y - minY]), lastCommittedPoint: null,
      startBinding: null, endBinding: null, startArrowhead: null, endArrowhead: "arrow" });
    elements.push(arrow);
    if (edge.label) pendingLabels.push({ edge, routed });
  }
  const placedLabels = [];
  for (const { edge, routed } of pendingLabels) {
    const placed = placeEdgeLabel(edge.label, routed, boxes, usedSegments, placedLabels);
    elements.push({ ...base(`edge-label-${index}`, "text", placed.x, placed.y, placed.width, placed.height, index++, ["#334155", "transparent"]),
      backgroundColor: "#ffffff", strokeWidth: 1, text: placed.display, fontSize: 14, fontFamily: 1,
      textAlign: "center", verticalAlign: "middle", baseline: 17, containerId: null,
      originalText: edge.label, autoResize: false, lineHeight: 1.25 });
  }
  return { type: "excalidraw", version: 2, source: "https://github.com/excalidraw/excalidraw",
    elements, appState: { gridSize: 20, gridStep: 5, gridModeEnabled: false, viewBackgroundColor: "#ffffff" }, files: {} };
}

for (const file of files) {
  const source = fs.readFileSync(path.join(dir, file), "utf8");
  fs.writeFileSync(path.join(outputDir, file.replace(/\.mmd$/, ".excalidraw")), JSON.stringify(convert(file, source), null, 2) + "\n");
}
console.log(`Converted ${files.length} Mermaid flowcharts to editable Excalidraw files.`);
