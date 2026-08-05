"use strict";

/* ===== BRAND PALETTE ===== */
const BRAND = {
  orange:  "#E67E22",
  orangeD: "#D35400",
  green:   "#22C55E",
  greenD:  "#16A34A",
  red:     "#EF4444",
  redD:    "#DC2626",
  amber:   "#F59E0B",
  blue:    "#3B82F6",
  purple:  "#8B5CF6",
  cyan:    "#06B6D4",
  muted:   "#64748B",
  grid:    "#F1F5F9",
};

const CHART_COLORS = [
  BRAND.orange, BRAND.blue, BRAND.green, BRAND.purple,
  BRAND.cyan, BRAND.amber, BRAND.red, "#A855F7",
];

document.addEventListener("DOMContentLoaded", function () {
  // Bootstrap tooltips
  document.querySelectorAll('[data-bs-toggle="tooltip"]').forEach(
    el => new bootstrap.Tooltip(el, { trigger: "hover" })
  );

  // Sidebar toggle
  const sidebar = document.getElementById("sidebar");
  const mainWrapper = document.getElementById("mainWrapper");
  const sidebarToggle = document.getElementById("sidebarToggle");

  if (sidebarToggle && sidebar) {
    sidebarToggle.addEventListener("click", function () {
      if (window.innerWidth <= 768) {
        sidebar.classList.toggle("open");
      } else {
        sidebar.classList.toggle("collapsed");
        mainWrapper && mainWrapper.classList.toggle("sidebar-collapsed");
      }
    });

    document.addEventListener("click", function (e) {
      if (window.innerWidth <= 768 &&
          sidebar.classList.contains("open") &&
          !sidebar.contains(e.target) &&
          !sidebarToggle.contains(e.target)) {
        sidebar.classList.remove("open");
      }
    });
  }

  // Clickable table rows
  document.querySelectorAll(".clickable-row").forEach(row => {
    row.addEventListener("click", () => {
      if (row.dataset.href) window.location.href = row.dataset.href;
    });
    row.style.cursor = "pointer";
  });

  // Password visibility toggles
  document.querySelectorAll('.toggle-password-btn').forEach(button => {
    button.addEventListener('click', () => {
      const targetId = button.getAttribute('data-target');
      const targetInput = document.getElementById(targetId);
      if (!targetInput) return;
      const isPassword = targetInput.type === 'password';
      targetInput.type = isPassword ? 'text' : 'password';
      button.querySelector('i').className = isPassword ? 'bi bi-eye-slash' : 'bi bi-eye';
    });
  });

  // Toggle forgot password panel
  const showForgot = document.getElementById('showForgotPassword');
  const cancelForgot = document.getElementById('cancelForgotPassword');
  const forgotPanel = document.getElementById('forgotPasswordPanel');
  if (showForgot && forgotPanel) {
    showForgot.addEventListener('click', event => {
      event.preventDefault();
      forgotPanel.classList.remove('d-none');
      forgotPanel.classList.add('auth-forgot-open');
    });
  }
  if (cancelForgot && forgotPanel) {
    cancelForgot.addEventListener('click', () => {
      forgotPanel.classList.add('d-none');
      forgotPanel.classList.remove('auth-forgot-open');
    });
  }

  // Auto-dismiss success alerts (5 s)
  document.querySelectorAll(".alert.alert-success").forEach(el => {
    setTimeout(() => {
      const bsAlert = bootstrap.Alert.getOrCreateInstance(el);
      bsAlert && bsAlert.close();
    }, 5000);
  });

  // Toast from flash (renders server-side toasts if any)
  document.querySelectorAll(".ccmp-toast").forEach(el => {
    const toast = bootstrap.Toast.getOrCreateInstance(el, { delay: 4500 });
    toast.show();
  });
});

/* ===== TOAST API ===== */
function showToast(message, type = "success") {
  const id = "toast_" + Date.now();
  const iconMap = {
    success: "check-circle-fill",
    danger:  "exclamation-circle-fill",
    warning: "exclamation-triangle-fill",
    info:    "info-circle-fill",
  };
  const colorMap = {
    success: BRAND.green,
    danger:  BRAND.red,
    warning: BRAND.amber,
    info:    BRAND.blue,
  };
  const html = `
    <div id="${id}" class="toast align-items-center border-0 ccmp-toast-item" role="alert" style="
      background:#fff; box-shadow:0 8px 24px rgba(0,0,0,0.12);
      border-radius:10px; min-width:300px; border-left:4px solid ${colorMap[type] || BRAND.green} !important;
    ">
      <div class="d-flex align-items-center gap-2 px-3 py-2">
        <i class="bi bi-${iconMap[type] || 'check-circle-fill'}" style="color:${colorMap[type]};font-size:1.1rem;"></i>
        <div class="flex-grow-1" style="font-size:0.85rem;font-weight:500;color:#1E293B;">${message}</div>
        <button type="button" class="btn-close btn-close-sm ms-1" data-bs-dismiss="toast"></button>
      </div>
    </div>`;
  let container = document.getElementById("ccmpToastContainer");
  if (!container) {
    container = document.createElement("div");
    container.id = "ccmpToastContainer";
    container.style.cssText = "position:fixed;bottom:24px;right:24px;z-index:9999;display:flex;flex-direction:column;gap:8px;";
    document.body.appendChild(container);
  }
  container.insertAdjacentHTML("beforeend", html);
  const el = document.getElementById(id);
  const toast = new bootstrap.Toast(el, { delay: 4500 });
  toast.show();
  el.addEventListener("hidden.bs.toast", () => el.remove());
}

/* ===== CHART HELPERS ===== */

const CHART_DEFAULTS = {
  font: { family: "'Inter', 'Segoe UI', system-ui, sans-serif", size: 11 },
  color: BRAND.muted,
};

function buildDonutChart(canvasId, labels, data, colors) {
  const ctx = document.getElementById(canvasId);
  if (!ctx) return;
  colors = colors || CHART_COLORS;
  return new Chart(ctx, {
    type: "doughnut",
    data: {
      labels,
      datasets: [{
        data,
        backgroundColor: colors,
        borderWidth: 2,
        borderColor: "#fff",
        hoverBorderWidth: 3,
        hoverOffset: 4,
      }]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      cutout: "68%",
      plugins: {
        legend: {
          position: "bottom",
          labels: {
            font: { size: 11, family: CHART_DEFAULTS.font.family },
            padding: 12,
            boxWidth: 10, boxHeight: 10,
            color: BRAND.muted,
          }
        },
        tooltip: {
          backgroundColor: "#1E293B",
          titleColor: "#fff",
          bodyColor: "#CBD5E1",
          cornerRadius: 8,
          padding: 10,
        }
      }
    }
  });
}

function buildBarChart(canvasId, labels, data, color) {
  const ctx = document.getElementById(canvasId);
  if (!ctx) return;
  color = color || BRAND.orange;
  return new Chart(ctx, {
    type: "bar",
    data: {
      labels,
      datasets: [{
        data,
        backgroundColor: color,
        hoverBackgroundColor: BRAND.orangeD,
        borderRadius: 6,
        borderSkipped: false,
      }]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: { display: false },
        tooltip: {
          backgroundColor: "#1E293B",
          titleColor: "#fff",
          bodyColor: "#CBD5E1",
          cornerRadius: 8,
          padding: 10,
        }
      },
      scales: {
        y: {
          beginAtZero: true,
          ticks: { stepSize: 1, font: { size: 11 }, color: "#94A3B8" },
          grid: { color: BRAND.grid },
          border: { display: false },
        },
        x: {
          ticks: { font: { size: 10 }, color: "#94A3B8", maxRotation: 30 },
          grid: { display: false },
          border: { display: false },
        }
      }
    }
  });
}

function buildTrendChart(canvasId, labels, grantedData, withdrawnData) {
  const ctx = document.getElementById(canvasId);
  if (!ctx) return;
  return new Chart(ctx, {
    type: "line",
    data: {
      labels,
      datasets: [
        {
          label: "Consents Granted",
          data: grantedData,
          borderColor: BRAND.green,
          backgroundColor: "rgba(34,197,94,0.08)",
          fill: true,
          tension: 0.4,
          pointRadius: 4,
          pointBackgroundColor: BRAND.green,
          pointBorderColor: "#fff",
          pointBorderWidth: 2,
          borderWidth: 2.5,
        },
        {
          label: "Consents Withdrawn",
          data: withdrawnData,
          borderColor: BRAND.red,
          backgroundColor: "rgba(239,68,68,0.06)",
          fill: true,
          tension: 0.4,
          pointRadius: 4,
          pointBackgroundColor: BRAND.red,
          pointBorderColor: "#fff",
          pointBorderWidth: 2,
          borderWidth: 2.5,
        }
      ]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: {
          position: "top",
          labels: {
            font: { size: 11, family: CHART_DEFAULTS.font.family },
            boxWidth: 12, boxHeight: 12,
            color: BRAND.muted,
            padding: 16,
          }
        },
        tooltip: {
          backgroundColor: "#1E293B",
          titleColor: "#fff",
          bodyColor: "#CBD5E1",
          cornerRadius: 8,
          padding: 10,
          mode: "index",
          intersect: false,
        }
      },
      scales: {
        y: {
          beginAtZero: true,
          ticks: { stepSize: 1, font: { size: 11 }, color: "#94A3B8" },
          grid: { color: BRAND.grid },
          border: { display: false },
        },
        x: {
          ticks: { font: { size: 11 }, color: "#94A3B8" },
          grid: { display: false },
          border: { display: false },
        }
      }
    }
  });
}
