const PRESETS = {
  apikey: "Hey can you help me debug this Stripe call: my key is sk_test_FAKEKEYFORLOCALDEMO000000 and the customer ID is cus_NhD8rfP7XKQy9Z",
  codename: "Quick update on Project Halcyon — we hit the milestone for the London demo, ready to ship next week.",
  variant: "Heads up: the Halcyon launch is locked for next week, and the Halcyon team will be on site.",
};

const $ = (id) => document.getElementById(id);
const chat = $("chat");

let lastMessages = [];

async function refreshStats() {
  try {
    const r = await fetch("/stats");
    const j = await r.json();
    $("rule-count").textContent = j.learned_rules ?? "0";
  } catch {
    $("rule-count").textContent = "!";
  }
}

function escapeHtml(s) {
  return String(s)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;");
}

function scrollDown() {
  chat.scrollTop = chat.scrollHeight;
}

function renderRedacted(text, regexHits, semanticHits) {
  const ranges = [];
  for (const h of regexHits) {
    let i = 0;
    while (true) {
      const idx = text.indexOf(h.value, i);
      if (idx < 0) break;
      ranges.push({ start: idx, end: idx + h.value.length, kind: "regex", label: h.type });
      i = idx + 1;
    }
  }
  for (const h of semanticHits) {
    const tokens = h.example.split(/\s+/).filter((t) => t.length >= 4);
    for (const tok of tokens) {
      const re = new RegExp("\\b" + tok.replace(/[.*+?^${}()|[\]\\]/g, "\\$&") + "\\b", "gi");
      let m;
      while ((m = re.exec(text)) !== null) {
        ranges.push({ start: m.index, end: m.index + m[0].length, kind: "semantic", label: h.label });
      }
    }
  }
  ranges.sort((a, b) => a.start - b.start || b.end - a.end);
  const merged = [];
  for (const r of ranges) {
    const last = merged[merged.length - 1];
    if (last && r.start < last.end) {
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

function appendUser(text) {
  const m = document.createElement("div");
  m.className = "msg user";
  m.innerHTML = `<div class="bubble">${escapeHtml(text)}</div>`;
  chat.appendChild(m);
  scrollDown();
}

function appendThinking() {
  const m = document.createElement("div");
  m.className = "msg agent";
  m.innerHTML = `<div class="agent-card"><span class="thinking">guardian thinking</span></div>`;
  chat.appendChild(m);
  scrollDown();
  return m;
}

function renderMatchChips(regexHits, semanticHits) {
  const parts = [];
  for (const h of regexHits) {
    parts.push(`<span class="match-chip regex">${escapeHtml(h.type)}: ${escapeHtml(h.value)}</span>`);
  }
  for (const h of semanticHits) {
    parts.push(`<span class="match-chip semantic">${escapeHtml(h.label)} ← memory (${h.score})</span>`);
  }
  if (!parts.length) return "";
  return `<div><div class="row-label">caught</div><div class="matches-row">${parts.join("")}</div></div>`;
}

function renderSuggestionPrompts(originalText, suggestions) {
  if (!suggestions || suggestions.length === 0) {
    return `<div><div class="row-label">agent suggests</div><div class="empty-suggest">nothing else stood out — looks clean to the local TinyML</div></div>`;
  }
  const blocks = suggestions
    .map((s, i) => {
      const labelSlug = s.label.toUpperCase().replace(/\s+/g, "_");
      return `
        <div class="prompt" data-idx="${i}">
          <span>I noticed</span>
          <span class="quoted">"${escapeHtml(s.text)}"</span>
          <span class="why">looks like a ${escapeHtml(s.label)} (${s.score}). Should I redact this and remember it for next time?</span>
          <div class="prompt-actions">
            <button class="btn-yes" data-action="yes" data-text="${escapeHtml(s.text)}" data-label="${escapeHtml(labelSlug)}" data-source-label="${escapeHtml(s.label)}" data-score="${s.score}">Yes</button>
            <button class="btn-no" data-action="no">No</button>
          </div>
        </div>`;
    })
    .join("");
  return `<div><div class="row-label">agent suggests <span style="color:var(--ink-faint);text-transform:none;letter-spacing:0;font-weight:normal;">· local TinyML, never leaves device</span></div><div class="suggestions">${blocks}</div></div>`;
}

function renderAgentCard(originalText, scanResp, suggestResp) {
  const card = document.createElement("div");
  card.className = "agent-card";
  const aiSeesHtml = renderRedacted(originalText, scanResp.regex_matches, scanResp.semantic_matches);
  card.innerHTML = `
    <div>
      <div class="row-label">what your AI agent would actually see</div>
      <div class="ai-sees">${aiSeesHtml}</div>
    </div>
    ${renderMatchChips(scanResp.regex_matches, scanResp.semantic_matches)}
    ${renderSuggestionPrompts(originalText, suggestResp.suggestions)}
  `;
  card.querySelectorAll(".prompt-actions button").forEach((btn) => {
    btn.addEventListener("click", async (ev) => {
      const target = ev.currentTarget;
      const prompt = target.closest(".prompt");
      const action = target.dataset.action;
      if (action === "no") {
        prompt.classList.add("resolved");
        prompt.insertAdjacentHTML("beforeend", `<span class="resolution">✗ ignored</span>`);
        return;
      }
      target.disabled = true;
      target.textContent = "saving…";
      try {
        await fetch("/correct", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            label: target.dataset.label,
            example: target.dataset.text,
            context: "agent-suggested in chat",
            reason: `Flagged by local NER as "${target.dataset.sourceLabel}" (score ${target.dataset.score})`,
          }),
        });
        prompt.classList.add("resolved");
        prompt.insertAdjacentHTML("beforeend", `<span class="resolution">✓ remembered · will catch every variant</span>`);
        refreshStats();
        const aiSees = card.querySelector(".ai-sees");
        const t = target.dataset.text;
        const lab = target.dataset.label;
        if (aiSees && t) {
          const re = new RegExp(t.replace(/[.*+?^${}()|[\]\\]/g, "\\$&"), "g");
          aiSees.innerHTML = aiSees.innerHTML.replace(
            re,
            `<span class="tok-tinyml">&lt;${escapeHtml(lab)}&gt;</span>`
          );
        }
      } catch (e) {
        target.textContent = "error";
      }
    });
  });
  return card;
}

async function send(text) {
  if (!text.trim()) return;
  appendUser(text);
  $("input").value = "";
  $("send").disabled = true;
  const thinking = appendThinking();

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

    const card = renderAgentCard(text, scanResp, suggestResp);
    thinking.replaceChildren(card);
    scrollDown();
  } catch (e) {
    thinking.innerHTML = `<div class="agent-card"><span style="color:var(--danger);font-family:var(--mono);font-size:12px;">error: ${escapeHtml(e.message)}</span></div>`;
  } finally {
    $("send").disabled = false;
    $("input").focus();
  }
}

document.querySelectorAll(".preset").forEach((b) => {
  b.addEventListener("click", () => {
    $("input").value = PRESETS[b.dataset.preset] || "";
    $("input").focus();
  });
});

$("composer").addEventListener("submit", (e) => {
  e.preventDefault();
  send($("input").value);
});

$("input").addEventListener("keydown", (e) => {
  if ((e.metaKey || e.ctrlKey) && e.key === "Enter") {
    e.preventDefault();
    send($("input").value);
  } else if (e.key === "Enter" && !e.shiftKey) {
    e.preventDefault();
    send($("input").value);
  }
});

refreshStats();
