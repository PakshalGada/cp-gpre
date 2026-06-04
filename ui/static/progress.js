document.addEventListener("DOMContentLoaded", () => {
    // ─── DOM Elements ───
    const cfHandleInput = document.getElementById("cf-handle");
    const csesUserInput = document.getElementById("cses-user");
    const csesPasswordInput = document.getElementById("cses-password");
    const syncBtn = document.getElementById("sync-btn");
    const syncStatusMsg = document.getElementById("sync-status-msg");
    const loadingState = document.getElementById("loading-state");
    const errorState = document.getElementById("error-state");
    
    const statsOverview = document.getElementById("stats-overview");
    const cfRatingEl = document.getElementById("cf-rating");
    const cfRankEl = document.getElementById("cf-rank");
    const cfSolvedEl = document.getElementById("cf-solved");
    const csesSolvedEl = document.getElementById("cses-solved");
    const totalSolvedEl = document.getElementById("total-solved");

    const heatmapSection = document.getElementById("heatmap-section");
    const heatmapGrid = document.getElementById("heatmap-grid");
    const tooltip = document.getElementById("heatmap-tooltip");
    const toggleButtons = document.querySelectorAll(".toggle-btn");
    const chartsSection = document.getElementById("charts-section");

    // ─── Chart Instances ───
    let cfRatingChart = null;
    let cfTagChart = null;

    // ─── State & Cache Keys ───
    const CACHE_KEY = "cp-gpre-progress-cache";
    let activePlatform = "both"; // 'both' | 'codeforces' | 'cses'

    // Restore cached inputs on load
    const savedCfHandle = localStorage.getItem("cf-handle") || "";
    const savedCsesUser = localStorage.getItem("cses-user") || "";
    if (savedCfHandle) cfHandleInput.value = savedCfHandle;
    if (savedCsesUser) csesUserInput.value = savedCsesUser;

    // Persist input values on change
    cfHandleInput.addEventListener("input", (e) => {
        localStorage.setItem("cf-handle", e.target.value.trim());
    });
    csesUserInput.addEventListener("input", (e) => {
        localStorage.setItem("cses-user", e.target.value.trim());
    });

    // Theme integration for Chart.js
    const themeBtn = document.getElementById("theme-toggle");
    themeBtn?.addEventListener("click", () => {
        setTimeout(() => {
            if (window.cachedProgressData) {
                renderCharts(window.cachedProgressData);
            }
        }, 100);
    });

    // Handle platform toggle buttons click
    toggleButtons.forEach(btn => {
        btn.addEventListener("click", () => {
            toggleButtons.forEach(b => b.classList.remove("active"));
            btn.classList.add("active");
            activePlatform = btn.dataset.platform;
            if (window.cachedProgressData) {
                renderHeatmap(window.cachedProgressData);
            }
        });
    });

    // Load initial cached dashboard data if present
    const cachedData = loadCache();
    if (cachedData) {
        window.cachedProgressData = cachedData;
        displayDashboard(cachedData);
        // If last sync was today, show it
        const syncDate = new Date(cachedData.lastSync);
        syncStatusMsg.textContent = `Last synced: ${syncDate.toLocaleString()}`;
    }

    // ─── Sync Action ───
    syncBtn.addEventListener("click", async () => {
        const cfHandle = cfHandleInput.value.trim();
        const csesUser = csesUserInput.value.trim();
        const csesPassword = csesPasswordInput.value;

        if (!cfHandle && !csesUser) {
            showError("Please enter at least a Codeforces handle or CSES username.");
            return;
        }

        showLoading();
        hideError();

        try {
            let cfSubmissions = [];
            let cfUserInfo = null;
            let csesSolvedIds = [];

            // 1. Fetch Codeforces Submissions & User Info (directly from browser client)
            if (cfHandle) {
                cfUserInfo = await fetchCodeforcesUserInfo(cfHandle);
                cfSubmissions = await fetchCodeforcesSubmissions(cfHandle);
            }

            // 2. Fetch CSES Solves (via local Flask server API scraper)
            if (csesUser) {
                if (csesPassword) {
                    const csesRes = await syncCsesProgressServer(csesUser, csesPassword);
                    csesSolvedIds = csesRes.solved_ids;
                    csesPasswordInput.value = ""; // Clear password field
                } else {
                    // Fall back to previously cached CSES solved IDs
                    const cachedProgress = loadCache();
                    if (cachedProgress && cachedProgress.csesUser === csesUser) {
                        csesSolvedIds = cachedProgress.csesSolvedIds || [];
                    }
                }
            }

            // 3. Process CSES daily solved dates mapping
            const csesSolvedDates = processCsesDates(csesSolvedIds);

            // 4. Save aggregated data to cache
            const newCache = {
                cfHandle,
                csesUser,
                lastSync: new Date().toISOString(),
                cfUserInfo,
                cfSubmissions,
                csesSolvedIds,
                csesSolvedDates
            };

            saveCache(newCache);
            window.cachedProgressData = newCache;
            displayDashboard(newCache);

            syncStatusMsg.textContent = `Last synced: ${new Date().toLocaleString()}`;
            hideLoading();
        } catch (err) {
            console.error(err);
            showError(err.message || "An error occurred during synchronization.");
        }
    });

    // ─── API Helpers ───
    async function fetchCodeforcesUserInfo(handle) {
        const res = await fetch(`https://codeforces.com/api/user.info?handles=${handle}`);
        const data = await res.json();
        if (data.status !== "OK") {
            throw new Error(data.comment || "Failed to fetch Codeforces profile info");
        }
        return data.result[0];
    }

    async function fetchCodeforcesSubmissions(handle) {
        const res = await fetch(`https://codeforces.com/api/user.status?handle=${handle}`);
        const data = await res.json();
        if (data.status !== "OK") {
            throw new Error(data.comment || "Failed to fetch Codeforces submissions");
        }
        return data.result;
    }

    async function syncCsesProgressServer(csesUser, csesPassword) {
        const res = await fetch("/api/cses/progress", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ cses_user: csesUser, cses_password: csesPassword })
        });
        const data = await res.json();
        if (!data.success) {
            throw new Error(data.error || "Failed to synchronize CSES progress with the server");
        }
        return data.data;
    }

    // Process CSES solved IDs and map them to the sync day to build the daily heatmap
    function processCsesDates(solvedIds) {
        let storedDates = JSON.parse(localStorage.getItem("cp-cses-solved-dates") || "{}");
        let storedIds = JSON.parse(localStorage.getItem("cp-cses-solved-ids") || "[]");
        const storedSet = new Set(storedIds);
        const todayStr = new Date().toISOString().split("T")[0];

        // First sync ever warning grouping
        const isFirstSync = storedIds.length === 0;

        solvedIds.forEach(id => {
            const idStr = id.toString();
            if (!storedDates[idStr]) {
                // If it is the first sync, we group them on today but mark them as historical
                // Otherwise, it was solved on the day of this sync
                storedDates[idStr] = todayStr;
            }
        });

        localStorage.setItem("cp-cses-solved-dates", JSON.stringify(storedDates));
        localStorage.setItem("cp-cses-solved-ids", JSON.stringify(solvedIds));

        return storedDates;
    }

    // ─── Rendering Dashboard ───
    function displayDashboard(data) {
        // Calculate solved counts
        const cfSolvedSet = new Set();
        if (data.cfSubmissions) {
            data.cfSubmissions.forEach(sub => {
                if (sub.verdict === "OK" && sub.problem) {
                    const key = `${sub.problem.contestId}-${sub.problem.index}`;
                    cfSolvedSet.add(key);
                }
            });
        }

        const cfSolvedCount = cfSolvedSet.size;
        const csesSolvedCount = data.csesSolvedIds ? data.csesSolvedIds.length : 0;
        const totalSolvedCount = cfSolvedCount + csesSolvedCount;

        // Render Stats overview card
        if (data.cfUserInfo) {
            cfRatingEl.textContent = data.cfUserInfo.rating || "Unrated";
            cfRankEl.textContent = data.cfUserInfo.rank || "Unrated";
        } else {
            cfRatingEl.textContent = "-";
            cfRankEl.textContent = "-";
        }
        cfSolvedEl.textContent = cfSolvedCount;
        csesSolvedEl.textContent = csesSolvedCount;
        totalSolvedEl.textContent = totalSolvedCount;
        statsOverview.classList.remove("hidden");

        // Render Heatmap
        renderHeatmap(data);
        heatmapSection.classList.remove("hidden");

        // Render Codeforces Charts
        renderCharts(data);
        chartsSection.classList.remove("hidden");
    }

    // ─── Heatmap Construction ───
    function renderHeatmap(data) {
        heatmapGrid.innerHTML = "";

        // Build past 365 days dates mapping
        const datesMap = {};
        const today = new Date();
        const todayStr = today.toISOString().split("T")[0];
        
        const days = [];
        for (let i = 364; i >= 0; i--) {
            const tempDate = new Date();
            tempDate.setDate(today.getDate() - i);
            const dateStr = tempDate.toISOString().split("T")[0];
            days.push({
                dateStr,
                dateObj: tempDate,
                cfSolves: [],
                csesSolves: []
            });
            datesMap[dateStr] = days[days.length - 1];
        }

        // Map Codeforces solves by date
        if (data.cfSubmissions) {
            const cfUniqueSolves = new Set();
            data.cfSubmissions.forEach(sub => {
                if (sub.verdict === "OK" && sub.problem) {
                    const key = `${sub.problem.contestId}-${sub.problem.index}`;
                    if (!cfUniqueSolves.has(key)) {
                        cfUniqueSolves.add(key);
                        const ts = sub.creationTimeSeconds * 1000;
                        const dateStr = new Date(ts).toISOString().split("T")[0];
                        if (datesMap[dateStr]) {
                            datesMap[dateStr].cfSolves.push(sub.problem);
                        }
                    }
                }
            });
        }

        // Map CSES solves by date
        if (data.csesSolvedIds && data.csesSolvedDates) {
            data.csesSolvedIds.forEach(id => {
                const idStr = id.toString();
                const dateStr = data.csesSolvedDates[idStr];
                if (dateStr && datesMap[dateStr]) {
                    datesMap[dateStr].csesSolves.push(id);
                }
            });
        }

        // Align contribution grid to days of week (Sunday is 0, padding column-wise layout)
        const firstDay = days[0].dateObj;
        const firstDayOfWeek = firstDay.getDay(); // 0 (Sunday) to 6 (Saturday)
        for (let i = 0; i < firstDayOfWeek; i++) {
            const spacer = document.createElement("div");
            spacer.className = "day-cell spacer";
            spacer.style.opacity = "0";
            spacer.style.pointerEvents = "none";
            heatmapGrid.appendChild(spacer);
        }

        // Display/hide legends depending on active view
        const cfLegend = document.getElementById("cf-legend");
        const csesLegend = document.getElementById("cses-legend");
        const csesWarning = document.getElementById("cses-warning-msg");

        if (activePlatform === "codeforces") {
            cfLegend.classList.remove("hidden");
            csesLegend.classList.add("hidden");
            csesWarning.classList.add("hidden");
        } else if (activePlatform === "cses") {
            cfLegend.classList.add("hidden");
            csesLegend.classList.remove("hidden");
            csesWarning.classList.remove("hidden");
        } else {
            cfLegend.classList.remove("hidden");
            csesLegend.classList.remove("hidden");
            csesWarning.classList.remove("hidden");
        }

        // Render cells
        days.forEach(day => {
            const cell = document.createElement("div");
            cell.className = "day-cell";
            cell.dataset.date = day.dateStr;

            let tooltipText = `${formatDateString(day.dateObj)}`;
            let hasSolved = false;

            if (activePlatform === "codeforces" || activePlatform === "both") {
                const count = day.cfSolves.length;
                if (count > 0) {
                    hasSolved = true;
                    // Find max rating solved on this day
                    let maxRating = 0;
                    day.cfSolves.forEach(p => {
                        if (p.rating && p.rating > maxRating) maxRating = p.rating;
                    });
                    
                    // Add rating class color
                    cell.classList.add(`cf-${getRatingColorClass(maxRating)}`);
                    tooltipText += `\n• Codeforces: Solved ${count} problem(s)`;
                    day.cfSolves.forEach(p => {
                        tooltipText += `\n  - ${p.name} (${p.rating || "unrated"})`;
                    });
                }
            }

            if (activePlatform === "cses" || activePlatform === "both") {
                const count = day.csesSolves.length;
                if (count > 0) {
                    hasSolved = true;
                    
                    // If both platform selected, only color using CSES green if Codeforces solves do not exist
                    if (activePlatform === "cses" || day.cfSolves.length === 0) {
                        const level = count >= 3 ? 3 : count;
                        cell.classList.add(`cses-${level}`);
                    }
                    
                    tooltipText += `\n• CSES: Solved ${count} task(s)`;
                }
            }

            if (!hasSolved) {
                tooltipText += "\nNo problems solved";
            }

            // Bind tooltip hover listeners
            cell.addEventListener("mouseover", (e) => {
                tooltip.textContent = tooltipText;
                tooltip.style.display = "block";
                
                const rect = cell.getBoundingClientRect();
                const tooltipRect = tooltip.getBoundingClientRect();
                
                // Position tooltip above the cell centered
                let top = rect.top + window.scrollY - tooltipRect.height - 8;
                let left = rect.left + window.scrollX - (tooltipRect.width / 2) + 5;
                
                // Edge corrections
                if (top < window.scrollY) {
                    top = rect.bottom + window.scrollY + 8; // flip below if offscreen top
                }
                if (left < 10) left = 10;
                
                tooltip.style.top = `${top}px`;
                tooltip.style.left = `${left}px`;
            });

            cell.addEventListener("mouseout", () => {
                tooltip.style.display = "none";
            });

            heatmapGrid.appendChild(cell);
        });
    }

    // Helper formatting: "Thu, Jun 4, 2026"
    function formatDateString(date) {
        return date.toLocaleDateString("en-US", {
            weekday: "short",
            year: "numeric",
            month: "short",
            day: "numeric"
        });
    }

    function getRatingColorClass(rating) {
        if (!rating || rating < 1200) return "newbie";
        if (rating < 1400) return "pupil";
        if (rating < 1600) return "specialist";
        if (rating < 1900) return "expert";
        if (rating < 2100) return "cm";
        if (rating < 2300) return "master";
        return "gm";
    }

    // ─── Chart.js Visualizations ───
    function renderCharts(data) {
        // Destroy existing instances if recreating
        if (cfRatingChart) cfRatingChart.destroy();
        if (cfTagChart) cfTagChart.destroy();

        const cfSolvedProblems = [];
        const cfUniqueKeys = new Set();

        if (data.cfSubmissions) {
            data.cfSubmissions.forEach(sub => {
                if (sub.verdict === "OK" && sub.problem) {
                    const key = `${sub.problem.contestId}-${sub.problem.index}`;
                    if (!cfUniqueKeys.has(key)) {
                        cfUniqueKeys.add(key);
                        cfSolvedProblems.push(sub.problem);
                    }
                }
            });
        }

        // Get theme-specific colors
        const themeColors = getChartThemeColors();

        // ─── 1. CF Rating Bar Chart ───
        const ratingCounts = {};
        cfSolvedProblems.forEach(p => {
            if (p.rating) {
                ratingCounts[p.rating] = (ratingCounts[p.rating] || 0) + 1;
            }
        });

        const sortedRatings = Object.keys(ratingCounts).map(Number).sort((a, b) => a - b);
        const ratingLabels = sortedRatings.map(r => r.toString());
        const ratingDataValues = sortedRatings.map(r => ratingCounts[r]);

        // Codeforces rating boundary bar colors
        const barColors = sortedRatings.map(r => getCfRatingHexColor(r));

        const ctxRating = document.getElementById("cf-rating-chart").getContext("2d");
        cfRatingChart = new Chart(ctxRating, {
            type: 'bar',
            data: {
                labels: ratingLabels,
                datasets: [{
                    label: 'Solved Problems',
                    data: ratingDataValues,
                    backgroundColor: barColors,
                    borderWidth: 0,
                    borderRadius: 4
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: { display: false },
                    tooltip: {
                        backgroundColor: '#1f1f1d',
                        titleColor: '#fff',
                        bodyColor: '#fff',
                        padding: 10,
                        cornerRadius: 6
                    }
                },
                scales: {
                    x: {
                        ticks: { color: themeColors.text, font: { family: "DM Sans, sans-serif" } },
                        grid: { display: false }
                    },
                    y: {
                        ticks: { color: themeColors.text, font: { family: "DM Sans, sans-serif" } },
                        grid: { color: themeColors.grid }
                    }
                }
            }
        });

        // ─── 2. CF Tag Doughnut Chart ───
        const tagCounts = {};
        cfSolvedProblems.forEach(p => {
            if (p.tags) {
                p.tags.forEach(tag => {
                    tagCounts[tag] = (tagCounts[tag] || 0) + 1;
                });
            }
        });

        const sortedTags = Object.entries(tagCounts).sort((a, b) => b[1] - a[1]);
        const topTags = sortedTags.slice(0, 9);
        const otherTagsCount = sortedTags.slice(9).reduce((acc, curr) => acc + curr[1], 0);

        const tagLabels = topTags.map(t => t[0]);
        const tagDataValues = topTags.map(t => t[1]);

        if (otherTagsCount > 0) {
            tagLabels.push("other");
            tagDataValues.push(otherTagsCount);
        }

        // Premium Doughnut slice colors
        const doughnutColors = [
            '#f97316', '#3b82f6', '#10b981', '#a855f7', '#ec4899',
            '#eab308', '#06b6d4', '#f43f5e', '#84cc16', '#64748b'
        ];

        const ctxTag = document.getElementById("cf-tag-chart").getContext("2d");
        cfTagChart = new Chart(ctxTag, {
            type: 'doughnut',
            data: {
                labels: tagLabels,
                datasets: [{
                    data: tagDataValues,
                    backgroundColor: doughnutColors.slice(0, tagLabels.length),
                    borderWidth: 1,
                    borderColor: document.documentElement.getAttribute("data-theme") === "dark" ? "#1c1b1a" : "#fff"
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: {
                        position: 'right',
                        labels: {
                            color: themeColors.text,
                            font: { family: "DM Sans, sans-serif", size: 11.5 }
                        }
                    },
                    tooltip: {
                        backgroundColor: '#1f1f1d',
                        titleColor: '#fff',
                        bodyColor: '#fff',
                        padding: 10,
                        cornerRadius: 6
                    }
                },
                cutout: '60%'
            }
        });
    }

    function getCfRatingHexColor(rating) {
        if (rating < 1200) return "#808080"; // Gray
        if (rating < 1400) return "#00a92a"; // Green
        if (rating < 1600) return "#03a89e"; // Cyan
        if (rating < 1900) return "#0000ff"; // Blue
        if (rating < 2100) return "#aa00aa"; // Purple
        if (rating < 2300) return "#ff8c00"; // Orange
        return "#ff0000"; // Red
    }

    function getChartThemeColors() {
        const isDark = document.documentElement.getAttribute("data-theme") === "dark";
        return {
            text: isDark ? "#9e9b93" : "#6f6d66",
            grid: isDark ? "#2c2b28" : "#e8e6e1"
        };
    }

    // ─── Cache & Helpers ───
    function saveCache(data) {
        localStorage.setItem(CACHE_KEY, JSON.stringify(data));
    }

    function loadCache() {
        const str = localStorage.getItem(CACHE_KEY);
        if (!str) return null;
        try {
            return JSON.parse(str);
        } catch (e) {
            return null;
        }
    }

    function showLoading() {
        loadingState.classList.remove("hidden");
        errorState.classList.add("hidden");
    }

    function hideLoading() {
        loadingState.classList.add("hidden");
    }

    function showError(msg) {
        errorState.classList.remove("hidden");
        errorState.querySelector(".error-message").textContent = msg;
        hideLoading();
    }

    function hideError() {
        errorState.classList.add("hidden");
    }

    // ─── Hamburger/Menu toggles (matching global navigation) ───
    const hamburger = document.getElementById("hamburger-btn");
    const drawer = document.getElementById("mobile-drawer");
    const overlay = document.getElementById("sidebar-overlay");
    const closeBtn = document.getElementById("drawer-close-btn");

    function openDrawer() {
        drawer.classList.add("open");
        overlay.classList.add("active");
        document.body.style.overflow = "hidden";
    }
    function closeDrawer() {
        drawer.classList.remove("open");
        overlay.classList.remove("active");
        document.body.style.overflow = "";
    }

    hamburger?.addEventListener("click", openDrawer);
    closeBtn?.addEventListener("click", closeDrawer);
    overlay?.addEventListener("click", closeDrawer);

    const mobileNavLinks = document.querySelectorAll(".mobile-nav-link");
    mobileNavLinks.forEach((link) => {
        link.addEventListener("click", closeDrawer);
    });

    const savedTheme = localStorage.getItem("theme");
    if (savedTheme) document.documentElement.setAttribute("data-theme", savedTheme);

    const themeToggleBtn = document.getElementById("theme-toggle");
    themeToggleBtn?.addEventListener("click", () => {
        const isDark = document.documentElement.getAttribute("data-theme") === "dark";
        const next = isDark ? "light" : "dark";
        document.documentElement.setAttribute("data-theme", next);
        localStorage.setItem("theme", next);
    });
});
