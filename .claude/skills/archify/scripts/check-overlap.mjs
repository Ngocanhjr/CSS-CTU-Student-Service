#!/usr/bin/env node
// Diagnostic: detect connection segments that visually overlap or run too
// close in parallel, for architecture-mode JSON files. Not part of the
// shipped skill — throwaway analysis tool for this session.

import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { anchor, defaultFromSide, defaultToSide, chosenSide } from '../renderers/shared/geometry.mjs';

const inputPath = process.argv[2];
if (!inputPath) {
  console.error('Usage: node scripts/check-overlap.mjs <diagram.json>');
  process.exit(2);
}

const arch = JSON.parse(fs.readFileSync(path.resolve(inputPath), 'utf8'));

function measureComponent(c) {
  const [x, y] = c.pos;
  const [w, h] = c.size || [120, 60];
  return { ...c, x, y, width: w, height: h, cx: x + w / 2, cy: y + h / 2 };
}
const components = new Map(arch.components.map((c) => [c.id, measureComponent(c)]));

function routeVia(conn, start, end) {
  if (conn.via) return conn.via;
  switch (conn.route || 'auto') {
    case 'straight': return [];
    case 'orthogonal-h': {
      const midX = (start[0] + end[0]) / 2;
      return [[midX, start[1]], [midX, end[1]]];
    }
    case 'orthogonal-v': {
      const midY = (start[1] + end[1]) / 2;
      return [[start[0], midY], [end[0], midY]];
    }
    default: {
      if (Math.abs(start[0] - end[0]) < 4 || Math.abs(start[1] - end[1]) < 4) return [];
      const midX = (start[0] + end[0]) / 2;
      return [[midX, start[1]], [midX, end[1]]];
    }
  }
}

const paths = arch.connections.map((conn, i) => {
  const from = components.get(conn.from);
  const to = components.get(conn.to);
  const start = anchor(from, chosenSide(conn.fromSide, defaultFromSide(from, to)));
  const end = anchor(to, chosenSide(conn.toSide, defaultToSide(from, to)));
  const points = [start, ...routeVia(conn, start, end), end];
  return { i, conn, points };
});

function segments(points) {
  const segs = [];
  for (let i = 1; i < points.length; i += 1) segs.push({ a: points[i - 1], b: points[i] });
  return segs;
}

function isVertical(seg) { return Math.abs(seg.a[0] - seg.b[0]) < 0.5; }
function isHorizontal(seg) { return Math.abs(seg.a[1] - seg.b[1]) < 0.5; }
function range(a, b) { return [Math.min(a, b), Math.max(a, b)]; }
function overlaps1d(r1, r2, gap = 0) {
  return r1[0] < r2[1] + gap && r2[0] < r1[1] + gap;
}

const GAP = 10; // px, minimum comfortable spacing between parallel lines
const issues = [];

for (let i = 0; i < paths.length; i += 1) {
  for (let j = i + 1; j < paths.length; j += 1) {
    const segsA = segments(paths[i].points);
    const segsB = segments(paths[j].points);
    for (const sa of segsA) {
      for (const sb of segsB) {
        if (isVertical(sa) && isVertical(sb)) {
          const dx = Math.abs(sa.a[0] - sb.a[0]);
          const [ay1, ay2] = range(sa.a[1], sa.b[1]);
          const [by1, by2] = range(sb.a[1], sb.b[1]);
          if (dx < GAP && overlaps1d([ay1, ay2], [by1, by2])) {
            issues.push(`V-overlap conn#${paths[i].i}(${paths[i].conn.from}->${paths[i].conn.to}) vs conn#${paths[j].i}(${paths[j].conn.from}->${paths[j].conn.to}): dx=${dx.toFixed(1)} yrange overlap [${Math.max(ay1,by1).toFixed(0)},${Math.min(ay2,by2).toFixed(0)}]`);
          }
        }
        if (isHorizontal(sa) && isHorizontal(sb)) {
          const dy = Math.abs(sa.a[1] - sb.a[1]);
          const [ax1, ax2] = range(sa.a[0], sa.b[0]);
          const [bx1, bx2] = range(sb.a[0], sb.b[0]);
          if (dy < GAP && overlaps1d([ax1, ax2], [bx1, bx2])) {
            issues.push(`H-overlap conn#${paths[i].i}(${paths[i].conn.from}->${paths[i].conn.to}) vs conn#${paths[j].i}(${paths[j].conn.from}->${paths[j].conn.to}): dy=${dy.toFixed(1)} xrange overlap [${Math.max(ax1,bx1).toFixed(0)},${Math.min(ax2,bx2).toFixed(0)}]`);
          }
        }
      }
    }
  }
}

// Also check: connection segments passing through unrelated components
for (const p of paths) {
  for (const seg of segments(p.points)) {
    for (const [id, c] of components) {
      if (id === p.conn.from || id === p.conn.to) continue;
      const box = { x1: c.x - 4, y1: c.y - 4, x2: c.x + c.width + 4, y2: c.y + c.height + 4 };
      if (segCrossesBox(seg, box)) {
        issues.push(`CROSSES conn#${p.i}(${p.conn.from}->${p.conn.to}) passes through component "${id}"`);
      }
    }
  }
}

function segCrossesBox(seg, box) {
  const inside = (pt) => pt[0] >= box.x1 && pt[0] <= box.x2 && pt[1] >= box.y1 && pt[1] <= box.y2;
  if (inside(seg.a) || inside(seg.b)) return true;
  // simple axis-aligned clip check since our segments are always axis-aligned or diagonal-straight
  if (isVertical(seg)) {
    const x = seg.a[0];
    if (x < box.x1 || x > box.x2) return false;
    const [y1, y2] = range(seg.a[1], seg.b[1]);
    return overlaps1d([y1, y2], [box.y1, box.y2]);
  }
  if (isHorizontal(seg)) {
    const y = seg.a[1];
    if (y < box.y1 || y > box.y2) return false;
    const [x1, x2] = range(seg.a[0], seg.b[0]);
    return overlaps1d([x1, x2], [box.x1, box.x2]);
  }
  return false;
}

console.log(`File: ${inputPath}`);
console.log(`Connections: ${paths.length}`);
if (issues.length === 0) {
  console.log('No overlap/crossing issues found.');
} else {
  console.log(`${issues.length} issue(s):`);
  for (const iss of issues) console.log(' - ' + iss);
}
