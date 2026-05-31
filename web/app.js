const $ = (id) => document.getElementById(id);

// ------- i18n -------
const I18N = {
  en: {
    token_h: "Discord token",
    token_hint: 'Your token never leaves this machine. It\'s stored in <code>config.json</code> next to the app.',
    token_help: "How do I get my token?",
    token_warn: "Treat your token like a password. Anyone with it can read every channel you can see.",
    subs_h: "What to listen for",
    subs_hint: "You'll get a notification any time any of the listed users post in the listed channel. Separate multiple usernames with commas or spaces.",
    th_channel: "Channel ID",
    th_users: "Usernames (comma- or space-separated)",
    th_label: "Label (optional)",
    add_sub: "+ Add subscription",
    notify_h: "Notifications",
    notify_mac: "macOS desktop notification",
    notify_webhook: "Discord webhook URL (optional)",
    notify_test: "Send test notification",
    btn_save: "Save", btn_start: "Start listening", btn_stop: "Stop",
    hits_h: "Recent hits",
    saved: "Saved", listening: "Listening", stopped: "Stopped",
    test_sent: "Sent — check your notifications",
    nothing: "nothing yet — waiting…",
    image_only: "(image / embed only)",
    status_connected: "connected", status_starting: "starting…", status_stopped: "stopped",
  },
  zh: {
    token_h: "Discord 令牌",
    token_hint: '令牌只保存在你的电脑上，写到应用同目录的 <code>config.json</code> 里。',
    token_help: "怎么获取我的 token？",
    token_warn: "把令牌当密码看待。任何拿到它的人都能读取你能看到的所有频道。",
    subs_h: "监听什么",
    subs_hint: "列表里的任何一个用户在指定频道发言时都会推送通知。多个用户名用逗号或空格分隔。",
    th_channel: "频道 ID",
    th_users: "用户名（逗号或空格分隔）",
    th_label: "备注（可选）",
    add_sub: "+ 添加订阅",
    notify_h: "通知方式",
    notify_mac: "macOS 桌面通知",
    notify_webhook: "Discord webhook URL（可选）",
    notify_test: "发送测试通知",
    btn_save: "保存", btn_start: "开始监听", btn_stop: "停止",
    hits_h: "最近收到",
    saved: "已保存", listening: "已开启", stopped: "已停止",
    test_sent: "已发送 — 检查你的通知中心",
    nothing: "暂无 — 等待中…",
    image_only: "（仅图片或嵌入内容）",
    status_connected: "已连接", status_starting: "连接中…", status_stopped: "已停止",
  },
};
let lang = (localStorage.getItem("lang") || (navigator.language || "").startsWith("zh") ? "zh" : "en");
function t(key) { return (I18N[lang] || I18N.en)[key] || key; }
function applyI18n() {
  document.querySelectorAll("[data-i18n]").forEach(el => el.textContent = t(el.dataset.i18n));
  document.querySelectorAll("[data-i18n-html]").forEach(el => el.innerHTML = t(el.dataset.i18nHtml) || el.innerHTML);
  document.documentElement.lang = lang;
}

// ------- state -------
let state = { token: "", subs: [], notify: { mac: true, webhook_url: "" } };

async function api(path, body) {
  const opts = { method: body !== undefined ? "POST" : "GET", headers: { "Content-Type": "application/json" } };
  if (body !== undefined) opts.body = JSON.stringify(body);
  const r = await fetch(path, opts);
  if (!r.ok) {
    let detail = `${r.status}`;
    try { const j = await r.json(); detail = JSON.stringify(j.detail || j); } catch {}
    throw new Error(detail);
  }
  return r.json();
}

function toast(msg, kind = "good") {
  const el = document.createElement("div");
  el.className = "toast " + (kind === "bad" ? "bad" : "good");
  el.textContent = msg;
  document.body.appendChild(el);
  requestAnimationFrame(() => el.classList.add("show"));
  setTimeout(() => { el.classList.remove("show"); setTimeout(() => el.remove(), 300); }, 2400);
}

function escapeAttr(s) { return String(s).replace(/"/g, "&quot;"); }
function escapeHtml(s) { return String(s).replace(/[&<>"]/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;"}[c])); }

function renderSubs() {
  const tbody = $("subs-body");
  tbody.innerHTML = state.subs.map((s, i) => `
    <tr>
      <td><input data-i="${i}" data-k="channel_id" value="${escapeAttr(s.channel_id || "")}" placeholder="123…"></td>
      <td><input data-i="${i}" data-k="usernames" value="${escapeAttr((s.usernames || []).join(", "))}" placeholder="alice, bob"></td>
      <td><input data-i="${i}" data-k="label" value="${escapeAttr(s.label || "")}" placeholder=""></td>
      <td><button class="danger" data-del="${i}">×</button></td>
    </tr>`).join("");
  tbody.querySelectorAll("input").forEach(inp => {
    inp.addEventListener("input", e => {
      const i = +e.target.dataset.i, k = e.target.dataset.k;
      if (k === "usernames") {
        // accept commas, spaces, mix.
        state.subs[i].usernames = e.target.value.split(/[\s,]+/).map(x => x.trim()).filter(Boolean);
      } else {
        state.subs[i][k] = e.target.value.trim();
      }
    });
  });
  tbody.querySelectorAll("button[data-del]").forEach(b => {
    b.addEventListener("click", e => {
      state.subs.splice(+e.target.dataset.del, 1);
      renderSubs();
    });
  });
}

async function load() {
  const c = await api("/api/config");
  state.subs = c.subscriptions.length
    ? c.subscriptions.map(s => ({ ...s, usernames: s.usernames || (s.username ? [s.username] : []) }))
    : [{ channel_id: "", usernames: [], label: "" }];
  state.notify = c.notify;
  $("token").placeholder = c.token_set ? "(token saved — paste again to replace)" : t("token_h");
  $("n-mac").checked = !!c.notify.mac;
  $("n-webhook").value = c.notify.webhook_url || "";
  renderSubs();
}

async function save() {
  const payload = {
    token: $("token").value.trim(),  // empty = keep existing
    subscriptions: state.subs.filter(s => s.channel_id && (s.usernames || []).length),
    notify: { mac: $("n-mac").checked, webhook_url: $("n-webhook").value.trim() },
  };
  try {
    await api("/api/config", payload);
    $("token").value = "";
    toast(t("saved"));
    await load();
    return true;
  } catch (e) {
    toast(e.message, "bad");
    return false;
  }
}

async function refreshStatus() {
  try {
    const s = await api("/api/status");
    const el = $("status");
    if (s.running && s.connected) {
      el.textContent = t("status_connected"); el.className = "status connected";
    } else if (s.running) {
      el.textContent = t("status_starting"); el.className = "status starting";
    } else if (s.last_error) {
      el.textContent = s.last_error; el.className = "status error";
    } else {
      el.textContent = t("status_stopped"); el.className = "status";
    }
    $("hits-count").textContent = s.hits.length ? `(${s.hits.length})` : "";
    $("hits").innerHTML = s.hits.map(h => {
      const labelTag = (h.label && h.label !== h.author)
        ? `<span class="label-tag">${escapeHtml(h.label)}</span>` : "";
      const body = h.content ? escapeHtml(h.content) : `<em style='color:var(--muted)'>${escapeHtml(t("image_only"))}</em>`;
      const ts = escapeHtml((h.timestamp || "").replace("T", " ").slice(0, 16));
      const where = h.channel_name ? `#${escapeHtml(h.channel_name)}` : `channel ${escapeHtml(h.channel_id)}`;
      const link = h.url ? `<a href="${escapeAttr(h.url)}" target="_blank" rel="noopener" style="color:var(--accent2);">↗</a>` : "";
      return `<li>
        <div>${labelTag}<span class="author">${escapeHtml(h.author)}</span>: <span class="content">${body}</span></div>
        <div class="hit-meta">${ts} · ${where} ${link}</div>
      </li>`;
    }).join("") || `<li class='hint'>${escapeHtml(t("nothing"))}</li>`;
  } catch (e) { /* swallow during boot */ }
}

// ------- bindings -------
$("lang").value = lang;
$("lang").addEventListener("change", e => {
  lang = e.target.value; localStorage.setItem("lang", lang);
  applyI18n(); load(); refreshStatus();
});
$("add-sub").addEventListener("click", () => {
  state.subs.push({ channel_id: "", usernames: [], label: "" });
  renderSubs();
});
$("save").addEventListener("click", save);
$("start").addEventListener("click", async () => {
  if (!await save()) return;
  try { await api("/api/start", {}); toast(t("listening")); }
  catch (e) { toast(e.message, "bad"); }
});
$("stop").addEventListener("click", async () => {
  await api("/api/stop", {}); toast(t("stopped"));
});
$("test-notify").addEventListener("click", async () => {
  if (!await save()) return;
  await api("/api/test-notify", {});
  toast(t("test_sent"));
});

applyI18n();
load();
setInterval(refreshStatus, 1500);
refreshStatus();
