import { useMemo } from "react";

const COL = 210;
const ROW = 208;
const PAD_X = 130;
const TOP = 136;

function initials(name) {
  const clean = String(name || "").replace(/\([^)]*\)/g, "").trim();
  const words = clean.split(/\s+/).filter(Boolean);
  if (!words.length) return "?";
  if (words.length === 1) return words[0].slice(0, 2).toUpperCase();
  return (words[0][0] + words[words.length - 1][0]).toUpperCase();
}

function splitName(name, max = 18) {
  const clean = String(name || "").replace(/\s+/g, " ").trim();
  if (clean.length <= max) return [clean];
  const words = clean.split(" ");
  let lineOne = "";
  let lineTwo = "";
  for (const word of words) {
    if (!lineTwo && `${lineOne} ${word}`.trim().length <= max) {
      lineOne = `${lineOne} ${word}`.trim();
    } else {
      lineTwo = `${lineTwo} ${word}`.trim();
    }
  }
  if (!lineOne) {
    lineOne = `${clean.slice(0, max - 1)}…`;
  }
  if (!lineTwo) lineTwo = "";
  if (lineTwo.length > max + 4) lineTwo = `${lineTwo.slice(0, max + 3)}…`;
  return lineTwo ? [lineOne, lineTwo] : [lineOne];
}

function roleText(node) {
  if (node.is_root) return "the deceased";
  const roles = (node.roles || []).filter(Boolean);
  if (!roles.length) return "named in notice";
  const unique = [...new Set(roles)];
  return unique.slice(0, 2).join(" · ");
}

function edgeHash(edge) {
  const hash = edge.sources?.find((source) => source.record_hash)?.record_hash;
  return hash ? hash.slice(0, 6).toUpperCase() : "UNHASHED";
}

function buildLayout(graph) {
  const nodes = graph?.nodes || [];
  const edges = graph?.edges || [];
  if (!nodes.length) {
    return { nodes: [], edges: [], width: 900, height: 420, positions: new Map() };
  }

  const byGeneration = new Map();
  for (const node of nodes) {
    const generation = Number.isFinite(node.generation) ? node.generation : 0;
    if (!byGeneration.has(generation)) byGeneration.set(generation, []);
    byGeneration.get(generation).push(node);
  }

  const generations = [...byGeneration.keys()].sort((a, b) => a - b);
  const widest = Math.max(...generations.map((g) => byGeneration.get(g).length));
  const width = Math.max(900, widest * COL + PAD_X * 2);
  const height = (generations[generations.length - 1] - generations[0]) * ROW + 320;
  const positions = new Map();

  const place = (list, generation) => {
    const y = TOP + (generation - generations[0]) * ROW;
    const total = (list.length - 1) * COL;
    list.forEach((node, index) => {
      positions.set(node.id, {
        x: width / 2 - total / 2 + index * COL,
        y,
      });
    });
  };

  for (const generation of generations) {
    byGeneration.get(generation).sort((a, b) => a.name.localeCompare(b.name));
    place(byGeneration.get(generation), generation);
  }

  const neighbours = new Map(nodes.map((node) => [node.id, []]));
  for (const edge of edges) {
    neighbours.get(edge.source)?.push(edge.target);
    neighbours.get(edge.target)?.push(edge.source);
  }

  for (let pass = 0; pass < 2; pass += 1) {
    for (const generation of generations) {
      const list = byGeneration.get(generation);
      if (list.length < 2) continue;
      const barycenter = new Map();
      for (const node of list) {
        const xs = (neighbours.get(node.id) || [])
          .map((id) => positions.get(id)?.x)
          .filter((x) => Number.isFinite(x));
        barycenter.set(
          node.id,
          xs.length ? xs.reduce((sum, x) => sum + x, 0) / xs.length : positions.get(node.id).x
        );
      }
      list.sort(
        (a, b) =>
          barycenter.get(a.id) - barycenter.get(b.id) || a.name.localeCompare(b.name)
      );
      place(list, generation);
    }
  }

  return {
    nodes,
    edges,
    width,
    height,
    positions,
  };
}

function edgePath(from, to) {
  if (!from || !to) return null;
  if (Math.abs(to.y - from.y) < 40) {
    const midX = (from.x + to.x) / 2;
    const lift = Math.min(from.y, to.y) - 122;
    const startY = from.y - 50;
    const endY = to.y - 50;
    const pointAt = (t) => {
      const a = (1 - t) * (1 - t);
      const b = 2 * (1 - t) * t;
      const c = t * t;
      return { x: a * from.x + b * midX + c * to.x, y: a * startY + b * lift + c * endY };
    };
    return {
      d: `M ${from.x} ${startY} Q ${midX} ${lift} ${to.x} ${endY}`,
      pointAt,
    };
  }
  const downward = to.y > from.y;
  const startY = from.y + (downward ? 54 : -54);
  const endY = to.y + (downward ? -54 : 54);
  const midY = (startY + endY) / 2;
  const pointAt = (t) => {
    const a = (1 - t) ** 3;
    const b = 3 * (1 - t) ** 2 * t;
    const c = 3 * (1 - t) * t ** 2;
    const e = t ** 3;
    return { x: from.x + (to.x - from.x) * (c + e), y: a * startY + (b + c) * midY + e * endY };
  };
  return {
    d: `M ${from.x} ${startY} C ${from.x} ${midY}, ${to.x} ${midY}, ${to.x} ${endY}`,
    pointAt,
  };
}

function edgeLabelWidth(edge) {
  return Math.max(104, edge.label.length * 10 + 48);
}

function layoutEdgeLabels(edges, nodes, positions, width, height) {
  const labels = new Map();
  const placed = [];
  const circles = nodes
    .map((node) => {
      const position = positions.get(node.id);
      if (!position) return null;
      return { x: position.x, y: position.y, r: (node.is_root ? 55 : 44) + 10 };
    })
    .filter(Boolean);

  const fractions = [0.5, 0.38, 0.62, 0.28, 0.72, 0.2, 0.8];
  const sides = [0, 64, -64, 120, -120];
  const shifts = [0, -52, 52, -100, 100];

  for (const edge of edges) {
    const geometry = edgePath(positions.get(edge.source), positions.get(edge.target));
    if (!geometry) continue;
    const w = edgeLabelWidth(edge);
    const h = 40;
    let chosen = null;

    for (const t of fractions) {
      for (const dx of sides) {
        for (const dy of shifts) {
          const point = geometry.pointAt(t);
          const rect = {
            left: point.x + dx - w / 2,
            right: point.x + dx + w / 2,
            top: point.y + dy - h / 2,
            bottom: point.y + dy + h / 2,
          };
          if (rect.left < 14 || rect.right > width - 14 || rect.top < 30 || rect.bottom > height - 18) {
            continue;
          }
          const hitsNode = circles.some((circle) => {
            const nx = Math.max(rect.left, Math.min(circle.x, rect.right));
            const ny = Math.max(rect.top, Math.min(circle.y, rect.bottom));
            return (nx - circle.x) ** 2 + (ny - circle.y) ** 2 < circle.r ** 2;
          });
          if (hitsNode) continue;
          const hitsLabel = placed.some(
            (other) =>
              !(
                rect.right + 8 < other.left ||
                rect.left - 8 > other.right ||
                rect.bottom + 8 < other.top ||
                rect.top - 8 > other.bottom
              )
          );
          if (hitsLabel) continue;
          chosen = { x: point.x + dx, y: point.y + dy, w };
          break;
        }
        if (chosen) break;
      }
      if (chosen) break;
    }

    if (!chosen) {
      const point = geometry.pointAt(0.5);
      chosen = { x: point.x, y: point.y, w };
    }
    placed.push({
      left: chosen.x - w / 2,
      right: chosen.x + w / 2,
      top: chosen.y - h / 2,
      bottom: chosen.y + h / 2,
    });
    labels.set(edge.id, chosen);
  }

  return labels;
}

export default function FamilyTree({ graph, selection, onSelect }) {
  const { nodes, edges, width, height, positions, labels } = useMemo(() => {
    const layout = buildLayout(graph);
    return {
      ...layout,
      labels: layoutEdgeLabels(layout.edges, layout.nodes, layout.positions, layout.width, layout.height),
    };
  }, [graph]);

  if (!nodes.length) {
    return (
      <div className="tree-empty">
        <p>No names have been reconstructed yet.</p>
        <span>Add a second clipping or review the extracted text.</span>
      </div>
    );
  }

  return (
    <div className="tree-wrap">
      <div className="tree-plate-head">
        <div>
          <span className="kicker">The family ledger</span>
          <h3>{graph.root_name || "Unidentified memorial"}</h3>
        </div>
        <div className="tree-legend">
          <span className="legend-item">
            <i className="legend-line legend-corroborated" /> Corroborated
          </span>
          <span className="legend-item">
            <i className="legend-line legend-single" /> Single source
          </span>
          <span className="legend-item">
            <i className="legend-line legend-conflict" /> Conflict
          </span>
          <span className="legend-item">
            <i className="legend-seal">✓</i> Sealed
          </span>
        </div>
      </div>

      <div className="tree-canvas">
        <svg
          className="tree-svg"
          viewBox={`0 0 ${width} ${height}`}
          role="img"
          aria-label={`Family tree for ${graph.root_name || "the deceased"}`}
        >
          <defs>
            <pattern id="ledgerGrid" width="28" height="28" patternUnits="userSpaceOnUse">
              <path d="M 28 0 L 0 0 0 28" fill="none" stroke="rgba(215,174,103,0.09)" strokeWidth="0.8" />
            </pattern>
            <pattern id="ledgerGridMajor" width="140" height="140" patternUnits="userSpaceOnUse">
              <rect width="140" height="140" fill="url(#ledgerGrid)" />
              <path d="M 140 0 L 0 0 0 140" fill="none" stroke="rgba(215,174,103,0.16)" strokeWidth="1" />
            </pattern>
            <radialGradient id="plateGlow" cx="50%" cy="38%" r="70%">
              <stop offset="0%" stopColor="#23493d" stopOpacity="0.55" />
              <stop offset="100%" stopColor="#0f251f" stopOpacity="0" />
            </radialGradient>
            <radialGradient id="nodeFill" cx="42%" cy="34%" r="72%">
              <stop offset="0%" stopColor="#fbf4e3" />
              <stop offset="100%" stopColor="#e7d8b9" />
            </radialGradient>
            <filter id="nodeShadow" x="-50%" y="-50%" width="200%" height="200%">
              <feDropShadow dx="0" dy="5" stdDeviation="6" floodColor="#000000" floodOpacity="0.42" />
            </filter>
            <filter id="brassGlow" x="-40%" y="-40%" width="180%" height="180%">
              <feGaussianBlur stdDeviation="3.4" result="blur" />
              <feMerge>
                <feMergeNode in="blur" />
                <feMergeNode in="SourceGraphic" />
              </feMerge>
            </filter>
          </defs>

          <rect width={width} height={height} fill="#0f251f" />
          <rect width={width} height={height} fill="url(#ledgerGridMajor)" />
          <rect width={width} height={height} fill="url(#plateGlow)" />

          <text className="plate-overline" x={width / 2} y="48" textAnchor="middle">
            ORBITREE · CHAIN OF EVIDENCE
          </text>

          {edges.map((edge) => {
            const geometry = edgePath(positions.get(edge.source), positions.get(edge.target));
            if (!geometry) return null;
            const selected = selection?.type === "edge" && selection.id === edge.id;
            const plaque = labels.get(edge.id) || { ...geometry.pointAt(0.5), w: edgeLabelWidth(edge) };
            return (
              <g
                key={edge.id}
                className={`tree-edge edge-${edge.status} ${selected ? "is-selected" : ""}`}
                onClick={(event) => {
                  event.stopPropagation();
                  onSelect?.({ type: "edge", id: edge.id });
                }}
                role="button"
                tabIndex={0}
                onKeyDown={(event) => {
                  if (event.key === "Enter" || event.key === " ") {
                    event.preventDefault();
                    onSelect?.({ type: "edge", id: edge.id });
                  }
                }}
              >
                <path className="edge-hit" d={geometry.d} />
                <path className="edge-halo" d={geometry.d} />
                <path className="edge-line" d={geometry.d} />
                <g className="edge-plaque" transform={`translate(${plaque.x}, ${plaque.y})`}>
                  <title>
                    {edge.label}
                    {edge.corroboration > 1 ? ` · ${edge.corroboration} witnesses` : ""} ·{" "}
                    {edgeHash(edge)}
                  </title>
                  <rect x={-plaque.w / 2} y="-20" width={plaque.w} height="40" rx="4" />
                  <text className="edge-label" y="6" textAnchor="middle">
                    {edge.label}
                  </text>
                  {edge.corroboration > 1 && (
                    <circle className="edge-agreement-dot" cx={plaque.w / 2 - 10} cy="-10" r="4" />
                  )}
                  {edge.conflict && (
                    <text className="edge-conflict-mark" x={plaque.w / 2 - 11} y="-7" textAnchor="middle">
                      !
                    </text>
                  )}
                </g>
              </g>
            );
          })}

          {nodes.map((node) => {
            const position = positions.get(node.id);
            if (!position) return null;
            const root = node.is_root;
            const radius = root ? 55 : 44;
            const lines = splitName(node.name, root ? 20 : 17);
            const selected = selection?.type === "node" && selection.id === node.id;
            const nameStep = root ? 23 : 19;
            const nameY = radius + 21;
            const roleY = nameY + lines.length * nameStep + 2;
            return (
              <g
                key={node.id}
                className={`tree-node ${root ? "node-root" : ""} ${
                  node.generation < 0 ? "node-ancestor" : ""
                } ${node.generation > 0 ? "node-descendant" : ""} ${
                  selected ? "is-selected" : ""
                }`}
                transform={`translate(${position.x}, ${position.y})`}
                onClick={(event) => {
                  event.stopPropagation();
                  onSelect?.({ type: "node", id: node.id });
                }}
                role="button"
                tabIndex={0}
                onKeyDown={(event) => {
                  if (event.key === "Enter" || event.key === " ") {
                    event.preventDefault();
                    onSelect?.({ type: "node", id: node.id });
                  }
                }}
              >
                <circle className="node-halo" r={radius + 13} />
                {root && <circle className="node-orbit" r={radius + 8} />}
                <circle className="node-shadow" r={radius} filter="url(#nodeShadow)" />
                <circle className="node-ring" r={radius} />
                <circle className="node-ring-inner" r={radius - 7} />
                <circle className="node-core" r={radius - 13} fill="url(#nodeFill)" />
                <text className="node-initials" y="5" textAnchor="middle">
                  {initials(node.name)}
                </text>

                {node.source_count > 1 && (
                  <g className="node-source-badge" transform={`translate(${radius - 4}, ${radius - 10})`}>
                    <circle r="10" />
                    <text y="4" textAnchor="middle">{node.source_count}</text>
                  </g>
                )}

                {node.attested && (
                  <g className="node-seal" transform={`translate(${-radius + 2}, ${-radius + 2})`}>
                    <circle r="10" />
                    <text y="4" textAnchor="middle">✓</text>
                  </g>
                )}

                <g className="node-caption">
                  {lines.map((line, index) => (
                    <text
                      key={line + index}
                      className="node-name"
                      y={nameY + index * nameStep}
                      textAnchor="middle"
                    >
                      {line}
                    </text>
                  ))}
                  <text className="node-role" y={roleY} textAnchor="middle">
                    {roleText(node)}
                  </text>
                  {root && (
                    <text className="node-root-flag" y={roleY + 19} textAnchor="middle">
                      GENESIS RECORD
                    </text>
                  )}
                </g>
              </g>
            );
          })}
        </svg>
      </div>
    </div>
  );
}
