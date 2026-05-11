let currentTopics = {};
let currentSlug = null;

// ── Search Index ──────────────────────────────────────────────────────────────
let searchIndex = []; // [{slug, title, category, tags, fields:{…}}]
let searchIndexReady = false;
let searchIndexBuilding = false;

const FIELD_LABELS = {
  description: "description",
  explanation: "explanation",
  key_insight: "key insight",
  worked_example: "example",
  when_to_use: "when to use",
  variants: "variants",
  pitfalls: "pitfalls",
  prereqs: "prerequisites",
  leads_to: "advanced topics",
  cpp_notes: "notes",
  walkthrough: "walkthrough",
  proof: "proof",
};

function buildIndexEntry(topic) {
  return {
    slug: topic.slug || "",
    title: (topic.title || "").toLowerCase(),
    titleRaw: topic.title || "",
    category: (topic.category || "").toLowerCase(),
    tags: (topic.tags || []).map((t) => t.toLowerCase()),
    fields: {
      description: topic.description || "",
      explanation: topic.explanation || "",
      key_insight: topic.key_insight || "",
      worked_example: topic.worked_example || "",
      when_to_use: topic.when_to_use || "",
      variants: (topic.variants || []).join(" "),
      pitfalls: (topic.pitfalls || []).join(" "),
      prereqs: (topic.prereqs || []).join(" "),
      leads_to: (topic.leads_to || []).join(" "),
      cpp_notes: (topic.cpp_notes || []).join(" "),
      walkthrough: topic.walkthrough || "",
      proof: topic.proof || "",
    },
  };
}

function setSearchStatus(state) {
  // state: 'building' | 'ready' | ''
  const el = document.getElementById("search-status");
  if (!el) return;
  el.dataset.state = state;
  if (state === "building") {
    el.textContent = "Building index…";
    el.title = "Indexing all topic content for deep search";
  } else if (state === "ready") {
    el.textContent = "Full search ready";
    el.title = "Searching across titles, tags, and all topic content";
    // fade out after 2.5 s
    setTimeout(() => {
      el.style.opacity = "0";
      setTimeout(() => {
        el.dataset.state = "";
        el.style.opacity = "";
      }, 400);
    }, 2500);
  }
}

async function buildSearchIndex(categories) {
  if (searchIndexBuilding) return;
  searchIndexBuilding = true;
  setSearchStatus("building");

  const allTopics = [];
  Object.values(categories).forEach((topics) => allTopics.push(...topics));

  const BATCH = 6;
  for (let i = 0; i < allTopics.length; i += BATCH) {
    const batch = allTopics.slice(i, i + BATCH);
    await Promise.all(
      batch.map(async ({ slug }) => {
        try {
          const res = await fetch(`/api/topic/${slug}`);
          const topic = await res.json();
          if (!topic.error) searchIndex.push(buildIndexEntry(topic));
        } catch {
          /* silently skip */
        }
      }),
    );
  }

  searchIndexReady = true;
  setSearchStatus("ready");

  // Re-run any active query with the new full index
  const searchInput = document.getElementById("sidebar-search");
  const q = searchInput?.value?.trim();
  if (q) filterTopics(q);
}

// ── Full-text match using the index ─────────────────────────────────────────
function getIndexMatch(slug, q) {
  const entry = searchIndex.find((e) => e.slug === slug);
  if (!entry) {
    // Index not yet populated for this slug — fall back to title
    return null;
  }

  const matchIn = [];
  if (entry.title.includes(q)) matchIn.push("title");
  if (entry.category.includes(q)) matchIn.push("category");
  if (entry.tags.some((t) => t.includes(q))) matchIn.push("tags");
  Object.entries(entry.fields).forEach(([field, text]) => {
    if (text.toLowerCase().includes(q)) matchIn.push(field);
  });

  return matchIn.length ? matchIn : null;
}

// ── Collapsed state ──────────────────────────────────────────────────────────
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

// ── DOMContentLoaded ─────────────────────────────────────────────────────────
document.addEventListener("DOMContentLoaded", () => {
  loadTopics();

  window.addEventListener("popstate", (e) => {
    if (e.state?.slug) loadTopic(e.state.slug, false);
    else showWelcome();
  });

  const urlParams = new URLSearchParams(window.location.search);
  const slugParam = urlParams.get("topic");
  if (slugParam) loadTopic(slugParam, false);

  // Navbar scroll shadow
  const navbar = document.getElementById("navbar");
  window.addEventListener("scroll", () => {
    navbar?.classList.toggle("scrolled", window.scrollY > 4);
  });

  // ── Mobile sidebar ──
  const hamburger = document.getElementById("hamburger-btn");
  const sidebar = document.getElementById("sidebar");
  const overlay = document.getElementById("sidebar-overlay");

  const openSidebar = () => {
    sidebar.classList.add("open");
    overlay.classList.add("active");
    document.body.style.overflow = "hidden";
  };
  const closeSidebar = () => {
    sidebar.classList.remove("open");
    overlay.classList.remove("active");
    document.body.style.overflow = "";
  };

  hamburger?.addEventListener("click", openSidebar);
  overlay?.addEventListener("click", closeSidebar);

  document.getElementById("sidebar-nav")?.addEventListener("click", (e) => {
    if (e.target.closest(".topic-link") && window.innerWidth <= 768)
      closeSidebar();
  });

  // ── Theme ──
  const saved = localStorage.getItem("theme");
  if (saved) document.documentElement.setAttribute("data-theme", saved);

  document.getElementById("theme-toggle")?.addEventListener("click", () => {
    const isDark =
      document.documentElement.getAttribute("data-theme") === "dark";
    const next = isDark ? "light" : "dark";
    document.documentElement.setAttribute("data-theme", next);
    localStorage.setItem("theme", next);
  });

  // ── Sidebar search ──
  const searchInput = document.getElementById("sidebar-search");
  const clearBtn = document.getElementById("search-clear-btn");

  searchInput?.addEventListener("input", (e) => {
    const q = e.target.value.trim();
    clearBtn?.classList.toggle("visible", q.length > 0);
    filterTopics(q);
  });

  clearBtn?.addEventListener("click", () => {
    searchInput.value = "";
    clearBtn.classList.remove("visible");
    filterTopics("");
    searchInput.focus();
  });
});

// ── Filter / search ──────────────────────────────────────────────────────────
function filterTopics(query) {
  const nav = document.getElementById("sidebar-nav");
  const noResults = document.getElementById("search-no-results");
  const q = query.toLowerCase().trim();

  // ── Empty query: full reset, then done ──
  if (!q) {
    nav.querySelectorAll(".category-section").forEach((section) => {
      section.style.display = "";
    });
    nav.querySelectorAll(".topic-item").forEach((item) => {
      item.style.display = "";
      const link = item.querySelector(".topic-link");
      if (!link) return;
      const title = link.dataset.title || "";
      setLinkTitle(link, title, "", "");
      setLinkHint(link, []);
    });
    noResults?.classList.remove("visible");
    return;
  }

  // ── Non-empty query: filter ──
  let totalVisible = 0;

  nav.querySelectorAll(".category-section").forEach((section) => {
    const items = section.querySelectorAll(".topic-item");
    let sectionVisible = 0;

    items.forEach((item) => {
      const link = item.querySelector(".topic-link");
      if (!link) return;
      const slug = link.dataset.slug;
      const title = link.dataset.title || "";

      let matchIn = null;
      if (searchIndexReady) {
        matchIn = getIndexMatch(slug, q);
      } else {
        // Index still building — title-only fallback
        if (title.toLowerCase().includes(q)) matchIn = ["title"];
      }

      if (matchIn) {
        item.style.display = "";
        sectionVisible++;
        setLinkTitle(link, title, matchIn.includes("title") ? q : "", "title");
        setLinkHint(
          link,
          matchIn.filter((f) => f !== "title"),
        );
      } else {
        item.style.display = "none";
        setLinkTitle(link, title, "", "");
        setLinkHint(link, []);
      }
    });

    section.style.display = sectionVisible > 0 ? "" : "none";
    if (sectionVisible > 0) section.classList.remove("collapsed");
    totalVisible += sectionVisible;
  });

  noResults?.classList.toggle("visible", totalVisible === 0);
}

function setLinkTitle(link, title, q, matchType) {
  const titleEl = link.querySelector(".topic-link-title");
  if (!titleEl) {
    link.textContent = title;
    return;
  }

  if (q && matchType === "title") {
    const idx = title.toLowerCase().indexOf(q);
    if (idx === -1) {
      titleEl.textContent = title;
      return;
    }
    titleEl.innerHTML =
      escapeHtml(title.slice(0, idx)) +
      "<mark>" +
      escapeHtml(title.slice(idx, idx + q.length)) +
      "</mark>" +
      escapeHtml(title.slice(idx + q.length));
  } else {
    titleEl.textContent = title;
  }
}

function setLinkHint(link, fields) {
  const hintEl = link.querySelector(".topic-link-hint");
  if (!hintEl) return;
  if (!fields.length) {
    hintEl.textContent = "";
    hintEl.style.display = "none";
    return;
  }
  const labels = fields.slice(0, 3).map((f) => FIELD_LABELS[f] || f);
  hintEl.textContent = "in " + labels.join(", ");
  hintEl.style.display = "";
}

// ── Load topics list ─────────────────────────────────────────────────────────
async function loadTopics() {
  try {
    const response = await fetch("api/topics");
    currentTopics = await response.json();
    renderSidebar(currentTopics);
    // Kick off background full-text indexing
    buildSearchIndex(currentTopics);
  } catch (error) {
    console.error("Error loading topics:", error);
  }
}

// ── Render sidebar ───────────────────────────────────────────────────────────
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

      // Header
      const categoryHeader = document.createElement("div");
      categoryHeader.className = "category-header";

      const categoryTitle = document.createElement("span");
      categoryTitle.className = "category-title";
      categoryTitle.textContent = category;

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
      const polyline = document.createElementNS(
        "http://www.w3.org/2000/svg",
        "polyline",
      );
      polyline.setAttribute("points", "4 6 8 10 12 6");
      chevron.appendChild(polyline);

      categoryHeader.appendChild(categoryTitle);
      categoryHeader.appendChild(chevron);
      categoryHeader.addEventListener("click", () => {
        const isNowCollapsed = categorySection.classList.toggle("collapsed");
        const state = getCollapsedState();
        if (isNowCollapsed) state[category] = true;
        else delete state[category];
        setCollapsedState(state);
      });

      // Topic list
      const topicList = document.createElement("ul");
      topicList.className = "topic-list";

      categories[category].forEach((topic) => {
        const topicItem = document.createElement("li");
        topicItem.className = "topic-item";

        const topicLink = document.createElement("a");
        topicLink.className = "topic-link";
        topicLink.dataset.slug = topic.slug;
        topicLink.dataset.title = topic.title;

        // Inner structure: title span + hint span
        const titleSpan = document.createElement("span");
        titleSpan.className = "topic-link-title";
        titleSpan.textContent = topic.title;

        const hintSpan = document.createElement("span");
        hintSpan.className = "topic-link-hint";
        hintSpan.style.display = "none";

        topicLink.appendChild(titleSpan);
        topicLink.appendChild(hintSpan);

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

// ── Load and display a topic ─────────────────────────────────────────────────
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

  if (topic.tags?.length) {
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
    if (topic.time_complexity)
      html += `<span class="complexity-badge">Time: ${escapeHtml(topic.time_complexity)}</span>`;
    if (topic.space_complexity)
      html += `<span class="complexity-badge">Space: ${escapeHtml(topic.space_complexity)}</span>`;
    html += "</div>";
  }

  html += '<div class="divider"></div>';

  if (topic.explanation) {
    html += '<h2 class="section-heading">Explanation</h2>';
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

  if (topic.variants?.length) {
    html +=
      '<h2 class="section-heading">Variants</h2><ul class="section-list">';
    topic.variants.forEach((v) => {
      html += `<li>${escapeHtml(v)}</li>`;
    });
    html += "</ul>";
  }

  if (topic.pitfalls?.length) {
    html +=
      '<h2 class="section-heading">Common Pitfalls</h2><ul class="section-list">';
    topic.pitfalls.forEach((p) => {
      html += `<li>${escapeHtml(p)}</li>`;
    });
    html += "</ul>";
  }

  if (topic.proof) {
    html += '<h2 class="section-heading">Proof</h2>';
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
    html += '<div class="code-section"><div class="code-block no-header">';
    html += `<pre><code>${escapeHtml(topic.dry_run)}</code></pre>`;
    html += "</div></div>";
  }

  if (topic.usage_example) {
    html += '<h2 class="section-heading">Usage Example</h2>';
    html += '<div class="code-section"><div class="code-block no-header">';
    html += `<pre><code class="language-cpp">${escapeHtml(topic.usage_example)}</code></pre>`;
    html += "</div></div>";
  }

  if (topic.cpp_notes?.length) {
    html +=
      '<h2 class="section-heading">Implementation Notes</h2><ul class="section-list">';
    topic.cpp_notes.forEach((n) => {
      html += `<li>${escapeHtml(n)}</li>`;
    });
    html += "</ul>";
  }

  if (topic.prereqs?.length) {
    html +=
      '<h2 class="section-heading">Prerequisites</h2><div class="section-tags">';
    topic.prereqs.forEach((p) => {
      html += `<span class="tag">${escapeHtml(p)}</span>`;
    });
    html += "</div>";
  }

  if (topic.leads_to?.length) {
    html +=
      '<h2 class="section-heading">Advanced Topics</h2><div class="section-tags">';
    topic.leads_to.forEach((l) => {
      html += `<span class="tag">${escapeHtml(l)}</span>`;
    });
    html += "</div>";
  }

  topicContent.innerHTML = html;

  topicContent
    .querySelectorAll("pre code")
    .forEach((block) => hljs.highlightElement(block));

  if (window.MathJax?.typesetPromise) {
    window.MathJax.typesetPromise([topicContent]).catch((err) =>
      console.error("MathJax error:", err),
    );
  }
}

// ── Helpers ──────────────────────────────────────────────────────────────────
function sanitizeText(text) {
  if (!text) return "";
  const div = document.createElement("div");
  div.textContent = text;
  let escaped = div.innerHTML;
  escaped = escaped
    .replace(/&amp;/g, "&")
    .replace(/\\\(/g, "\\(")
    .replace(/\\\)/g, "\\)")
    .replace(/\\\[/g, "\\[")
    .replace(/\\\]/g, "\\]");
  return escaped;
}

function updateActiveLink(slug) {
  document.querySelectorAll(".topic-link").forEach((link) => {
    if (link.dataset.slug === slug) {
      link.classList.add("active");
      const section = link.closest(".category-section");
      if (section?.classList.contains("collapsed")) {
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
  document.getElementById("welcome-screen").style.display = "block";
  document.getElementById("topic-content").style.display = "none";
  document
    .querySelectorAll(".topic-link")
    .forEach((l) => l.classList.remove("active"));
}

function escapeHtml(text) {
  if (!text) return "";
  const div = document.createElement("div");
  div.textContent = text;
  return div.innerHTML;
}
