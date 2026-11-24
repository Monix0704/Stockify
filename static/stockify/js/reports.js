(() => {
  const source = document.getElementById("reports-chart-data");
  if (!source) return;

  const data = JSON.parse(source.textContent);
  const colors = { incoming: "#1b9b77", outgoing: "#e18a53", axis: "#8c9aac", grid: "#e9eef4", ink: "#40536c" };

  function prepareCanvas(canvas, height) {
    if (!canvas) return null;
    const ratio = window.devicePixelRatio || 1;
    const width = Math.max(canvas.clientWidth, 280);
    canvas.style.height = `${height}px`;
    canvas.width = Math.round(width * ratio);
    canvas.height = Math.round(height * ratio);
    const context = canvas.getContext("2d");
    context.scale(ratio, ratio);
    context.clearRect(0, 0, width, height);
    context.font = '10px "DM Sans", sans-serif';
    return { context, width, height };
  }

  function drawGroupedBars(canvas, series) {
    const chart = prepareCanvas(canvas, 255);
    if (!chart) return;
    const { context: ctx, width, height } = chart;
    const left = 36, right = 8, top = 14, bottom = 33;
    const plotWidth = width - left - right, plotHeight = height - top - bottom;
    const maxValue = Math.max(1, ...series.incoming, ...series.outgoing);
    const step = plotHeight / 4;
    ctx.strokeStyle = colors.grid;
    ctx.fillStyle = colors.axis;
    ctx.textAlign = "right";
    for (let tick = 0; tick <= 4; tick += 1) {
      const y = top + plotHeight - tick * step;
      ctx.beginPath(); ctx.moveTo(left, y); ctx.lineTo(width - right, y); ctx.stroke();
      ctx.fillText(String(Math.round(maxValue * tick / 4)), left - 8, y + 3);
    }
    const count = Math.max(series.labels.length, 1);
    const slotWidth = plotWidth / count;
    const barWidth = Math.min(12, Math.max(2, slotWidth * .29));
    series.labels.forEach((label, index) => {
      const center = left + slotWidth * (index + .5);
      const incomingHeight = (series.incoming[index] || 0) / maxValue * plotHeight;
      const outgoingHeight = (series.outgoing[index] || 0) / maxValue * plotHeight;
      ctx.fillStyle = colors.incoming;
      ctx.fillRect(center - barWidth - 1, top + plotHeight - incomingHeight, barWidth, incomingHeight);
      ctx.fillStyle = colors.outgoing;
      ctx.fillRect(center + 1, top + plotHeight - outgoingHeight, barWidth, outgoingHeight);
      const stride = Math.max(1, Math.ceil(count / 10));
      if (index % stride === 0 || index === count - 1) {
        ctx.fillStyle = colors.axis;
        ctx.textAlign = "center";
        ctx.fillText(label, center, height - 9);
      }
    });
    if (!series.incoming.some(Boolean) && !series.outgoing.some(Boolean)) {
      ctx.fillStyle = colors.axis; ctx.textAlign = "center";
      ctx.fillText("За этот период операций нет", width / 2, top + plotHeight / 2);
    }
  }

  function drawComparison(canvas, comparison) {
    const chart = prepareCanvas(canvas, 190);
    if (!chart) return;
    const { context: ctx, width, height } = chart;
    const left = 87, right = 20, top = 24, rowGap = 69;
    const maxValue = Math.max(1, ...comparison.values);
    comparison.labels.forEach((label, index) => {
      const y = top + index * rowGap;
      const barWidth = Math.max(0, (width - left - right) * comparison.values[index] / maxValue);
      ctx.fillStyle = colors.ink; ctx.textAlign = "left"; ctx.fillText(label, 2, y + 9);
      ctx.fillStyle = index === 0 ? colors.incoming : colors.outgoing;
      ctx.beginPath(); ctx.roundRect(left, y - 5, Math.max(barWidth, comparison.values[index] ? 4 : 0), 20, 5); ctx.fill();
      ctx.fillStyle = colors.axis; ctx.textAlign = "right";
      ctx.fillText(String(comparison.values[index]), width - 2, y + 9);
    });
    if (comparison.values.every((value) => value === 0)) {
      ctx.fillStyle = colors.axis; ctx.textAlign = "center";
      ctx.fillText("Нет операций за период", width / 2, height - 12);
    }
  }

  function drawWarehouseActivity(canvas, series) {
    if (!canvas) return;
    if (!series.labels.length) {
      const wrapper = canvas.parentElement;
      wrapper.innerHTML = '<div class="chart-empty">Склады ещё не созданы.</div>';
      return;
    }
    const height = Math.max(180, series.labels.length * 37 + 26);
    const chart = prepareCanvas(canvas, height);
    if (!chart) return;
    const { context: ctx, width } = chart;
    const labelWidth = Math.min(155, Math.max(88, width * .32));
    const right = 26, barArea = width - labelWidth - right;
    const maxValue = Math.max(1, ...series.values);
    series.labels.forEach((label, index) => {
      const y = 15 + index * 37;
      ctx.fillStyle = colors.ink; ctx.textAlign = "left";
      const clippedLabel = label.length > 22 ? `${label.slice(0, 20)}…` : label;
      ctx.fillText(clippedLabel, 0, y + 12);
      ctx.fillStyle = "#eff3f7";
      ctx.beginPath(); ctx.roundRect(labelWidth, y, barArea, 18, 5); ctx.fill();
      const valueWidth = barArea * series.values[index] / maxValue;
      if (valueWidth > 0) {
        ctx.fillStyle = "#7584d1";
        ctx.beginPath(); ctx.roundRect(labelWidth, y, Math.max(valueWidth, 5), 18, 5); ctx.fill();
      }
      ctx.fillStyle = colors.axis; ctx.textAlign = "right";
      ctx.fillText(String(series.values[index]), width - 1, y + 12);
    });
  }

  function render() {
    drawGroupedBars(document.getElementById("dailyChart"), data.daily);
    drawComparison(document.getElementById("comparisonChart"), data.comparison);
    drawWarehouseActivity(document.getElementById("warehouseChart"), data.warehouses);
  }

  render();
  let resizeTimer;
  window.addEventListener("resize", () => {
    window.clearTimeout(resizeTimer);
    resizeTimer = window.setTimeout(render, 120);
  });
})();
