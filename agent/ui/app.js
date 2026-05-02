const PRESETS = {
  basic: "Hi, I'm alex@example.com. My AWS key is AKIAIOSFODNN7EXAMPLE and my IBAN is GB29NWBK60161331926819.",
  leak: "Quick update on Project Halcyon — we hit the milestone for the London demo, ready to ship next week.",
  variant: "Heads up: the Halcyon launch is locked for next week, and the Halcyon team will be on site.",
};

const $ = (id) => document.getElementById(id);

async function refreshStats() {
  try {
    const r = await fetch("/stats");
    const j = await r.json();
    $("rule-count").textContent = j.learned_rules ?? "0";
  } catch (e) {
    $("rule-count").textContent = "!";
  }
}

function escapeHtml(s) {
  return s
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;");
}

function renderRedacted(text, regexHits, semanticHits) {
  const ranges = [];
  for (const h of regexHits) {
    const idx = text.indexOf(h.value);
    if (idx >= 0) ranges.push({ start: idx, end: idx + h.value.length, kind: "regex", label: h.type });
  }
  for (const h of semanticHits) {
    let idx = 0;
    while (true) {
      const found = text.indexOf(h.example, idx);
      if (found < 0) break;
      ranges.push({ start: found, end: found + h.example.length, kind: "semantic", label: h.label });
      idx = found + 1;
    }
    const tokens = h.example.split(/\s+/).filter((t) => t.length >= 4);
    for (const tok of tokens) {
      const re = new RegExp("\\b" + tok.replace(/[.*+?^${}()|[\]\\]/g, "\\$&") + "\\b", "gi");
      let m;
      while ((m = re.exec(text)) !== null) {
        ranges.push({ start: m.index, end: m.index + m[0].length, kind: "semantic", label: h.label });
      }
    }
  }

  ranges.sort((a, b) => a.start - b.start);
  const merged = [];
  for (const r of ranges) {
    const last = merged[merged.length - 1];
    if (last && r.start <= last.end) {
      last.end = Math.max(last.end, r.end);
      if (r.kind === "regex") last.kind = "regex";
    } else {
      merged.push({ ...r });
    }
  }

  let out = "";
  let cursor = 0;
  for (const r of merged) {
    out += escapeHtml(text.slice(cursor, r.start));
    const cls = r.kind === "regex" ? "tok-regex" : "tok-semantic";
    out += `<span class="${cls}">&lt;${escapeHtml(r.label)}&gt;</span>`;
    cursor = r.end;
  }
  out += escapeHtml(text.slice(cursor));
  return out;
}

function renderMatches(regexHits, semanticHits) {
  const ul = $("matches");
  ul.innerHTML = "";
  if (regexHits.length === 0 && semanticHits.length === 0) {
    ul.innerHTML = '<li class="empty">no matches</li>';
    return;
  }
  for (const h of regexHits) {
    const li = document.createElement("li");
    li.className = "regex";
    li.innerHTML = `<span class="badge">REGEX</span>${escapeHtml(h.type)} → ${escapeHtml(h.value)}`;
    ul.appendChild(li);
  }
  for (const h of semanticHits) {
    const li = document.createElement("li");
    li.className = "semantic";
    li.innerHTML = `<span class="badge">SEMANTIC</span>${escapeHtml(h.label)} → "${escapeHtml(h.example)}" (score ${h.score})`;
    ul.appendChild(li);
  }
}

function renderSuggestions(text, suggestions) {
  const ul = $("suggestions");
  ul.innerHTML = "";
  if (!suggestions || suggestions.length === 0) {
    ul.innerHTML = '<li class="empty">no extra suggestions — looks clean to the agent</li>';
    return;
  }
  for (const s of suggestions) {
    const li = document.createElement("li");
    li.className = "suggestion";
    li.innerHTML = `
      <span class="span">"${escapeHtml(s.text)}"</span>
      <span class="label">${escapeHtml(s.label)}</span>
      <span class="score">${s.score}</span>
      <button data-text="${escapeHtml(s.text)}" data-label="${escapeHtml(s.label.toUpperCase().replace(/\s+/g, "_"))}">Remember</button>
    `;
    li.querySelector("button").addEventListener("click", async (ev) => {
      const btn = ev.target;
      btn.disabled = true;
      btn.textContent = "saving…";
      try {
        await fetch("/correct", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            label: btn.dataset.label,
            example: btn.dataset.text,
            context: "agent-suggested",
            reason: `Flagged by local NER as "${s.label}" (score ${s.score})`,
          }),
        });
        li.classList.add("accepted");
        btn.textContent = "remembered ✓";
        refreshStats();
      } catch (err) {
        btn.textContent = "error";
      }
    });
    ul.appendChild(li);
  }
}

async function onScan() {
  const text = $("scan-input").value.trim();
  if (!text) return;
  const btn = $("scan-btn");
  btn.disabled = true;
  btn.textContent = "Scanning…";
  $("suggestions").innerHTML = '<li class="empty">agent thinking…</li>';
  $("scan-output").classList.remove("hidden");
  try {
    const [scanResp, suggestResp] = await Promise.all([
      fetch("/scan", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ text }),
      }).then((r) => r.json()),
      fetch("/suggest", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ text }),
      }).then((r) => r.json()),
    ]);
    $("redacted").innerHTML = renderRedacted(text, scanResp.regex_matches, scanResp.semantic_matches);
    renderMatches(scanResp.regex_matches, scanResp.semantic_matches);
    renderSuggestions(text, suggestResp.suggestions);
  } catch (e) {
    $("redacted").textContent = "error: " + e.message;
  } finally {
    btn.disabled = false;
    btn.textContent = "Scan";
  }
}

async function onTeach() {
  const label = $("teach-label").value.trim();
  const example = $("teach-example").value.trim();
  if (!label || !example) {
    showTeach("label and example required", true);
    return;
  }
  const btn = $("teach-btn");
  btn.disabled = true;
  btn.textContent = "Saving…";
  try {
    const r = await fetch("/correct", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        label,
        example,
        context: $("teach-context").value.trim(),
        reason: $("teach-reason").value.trim(),
      }),
    });
    const j = await r.json();
    showTeach(`✓ remembered (id: ${j.id.slice(0, 8)}…) · ${j.total_rules} rules in Atlas`);
    refreshStats();
  } catch (e) {
    showTeach("error: " + e.message, true);
  } finally {
    btn.disabled = false;
    btn.textContent = "Remember";
  }
}

function showTeach(msg, isError = false) {
  const el = $("teach-output");
  el.innerHTML = `<span class="toast${isError ? " error" : ""}">${escapeHtml(msg)}</span>`;
  el.classList.remove("hidden");
}

document.querySelectorAll(".preset").forEach((b) => {
  b.addEventListener("click", () => {
    $("scan-input").value = PRESETS[b.dataset.preset] || "";
    $("scan-input").focus();
  });
});

$("scan-btn").addEventListener("click", onScan);
$("teach-btn").addEventListener("click", onTeach);

$("scan-input").addEventListener("keydown", (e) => {
  if ((e.metaKey || e.ctrlKey) && e.key === "Enter") onScan();
});

refreshStats();
