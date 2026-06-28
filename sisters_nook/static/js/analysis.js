(() => {
  const palette = {
    primary: "#5a3721",
    primaryLight: "#8b6344",
    container: "#d9b89a",
    tertiary: "#7d7a4d",
    surface: "#fbf7f2",
    muted: "#62564d",
    grid: "#e7ddd3",
  };

  let salesChart = null;

  function readChartData() {
    const node = document.getElementById("analysis-chart-data");
    if (!node) return null;
    try {
      return JSON.parse(node.textContent || "{}");
    } catch {
      return null;
    }
  }

  function currencyTick(value) {
    return `NRs ${Number(value).toLocaleString(undefined, { minimumFractionDigits: 0, maximumFractionDigits: 0 })}`;
  }

  function seriesHasData(series) {
    if (!series || !series.labels || !series.labels.length) return false;
    return series.salesAmounts.some((value) => Number(value) > 0) || series.orderCounts.some((value) => Number(value) > 0);
  }

  function getSeries(chartData, view, trendGranularity) {
    const charts = chartData.salesCharts || {};
    if (view === "hourly") return charts.hourly;
    if (view === "weekday") return charts.weekday;
    return charts.trend?.[trendGranularity] || charts.trend?.daily;
  }

  function getSeriesMeta(view, trendGranularity) {
    if (view === "hourly") {
      return {
        title: "Sales by hour",
        subtitle: "24-hour view with order bars and sales line",
      };
    }
    if (view === "weekday") {
      return {
        title: "Sales by day of week",
        subtitle: "Totals grouped Monday through Sunday",
      };
    }
    const labels = {
      daily: "Daily sales trend",
      weekly: "Weekly sales trend",
      monthly: "Monthly sales trend",
    };
    const subtitles = {
      daily: "One point per day in the selected range",
      weekly: "Grouped by calendar week",
      monthly: "Grouped by calendar month",
    };
    return {
      title: labels[trendGranularity] || labels.daily,
      subtitle: subtitles[trendGranularity] || subtitles.daily,
    };
  }

  function setActiveButtons(view, trendGranularity) {
    document.querySelectorAll("[data-chart-view]").forEach((button) => {
      button.classList.toggle("active", button.dataset.chartView === view);
    });
    document.querySelectorAll("[data-trend-granularity]").forEach((button) => {
      button.classList.toggle("active", button.dataset.trendGranularity === trendGranularity);
    });
    const trendTabs = document.getElementById("trendGranularityTabs");
    if (trendTabs) {
      trendTabs.hidden = view !== "trend";
    }
  }

  function updateChartCaption(view, trendGranularity) {
    const meta = getSeriesMeta(view, trendGranularity);
    const title = document.getElementById("salesChartTitle");
    const subtitle = document.getElementById("salesChartSubtitle");
    if (title) title.textContent = meta.title;
    if (subtitle) subtitle.textContent = meta.subtitle;
  }

  function renderSalesChart(chartData, view, trendGranularity) {
    const canvas = document.getElementById("salesOverTimeChart");
    if (!canvas || typeof Chart === "undefined") return;

    const series = getSeries(chartData, view, trendGranularity);
    const hasData = seriesHasData(series);

    if (salesChart) {
      salesChart.destroy();
      salesChart = null;
    }

    if (!hasData) {
      updateChartCaption(view, trendGranularity);
      setActiveButtons(view, trendGranularity);
      return;
    }

    salesChart = new Chart(canvas, {
      type: "bar",
      data: {
        labels: series.labels,
        datasets: [
          {
            type: "bar",
            label: "Orders",
            data: series.orderCounts,
            yAxisID: "yOrders",
            backgroundColor: "rgba(217, 184, 154, 0.85)",
            borderColor: palette.container,
            borderWidth: 1,
            borderRadius: 8,
            order: 2,
          },
          {
            type: "line",
            label: "Sales (NRs)",
            data: series.salesAmounts,
            yAxisID: "ySales",
            borderColor: palette.primary,
            backgroundColor: "rgba(90, 55, 33, 0.12)",
            borderWidth: 2.5,
            pointRadius: view === "trend" ? 3 : 4,
            pointBackgroundColor: palette.primary,
            pointBorderColor: palette.surface,
            pointBorderWidth: 2,
            tension: 0.35,
            fill: true,
            order: 1,
          },
        ],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        interaction: { mode: "index", intersect: false },
        plugins: {
          legend: {
            position: "top",
            align: "end",
            labels: {
              color: palette.muted,
              boxWidth: 12,
              boxHeight: 12,
              usePointStyle: true,
            },
          },
          tooltip: {
            callbacks: {
              label(context) {
                if (context.dataset.label === "Sales (NRs)") {
                  return ` Sales: NRs ${Number(context.parsed.y).toFixed(2)}`;
                }
                return ` Orders: ${context.parsed.y}`;
              },
            },
          },
        },
        scales: {
          x: {
            grid: { color: palette.grid },
            ticks: {
              color: palette.muted,
              maxRotation: view === "trend" && trendGranularity === "daily" ? 45 : 0,
              minRotation: 0,
            },
          },
          ySales: {
            type: "linear",
            position: "left",
            grid: { color: palette.grid },
            ticks: {
              color: palette.muted,
              callback: (value) => currencyTick(value),
            },
          },
          yOrders: {
            type: "linear",
            position: "right",
            beginAtZero: true,
            grid: { drawOnChartArea: false },
            ticks: {
              color: palette.muted,
              stepSize: 1,
              precision: 0,
            },
          },
        },
      },
    });

    updateChartCaption(view, trendGranularity);
    setActiveButtons(view, trendGranularity);
  }

  function initPaymentDonut(data) {
    const canvas = document.getElementById("paymentMethodChart");
    if (!canvas || typeof Chart === "undefined") return;

    const labels = data.paymentLabels || [];
    const amounts = data.paymentAmounts || [];
    const colors = data.colors || [palette.primary, palette.primaryLight, palette.container, palette.tertiary];

    new Chart(canvas, {
      type: "doughnut",
      data: {
        labels,
        datasets: [
          {
            data: amounts.length ? amounts : [1],
            backgroundColor: amounts.length ? colors : [palette.grid],
            borderColor: palette.surface,
            borderWidth: 3,
            hoverOffset: 6,
          },
        ],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        cutout: "62%",
        plugins: {
          legend: { display: false },
          tooltip: {
            callbacks: {
              label(context) {
                const total = amounts.reduce((sum, val) => sum + val, 0);
                const pct = total > 0 ? ((context.parsed / total) * 100).toFixed(1) : "0.0";
                return ` ${context.label}: NRs ${Number(context.parsed).toFixed(2)} (${pct}%)`;
              },
            },
          },
        },
      },
    });
  }

  document.addEventListener("DOMContentLoaded", () => {
    const dateRange = document.getElementById("analysisDateRange");
    const customDates = document.getElementById("analysisCustomDates");
    if (dateRange && customDates) {
      dateRange.addEventListener("change", () => {
        customDates.hidden = dateRange.value !== "custom";
      });
    }

    const chartData = readChartData();
    if (!chartData) return;

    let currentView = chartData.defaultView || "hourly";
    let currentTrend = chartData.defaultTrend || "daily";

    renderSalesChart(chartData, currentView, currentTrend);
    initPaymentDonut(chartData);

    document.querySelectorAll("[data-chart-view]").forEach((button) => {
      button.addEventListener("click", () => {
        currentView = button.dataset.chartView;
        renderSalesChart(chartData, currentView, currentTrend);
      });
    });

    document.querySelectorAll("[data-trend-granularity]").forEach((button) => {
      button.addEventListener("click", () => {
        currentTrend = button.dataset.trendGranularity;
        currentView = "trend";
        renderSalesChart(chartData, currentView, currentTrend);
      });
    });
  });
})();
