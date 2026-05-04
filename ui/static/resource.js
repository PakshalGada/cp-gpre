let currentTopics = {};
let currentSlug = null;

// Track which categories are collapsed (persisted in sessionStorage)
function getCollapsedState() {
  try {
    return JSON.parse(sessionStorage.getItem("collapsedCategories") || "{}");
  } catch {
    return {};
  }
}
function setCollapsedState(state) {
  sessionStorage.setItem("collapsedCategories", JSON.stringify(state));
}

document.addEventListener("DOMContentLoaded", () => {
  loadTopics();

  window.addEventListener("popstate", (e) => {
    if (e.state && e.state.slug) {
      loadTopic(e.state.slug, false);
    } else {
      showWelcome();
    }
  });

  const urlParams = new URLSearchParams(window.location.search);
  const slugParam = urlParams.get("topic");
  if (slugParam) {
    loadTopic(slugParam, false);
  }
  const navbar = document.getElementById("navbar");
  window.addEventListener("scroll", () => {
    if (navbar) {
      navbar.classList.toggle("scrolled", window.scrollY > 4);
    }
  });

  const hamburger = document.getElementById("hamburger-btn");
  const sidebar = document.getElementById("sidebar");
  const overlay = document.getElementById("sidebar-overlay");

  function openSidebar() {
    sidebar.classList.add("open");
    overlay.classList.add("active");
    document.body.style.overflow = "hidden";
  }

  function closeSidebar() {
    sidebar.classList.remove("open");
    overlay.classList.remove("active");
    document.body.style.overflow = "";
  }

  if (hamburger) hamburger.addEventListener("click", openSidebar);
  if (overlay) overlay.addEventListener("click", closeSidebar);

  const sidebarNav = document.getElementById("sidebar-nav");
  if (sidebarNav) {
    sidebarNav.addEventListener("click", (e) => {
      if (
        e.target.classList.contains("topic-link") &&
        window.innerWidth <= 768
      ) {
        closeSidebar();
      }
    });
  }

  // Theme toggle
  const themeBtn = document.getElementById("theme-toggle");

  // Apply saved theme
  const saved = localStorage.getItem("theme");
  if (saved) {
    document.documentElement.setAttribute("data-theme", saved);
  }

  if (themeBtn) {
    themeBtn.addEventListener("click", () => {
      const isDark =
        document.documentElement.getAttribute("data-theme") === "dark";
      const next = isDark ? "light" : "dark";

      document.documentElement.setAttribute("data-theme", next);
      localStorage.setItem("theme", next);
    });
  }

  // ── Sidebar Search ──
  const searchInput = document.getElementById("sidebar-search");
  const clearBtn = document.getElementById("search-clear-btn");
  const noResults = document.getElementById("search-no-results");

  if (searchInput) {
    searchInput.addEventListener("input", (e) => {
      const query = e.target.value.trim();
      clearBtn.classList.toggle("visible", query.length > 0);
      filterTopics(query);
    });
  }

  if (clearBtn) {
    clearBtn.addEventListener("click", () => {
      searchInput.value = "";
      clearBtn.classList.remove("visible");
      filterTopics("");
      searchInput.focus();
    });
  }
});

// ── Search / filter ──
function filterTopics(query) {
  const nav = document.getElementById("sidebar-nav");
  const noResults = document.getElementById("search-no-results");
  const q = query.toLowerCase();

  const categorySections = nav.querySelectorAll(".category-section");
  let totalVisible = 0;

  categorySections.forEach((section) => {
    const items = section.querySelectorAll(".topic-item");
    let sectionVisible = 0;

    items.forEach((item) => {
      const link = item.querySelector(".topic-link");
      const title = link.dataset.title || link.textContent;

      if (!q || title.toLowerCase().includes(q)) {
        item.style.display = "";
        sectionVisible++;

        // Highlight matched text
        if (q) {
          const idx = title.toLowerCase().indexOf(q);
          link.innerHTML =
            escapeHtml(title.slice(0, idx)) +
            "<mark>" +
            escapeHtml(title.slice(idx, idx + q.length)) +
            "</mark>" +
            escapeHtml(title.slice(idx + q.length));
        } else {
          link.textContent = title;
        }
      } else {
        item.style.display = "none";
      }
    });

    section.style.display = sectionVisible > 0 ? "" : "none";

    // Auto-expand sections that have matches
    if (q && sectionVisible > 0) {
      section.classList.remove("collapsed");
    }

    totalVisible += sectionVisible;
  });

  if (noResults) {
    noResults.classList.toggle("visible", q.length > 0 && totalVisible === 0);
  }
}

async function loadTopics() {
  try {
    const response = await fetch("api/topics");
    currentTopics = await response.json();
    renderSidebar(currentTopics);
  } catch (error) {
    console.error("Error loading topics:", error);
  }
}

function renderSidebar(categories) {
  const nav = document.getElementById("sidebar-nav");
  nav.innerHTML = "";

  const collapsed = getCollapsedState();

  Object.keys(categories)
    .sort()
    .forEach((category) => {
      const isCollapsed = collapsed[category] === true;

      const categorySection = document.createElement("div");
      categorySection.className =
        "category-section" + (isCollapsed ? " collapsed" : "");

      // Clickable header row
      const categoryHeader = document.createElement("div");
      categoryHeader.className = "category-header";

      const categoryTitle = document.createElement("span");
      categoryTitle.className = "category-title";
      categoryTitle.textContent = category;

      // Chevron SVG
      const chevron = document.createElementNS(
        "http://www.w3.org/2000/svg",
        "svg",
      );
      chevron.setAttribute("class", "category-chevron");
      chevron.setAttribute("viewBox", "0 0 16 16");
      chevron.setAttribute("fill", "none");
      chevron.setAttribute("stroke", "currentColor");
      chevron.setAttribute("stroke-width", "2");
      chevron.setAttribute("stroke-linecap", "round");
      chevron.setAttribute("stroke-linejoin", "round");
      const path = document.createElementNS(
        "http://www.w3.org/2000/svg",
        "polyline",
      );
      path.setAttribute("points", "4 6 8 10 12 6");
      chevron.appendChild(path);

      categoryHeader.appendChild(categoryTitle);
      categoryHeader.appendChild(chevron);

      // Toggle on click
      categoryHeader.addEventListener("click", () => {
        const isNowCollapsed = categorySection.classList.toggle("collapsed");
        const state = getCollapsedState();
        if (isNowCollapsed) {
          state[category] = true;
        } else {
          delete state[category];
        }
        setCollapsedState(state);
      });

      const topicList = document.createElement("ul");
      topicList.className = "topic-list";

      categories[category].forEach((topic) => {
        const topicItem = document.createElement("li");
        topicItem.className = "topic-item";

        const topicLink = document.createElement("a");
        topicLink.className = "topic-link";
        topicLink.textContent = topic.title;
        topicLink.dataset.slug = topic.slug;
        topicLink.dataset.title = topic.title; // for search filtering
        topicLink.addEventListener("click", (e) => {
          e.preventDefault();
          loadTopic(topic.slug);
        });

        topicItem.appendChild(topicLink);
        topicList.appendChild(topicItem);
      });

      categorySection.appendChild(categoryHeader);
      categorySection.appendChild(topicList);
      nav.appendChild(categorySection);
    });
}

// Load and display a specific topic
async function loadTopic(slug, updateHistory = true) {
  try {
    const response = await fetch(`/api/topic/${slug}`);
    const topic = await response.json();

    if (topic.error) {
      console.error("Topic not found");
      return;
    }

    currentSlug = slug;
    renderTopic(topic);
    updateActiveLink(slug);

    if (updateHistory) {
      const url = new URL(window.location);
      url.searchParams.set("topic", slug);
      window.history.pushState({ slug }, "", url);
    }

    window.scrollTo({ top: 0, behavior: "smooth" });
  } catch (error) {
    console.error("Error loading topic:", error);
  }
}

function renderTopic(topic) {
  const welcomeScreen = document.getElementById("welcome-screen");
  const topicContent = document.getElementById("topic-content");

  welcomeScreen.style.display = "none";
  topicContent.style.display = "block";

  let html = "";

  html += `<h1 class="section-title">${escapeHtml(topic.title)}</h1>`;
  html += `<div class="section-category">${escapeHtml(topic.category)}</div>`;

  if (topic.tags && topic.tags.length > 0) {
    html += '<div class="section-tags">';
    topic.tags.forEach((tag) => {
      html += `<span class="tag">${escapeHtml(tag)}</span>`;
    });
    html += "</div>";
  }

  if (topic.description && topic.description !== "GENERATION_FAILED") {
    html += `<div class="section-text">${escapeHtml(topic.description)}</div>`;
  }

  if (topic.time_complexity || topic.space_complexity) {
    html += '<div style="margin: 24px 0;">';
    if (topic.time_complexity) {
      html += `<span class="complexity-badge">Time: ${escapeHtml(topic.time_complexity)}</span>`;
    }
    if (topic.space_complexity) {
      html += `<span class="complexity-badge">Space: ${escapeHtml(topic.space_complexity)}</span>`;
    }
    html += "</div>";
  }

  html += '<div class="divider"></div>';

  if (topic.explanation) {
    html += '<h2 class="section-heading">Explanation</h2>';
    // Allow LaTeX in explanation — render as safe HTML (not escaped)
    html += `<div class="section-text latex-content">${sanitizeText(topic.explanation)}</div>`;
  }

  if (topic.key_insight) {
    html += '<div class="info-box">';
    html += '<div class="info-box-title">Key Insight</div>';
    html += `<div class="latex-content">${sanitizeText(topic.key_insight)}</div>`;
    html += "</div>";
  }

  if (topic.worked_example) {
    html += '<h2 class="section-heading">Worked Example</h2>';
    html += `<div class="section-text latex-content">${sanitizeText(topic.worked_example)}</div>`;
  }

  if (topic.when_to_use) {
    html += '<h2 class="section-heading">When to Use</h2>';
    html += `<div class="section-text">${escapeHtml(topic.when_to_use)}</div>`;
  }

  if (topic.variants && topic.variants.length > 0) {
    html += '<h2 class="section-heading">Variants</h2>';
    html += '<ul class="section-list">';
    topic.variants.forEach((variant) => {
      html += `<li>${escapeHtml(variant)}</li>`;
    });
    html += "</ul>";
  }

  if (topic.pitfalls && topic.pitfalls.length > 0) {
    html += '<h2 class="section-heading">Common Pitfalls</h2>';
    html += '<ul class="section-list">';
    topic.pitfalls.forEach((pitfall) => {
      html += `<li>${escapeHtml(pitfall)}</li>`;
    });
    html += "</ul>";
  }

  if (topic.proof) {
    html += '<h2 class="section-heading">Proof</h2>';
    // Proofs are most likely to contain LaTeX — keep raw
    html += `<div class="section-text latex-content">${sanitizeText(topic.proof)}</div>`;
  }

  if (topic.cpp) {
    html += '<h2 class="section-heading">Implementation</h2>';
    html += '<div class="code-section">';
    html +=
      '<div class="code-header"><span class="code-title">C++</span></div>';
    html += '<div class="code-block">';
    html += `<pre><code class="language-cpp">${escapeHtml(topic.cpp)}</code></pre>`;
    html += "</div></div>";
  }

  if (topic.walkthrough) {
    html += '<h2 class="section-heading">Code Walkthrough</h2>';
    html += `<div class="section-text">${escapeHtml(topic.walkthrough)}</div>`;
  }

  if (topic.dry_run) {
    html += '<h2 class="section-heading">Dry Run</h2>';
    html += '<div class="code-section">';
    html += '<div class="code-block no-header">';
    html += `<pre><code>${escapeHtml(topic.dry_run)}</code></pre>`;
    html += "</div></div>";
  }

  if (topic.usage_example) {
    html += '<h2 class="section-heading">Usage Example</h2>';
    html += '<div class="code-section">';
    html += '<div class="code-block no-header">';
    html += `<pre><code class="language-cpp">${escapeHtml(topic.usage_example)}</code></pre>`;
    html += "</div></div>";
  }

  if (topic.cpp_notes && topic.cpp_notes.length > 0) {
    html += '<h2 class="section-heading">Implementation Notes</h2>';
    html += '<ul class="section-list">';
    topic.cpp_notes.forEach((note) => {
      html += `<li>${escapeHtml(note)}</li>`;
    });
    html += "</ul>";
  }

  if (topic.prereqs && topic.prereqs.length > 0) {
    html += '<h2 class="section-heading">Prerequisites</h2>';
    html += '<div class="section-tags">';
    topic.prereqs.forEach((prereq) => {
      html += `<span class="tag">${escapeHtml(prereq)}</span>`;
    });
    html += "</div>";
  }

  if (topic.leads_to && topic.leads_to.length > 0) {
    html += '<h2 class="section-heading">Advanced Topics</h2>';
    html += '<div class="section-tags">';
    topic.leads_to.forEach((lead) => {
      html += `<span class="tag">${escapeHtml(lead)}</span>`;
    });
    html += "</div>";
  }

  topicContent.innerHTML = html;

  // Apply syntax highlighting to all code blocks
  topicContent.querySelectorAll("pre code").forEach((block) => {
    hljs.highlightElement(block);
  });

  // Typeset any LaTeX in the newly rendered content
  if (window.MathJax && window.MathJax.typesetPromise) {
    window.MathJax.typesetPromise([topicContent]).catch((err) =>
      console.error("MathJax error:", err),
    );
  }
}

function sanitizeText(text) {
  if (!text) return "";
  // Escape HTML first
  const div = document.createElement("div");
  div.textContent = text;
  let escaped = div.innerHTML;
  // Restore LaTeX-relevant characters that got escaped
  escaped = escaped
    .replace(/&amp;/g, "&") // & used in \begin{align} etc.
    .replace(/\\\(/g, "\\(")
    .replace(/\\\)/g, "\\)")
    .replace(/\\\[/g, "\\[")
    .replace(/\\\]/g, "\\]");
  return escaped;
}

function updateActiveLink(slug) {
  const links = document.querySelectorAll(".topic-link");
  links.forEach((link) => {
    if (link.dataset.slug === slug) {
      link.classList.add("active");
      // Auto-expand the parent category if it's collapsed
      const section = link.closest(".category-section");
      if (section && section.classList.contains("collapsed")) {
        section.classList.remove("collapsed");
        const state = getCollapsedState();
        const title = section.querySelector(".category-title");
        if (title) delete state[title.textContent];
        setCollapsedState(state);
      }
    } else {
      link.classList.remove("active");
    }
  });
}

function showWelcome() {
  const welcomeScreen = document.getElementById("welcome-screen");
  const topicContent = document.getElementById("topic-content");

  welcomeScreen.style.display = "block";
  topicContent.style.display = "none";

  const links = document.querySelectorAll(".topic-link");
  links.forEach((link) => link.classList.remove("active"));
}

function escapeHtml(text) {
  if (!text) return "";
  const div = document.createElement("div");
  div.textContent = text;
  return div.innerHTML;
}
