const OWNER = "ALI88708";
const REPOSITORY = "CloudMesh";
const RELEASES_ENDPOINT = `https://api.github.com/repos/${OWNER}/${REPOSITORY}/releases`;
const CACHE_KEY = "cloudmesh-site-releases-v1";

const releaseList = document.querySelector("#release-list");
const releaseStatus = document.querySelector("#release-status");

function setStatus(message, { error = false, loading = false } = {}) {
  releaseStatus.replaceChildren();
  releaseStatus.hidden = false;
  releaseStatus.classList.toggle("is-error", error);

  if (loading) {
    const spinner = document.createElement("span");
    spinner.className = "loading-spinner";
    spinner.setAttribute("aria-hidden", "true");
    releaseStatus.append(spinner);
  }

  const text = document.createElement("span");
  text.textContent = message;
  releaseStatus.append(text);
}

function addLink(parent, label, href, className) {
  let target;
  try {
    target = new URL(href);
  } catch (error) {
    console.warn("Skipping invalid GitHub release URL:", href, error);
    return null;
  }
  if (target.protocol !== "https:" || target.hostname !== "github.com") {
    console.warn("Skipping non-GitHub release URL:", href);
    return null;
  }

  const link = document.createElement("a");
  link.className = className;
  link.href = target.href;
  link.textContent = label;
  link.target = "_blank";
  link.rel = "noreferrer";
  parent.append(link);
  return link;
}

function formatDate(dateValue) {
  const date = new Date(dateValue);
  if (Number.isNaN(date.getTime())) {
    return "Date unavailable";
  }
  return new Intl.DateTimeFormat(undefined, {
    year: "numeric",
    month: "short",
    day: "numeric",
    timeZone: "UTC",
  }).format(date);
}

function createReleaseCard(release, isLatest) {
  const card = document.createElement("article");
  card.className = "release-card";

  const topLine = document.createElement("div");
  topLine.className = "release-topline";

  const title = document.createElement("h3");
  title.className = "release-title";
  addLink(title, release.tag_name || "Release", release.html_url, "");

  const tag = document.createElement("span");
  tag.className = "release-tag";
  tag.textContent = release.tag_name || "untagged";
  title.append(tag);

  if (isLatest) {
    const latest = document.createElement("span");
    latest.className = "latest-label";
    latest.textContent = "LATEST";
    title.append(latest);
  }

  const date = document.createElement("time");
  date.className = "release-date";
  const releaseDate = release.published_at || release.created_at;
  date.dateTime = releaseDate || "";
  date.textContent = formatDate(releaseDate);

  topLine.append(title, date);
  card.append(topLine);

  if (release.name && release.name !== release.tag_name) {
    const name = document.createElement("p");
    name.className = "release-name";
    name.textContent = release.name;
    card.append(name);
  }

  if (release.body) {
    const notes = document.createElement("p");
    notes.className = "release-notes";
    notes.textContent = release.body.trim();
    card.append(notes);
  } else {
    const notes = document.createElement("p");
    notes.className = "release-notes";
    notes.textContent = "No release notes were provided.";
    card.append(notes);
  }

  const bottom = document.createElement("div");
  bottom.className = "release-bottom";

  if (Array.isArray(release.assets)) {
    for (const asset of release.assets) {
      if (!asset.browser_download_url) {
        continue;
      }
      const size = Number.isFinite(asset.size)
        ? ` · ${(asset.size / (1024 * 1024)).toFixed(1)} MB`
        : "";
      addLink(
        bottom,
        `${asset.name || "Download"}${size}`,
        asset.browser_download_url,
        "release-download",
      );
    }
  }

  addLink(
    bottom,
    "Release page & downloads ↗",
    release.html_url,
    `release-source${bottom.childElementCount === 0 ? " primary-download" : ""}`,
  );
  card.append(bottom);
  return card;
}

function renderReleases(releases, { cached = false } = {}) {
  releaseList.replaceChildren();
  const published = releases.filter((release) => !release.draft);

  if (published.length === 0) {
    setStatus("No published releases yet. New GitHub releases will appear here automatically.");
    return;
  }

  const fragment = document.createDocumentFragment();
  published.forEach((release, index) => {
    fragment.append(createReleaseCard(release, index === 0));
  });
  releaseList.append(fragment);
  releaseStatus.hidden = true;

  if (cached) {
    setStatus("Showing the last saved release list. GitHub could not be reached just now.", {
      error: true,
    });
  }
}

function readCache() {
  try {
    const cached = JSON.parse(localStorage.getItem(CACHE_KEY) || "null");
    if (cached && Array.isArray(cached.releases)) {
      return cached.releases;
    }
  } catch (error) {
    console.warn("Could not read cached CloudMesh releases:", error);
  }
  return null;
}

function saveCache(releases) {
  try {
    localStorage.setItem(
      CACHE_KEY,
      JSON.stringify({ savedAt: Date.now(), releases }),
    );
  } catch (error) {
    console.warn("Could not cache CloudMesh releases:", error);
  }
}

async function fetchReleases() {
  const releases = [];
  let page = 1;

  while (true) {
    const response = await fetch(
      `${RELEASES_ENDPOINT}?per_page=100&page=${page}`,
      { headers: { Accept: "application/vnd.github+json" } },
    );
    if (!response.ok) {
      throw new Error(`GitHub returned HTTP ${response.status}`);
    }

    const batch = await response.json();
    if (!Array.isArray(batch)) {
      throw new Error("GitHub returned an unexpected release response");
    }

    releases.push(...batch);
    if (batch.length < 100) {
      return releases;
    }
    page += 1;
  }
}

async function loadReleases() {
  setStatus("Loading releases from GitHub…", { loading: true });
  try {
    const releases = await fetchReleases();
    saveCache(releases);
    renderReleases(releases);
  } catch (error) {
    const cached = readCache();
    if (cached) {
      renderReleases(cached, { cached: true });
      return;
    }

    console.error("Could not load CloudMesh releases:", error);
    setStatus(
      "Couldn't load releases right now. Visit GitHub to view versions and downloads.",
      { error: true },
    );
    addLink(
      releaseStatus,
      "Open GitHub releases ↗",
      `https://github.com/${OWNER}/${REPOSITORY}/releases`,
      "release-source",
    );
  }
}

loadReleases();
