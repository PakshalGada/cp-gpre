// practice_problems.js

document.addEventListener("DOMContentLoaded", () => {
  // ─── State Management ───
  let currentPlatform = "codeforces";
  let cfHandle = localStorage.getItem("cf-handle") || "";
  let atcoderHandle = localStorage.getItem("atcoder-handle") || "";

  let solvedCF = new Set();
  let solvedAC = new Set();

  let cfData = null;
  let atcoderData = null;

  let cfSelectedCategory = "Div. 2";
  let atcoderSelectedCategory = "ABC";
  let searchQuery = "";

  let currentPage = 1;
  const contestsPerPage = 75; // Expanded to show at least 75 contests per page

  // ─── DOM Elements ───
  const btnCf = document.getElementById("platform-cf");
  const btnAtcoder = document.getElementById("platform-atcoder");

  const categoryButtonsContainer = document.getElementById("category-buttons");
  const searchInput = document.getElementById("search-input");

  const loadingState = document.getElementById("loading-state");
  const errorState = document.getElementById("error-state");
  const retryBtn = document.getElementById("retry-btn");
  const contentSection = document.getElementById("content-section");
  const contestsList = document.getElementById("contests-list");
  const resultsCount = document.getElementById("results-count");

  const paginationWrapper = document.getElementById("pagination-wrapper");
  const btnPrevPage = document.getElementById("btn-prev-page");
  const btnNextPage = document.getElementById("btn-next-page");
  const pageInfo = document.getElementById("page-info");

  // ─── Initialize ───
  updatePlatformUI();
  renderCategoryButtons();

  // Load initial data
  loadPlatformData(currentPlatform);
  if (cfHandle || atcoderHandle) {
    fetchSolvedStatus();
  }

  // Highlight the active sidebar menu link for "Practice Problems"
  const sidebarLinkProblems = document.getElementById("sidebar-link-problems");
  if (sidebarLinkProblems) {
    document
      .querySelectorAll(".sidebar-menu-link")
      .forEach((el) => el.classList.remove("active"));
    sidebarLinkProblems.classList.add("active");
  }

  // ─── Event Listeners ───
  btnCf.addEventListener("click", () => {
    if (currentPlatform === "codeforces") return;
    currentPlatform = "codeforces";
    updatePlatformUI();
    renderCategoryButtons();
    currentPage = 1;
    loadPlatformData(currentPlatform);
  });

  btnAtcoder.addEventListener("click", () => {
    if (currentPlatform === "atcoder") return;
    currentPlatform = "atcoder";
    updatePlatformUI();
    renderCategoryButtons();
    currentPage = 1;
    loadPlatformData(currentPlatform);
  });

  searchInput.addEventListener("input", (e) => {
    searchQuery = e.target.value.trim().toLowerCase();
    currentPage = 1;
    renderContests();
  });

  retryBtn.addEventListener("click", () => {
    loadPlatformData(currentPlatform);
  });

  // Pagination Click Listeners
  btnPrevPage.addEventListener("click", () => {
    if (currentPage > 1) {
      currentPage--;
      renderContests();
      scrollToTop();
    }
  });

  btnNextPage.addEventListener("click", () => {
    const totalPages = Math.ceil(
      getFilteredContests().length / contestsPerPage,
    );
    if (currentPage < totalPages) {
      currentPage++;
      renderContests();
      scrollToTop();
    }
  });

  // Listen to changes from the sidebar handles sync
  window.addEventListener("handlesynced", (e) => {
    if (e.detail.key === "cf-handle") {
      cfHandle = e.detail.value;
      fetchSolvedStatus();
    } else if (e.detail.key === "atcoder-handle") {
      atcoderHandle = e.detail.value;
      fetchSolvedStatus();
    }
  });

  // ─── Functions ───
  function updatePlatformUI() {
    if (currentPlatform === "codeforces") {
      btnCf.classList.add("active");
      btnAtcoder.classList.remove("active");
    } else {
      btnAtcoder.classList.add("active");
      btnCf.classList.remove("active");
    }
  }

  function renderCategoryButtons() {
    categoryButtonsContainer.innerHTML = "";

    const cfCategories = [
      { value: "Div. 1", label: "Div. 1" },
      { value: "Div. 2", label: "Div. 2" },
      { value: "Div. 3", label: "Div. 3" },
      { value: "Div. 4", label: "Div. 4" },
      { value: "Educational", label: "Educational" },
      { value: "Global Round", label: "Global Round" },
      { value: "Combined", label: "Combined" },
      { value: "Other", label: "Other" },
    ];

    const acCategories = [
      { value: "ABC", label: "ABC" },
      { value: "ARC", label: "ARC" },
      { value: "AGC", label: "AGC" },
      { value: "Other", label: "Other / Heuristics" },
    ];

    const list = currentPlatform === "codeforces" ? cfCategories : acCategories;
    const activeSelected =
      currentPlatform === "codeforces"
        ? cfSelectedCategory
        : atcoderSelectedCategory;

    list.forEach((item) => {
      const btn = document.createElement("button");
      btn.className = `category-btn ${item.value === activeSelected ? "active" : ""}`;
      btn.textContent = item.label;

      btn.addEventListener("click", () => {
        // Remove active classes
        categoryButtonsContainer
          .querySelectorAll(".category-btn")
          .forEach((el) => el.classList.remove("active"));
        btn.classList.add("active");

        if (currentPlatform === "codeforces") {
          cfSelectedCategory = item.value;
        } else {
          atcoderSelectedCategory = item.value;
        }
        currentPage = 1;
        renderContests();
      });

      categoryButtonsContainer.appendChild(btn);
    });
  }

  async function loadPlatformData(platform) {
    showLoading();
    hideError();
    contentSection.classList.add("hidden");

    if (platform === "codeforces" && cfData) {
      hideLoading();
      contentSection.classList.remove("hidden");
      renderContests();
      return;
    }
    if (platform === "atcoder" && atcoderData) {
      hideLoading();
      contentSection.classList.remove("hidden");
      renderContests();
      return;
    }

    try {
      const endpoint = `/api/practice/${platform}`;
      const response = await fetch(endpoint);
      const data = await response.json();

      if (!data.success) {
        throw new Error(data.error || `Failed to fetch ${platform} problems`);
      }

      if (platform === "codeforces") {
        cfData = data.data;
      } else {
        atcoderData = data.data;
      }

      hideLoading();
      contentSection.classList.remove("hidden");
      renderContests();
    } catch (err) {
      console.error(err);
      showError(err.message || "An error occurred while loading problems.");
    }
  }

  async function fetchSolvedStatus() {
    const cfHandleVal = localStorage.getItem("cf-handle") || "";
    const acHandleVal = localStorage.getItem("atcoder-handle") || "";

    if (!cfHandleVal && !acHandleVal) {
      return;
    }

    try {
      const params = new URLSearchParams();
      if (cfHandleVal) params.append("handle", cfHandleVal);
      if (acHandleVal) params.append("atcoder_handle", acHandleVal);

      const r = await fetch(`/api/practice/solved?${params}`);
      const data = await r.json();

      if (data.success) {
        solvedCF = new Set(data.codeforces);
        solvedAC = new Set(data.atcoder);
        console.log(
          `Synced solved status: CF=${solvedCF.size}, AC=${solvedAC.size}`,
        );
        renderContests();
      }
    } catch (err) {
      console.error("Sync error:", err);
    }
  }

  function getFilteredContests() {
    const data = currentPlatform === "codeforces" ? cfData : atcoderData;
    if (!data) return [];

    const category =
      currentPlatform === "codeforces"
        ? cfSelectedCategory
        : atcoderSelectedCategory;
    const contests = data[category] || [];

    if (!searchQuery) return contests;

    return contests.filter((c) => {
      const nameMatch = c.name.toLowerCase().includes(searchQuery);
      const idMatch = c.contestId
        .toString()
        .toLowerCase()
        .includes(searchQuery);
      return nameMatch || idMatch;
    });
  }

  function getRatingClass(rating) {
    if (!rating) return "";
    if (rating < 1200) return "rating-newbie";
    if (rating < 1400) return "rating-pupil";
    if (rating < 1600) return "rating-specialist";
    if (rating < 1900) return "rating-expert";
    if (rating < 2100) return "rating-cm";
    if (rating < 2300) return "rating-master";
    if (rating < 2600) return "rating-gm";
    return "rating-lgm";
  }

  function isProblemSolved(p) {
    if (currentPlatform === "codeforces") {
      const contestId = p.url.split("/").slice(-2)[0];
      const index = p.index;
      return solvedCF.has(`${contestId}${index}`);
    } else {
      return solvedAC.has(p.id);
    }
  }

  function renderContests() {
    contestsList.innerHTML = "";
    const filtered = getFilteredContests();
    const totalContests = filtered.length;

    resultsCount.textContent = `Showing ${totalContests} contest${totalContests !== 1 ? "s" : ""} in this category`;

    if (totalContests === 0) {
      contestsList.innerHTML = `
                <div class="loading-state">
                    <p>No contests found matching your filters.</p>
                </div>
            `;
      paginationWrapper.classList.add("hidden");
      return;
    }

    // Pagination
    const totalPages = Math.ceil(totalContests / contestsPerPage);
    if (currentPage > totalPages) currentPage = totalPages || 1;

    const startIndex = (currentPage - 1) * contestsPerPage;
    const endIndex = Math.min(startIndex + contestsPerPage, totalContests);
    const paginatedContests = filtered.slice(startIndex, endIndex);

    // Render
    paginatedContests.forEach((contest) => {
      const cid = contest.contestId;
      const name = contest.name;
      const problems = contest.problems || [];

      const solvedCount = problems.filter((p) => isProblemSolved(p)).length;

      const contestRow = document.createElement("div");
      contestRow.className = "contest-row";
      contestRow.dataset.contestId = cid;

      let solvedBadgeHtml = "";
      if (solvedCount > 0) {
        solvedBadgeHtml = `
                    <div class="solved-status-summary">
                        <svg class="status-icon-check" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3" stroke-linecap="round" stroke-linejoin="round">
                            <polyline points="20 6 9 17 4 12" />
                        </svg>
                        <span>${solvedCount}/${problems.length} Solved</span>
                    </div>
                `;
      }

      // direct row displaying details on the left, problems grid on the right
      contestRow.innerHTML = `
                <div class="contest-info">
                    <h3 class="contest-title">${name}</h3>
                    <div class="contest-meta">
                        <span class="contest-id-badge">ID: ${cid}</span>
                        <span class="contest-meta-separator">•</span>
                        ${solvedBadgeHtml ? solvedBadgeHtml : `<span>${problems.length} problems</span>`}
                    </div>
                </div>
                <div class="contest-problems-cell">
                    <div class="problems-grid"></div>
                </div>
            `;

      // Append problems to grid directly
      const grid = contestRow.querySelector(".problems-grid");
      problems.forEach((p) => {
        const isSolved = isProblemSolved(p);

        const cardLink = document.createElement("a");
        cardLink.href = p.url;
        cardLink.target = "_blank";
        cardLink.rel = "noopener";
        cardLink.className = `problem-item-card ${isSolved ? "solved" : ""}`;

        let tooltipText = `${p.name}`;
        let cfRatingHtml = "";
        let ratingClass = "";

        if (currentPlatform === "codeforces") {
          if (p.rating) {
            ratingClass = getRatingClass(p.rating);
            tooltipText += `\nRating: ${p.rating}`;
            cfRatingHtml = `<span class="problem-rating-text ${ratingClass}">${p.rating}</span>`;
          }
          if (p.tags && p.tags.length > 0) {
            tooltipText += `\nTags: ${p.tags.join(", ")}`;
          }
        }

        cardLink.title = tooltipText;

        const solvedDot = isSolved
          ? '<span class="solved-indicator-dot"></span>'
          : "";

        cardLink.innerHTML = `
                    <span class="problem-index-text">${p.index}</span>
                    ${cfRatingHtml}
                    ${solvedDot}
                `;

        grid.appendChild(cardLink);
      });

      contestsList.appendChild(contestRow);
    });

    // Update pagination controls
    paginationWrapper.classList.remove("hidden");
    pageInfo.textContent = `Page ${currentPage} of ${totalPages}`;
    btnPrevPage.disabled = currentPage === 1;
    btnNextPage.disabled = currentPage === totalPages;
  }

  function showLoading() {
    loadingState.classList.remove("hidden");
  }

  function hideLoading() {
    loadingState.classList.add("hidden");
  }

  function showError(message) {
    errorState.classList.remove("hidden");
    errorState.querySelector(".error-message").textContent = message;
  }

  function hideError() {
    errorState.classList.add("hidden");
  }

  function scrollToTop() {
    contentSection.scrollIntoView({ behavior: "smooth", block: "start" });
  }
});
