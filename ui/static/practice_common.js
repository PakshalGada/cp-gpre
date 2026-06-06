document.addEventListener("DOMContentLoaded", () => {
  // ─── Navbar Shadow ───
  const navbar = document.getElementById("navbar");
  if (navbar) {
    window.addEventListener("scroll", () => {
      navbar.classList.toggle("scrolled", window.scrollY > 4);
    });
  }

  // ─── Theme Toggle ───
  const themeBtn = document.getElementById("theme-toggle");
  const savedTheme = localStorage.getItem("theme");
  if (savedTheme) {
    document.documentElement.setAttribute("data-theme", savedTheme);
  }

  if (themeBtn) {
    themeBtn.addEventListener("click", () => {
      const isDark = document.documentElement.getAttribute("data-theme") === "dark";
      const next = isDark ? "light" : "dark";
      document.documentElement.setAttribute("data-theme", next);
      localStorage.setItem("theme", next);

      // Trigger standard theme change event for libraries like Chart.js
      window.dispatchEvent(new Event("themechanged"));
    });
  }

  // ─── Hamburger / Mobile Drawer ───
  const hamburger = document.getElementById("hamburger-btn");
  const drawer = document.getElementById("mobile-drawer");
  const overlay = document.getElementById("sidebar-overlay");
  const closeBtn = document.getElementById("drawer-close-btn");

  function openDrawer() {
    if (drawer) drawer.classList.add("open");
    if (overlay) overlay.classList.add("active");
    document.body.style.overflow = "hidden";
  }

  function closeDrawer() {
    if (drawer) drawer.classList.remove("open");
    if (overlay) overlay.classList.remove("active");
    document.body.style.overflow = "";
  }

  if (hamburger) hamburger.addEventListener("click", openDrawer);
  if (closeBtn) closeBtn.addEventListener("click", closeDrawer);
  if (overlay) overlay.addEventListener("click", closeDrawer);

  const mobileNavLinks = document.querySelectorAll(".mobile-nav-link, .drawer-menu-link");
  mobileNavLinks.forEach((link) => {
    link.addEventListener("click", closeDrawer);
  });

  // ─── Global Handles Sync & Top-Left Display ───
  const cfInput = document.getElementById("cf-handle");
  const csesInput = document.getElementById("cses-user");
  const mobCfInput = document.getElementById("mobile-cf-handle");
  const mobCsesInput = document.getElementById("mobile-cses-user");

  // Load from localStorage
  const cfHandle = localStorage.getItem("cf-handle") || "";
  const csesUser = localStorage.getItem("cses-user") || "";

  // Populate desktop and mobile inputs if they exist
  if (cfInput) cfInput.value = cfHandle;
  if (mobCfInput) mobCfInput.value = cfHandle;
  if (csesInput) csesInput.value = csesUser;
  if (mobCsesInput) mobCsesInput.value = csesUser;

  // Function to update the top-left corner navbar status
  function updateNavBadges(cf, cses) {
    const statusContainer = document.getElementById("nav-user-status");
    if (!statusContainer) return;

    statusContainer.innerHTML = "";

    if (cf) {
      const cfBadge = document.createElement("span");
      cfBadge.className = "nav-badge cf-badge";
      cfBadge.title = `Codeforces: ${cf}`;
      cfBadge.innerHTML = `<span class="badge-label">CF:</span><span class="badge-value">${cf}</span>`;
      statusContainer.appendChild(cfBadge);
    }

    if (cses) {
      const csesBadge = document.createElement("span");
      csesBadge.className = "nav-badge cses-badge";
      csesBadge.title = `CSES: ${cses}`;
      csesBadge.innerHTML = `<span class="badge-label">CSES:</span><span class="badge-value">${cses}</span>`;
      statusContainer.appendChild(csesBadge);
    }
  }

  // Initial update
  updateNavBadges(cfHandle, csesUser);

  // Sync event listener helper
  function setupSyncListener(desktopEl, mobileEl, key, isCf) {
    function handleSync(val) {
      localStorage.setItem(key, val);
      if (desktopEl && desktopEl.value !== val) desktopEl.value = val;
      if (mobileEl && mobileEl.value !== val) mobileEl.value = val;

      const currentCf = isCf ? val : (localStorage.getItem("cf-handle") || "");
      const currentCses = !isCf ? val : (localStorage.getItem("cses-user") || "");
      updateNavBadges(currentCf, currentCses);

      // Trigger custom events to notify page-specific scripts if needed
      window.dispatchEvent(new CustomEvent("handlesynced", { detail: { key, value: val } }));
    }

    if (desktopEl) {
      desktopEl.addEventListener("input", (e) => handleSync(e.target.value.trim()));
    }
    if (mobileEl) {
      mobileEl.addEventListener("input", (e) => handleSync(e.target.value.trim()));
    }
  }

  setupSyncListener(cfInput, mobCfInput, "cf-handle", true);
  setupSyncListener(csesInput, mobCsesInput, "cses-user", false);
});
