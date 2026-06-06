const modeDescriptions = {
  balanced: "Weak topics + slight rating push (default)",
  stretch: "Harder problems to force growth (+200 rating)",
  "weak-topics": "Focus on your weakest areas",
  explore: "Topics you have never touched",
  grind: "Popular problems to build speed (-100 rating)",
};

let currentMode = localStorage.getItem("mode") || "balanced";
let currentHandle = localStorage.getItem("cf-handle") || "";
let currentCsesUser = localStorage.getItem("cses-user") || "";

const handleInput = document.getElementById("cf-handle");
const csesUserInput = document.getElementById("cses-user");
const csesPasswordInput = document.getElementById("cses-password");

// ── Restore all persisted form values on load ──
if (currentHandle) handleInput.value = currentHandle;
if (currentCsesUser) csesUserInput.value = currentCsesUser;

const problemCountInput = document.getElementById("problem-count");
const platformFilterInput = document.getElementById("platform-filter");
const tagsFilterInput = document.getElementById("tags-filter");
const minRatingInput = document.getElementById("min-rating");
const maxRatingInput = document.getElementById("max-rating");

(function restoreFormState() {
  const savedCount = localStorage.getItem("problem-count");
  if (savedCount) problemCountInput.value = savedCount;

  const savedPlatform = localStorage.getItem("platform-filter");
  if (savedPlatform !== null) platformFilterInput.value = savedPlatform;

  const savedTags = localStorage.getItem("tags-filter");
  if (savedTags) tagsFilterInput.value = savedTags;

  const savedMinRating = localStorage.getItem("min-rating");
  if (savedMinRating) minRatingInput.value = savedMinRating;

  const savedMaxRating = localStorage.getItem("max-rating");
  if (savedMaxRating) maxRatingInput.value = savedMaxRating;
})();

// ── Persist all form fields on change ──
handleInput.addEventListener("input", (e) => {
  currentHandle = e.target.value.trim();
  localStorage.setItem("cf-handle", currentHandle);
});

csesUserInput.addEventListener("input", (e) => {
  currentCsesUser = e.target.value.trim();
  localStorage.setItem("cses-user", currentCsesUser);
});

problemCountInput.addEventListener("input", (e) => {
  localStorage.setItem("problem-count", e.target.value);
});

platformFilterInput.addEventListener("change", (e) => {
  localStorage.setItem("platform-filter", e.target.value);
});

tagsFilterInput.addEventListener("input", (e) => {
  localStorage.setItem("tags-filter", e.target.value.trim());
});

minRatingInput.addEventListener("input", (e) => {
  localStorage.setItem("min-rating", e.target.value);
});

maxRatingInput.addEventListener("input", (e) => {
  localStorage.setItem("max-rating", e.target.value);
});

const modeButtons = document.querySelectorAll(".mode-btn");
const modeDescription = document.getElementById("mode-description");

// Restore saved mode selection
(function restoreMode() {
  modeButtons.forEach((b) => b.classList.remove("active"));
  const activeBtn = [...modeButtons].find(
    (b) => b.dataset.mode === currentMode,
  );
  if (activeBtn) activeBtn.classList.add("active");
  modeDescription.textContent = modeDescriptions[currentMode];
})();

modeButtons.forEach((btn) => {
  btn.addEventListener("click", () => {
    modeButtons.forEach((b) => b.classList.remove("active"));
    btn.classList.add("active");
    currentMode = btn.dataset.mode;
    localStorage.setItem("mode", currentMode);
    modeDescription.textContent = modeDescriptions[currentMode];
  });
});

const loadingState = document.getElementById("loading-state");
const errorState = document.getElementById("error-state");
const userStats = document.getElementById("user-stats");
const recommendationsSection = document.getElementById(
  "recommendations-section",
);

function showLoading() {
  loadingState.classList.remove("hidden");
  errorState.classList.add("hidden");
  userStats.classList.add("hidden");
  recommendationsSection.classList.add("hidden");
}

function hideLoading() {
  loadingState.classList.add("hidden");
}

function showError(message) {
  errorState.classList.remove("hidden");
  errorState.querySelector(".error-message").textContent = message;
  hideLoading();
}

function hideError() {
  errorState.classList.add("hidden");
}

async function getRecommendations() {
  const handle = handleInput.value.trim();
  if (!handle) {
    showError("Please enter a Codeforces handle");
    return;
  }

  const count = problemCountInput.value;
  const platform = platformFilterInput.value;
  const tags = tagsFilterInput.value.trim();
  const minRating = minRatingInput.value;
  const maxRating = maxRatingInput.value;

  const csesUser = csesUserInput.value.trim();
  const csesPassword = csesPasswordInput.value;
  const platformNeedsCses = platform === "cses" || platform === "" || !platform;

  if (platform === "cses" && !csesUser) {
    showError("Enter your CSES username to get unsolved CSES recommendations.");
    return;
  }

  showLoading();
  hideError();

  try {
    let response;
    const basePayload = {
      handle,
      count,
      mode: currentMode,
      platform: platform || undefined,
      tags: tags || undefined,
      min_rating: minRating || undefined,
      max_rating: maxRating || undefined,
      cses_user: csesUser || undefined,
    };

    if (csesPassword && csesUser && platformNeedsCses) {
      response = await fetch("/api/recommendations", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ ...basePayload, cses_password: csesPassword }),
      });
      csesPasswordInput.value = "";
    } else {
      const params = new URLSearchParams();
      Object.entries(basePayload).forEach(([key, value]) => {
        if (value !== undefined && value !== "") params.append(key, value);
      });
      response = await fetch(`/api/recommendations?${params}`);
    }

    const data = await response.json();

    if (!data.success) {
      throw new Error(data.error || "Failed to fetch recommendations");
    }

    displayUserStats(data.data.user, data.data.weak_topics, data.data.cses);
    displayRecommendations(
      data.data.recommendations,
      data.data.mode,
      data.data.cses_notice,
    );
    hideLoading();
  } catch (error) {
    showError(error.message);
  }
}

function displayUserStats(user, weakTopics, cses) {
  document.getElementById("user-rating").textContent = user.rating || "-";
  document.getElementById("user-rank").textContent = user.rank || "-";
  document.getElementById("user-solved").textContent = user.solved_count || "-";
  document.getElementById("submission-streak").textContent =
    user.submission_streak || "0";
  document.getElementById("solve-streak").textContent =
    user.solve_streak || "0";

  const csesStatsEl = document.getElementById("cses-stats");
  if (csesStatsEl) {
    if (cses) {
      const cacheLabel = cses.from_cache ? "cached" : "synced";
      csesStatsEl.textContent = `CSES @${cses.username}: ${cses.solved_count} solved (${cacheLabel})`;
      csesStatsEl.classList.remove("hidden");
    } else {
      csesStatsEl.classList.add("hidden");
      csesStatsEl.textContent = "";
    }
  }

  const weakTopicsContainer = document.getElementById("weak-topics-container");
  if (weakTopics && weakTopics.length > 0) {
    weakTopicsContainer.innerHTML = `
            <div class="weak-topics-label">Weak Topics:</div>
            <div class="topics-pills">
                ${weakTopics
                  .map(
                    (topic) => `<span class="topic-pill weak">${topic}</span>`,
                  )
                  .join("")}
            </div>
        `;
  } else {
    weakTopicsContainer.innerHTML = "";
  }

  userStats.classList.remove("hidden");
}

function displayRecommendations(recommendations, mode, csesNotice) {
  const meta = document.getElementById("recommendations-meta");
  let metaText = `Mode: ${mode} • ${recommendations.length} problems`;
  if (csesNotice) metaText += ` • ${csesNotice}`;
  meta.textContent = metaText;

  const list = document.getElementById("recommendations-list");
  list.innerHTML = recommendations
    .map((rec, idx) => {
      const p = rec.problem;
      const isPlatformCses = p.platform === "cses";

      let ratingBadge = "";
      let solvedBadge = "";
      let tagsList = "";

      if (!isPlatformCses) {
        ratingBadge = p.rating
          ? `<span class="rating-badge rating-${getRatingClass(
              p.rating,
            )}">${p.rating}</span>`
          : "";
        solvedBadge = p.solvedCount
          ? `<span class="solved-badge">${p.solvedCount.toLocaleString()} solved</span>`
          : "";
        tagsList = p.tags
          ? `<div class="problem-tags">
                        ${p.tags
                          .slice(0, 4)
                          .map((tag) => `<span class="tag-pill">${tag}</span>`)
                          .join("")}
                    </div>`
          : "";
      } else {
        tagsList = p.category
          ? `<div class="problem-tags">
                        <span class="tag-pill">${p.category}</span>
                    </div>`
          : "";
      }

      return `
                <div class="problem-card">
                    <div class="problem-header">
                        <div class="problem-rank">#${rec.rank}</div>
                        <div class="problem-info">
                            <h3 class="problem-title">
                                <a href="${p.url}" target="_blank" rel="noopener">${
                                  p.name
                                }</a>
                            </h3>
                            <div class="problem-meta">
                                <span class="platform-badge">${p.platform}</span>
                                ${ratingBadge}
                                ${solvedBadge}
                            </div>
                        </div>
                    </div>
                    ${tagsList}
                </div>
            `;
    })
    .join("");

  recommendationsSection.classList.remove("hidden");
  recommendationsSection.scrollIntoView({
    behavior: "smooth",
    block: "nearest",
  });
}

function getRatingClass(rating) {
  if (rating < 1200) return "newbie";
  if (rating < 1400) return "pupil";
  if (rating < 1600) return "specialist";
  if (rating < 1900) return "expert";
  if (rating < 2100) return "cm";
  if (rating < 2300) return "master";
  if (rating < 2400) return "im";
  if (rating < 2600) return "gm";
  return "lgm";
}

document
  .getElementById("get-recommendations")
  .addEventListener("click", getRecommendations);

handleInput.addEventListener("keypress", (e) => {
  if (e.key === "Enter") {
    getRecommendations();
  }
});
