const state = {
  analysis: null,
  downloadUrl: null,
};

const dom = {
  body: document.body,
  form: document.getElementById("analyze-form"),
  submitButton: document.getElementById("submit-button"),
  fileInput: document.getElementById("file-input"),
  status: document.getElementById("status"),
  summary: document.getElementById("summary"),
  charts: document.getElementById("charts"),
  jsonPreview: document.getElementById("json-preview"),
  downloadJson: document.getElementById("download-json"),
};

const colors = {
  extrema: "#245f7a",
  maxima: "#be4a2f",
  minima: "#3f7c47",
  signedDiff: "#b13e53",
  absDiff: "#287271",
  amplitude: "#1d4e89",
  signChangeAmplitudeDiff: "#d97706",
  aggregateRatio: "#3f7c47",
  signChanges: "#4d5566",
  aggregate: "#8f2d56",
};

function setStatus(message, kind = "neutral") {
  dom.status.textContent = message;
  dom.status.className = `status${kind === "neutral" ? "" : ` ${kind}`}`;
}

function setBusy(isBusy) {
  dom.submitButton.disabled = isBusy;
  dom.fileInput.disabled = isBusy;
}

function createSvgEl(tag, attrs = {}) {
  const el = document.createElementNS("http://www.w3.org/2000/svg", tag);
  Object.entries(attrs).forEach(([key, value]) => {
    el.setAttribute(key, String(value));
  });
  return el;
}

function niceStep(range, targetTicks) {
  if (!Number.isFinite(range) || range <= 0) {
    return 1;
  }

  const raw = range / targetTicks;
  const magnitude = 10 ** Math.floor(Math.log10(raw));
  const residual = raw / magnitude;

  if (residual >= 5) {
    return 5 * magnitude;
  }
  if (residual >= 2) {
    return 2 * magnitude;
  }
  return magnitude;
}

function formatNumber(value) {
  if (!Number.isFinite(value)) {
    return "";
  }
  const rounded = Math.round(value * 1000) / 1000;
  return Number.isInteger(rounded) ? String(rounded) : String(rounded);
}

function clearDownloadUrl() {
  if (state.downloadUrl) {
    URL.revokeObjectURL(state.downloadUrl);
    state.downloadUrl = null;
  }
}

function updateDownload(result) {
  clearDownloadUrl();
  const blob = new Blob([JSON.stringify(result, null, 2)], { type: "application/json" });
  state.downloadUrl = URL.createObjectURL(blob);
  dom.downloadJson.disabled = false;
}

function renderSummary(result) {
  const frameInfo = result.frameInfo;
  const modeText = frameInfo.type === "manual"
    ? `Ручний діапазон ${frameInfo.manualStart}..${frameInfo.manualEnd}`
    : `Фрейм ${frameInfo.frameNumber} по ${frameInfo.frameSize} спостережень`;

  const cards = [
    ["Режим", result.modeName || result.mode || "невідомо"],
    ["Файл", result.filename],
    ["Вхідних спостережень", result.sourceCount],
    ["Обраний режим", modeText],
    ["Глобальний діапазон", `${frameInfo.selectedGlobalStart}..${frameInfo.selectedGlobalEnd}`],
    ["Спостережень у фреймі", frameInfo.selectedCount],
    ["Екстремумів", result.extrema.length],
    ["Максимальний k", result.effectiveMaxK >= 0 ? result.effectiveMaxK : "недостатньо даних"],
    ["Груп інтервалів", result.aggregateGroups.length],
  ];

  dom.summary.className = "summary";
  dom.summary.innerHTML = "";

  const grid = document.createElement("div");
  grid.className = "summary-grid";

  for (const [label, value] of cards) {
    const card = document.createElement("div");
    card.className = "summary-card";

    const strong = document.createElement("strong");
    strong.textContent = label;

    const span = document.createElement("span");
    span.textContent = String(value);

    card.appendChild(strong);
    card.appendChild(span);
    grid.appendChild(card);
  }

  dom.summary.appendChild(grid);
}

function buildPath(points, sx, sy) {
  if (!points.length) {
    return "";
  }

  return points
    .map((point, index) => `${index === 0 ? "M" : "L"} ${sx(point.x)} ${sy(point.y)}`)
    .join(" ");
}

function drawChart(svg, series, xLabel, yLabel, options = {}) {
  const width = 1120;
  const height = 430;
  const plot = { left: 78, top: 24, right: 1090, bottom: 350 };
  const plotWidth = plot.right - plot.left;
  const plotHeight = plot.bottom - plot.top;

  const allPoints = series.flatMap((item) => item.points);
  if (!allPoints.length) {
    return;
  }

  const xCandidates = allPoints.map((point) => point.x).concat(options.extraXValues || []);
  let xMin = Math.min(...xCandidates);
  let xMax = Math.max(...xCandidates);
  let yMin = Math.min(...allPoints.map((point) => point.y));
  let yMax = Math.max(...allPoints.map((point) => point.y));
  const stemSeries = series.filter((item) => item.type === "stem");
  const hasStems = stemSeries.length > 0;

  if (hasStems) {
    yMin = Math.min(yMin, 0);
    yMax = Math.max(yMax, 0);
  }

  if (xMin === xMax) {
    xMin -= 1;
    xMax += 1;
  }
  if (yMin === yMax) {
    yMin -= 1;
    yMax += 1;
  }

  const xPad = Math.max(1, (xMax - xMin) * 0.03);
  const yPad = Math.max(0.5, (yMax - yMin) * 0.08);
  xMin -= xPad;
  xMax += xPad;
  yMin -= yPad;
  yMax += yPad;

  const sx = (value) => plot.left + ((value - xMin) / (xMax - xMin)) * plotWidth;
  const sy = (value) => plot.bottom - ((value - yMin) / (yMax - yMin)) * plotHeight;

  const background = createSvgEl("rect", {
    x: 0,
    y: 0,
    width,
    height,
    fill: "#faf8f2",
  });
  svg.appendChild(background);

  const gridLayer = createSvgEl("g");
  const axisLayer = createSvgEl("g");
  const seriesLayer = createSvgEl("g");
  const labelLayer = createSvgEl("g");

  const xStep = niceStep(xMax - xMin, 10);
  const yStep = niceStep(yMax - yMin, 8);

  const xTickStart = Math.ceil(xMin / xStep) * xStep;
  for (let x = xTickStart; x <= xMax + xStep / 2; x += xStep) {
    const px = sx(x);
    gridLayer.appendChild(
      createSvgEl("line", {
        x1: px,
        y1: plot.top,
        x2: px,
        y2: plot.bottom,
        stroke: "#e2d9ce",
        "stroke-width": 1,
      }),
    );
    const label = createSvgEl("text", {
      x: px,
      y: plot.bottom + 22,
      fill: "#6a7282",
      "font-size": 13,
      "text-anchor": "middle",
    });
    label.textContent = formatNumber(x);
    labelLayer.appendChild(label);
  }

  const yTickStart = Math.ceil(yMin / yStep) * yStep;
  for (let y = yTickStart; y <= yMax + yStep / 2; y += yStep) {
    const py = sy(y);
    gridLayer.appendChild(
      createSvgEl("line", {
        x1: plot.left,
        y1: py,
        x2: plot.right,
        y2: py,
        stroke: "#e2d9ce",
        "stroke-width": 1,
      }),
    );
    const label = createSvgEl("text", {
      x: plot.left - 12,
      y: py + 4,
      fill: "#6a7282",
      "font-size": 13,
      "text-anchor": "end",
    });
    label.textContent = formatNumber(y);
    labelLayer.appendChild(label);
  }

  if (yMin <= 0 && yMax >= 0) {
    seriesLayer.appendChild(
      createSvgEl("line", {
        x1: plot.left,
        y1: sy(0),
        x2: plot.right,
        y2: sy(0),
        stroke: "#9fa8b7",
        "stroke-dasharray": "6 4",
        "stroke-width": 1.2,
      }),
    );
  }

  axisLayer.appendChild(
    createSvgEl("rect", {
      x: plot.left,
      y: plot.top,
      width: plotWidth,
      height: plotHeight,
      fill: "none",
      stroke: "#938574",
      "stroke-width": 1.5,
    }),
  );

  const xAxisLabel = createSvgEl("text", {
    x: plot.left + plotWidth / 2,
    y: height - 20,
    fill: "#4a5160",
    "font-size": 15,
    "text-anchor": "middle",
  });
  xAxisLabel.textContent = xLabel;
  labelLayer.appendChild(xAxisLabel);

  const yAxisLabel = createSvgEl("text", {
    x: 22,
    y: plot.top + plotHeight / 2,
    fill: "#4a5160",
    "font-size": 15,
    transform: `rotate(-90 22 ${plot.top + plotHeight / 2})`,
    "text-anchor": "middle",
  });
  yAxisLabel.textContent = yLabel;
  labelLayer.appendChild(yAxisLabel);

  const stemBaseY = sy(0);
  const stemSlotMap = new Map(stemSeries.map((item, index) => [item.name, index]));
  const stemSpacing = stemSeries.length > 1 ? 2 : 0;

  series.forEach((item) => {
    if (!item.points.length) {
      return;
    }

    if (item.type === "stem") {
      const slot = stemSlotMap.get(item.name) ?? 0;
      const offset = (slot - (stemSeries.length - 1) / 2) * stemSpacing;

      item.points.forEach((point) => {
        const x = sx(point.x) + offset;
        const y = sy(point.y);
        seriesLayer.appendChild(
          createSvgEl("line", {
            x1: x,
            y1: stemBaseY,
            x2: x,
            y2: y,
            stroke: item.color,
            "stroke-width": item.strokeWidth || 2.4,
            "stroke-linecap": "round",
          }),
        );
        seriesLayer.appendChild(
          createSvgEl("circle", {
            cx: x,
            cy: y,
            r: item.radius || 2.8,
            fill: item.fill || item.color,
            stroke: item.stroke || "#fffdf8",
            "stroke-width": item.strokeWidthPoints || 1.1,
          }),
        );

        if (point.label !== undefined && point.label !== null && point.label !== "") {
          const text = createSvgEl("text", {
            x,
            y: Math.max(plot.top + 12, y - 10),
            fill: point.labelColor || item.labelColor || item.color,
            "font-size": item.labelFontSize || 12,
            "font-weight": item.labelFontWeight || 600,
            "text-anchor": "middle",
          });
          text.textContent = String(point.label);
          labelLayer.appendChild(text);
        }
      });
      return;
    }

    if (item.type !== "points") {
      const path = createSvgEl("path", {
        d: buildPath(item.points, sx, sy),
        fill: "none",
        stroke: item.color,
        "stroke-width": item.strokeWidth || 2.3,
        "stroke-linejoin": "round",
        "stroke-linecap": "round",
      });
      if (item.dasharray) {
        path.setAttribute("stroke-dasharray", item.dasharray);
      }
      seriesLayer.appendChild(path);
    }

    item.points.forEach((point) => {
      const circle = createSvgEl("circle", {
        cx: sx(point.x),
        cy: sy(point.y),
        r: item.radius || 3.6,
        fill: item.fill || item.color,
        stroke: item.stroke || "#fffdf8",
        "stroke-width": item.strokeWidthPoints || 1.2,
      });
      seriesLayer.appendChild(circle);
    });
  });

  svg.appendChild(gridLayer);
  svg.appendChild(axisLayer);
  svg.appendChild(seriesLayer);
  svg.appendChild(labelLayer);

  return {
    plotLeftViewBox: plot.left,
    plotBottomViewBox: plot.bottom,
    plotWidthViewBox: plotWidth,
    viewBoxWidth: width,
    viewBoxHeight: height,
    xMin,
    xMax,
    xDomainSpan: xMax - xMin,
    yGridUnitViewBox: Math.abs(sy(yTickStart + yStep) - sy(yTickStart)),
    yUnitViewBox: Math.abs(sy(1) - sy(0)),
  };
}

function createLegend(series) {
  const legend = document.createElement("div");
  legend.className = "legend";

  series
    .filter((item) => item.points.length)
    .forEach((item) => {
      const entry = document.createElement("div");
      entry.className = "legend-item";

      const swatch = document.createElement("span");
      swatch.className = "legend-swatch";
      swatch.style.background = item.color;

      const label = document.createElement("span");
      label.textContent = item.name;

      entry.appendChild(swatch);
      entry.appendChild(label);
      legend.appendChild(entry);
    });

  return legend;
}

function groupIntervalsByDuration(intervals) {
  const grouped = new Map();

  intervals.forEach((row) => {
    const duration = Number(row.duration);
    if (!grouped.has(duration)) {
      grouped.set(duration, []);
    }
    grouped.get(duration).push(row);
  });

  return [...grouped.entries()]
    .sort((left, right) => left[0] - right[0])
    .map(([duration, rows]) => ({ duration, rows }));
}

function createIntervalTimeline(intervals) {
  const wrapper = document.createElement("div");
  wrapper.className = "interval-panel";

  const heading = document.createElement("h3");
  heading.textContent = "Частоти виділених інтервалів";
  wrapper.appendChild(heading);

  if (!intervals.length) {
    const empty = document.createElement("div");
    empty.className = "no-data interval-empty";
    empty.textContent = "Для цього k ще не накопичилось двох послідовних моментів зміни знака, тому інтервали відсутні.";
    wrapper.appendChild(empty);
    return wrapper;
  }

  const distribution = groupIntervalsByDuration(intervals);
  const list = document.createElement("div");
  list.className = "interval-timelines";

  distribution.forEach((row) => {
    const item = document.createElement("div");
    item.className = "interval-timeline-row";

    const label = document.createElement("div");
    label.className = "interval-timeline-label";
    label.textContent = `T = ${formatNumber(row.duration)}`;

    const sequenceWrap = document.createElement("div");
    sequenceWrap.className = "interval-sequence-wrap";

    const stack = document.createElement("div");
    stack.className = "interval-stack";

    const sequence = document.createElement("div");
    sequence.className = "interval-sequence";
    sequence.title = `T = ${formatNumber(row.duration)}, кількість = ${row.rows.length}`;

    row.rows.forEach((intervalRow) => {
      const segment = document.createElement("div");
      segment.className = "interval-segment";
      segment.dataset.duration = String(row.duration);
      segment.title = `T = ${formatNumber(row.duration)}; між ${intervalRow.startLocalIndex} і ${intervalRow.endLocalIndex}`;
      sequence.appendChild(segment);
    });

    const amplitudeSequence = document.createElement("div");
    amplitudeSequence.className = "amplitude-sequence";
    amplitudeSequence.title = `Модулі різниць амплітуд для T = ${formatNumber(row.duration)}`;

    row.rows.forEach((intervalRow) => {
      const segment = document.createElement("div");
      segment.className = "amplitude-segment";
      segment.dataset.amplitude = String(intervalRow.absAmplitudeDiff);
      segment.title = `|ΔA| = ${formatNumber(intervalRow.absAmplitudeDiff)}; екстремуми ${intervalRow.startGlobalIndex}..${intervalRow.endGlobalIndex}`;
      amplitudeSequence.appendChild(segment);
    });

    stack.appendChild(sequence);
    stack.appendChild(amplitudeSequence);
    sequenceWrap.appendChild(stack);

    const value = document.createElement("div");
    value.className = "interval-timeline-value";
    value.textContent = `${row.rows.length} раз`;

    item.appendChild(label);
    item.appendChild(sequenceWrap);
    item.appendChild(value);
    list.appendChild(item);
  });

  const note = document.createElement("div");
  note.className = "interval-scale-note";
  note.textContent = "Верхній ряд: T у шкалі між сусідніми горизонтальними лініями графіка. Нижній помаранчевий ряд: ширина кожного відрізка дорівнює піксельній висоті відповідного помаранчевого стема на основному графіку.";

  wrapper.appendChild(list);
  wrapper.appendChild(note);
  return wrapper;
}

function createChartCard({ title, meta, series, xLabel, yLabel, note, extraXValues }) {
  const card = document.createElement("section");
  card.className = "panel chart-card";

  const h2 = document.createElement("h2");
  h2.textContent = title;
  card.appendChild(h2);

  const metaNode = document.createElement("div");
  metaNode.className = "chart-meta";
  metaNode.textContent = meta;
  card.appendChild(metaNode);

  if (!series.some((item) => item.points.length)) {
    const empty = document.createElement("div");
    empty.className = "no-data";
    empty.textContent = note || "Недостатньо даних для цього графіка.";
    card.appendChild(empty);
    return card;
  }

  const wrap = document.createElement("div");
  wrap.className = "chart-wrap";

  const svg = createSvgEl("svg", {
    viewBox: "0 0 1120 430",
    preserveAspectRatio: "none",
    class: "chart-svg",
    "aria-label": title,
  });
  const chartScale = drawChart(svg, series, xLabel, yLabel, { extraXValues });
  wrap.appendChild(svg);
  card.appendChild(wrap);
  card.appendChild(createLegend(series));
  card._chartScale = chartScale;
  card._chartSvg = svg;

  if (note) {
    const noteNode = document.createElement("div");
    noteNode.className = "chart-note";
    noteNode.textContent = note;
    card.appendChild(noteNode);
  }

  return card;
}

function addLegendItem(legend, color, labelText) {
  const entry = document.createElement("div");
  entry.className = "legend-item";

  const swatch = document.createElement("span");
  swatch.className = "legend-swatch";
  swatch.style.background = color;

  const label = document.createElement("span");
  label.textContent = labelText;

  entry.appendChild(swatch);
  entry.appendChild(label);
  legend.appendChild(entry);
}

function computeAggregateOrangeRows(kCards, aggregateGroups) {
  const grouped = new Map();

  kCards.forEach(({ analysis, card }) => {
    if (!card || !card._chartScale) {
      return;
    }
    const amplitudeUnitViewBox = card._chartScale.yUnitViewBox;
    analysis.intervals.forEach((row) => {
      const duration = Number(row.duration);
      const pixelLength = Number(row.absAmplitudeDiff) * amplitudeUnitViewBox;
      if (!grouped.has(duration)) {
        grouped.set(duration, []);
      }
      grouped.get(duration).push(pixelLength);
    });
  });

  return [...grouped.entries()]
    .sort((left, right) => left[0] - right[0])
    .map(([duration, lengths]) => {
      const avgPixelLengthHalf = lengths.reduce((sum, value) => sum + value, 0) / lengths.length / 2;
      let matchingGroup = aggregateGroups.find((group) => duration >= group.minDuration && duration <= group.maxDuration);
      if (!matchingGroup && aggregateGroups.length) {
        matchingGroup = aggregateGroups.reduce((best, group) => {
          if (!best) {
            return group;
          }
          return Math.abs(group.avgDuration - duration) < Math.abs(best.avgDuration - duration) ? group : best;
        }, null);
      }
      const backendValue = matchingGroup ? Number(matchingGroup.avgAmplitude) : null;
      const ratio = backendValue !== null && avgPixelLengthHalf !== 0 ? backendValue / avgPixelLengthHalf : null;
      return {
        duration,
        avgPixelLengthHalf,
        count: lengths.length,
        backendValue,
        ratio,
      };
    });
}

function addAggregateOrangeOverlay(card, orangeRows) {
  if (!card || !card._chartSvg || !card._chartScale || !orangeRows.length) {
    return;
  }

  const existing = card._chartSvg.querySelector('g[data-overlay="aggregate-orange"]');
  if (existing) {
    existing.remove();
  }

  const scale = card._chartScale;
  const overlay = createSvgEl("g", { "data-overlay": "aggregate-orange" });
  const sx = (value) => scale.plotLeftViewBox + ((value - scale.xMin) / (scale.xMax - scale.xMin)) * scale.plotWidthViewBox;

  orangeRows.forEach((row) => {
    const x = sx(row.duration) + 5;
    overlay.appendChild(
      createSvgEl("line", {
        x1: x,
        y1: scale.plotBottomViewBox,
        x2: x,
        y2: scale.plotBottomViewBox - row.avgPixelLengthHalf,
        stroke: colors.signChangeAmplitudeDiff,
        "stroke-width": 3,
        "stroke-linecap": "round",
      }),
    );
    const text = createSvgEl("text", {
      x,
      y: scale.plotBottomViewBox + 30,
      fill: colors.signChangeAmplitudeDiff,
      "font-size": 11,
      "font-weight": 600,
      "text-anchor": "middle",
    });
    text.textContent = formatNumber(row.avgPixelLengthHalf);
    overlay.appendChild(text);

    if (row.ratio !== null && Number.isFinite(row.ratio)) {
      const ratioText = createSvgEl("text", {
        x,
        y: scale.plotBottomViewBox + 44,
        fill: colors.aggregateRatio,
        "font-size": 10,
        "font-weight": 600,
        "text-anchor": "middle",
      });
      ratioText.textContent = formatNumber(row.ratio);
      overlay.appendChild(ratioText);
    }
  });

  card._chartSvg.appendChild(overlay);

  const legend = card.querySelector(".legend");
  if (legend && !legend.querySelector('[data-extra-legend="aggregate-orange"]')) {
    const marker = document.createElement("div");
    marker.dataset.extraLegend = "aggregate-orange";
    marker.style.display = "contents";
    legend.appendChild(marker);
    addLegendItem(legend, colors.signChangeAmplitudeDiff, "Середня помаранчева довжина / 2");
  }
}

function addAggregatePurpleXOverlay(card, groups) {
  if (!card || !card._chartSvg || !card._chartScale || !groups.length) {
    return;
  }

  const existing = card._chartSvg.querySelector('g[data-overlay="aggregate-purple-x"]');
  if (existing) {
    existing.remove();
  }

  const scale = card._chartScale;
  const overlay = createSvgEl("g", { "data-overlay": "aggregate-purple-x" });
  const sx = (value) => scale.plotLeftViewBox + ((value - scale.xMin) / (scale.xMax - scale.xMin)) * scale.plotWidthViewBox;

  groups.forEach((group) => {
    const x = sx(group.avgDuration);
    const text = createSvgEl("text", {
      x,
      y: scale.plotBottomViewBox + 16,
      fill: colors.aggregate,
      "font-size": 11,
      "font-weight": 600,
      "text-anchor": "middle",
    });
    text.textContent = formatNumber(group.avgDuration);
    overlay.appendChild(text);
  });

  card._chartSvg.appendChild(overlay);
}

function syncIntervalTimelineScale(card) {
  if (!card || !card._chartScale || !card._chartSvg) {
    return;
  }

  const panel = card.querySelector(".interval-panel");
  if (!panel) {
    return;
  }

  const svgRect = card._chartSvg.getBoundingClientRect();
  if (!svgRect.width || !svgRect.height) {
    return;
  }

  const unitPx = svgRect.height * (card._chartScale.yGridUnitViewBox / card._chartScale.viewBoxHeight);
  const amplitudeUnitPx = svgRect.height * (card._chartScale.yUnitViewBox / card._chartScale.viewBoxHeight);

  panel.querySelectorAll(".interval-segment").forEach((segment) => {
    const duration = Number(segment.dataset.duration || "0");
    segment.style.width = `${duration * unitPx}px`;
  });

  panel.querySelectorAll(".amplitude-segment").forEach((segment) => {
    const amplitude = Number(segment.dataset.amplitude || "0");
    segment.style.width = `${Math.max(0, amplitude * amplitudeUnitPx)}px`;
  });
}

function syncAllIntervalTimelines() {
  dom.charts.querySelectorAll(".chart-card").forEach((card) => {
    syncIntervalTimelineScale(card);
  });
}

function renderExtremaCard(result) {
  const extrema = result.extrema;
  const series = [
    {
      name: "Амплітуди екстремумів",
      color: colors.extrema,
      points: extrema.map((row) => ({ x: row.localIndex, y: row.value })),
    },
    {
      name: "Максимуми",
      color: colors.maxima,
      type: "points",
      radius: 4.2,
      points: extrema
        .filter((row) => row.kind === "max")
        .map((row) => ({ x: row.localIndex, y: row.value })),
    },
    {
      name: "Мінімуми",
      color: colors.minima,
      type: "points",
      radius: 4.2,
      points: extrema
        .filter((row) => row.kind === "min")
        .map((row) => ({ x: row.localIndex, y: row.value })),
    },
  ];

  return createChartCard({
    title: "Екстремуми у вибраному фреймі",
    meta: `Знайдено ${extrema.length} екстремумів.`,
    series,
    xLabel: "Номер спостереження у фреймі",
    yLabel: "Амплітуда",
    note: extrema.length
      ? "Перший графік показує лише екстремуми у вибраному фреймі."
      : "У цьому фреймі локальних екстремумів не знайдено.",
  });
}

function renderKCard(analysis, extrema, mode) {
  const signChangeDisplayKeys = new Set(
    analysis.signChanges.map((row) => row.displayKey || String(row.extremumOrdinal)),
  );
  const displayExtrema = analysis.displayExtrema || extrema;
  const isArticle = mode === "article";

  const series = [
    {
      name: "Підписана різниця",
      color: colors.signedDiff,
      type: "stem",
      points: analysis.diffRows.map((row) => ({ x: row.endLocalIndex, y: row.signedDiff })),
    },
    {
      name: "Амплітуда екстремума",
      color: colors.amplitude,
      type: "stem",
      points: displayExtrema.map((row) => ({
        x: row.localIndex,
        y: row.value,
        label: row.displayLabel || row.ordinal,
        labelColor: signChangeDisplayKeys.has(row.displayKey || String(row.ordinal)) ? colors.signedDiff : colors.amplitude,
      })),
    },
    {
      name: "Модуль різниці",
      color: colors.absDiff,
      type: "stem",
      points: analysis.diffRows.map((row) => ({ x: row.endLocalIndex, y: row.absDiff })),
    },
    {
      name: "Модуль різниці між вибраними екстремумами",
      color: colors.signChangeAmplitudeDiff,
      type: "stem",
      points: analysis.signChangeDiffRows.map((row) => ({
        x: row.endLocalIndex,
        y: row.absAmplitudeDiff,
      })),
    },
  ];

  const card = createChartCard({
    title: isArticle ? `Графік для рівня k = ${analysis.k}` : `Графік для k = ${analysis.k}`,
    meta: `Крок 2^k = ${analysis.step}. Внутрішніх різниць: ${analysis.diffRows.length}. Змін знака: ${analysis.signChanges.length}. Різниць між вибраними екстремумами: ${analysis.signChangeDiffRows.length}. Інтервалів: ${analysis.intervals.length}.`,
    series,
    xLabel: "Номер спостереження екстремума",
    yLabel: "Амплітуда / різниця амплітуд",
    note: isArticle
      ? (
        analysis.intervals.length
          ? "Статейна версія: сині лінії показують екстремуми поточного рівня, червоні та зелені — signed/abs різниці між сусідніми екстремумами цього рівня, а рівні k будуються рекурсивним прорідженням масиву."
          : "Для цього рівня у статейній версії більше не вистачає екстремумів."
      )
      : (
        analysis.signChanges.length
          ? "Патентна версія: сині лінії показують амплітуди всіх екстремумів, червоні й зелені лишаються початковими різницями A[j] - A[j-2^k], а помаранчеві показують модулі різниць між сусідніми вибраними екстремумами в межах відповідної підпослідовності для цього k."
          : "Для цього k у вибраному фреймі не вистачає екстремумів."
      ),
  });

  card.appendChild(createIntervalTimeline(analysis.intervals));
  return card;
}

function renderAggregateCard(result, aggregateOrangeRows) {
  const groups = result.aggregateGroups;
  const series = [
    {
      name: "Усереднені амплітуди",
      color: colors.aggregate,
      type: "stem",
      points: groups.map((row) => ({
        x: row.avgDuration,
        y: row.avgAmplitude,
        label: formatNumber(row.avgAmplitude),
        labelColor: colors.aggregate,
        labelFontSize: 11,
      })),
    },
  ];

  return createChartCard({
    title: "Підсумковий графік за всіма k",
    meta: `Побудовано ${groups.length} груп часових інтервалів.`,
    series,
    extraXValues: aggregateOrangeRows.map((row) => row.duration),
    xLabel: "T, середня довжина групи інтервалів",
    yLabel: "Усереднений модуль різниці амплітуд",
    note: groups.length
      ? "Фіолетові лінії показують групований результат з tolerance-логікою. Помаранчеві лінії поруч ставляться в точних T = 1, 2, 3... і дорівнюють середній піксельній довжині помаранчевих ліній з усіх графіків k, поділеній на 2."
      : "Недостатньо подій зміни знака, щоб побудувати фінальний графік.",
  });
}

function renderSpectrumCard(result) {
  const groups = result.spectrumGroups || result.aggregateGroups || [];
  const isArticle = result.mode === "article";
  const series = [
    {
      name: "Спектральні складові",
      color: colors.aggregate,
      type: "stem",
      points: groups.map((row) => ({
        x: row.avgFrequency,
        y: row.avgAmplitude,
        label: formatNumber(row.avgAmplitude),
        labelColor: colors.aggregate,
        labelFontSize: 11,
      })),
    },
  ];

  return createChartCard({
    title: "Підсумковий спектр",
    meta: `Побудовано ${groups.length} спектральних груп.`,
    series,
    xLabel: "f = 1 / (2T)",
    yLabel: "Усереднений модуль різниці амплітуд",
    note: groups.length
      ? (
        isArticle
          ? "Статейна версія: фінальний спектр будується по рівнях рекурсивного прорідження. Сирі інтервали лишаються у технічних графіках, а у спектрі вони зводяться в одну складову на рівень."
          : "Цей графік показує ті самі групи, але вже у частотній області за формулою f = 1 / (2T)."
      )
      : "Недостатньо подій зміни знака, щоб побудувати спектр.",
  });
}

function renderCharts(result) {
  dom.charts.innerHTML = "";
  const extremaCard = renderExtremaCard(result);
  dom.charts.appendChild(extremaCard);
  const kCards = [];

  if (result.kAnalyses.length) {
    result.kAnalyses.forEach((analysis) => {
      const card = renderKCard(analysis, result.extrema, result.mode);
      dom.charts.appendChild(card);
      syncIntervalTimelineScale(card);
      kCards.push({ analysis, card });
    });
  } else {
    const card = document.createElement("section");
    card.className = "panel chart-card";
    card.innerHTML = `
      <h2>Графіки для k поки недоступні</h2>
      <div class="no-data">У вибраному фреймі замало екстремумів, щоб перейти до рядів різниць амплітуд.</div>
    `;
    dom.charts.appendChild(card);
  }

  const aggregateOrangeRows = computeAggregateOrangeRows(kCards, result.aggregateGroups);
  const aggregateCard = renderAggregateCard(result, aggregateOrangeRows);
  dom.charts.appendChild(aggregateCard);
  addAggregatePurpleXOverlay(aggregateCard, result.aggregateGroups);
  addAggregateOrangeOverlay(aggregateCard, aggregateOrangeRows);

  const spectrumCard = renderSpectrumCard(result);
  dom.charts.appendChild(spectrumCard);
}

async function submitAnalysis(event) {
  event.preventDefault();

  if (!dom.fileInput.files.length) {
    setStatus("Спочатку вибери текстовий файл.", "error");
    return;
  }

  const formData = new FormData(dom.form);
  setBusy(true);
  setStatus("Сервер аналізує фрейм і будує графіки...", "neutral");

  try {
    const response = await fetch(dom.body.dataset.apiAnalyzePath, {
      method: "POST",
      body: formData,
    });

    const payload = await response.json();
    if (!response.ok) {
      throw new Error(payload.error || "Сервер не зміг виконати аналіз.");
    }

    state.analysis = payload;
    dom.jsonPreview.textContent = JSON.stringify(payload, null, 2);
    updateDownload(payload);
    renderSummary(payload);
    renderCharts(payload);

    const frameInfo = payload.frameInfo;
    const rangeText = `${frameInfo.selectedGlobalStart}..${frameInfo.selectedGlobalEnd}`;
    setStatus(
      `Аналіз завершено. Обраний діапазон ${rangeText}, екстремумів: ${payload.extrema.length}, максимальний k: ${payload.effectiveMaxK >= 0 ? payload.effectiveMaxK : "н/д"}.`,
      "ok",
    );
  } catch (error) {
    state.analysis = null;
    clearDownloadUrl();
    dom.downloadJson.disabled = true;
    dom.summary.className = "summary empty";
    dom.summary.textContent = "Поки що немає результату.";
    dom.jsonPreview.textContent = "{}";
    dom.charts.innerHTML = `
      <section class="panel empty-panel">
        <h2>Аналіз не побудовано</h2>
        <p>${error.message}</p>
      </section>
    `;
    setStatus(error.message, "error");
  } finally {
    setBusy(false);
  }
}

function downloadJson() {
  if (!state.analysis || !state.downloadUrl) {
    return;
  }

  const base = (state.analysis.filename || "analysis")
    .replace(/\.[^.]+$/, "")
    .replace(/[^a-zA-Z0-9_-]+/g, "_");

  const anchor = document.createElement("a");
  anchor.href = state.downloadUrl;
  anchor.download = `${base}_frame_analysis.json`;
  document.body.appendChild(anchor);
  anchor.click();
  anchor.remove();
}

dom.form.addEventListener("submit", submitAnalysis);
dom.downloadJson.addEventListener("click", downloadJson);
window.addEventListener("resize", syncAllIntervalTimelines);
window.addEventListener("beforeunload", clearDownloadUrl);
