/**
 * Telemetry & FFT Charting Engine using Native Canvas for ultra-fast, dependency-light industrial rendering.
 */
class TelemetryChart {
  constructor(canvasId) {
    this.canvas = document.getElementById(canvasId);
    this.ctx = this.canvas ? this.canvas.getContext('2d') : null;
    this.data = [];
    this.labels = [];
    this.thresholdWarning = null;
    this.thresholdCritical = null;
  }

  setData(labels, data, unit = "mm/s", warnLimit = 4.5, critLimit = 7.1) {
    this.labels = labels;
    this.data = data;
    this.unit = unit;
    this.thresholdWarning = warnLimit;
    this.thresholdCritical = critLimit;
    this.render();
  }

  render() {
    if (!this.ctx || !this.canvas || this.data.length === 0) return;

    const ctx = this.ctx;
    const width = this.canvas.width = this.canvas.parentElement.clientWidth;
    const height = this.canvas.height = 240;

    ctx.clearRect(0, 0, width, height);

    const padLeft = 50;
    const padRight = 20;
    const padTop = 30;
    const padBottom = 30;

    const plotW = width - padLeft - padRight;
    const plotH = height - padTop - padBottom;

    const maxVal = Math.max(Math.max(...this.data) * 1.15, this.thresholdCritical ? this.thresholdCritical * 1.1 : 10.0);
    const minVal = 0;

    // Grid lines
    ctx.strokeStyle = '#1e293b';
    ctx.lineWidth = 1;
    for (let i = 0; i <= 4; i++) {
      const y = padTop + (plotH / 4) * i;
      ctx.beginPath();
      ctx.moveTo(padLeft, y);
      ctx.lineTo(width - padRight, y);
      ctx.stroke();

      const val = maxVal - (maxVal / 4) * i;
      ctx.fillStyle = '#64748b';
      ctx.font = '10px JetBrains Mono, monospace';
      ctx.textAlign = 'right';
      ctx.fillText(val.toFixed(1), padLeft - 8, y + 3);
    }

    // Critical Threshold Line
    if (this.thresholdCritical && this.thresholdCritical <= maxVal) {
      const critY = padTop + plotH * (1 - (this.thresholdCritical - minVal) / (maxVal - minVal));
      ctx.strokeStyle = '#ff3366';
      ctx.setLineDash([4, 4]);
      ctx.lineWidth = 1.5;
      ctx.beginPath();
      ctx.moveTo(padLeft, critY);
      ctx.lineTo(width - padRight, critY);
      ctx.stroke();
      ctx.fillStyle = '#ff3366';
      ctx.fillText(`CRIT: ${this.thresholdCritical} ${this.unit}`, width - padRight - 5, critY - 5);
      ctx.setLineDash([]);
    }

    // Warning Threshold Line
    if (this.thresholdWarning && this.thresholdWarning <= maxVal) {
      const warnY = padTop + plotH * (1 - (this.thresholdWarning - minVal) / (maxVal - minVal));
      ctx.strokeStyle = '#f59e0b';
      ctx.setLineDash([4, 4]);
      ctx.lineWidth = 1.5;
      ctx.beginPath();
      ctx.moveTo(padLeft, warnY);
      ctx.lineTo(width - padRight, warnY);
      ctx.stroke();
      ctx.fillStyle = '#f59e0b';
      ctx.fillText(`WARN: ${this.thresholdWarning} ${this.unit}`, width - padRight - 5, warnY - 5);
      ctx.setLineDash([]);
    }

    // Telemetry Line & Gradient Area
    const stepX = plotW / (this.data.length - 1);
    ctx.beginPath();
    ctx.moveTo(padLeft, padTop + plotH * (1 - (this.data[0] - minVal) / (maxVal - minVal)));

    for (let i = 1; i < this.data.length; i++) {
      const x = padLeft + i * stepX;
      const y = padTop + plotH * (1 - (this.data[i] - minVal) / (maxVal - minVal));
      ctx.lineTo(x, y);
    }

    ctx.strokeStyle = '#06b6d4';
    ctx.lineWidth = 2.5;
    ctx.stroke();

    // Fill area under curve
    ctx.lineTo(padLeft + (this.data.length - 1) * stepX, padTop + plotH);
    ctx.lineTo(padLeft, padTop + plotH);
    ctx.closePath();
    const grad = ctx.createLinearGradient(0, padTop, 0, padTop + plotH);
    grad.addColorStop(0, 'rgba(6, 182, 212, 0.35)');
    grad.addColorStop(1, 'rgba(6, 182, 212, 0.0)');
    ctx.fillStyle = grad;
    ctx.fill();
  }
}

class FFTChart {
  constructor(canvasId) {
    this.canvas = document.getElementById(canvasId);
    this.ctx = this.canvas ? this.canvas.getContext('2d') : null;
  }

  setSpectrum(freqs, amps, bpfiMarker = 248.5) {
    if (!this.ctx || !this.canvas || freqs.length === 0) return;

    const ctx = this.ctx;
    const width = this.canvas.width = this.canvas.parentElement.clientWidth;
    const height = this.canvas.height = 200;

    ctx.clearRect(0, 0, width, height);

    const padLeft = 40;
    const padRight = 20;
    const padTop = 20;
    const padBottom = 25;

    const plotW = width - padLeft - padRight;
    const plotH = height - padTop - padBottom;

    const maxAmp = Math.max(...amps) * 1.2 || 1.0;
    const maxFreq = freqs[freqs.length - 1] || 2000;

    // Draw spectrum bars / lines
    ctx.strokeStyle = '#8b5cf6';
    ctx.lineWidth = 1.5;
    ctx.beginPath();

    for (let i = 0; i < freqs.length; i++) {
      const x = padLeft + (freqs[i] / maxFreq) * plotW;
      const y = padTop + plotH * (1 - amps[i] / maxAmp);
      if (i === 0) ctx.moveTo(x, y);
      else ctx.lineTo(x, y);
    }
    ctx.stroke();

    // BPFI Bearing Peak Marker Flag
    if (bpfiMarker && bpfiMarker <= maxFreq) {
      const markX = padLeft + (bpfiMarker / maxFreq) * plotW;
      ctx.strokeStyle = '#ff3366';
      ctx.lineWidth = 2;
      ctx.beginPath();
      ctx.moveTo(markX, padTop);
      ctx.lineTo(markX, padTop + plotH);
      ctx.stroke();

      ctx.fillStyle = '#ff3366';
      ctx.font = '10px JetBrains Mono, monospace';
      ctx.fillText(`▲ BPFI (${bpfiMarker} Hz)`, markX + 4, padTop + 14);
    }

    // X Axis label
    ctx.fillStyle = '#64748b';
    ctx.font = '10px Inter, sans-serif';
    ctx.textAlign = 'center';
    ctx.fillText('Frequency (Hz)', padLeft + plotW / 2, height - 5);
  }
}
