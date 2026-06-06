// Common logic (theme, drawer, navbar) is handled in practice_common.js

let contestProblems = [];
let submissionPollInterval = null;

// ─── DOM references ───
const handleInput = document.getElementById("cf-handle");
const problemCountInput = document.getElementById("problem-count");
const generateBtn = document.getElementById("generate-contest");
const loadingState = document.getElementById("loading-state");
const errorState = document.getElementById("error-state");
const timerSection = document.getElementById("timer-section");
const problemsSection = document.getElementById("problems-section");
const timerDisplay = document.getElementById("timer-display");
const timerLabel = document.getElementById("timer-label");
const timerStartBtn = document.getElementById("timer-start");
const timerPauseBtn = document.getElementById("timer-pause");
const timerResetBtn = document.getElementById("timer-reset");
const customHoursInput = document.getElementById("custom-hours");
const customMinutesInput = document.getElementById("custom-minutes");
const setCustomTimeBtn = document.getElementById("set-custom-time");
const problemsTbody = document.getElementById("problems-tbody");
const problemsMeta = document.getElementById("problems-meta");

// ─── Handle persistence ───
let currentHandle = localStorage.getItem("cf-handle") || "";
if (currentHandle) handleInput.value = currentHandle;

handleInput.addEventListener("input", (e) => {
  currentHandle = e.target.value.trim();
  localStorage.setItem("cf-handle", currentHandle);
});

// ─── Division config ───
const divisionDefaults = {
  1: { count: 5, time: 150, label: "Div 1" },
  2: { count: 5, time: 120, label: "Div 2" },
  3: { count: 6, time: 135, label: "Div 3" },
  4: { count: 7, time: 120, label: "Div 4" },
};

let selectedDivision = 2;

// ─── Division card selection ───
const divisionCards = document.querySelectorAll(".division-card");

divisionCards.forEach((card) => {
  card.addEventListener("click", () => {
    divisionCards.forEach((c) => c.classList.remove("selected"));
    card.classList.add("selected");
    selectedDivision = parseInt(card.dataset.division);

    // Update problem count default
    const defaults = divisionDefaults[selectedDivision];
    problemCountInput.value = defaults.count;

    // Update custom time inputs
    const hours = Math.floor(defaults.time / 60);
    const minutes = defaults.time % 60;
    customHoursInput.value = hours;
    customMinutesInput.value = minutes;
  });
});

// ─── UI helpers ───
function showLoading() {
  loadingState.classList.remove("hidden");
  errorState.classList.add("hidden");
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

// ─── Rating class helper ───
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

// ─── Letter index helper ───
function getLetterIndex(n) {
  return String.fromCharCode(65 + n); // A=0, B=1, ...
}

// ─── Contest Generation ───
generateBtn.addEventListener("click", generateContest);

handleInput.addEventListener("keypress", (e) => {
  if (e.key === "Enter") generateContest();
});

async function generateContest() {
  const handle = handleInput.value.trim();
  if (!handle) {
    showError("Please enter your Codeforces handle");
    return;
  }

  const count = parseInt(problemCountInput.value) || divisionDefaults[selectedDivision].count;

  // Clamp count
  const clampedCount = Math.max(3, Math.min(10, count));
  problemCountInput.value = clampedCount;

  showLoading();
  hideError();
  timerSection.classList.add("hidden");
  problemsSection.classList.add("hidden");

  try {
    const response = await fetch(
      `/api/contest/generate?handle=${encodeURIComponent(handle)}&division=${selectedDivision}&count=${clampedCount}`
    );
    const data = await response.json();

    if (!data.success) {
      throw new Error(data.error || "Failed to generate contest");
    }

    displayProblems(data.data.problems, data.data.division);
    setupTimer(selectedDivision);
    checkSubmissions(); // Run immediate check on load
    hideLoading();
  } catch (error) {
    showError(error.message);
  }
}

// ─── Display Problems ───
function displayProblems(problems, division) {
  contestProblems = problems;
  problemsMeta.textContent = `Div. ${division} • ${problems.length} problems`;

  problemsTbody.innerHTML = problems
    .map((p, idx) => {
      const index = p.index || getLetterIndex(idx);
      const ratingBadge = p.rating
        ? `<span class="rating-badge rating-${getRatingClass(p.rating)}">${p.rating}</span>`
        : `<span class="rating-badge rating-newbie">?</span>`;

      return `
        <tr id="problem-row-${p.contestId}-${p.index}">
          <td class="problem-index-cell">${index}</td>
          <td>
            <a href="${p.url}" target="_blank" rel="noopener" class="problem-name-link">${p.name}</a>
          </td>
          <td>${ratingBadge}</td>
        </tr>
      `;
    })
    .join("");

  problemsSection.classList.remove("hidden");
  problemsSection.scrollIntoView({ behavior: "smooth", block: "nearest" });
}

// ─── Timer ───
let timerState = "idle"; // idle, running, paused
let timerInterval = null;
let timerTotalSeconds = 0;
let timerRemainingSeconds = 0;

function setActiveTimerButton(activeBtn) {
  [timerStartBtn, timerPauseBtn, timerResetBtn].forEach(btn => {
    if (btn === activeBtn) {
      btn.classList.add("active");
    } else {
      btn.classList.remove("active");
    }
  });
}

function setupTimer(division) {
  // Reset any existing timer
  clearInterval(timerInterval);
  timerInterval = null;
  clearInterval(submissionPollInterval);
  submissionPollInterval = null;
  timerState = "idle";
  setActiveTimerButton(null);

  const defaults = divisionDefaults[division];
  timerTotalSeconds = defaults.time * 60;
  timerRemainingSeconds = timerTotalSeconds;

  // Update custom time inputs
  const hours = Math.floor(defaults.time / 60);
  const minutes = defaults.time % 60;
  customHoursInput.value = hours;
  customMinutesInput.value = minutes;

  updateTimerDisplay();
  updateTimerClasses();
  timerLabel.textContent = "Ready to start";

  timerStartBtn.disabled = false;
  timerPauseBtn.disabled = true;

  timerSection.classList.remove("hidden");
  timerSection.scrollIntoView({ behavior: "smooth", block: "center" });
}

function formatTime(totalSeconds) {
  const h = Math.floor(totalSeconds / 3600);
  const m = Math.floor((totalSeconds % 3600) / 60);
  const s = totalSeconds % 60;
  return `${String(h).padStart(2, "0")}:${String(m).padStart(2, "0")}:${String(s).padStart(2, "0")}`;
}

function updateTimerDisplay() {
  timerDisplay.textContent = formatTime(timerRemainingSeconds);
}

function updateTimerClasses() {
  const wrapper = document.querySelector(".timer-display-wrapper");
  wrapper.classList.remove("timer-running", "timer-warning", "timer-critical", "timer-expired");

  if (timerState === "running") {
    if (timerRemainingSeconds <= 60) {
      wrapper.classList.add("timer-critical");
    } else if (timerRemainingSeconds <= 300) {
      wrapper.classList.add("timer-warning");
    } else {
      wrapper.classList.add("timer-running");
    }
  } else if (timerRemainingSeconds === 0 && timerState !== "idle") {
    wrapper.classList.add("timer-expired");
  }
}

// Timer Start
timerStartBtn.addEventListener("click", () => {
  if (timerState === "running") return;

  if (timerRemainingSeconds <= 0) {
    // Reset if expired
    timerRemainingSeconds = timerTotalSeconds;
  }

  setActiveTimerButton(timerStartBtn);
  timerState = "running";
  timerLabel.textContent = "Contest in progress";
  timerStartBtn.disabled = true;
  timerPauseBtn.disabled = false;

  // Start checking submissions
  checkSubmissions();
  clearInterval(submissionPollInterval);
  submissionPollInterval = setInterval(checkSubmissions, 10000);

  timerInterval = setInterval(() => {
    timerRemainingSeconds--;
    updateTimerDisplay();
    updateTimerClasses();

    if (timerRemainingSeconds <= 0) {
      clearInterval(timerInterval);
      timerInterval = null;
      clearInterval(submissionPollInterval);
      submissionPollInterval = null;
      timerState = "expired";
      timerRemainingSeconds = 0;
      updateTimerDisplay();
      updateTimerClasses();
      timerLabel.textContent = "Time's up!";
      timerStartBtn.disabled = false;
      timerPauseBtn.disabled = true;

      // Show alert
      setTimeout(() => {
        alert("⏰ Time's up! Your contest has ended.");
      }, 100);
    }
  }, 1000);

  updateTimerClasses();
});

// Timer Pause
timerPauseBtn.addEventListener("click", () => {
  if (timerState !== "running") return;

  setActiveTimerButton(timerPauseBtn);
  clearInterval(timerInterval);
  timerInterval = null;
  clearInterval(submissionPollInterval);
  submissionPollInterval = null;
  timerState = "paused";
  timerLabel.textContent = "Paused";
  timerStartBtn.disabled = false;
  timerPauseBtn.disabled = true;
  updateTimerClasses();
});

// Timer Reset
timerResetBtn.addEventListener("click", () => {
  setActiveTimerButton(timerResetBtn);
  clearInterval(timerInterval);
  timerInterval = null;
  clearInterval(submissionPollInterval);
  submissionPollInterval = null;
  timerState = "idle";
  timerRemainingSeconds = timerTotalSeconds;
  updateTimerDisplay();
  updateTimerClasses();
  timerLabel.textContent = "Ready to start";
  timerStartBtn.disabled = false;
  timerPauseBtn.disabled = true;

  // Reset solved elements in rows
  contestProblems.forEach((p) => {
    const row = document.getElementById(`problem-row-${p.contestId}-${p.index}`);
    if (row) {
      row.classList.remove("solved");
      row.querySelector(".solved-icon")?.remove();
    }
  });
});

// Set Custom Time
setCustomTimeBtn.addEventListener("click", () => {
  const hours = parseInt(customHoursInput.value) || 0;
  const minutes = parseInt(customMinutesInput.value) || 0;

  if (hours === 0 && minutes === 0) {
    return; // Don't allow 0:00
  }

  // Stop existing timer
  clearInterval(timerInterval);
  timerInterval = null;
  clearInterval(submissionPollInterval);
  submissionPollInterval = null;
  timerState = "idle";

  timerTotalSeconds = (hours * 60 + minutes) * 60;
  timerRemainingSeconds = timerTotalSeconds;
  updateTimerDisplay();
  updateTimerClasses();
  timerLabel.textContent = "Custom time set";
  timerStartBtn.disabled = false;
  timerPauseBtn.disabled = true;
});

// ─── Submissions Checker ───
async function checkSubmissions() {
  const handle = handleInput.value.trim();
  if (!handle || contestProblems.length === 0) return;

  try {
    const response = await fetch(`https://codeforces.com/api/user.status?handle=${encodeURIComponent(handle)}&from=1&count=50`);
    const data = await response.json();
    if (data.status === "OK") {
      const submissions = data.result;
      contestProblems.forEach((p) => {
        const isSolved = submissions.some(sub => 
          sub.problem.contestId === p.contestId && 
          sub.problem.index === (p.problemIndex || p.index) && 
          sub.verdict === "OK"
        );
        if (isSolved) {
          markProblemAsSolved(p);
        }
      });
    }
  } catch (error) {
    console.error("Failed to check submissions:", error);
  }
}

function markProblemAsSolved(p) {
  const row = document.getElementById(`problem-row-${p.contestId}-${p.index}`);
  if (row && !row.classList.contains("solved")) {
    row.classList.add("solved");
    const nameCell = row.cells[1];
    if (nameCell && !nameCell.querySelector(".solved-icon")) {
      const icon = document.createElement("span");
      icon.className = "solved-icon";
      icon.innerHTML = `<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3" stroke-linecap="round" stroke-linejoin="round" style="color: #10b981; margin-left: 8px; vertical-align: middle;"><polyline points="20 6 9 17 4 12"/></svg>`;
      nameCell.appendChild(icon);
    }
  }
}
