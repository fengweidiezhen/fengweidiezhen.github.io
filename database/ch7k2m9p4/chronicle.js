(function () {
  "use strict";

  var SPEAKER_LABEL = {
    user: "用户",
    others: "他人",
    unknown: "未知",
    background: "背景",
    marker: "标记"
  };

  var TYPE_LABEL = {
    record: "对话",
    summary: "总结",
    day: "日期"
  };

  var state = {
    idList: [],
    userIdsWithData: {},
    meta: null,
    index: null,
    entries: [],
    entriesUserId: null,
    loadingUser: false,
    currentResults: [],
    activeIndex: -1,
    activeEntry: null,
    activeDoc: null,
    activeDocPath: null,
    scopedPool: [],
    detailFilter: "",
    hideBackground: false,
    cache: {}
  };

  var els = {};

  function $(id) {
    return document.getElementById(id);
  }

  function esc(s) {
    if (s == null) return "";
    return String(s)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }

  function parseKeywords(q) {
    return q.trim().split(/\s+/).filter(function (t) {
      return t.length > 0;
    });
  }

  function highlight(text, query) {
    var safe = esc(text);
    var terms = parseKeywords(query);
    if (!terms.length) return safe;
    terms.forEach(function (term) {
      try {
        var re = new RegExp("(" + term.replace(/[.*+?^${}()|[\]\\]/g, "\\$&") + ")", "gi");
        safe = safe.replace(re, "<mark>$1</mark>");
      } catch (e) { /* ignore */ }
    });
    return safe;
  }

  function textMatchesAll(text, terms) {
    if (!terms.length) return true;
    var lower = (text || "").toLowerCase();
    return terms.every(function (t) {
      return lower.indexOf(t.toLowerCase()) !== -1;
    });
  }

  function showError(msg) {
    els.error.hidden = false;
    els.error.textContent = msg;
  }

  function fetchJson(url) {
    return fetch(url).then(function (r) {
      if (!r.ok) throw new Error("无法加载 " + url + " (" + r.status + ")");
      return r.json();
    });
  }

  function buildDayList(pool) {
    var typeF = els.typeFilter.value;
    var days = {};

    pool.forEach(function (item) {
      var d = item.date;
      if (!d) return;
      if (!days[d]) {
        days[d] = {
          date: d,
          user_id: item.user_id,
          user_name: item.user_name,
          recordPath: null,
          summaryPath: null,
          recordItems: 0
        };
      }
      if (item.type === "record") {
        days[d].recordPath = item.path;
        days[d].recordItems++;
      }
      if (item.type === "summary") {
        days[d].summaryPath = item.path;
      }
    });

    var list = Object.keys(days).map(function (k) { return days[k]; });
    list = list.filter(function (day) {
      if (typeF === "record") return !!day.recordPath;
      if (typeF === "summary") return !!day.summaryPath;
      return day.recordPath || day.summaryPath;
    });
    list.sort(function (a, b) { return b.date.localeCompare(a.date); });

    return list.map(function (day) {
      var typeF = els.typeFilter.value;
      var viewType = "record";
      var path = day.recordPath;
      if (typeF === "summary" || (!day.recordPath && day.summaryPath)) {
        viewType = "summary";
        path = day.summaryPath;
      }
      if (!path) path = day.recordPath || day.summaryPath;
      var parts = [];
      if (day.recordPath) parts.push(day.recordItems + " 条对话");
      if (day.summaryPath) parts.push("有总结");
      var snippet = parts.join(" · ");
      return {
        item: {
          id: "day:" + day.user_id + ":" + day.date,
          type: "day",
          viewType: viewType,
          date: day.date,
          user_id: day.user_id,
          user_name: day.user_name,
          path: path,
          recordPath: day.recordPath,
          summaryPath: day.summaryPath,
          text: snippet,
          snippet: snippet
        },
        score: 0
      };
    });
  }

  function collectUserIdsWithData() {
    var set = {};
    if (state.meta && state.meta.users) {
      state.meta.users.forEach(function (u) {
        if (u.user_id) set[u.user_id] = true;
      });
    } else {
      state.entries.forEach(function (e) {
        if (e.user_id) set[e.user_id] = true;
      });
    }
    state.userIdsWithData = set;
    return set;
  }

  function populateUsers() {
    var select = els.userFilter;
    var selected = select.value;
    while (select.options.length > 1) select.remove(1);

    var withData = collectUserIdsWithData();
    var users = state.meta && state.meta.users ? state.meta.users.slice() : [];

    users.sort(function (a, b) {
      return (a.user_name || a.user_id).localeCompare(b.user_name || b.user_id, "zh-CN");
    });

    users.forEach(function (u) {
      var opt = document.createElement("option");
      opt.value = u.user_id;
      opt.textContent = (u.user_name || u.user_id) + "（" + u.entries + " 条）";
      select.appendChild(opt);
    });

    if (selected && withData[selected]) select.value = selected;
  }

  function loadUserEntries(userId) {
    if (!userId) {
      state.entries = [];
      state.entriesUserId = null;
      return Promise.resolve([]);
    }
    if (state.entriesUserId === userId && state.entries.length) {
      return Promise.resolve(state.entries);
    }

    if (state.index && state.index.entries) {
      state.entries = state.index.entries.filter(function (e) {
        return e.user_id === userId;
      });
      state.entriesUserId = userId;
      return Promise.resolve(state.entries);
    }

    state.loadingUser = true;
    els.stats.textContent = "正在加载用户索引…";

    return fetchJson("search-index/" + userId + ".json")
      .then(function (data) {
        state.entries = (data && data.entries) || [];
        state.entriesUserId = userId;
        return state.entries;
      })
      .catch(function (err) {
        state.entries = [];
        state.entriesUserId = null;
        throw err;
      })
      .finally(function () {
        state.loadingUser = false;
      });
  }

  function hasScope() {
    return !!els.userFilter.value;
  }

  function describeScope() {
    var parts = [];
    var uid = els.userFilter.value;
    if (uid) {
      var u = state.idList.find(function (x) { return x.id === uid; });
      if (!u && state.meta && state.meta.users) {
        u = state.meta.users.find(function (x) { return x.user_id === uid; });
      }
      parts.push(u ? (u.display_name || u.name || u.user_name) : uid);
    }
    if (els.dateFrom.value || els.dateTo.value) {
      parts.push((els.dateFrom.value || "…") + " ~ " + (els.dateTo.value || "…"));
    }
    if (els.typeFilter.value) {
      parts.push(TYPE_LABEL[els.typeFilter.value] || els.typeFilter.value);
    }
    return parts.join(" · ") || "未选择范围";
  }

  function inDateRange(date, from, to) {
    if (!date) return true;
    if (from && date < from) return false;
    if (to && date > to) return false;
    return true;
  }

  function filterEntries() {
    var userId = els.userFilter.value;
    var type = els.typeFilter.value;
    var from = els.dateFrom.value;
    var to = els.dateTo.value;

    return state.entries.filter(function (e) {
      if (userId && e.user_id !== userId) return false;
      if (type && e.type !== type) return false;
      if (!inDateRange(e.date, from, to)) return false;
      return true;
    });
  }

  function buildCurrentResults(pool) {
    return buildDayList(pool);
  }

  function refreshActiveDetail() {
    if (state.activeIndex < 0 || !state.currentResults[state.activeIndex]) return;

    var entry = state.currentResults[state.activeIndex].item;
    state.activeEntry = entry;

    if (state.activeDoc && state.activeDocPath === entry.path) {
      renderDetail(entry, state.activeDoc);
      return;
    }

    els.detailBody.innerHTML = "<p>加载中…</p>";
    loadDayFile(entry.path)
      .then(function (doc) {
        state.activeDoc = doc;
        state.activeDocPath = entry.path;
        renderDetail(entry, doc);
      })
      .catch(function (err) {
        els.detailBody.innerHTML = '<p class="load-error">' + esc(err.message) + "</p>";
      });
  }

  function renderDetail(entry, doc) {
    if (entry.type === "summary" || (entry.type === "day" && entry.viewType === "summary")) {
      renderSummaryDetail(entry, doc);
    } else {
      renderRecordDetail(entry, doc);
    }
  }

  function runSearch() {
    var userId = els.userFilter.value;
    var prevId = state.activeEntry && state.activeEntry.id;

    if (!userId) {
      state.scopedPool = [];
      state.currentResults = [];
      state.activeIndex = -1;
      renderResults([]);
      updateStats(0, 0);
      updateNav();
      return;
    }

    if (state.entriesUserId !== userId) {
      loadUserEntries(userId)
        .then(function () {
          runSearch();
        })
        .catch(function (err) {
          showError("无法加载用户索引: " + err.message);
          renderResults([]);
          updateStats(0, 0);
        });
      return;
    }

    state.scopedPool = filterEntries();
    state.currentResults = buildCurrentResults(state.scopedPool);

    state.activeIndex = -1;
    if (prevId) {
      for (var i = 0; i < state.currentResults.length; i++) {
        if (state.currentResults[i].item.id === prevId) {
          state.activeIndex = i;
          break;
        }
      }
    }

    renderResults(state.currentResults);
    updateStats(state.scopedPool.length, state.currentResults.length);
    updateNav();
    refreshActiveDetail();
  }

  function updateStats(poolLen, resultLen) {
    var meta = state.meta;
    if (!meta) {
      els.stats.textContent = state.loadingUser ? "正在加载…" : "";
      return;
    }
    var st = meta.stats || {};
    var userPart = (meta.users ? meta.users.length : 0) + " 位用户有数据";

    var parts = [
      "索引 " + (st.entries || 0) + " 条",
      userPart,
      "日期 " + (st.dates || 0)
    ];
    if (meta.built_at) parts.push("构建于 " + meta.built_at);
    if (hasScope()) {
      parts.push("当前「" + describeScope() + "」");
      parts.push(resultLen + " 天");
    } else {
      parts.push("请先选择用户");
    }
    els.stats.textContent = parts.join(" · ");
  }

  function updateNav() {
    var total = state.currentResults.length;
    var idx = state.activeIndex;
    els.navPrev.disabled = idx <= 0;
    els.navNext.disabled = idx < 0 || idx >= total - 1;
    if (idx >= 0 && total > 0) {
      els.navPos.textContent = (idx + 1) + " / " + total;
    } else {
      els.navPos.textContent = total ? "点击左侧日期查看 · 可用 Ctrl+F 搜索" : "";
    }
  }

  function renderResults(results) {
    els.results.innerHTML = "";

    if (!results.length) {
      els.empty.hidden = false;
      if (!hasScope()) {
        els.empty.textContent = "请从下拉框选择用户，左侧将按日期列出记录";
        return;
      }
      els.empty.textContent = "该用户当前筛选条件下无记录";
      return;
    }

    els.empty.hidden = true;

    results.forEach(function (r, i) {
      var e = r.item;
      var li = document.createElement("li");
      li.className = "result-item" + (state.activeIndex === i ? " active" : "");
      li.dataset.id = e.id;

      var meta = document.createElement("div");
      meta.className = "result-meta";
      var tags = '<span class="tag">' + esc(TYPE_LABEL[e.type] || e.type) + "</span>";
      if (e.recordPath) tags += '<span class="tag">对话</span>';
      if (e.summaryPath) tags += '<span class="tag">总结</span>';
      meta.innerHTML = tags + esc(e.user_name || e.user_id) + " · " + esc(e.date);

      var snip = document.createElement("div");
      snip.className = "result-snippet";
      snip.textContent = e.snippet || e.text || "";

      li.appendChild(meta);
      li.appendChild(snip);
      li.addEventListener("click", function () {
        openDetailAt(i, true);
      });
      els.results.appendChild(li);
    });
  }

  function scrollResultIntoView() {
    var active = els.results.querySelector(".result-item.active");
    if (active) active.scrollIntoView({ block: "nearest", behavior: "smooth" });
  }

  function loadDayFile(path) {
    if (state.cache[path]) {
      return Promise.resolve(state.cache[path]);
    }
    return fetchJson(path).then(function (data) {
      state.cache[path] = data;
      return data;
    });
  }

  function extractTimeFromMarker(text) {
    var m = (text || "").match(/(\d{2}:\d{2}:\d{2})/);
    return m ? m[1] : "";
  }

  function extractClock(ts) {
    if (!ts) return "";
    var m = String(ts).match(/(\d{2}:\d{2}:\d{2})/);
    return m ? m[1] : ts;
  }

  function groupItemsIntoBlocks(items) {
    var blocks = [];
    var current = { label: "全天", start: "", end: "", items: [] };

    items.forEach(function (it, index) {
      if (it.speaker === "marker") {
        if (current.items.length) blocks.push(current);
        var t = extractTimeFromMarker(it.text);
        current = {
          label: t || it.text.replace(/^---\s*Time:\s*/i, "").replace(/\s*---$/, ""),
          start: t,
          end: "",
          items: []
        };
      } else {
        it._index = index;
        current.items.push(it);
        current.end = extractClock(it.timestamp) || current.end;
      }
    });
    if (current.items.length) blocks.push(current);
    return blocks;
  }

  function countSpeakers(items) {
    var c = { user: 0, others: 0, background: 0, unknown: 0 };
    items.forEach(function (it) {
      if (it.speaker === "marker") return;
      if (c[it.speaker] != null) c[it.speaker]++;
    });
    return c;
  }

  function dayTimeSpan(items) {
    var first = "";
    var last = "";
    items.forEach(function (it) {
      if (it.speaker === "marker") return;
      var t = extractClock(it.timestamp);
      if (!t) return;
      if (!first) first = t;
      last = t;
    });
    return first && last ? first + " – " + last : "";
  }

  function itemVisible(it, filterTerms, hideBg) {
    if (hideBg && it.speaker === "background") return false;
    if (!filterTerms.length) return true;
    return textMatchesAll(it.text, filterTerms);
  }

  function blockHasHit(block, entry, filterTerms, hideBg) {
    return block.items.some(function (it) {
      if (!itemVisible(it, filterTerms, hideBg)) return false;
      if (entry && entry.type === "record" && it._index === entry.item_index) return true;
      if (filterTerms.length) return true;
      return false;
    });
  }

  function renderMessage(it, entry, highlightQuery) {
    var sp = it.speaker || "unknown";
    var rowCls = "msg-row msg-" + sp;
    if (entry && entry.type === "record" && it._index === entry.item_index) {
      rowCls += " msg-active";
    }
    var label = SPEAKER_LABEL[sp] || sp;
    var time = extractClock(it.timestamp);
    return (
      '<div class="' + rowCls + '" id="msg-' + it._index + '">' +
        '<div class="msg-bubble">' +
          '<div class="msg-meta"><span class="speaker-' + sp + '">' + esc(label) + "</span>" +
          (time ? " · " + esc(time) : "") + "</div>" +
          '<div class="msg-text">' + highlight(it.text || "", highlightQuery) + "</div>" +
        "</div>" +
      "</div>"
    );
  }

  function renderRecordDetail(entry, doc) {
    var items = doc.items || [];
    var browseMode = entry.type === "day";
    var filterTerms = [];
    var hideBg = state.hideBackground;
    var blocks = groupItemsIntoBlocks(items);
    var counts = countSpeakers(items);
    var span = dayTimeSpan(items);

    var html = '<div class="detail-header">';
    html += "<h4>" + esc(entry.user_name) + " · " + esc(entry.date) + "</h4>";
    html += '<div class="detail-sub">';
    html += esc(items.length) + " 条对话";
    if (span) html += " · " + esc(span);
    html += " · 用户 " + counts.user + " / 他人 " + counts.others;
    if (counts.background) html += " / 背景 " + counts.background;
    html += "</div>";

    html += '<div class="detail-tools">';
    html += '<p class="detail-sub" style="margin:0;">在页面内按 Ctrl+F（Mac：⌘F）搜索对话</p>';
    if (browseMode && entry.summaryPath) {
      html += ' <button type="button" id="view-summary" style="font:inherit;padding:0.35rem 0.65rem;margin-left:0.5rem;cursor:pointer;">查看当日总结</button>';
    }
    html += '<label style="margin-left:0.75rem;"><input type="checkbox" id="hide-bg"' + (hideBg ? " checked" : "") + "> 隐藏背景音</label>";
    html += "</div></div>";

    var visibleBlocks = 0;
    blocks.forEach(function (block, bi) {
      var visibleItems = block.items.filter(function (it) {
        return itemVisible(it, filterTerms, hideBg);
      });
      if (!visibleItems.length) return;
      visibleBlocks++;

      var expanded = browseMode || blocks.length <= 5;
      var blockLabel = block.start && block.end && block.start !== block.end
        ? block.start + " – " + block.end
        : (block.start || block.label || "时段 " + (bi + 1));

      html += '<div class="time-block' + (expanded ? "" : " collapsed") + '" data-block="' + bi + '">';
      html += '<div class="time-block-head" role="button" tabindex="0" aria-expanded="' + expanded + '">';
      html += "<span>" + esc(blockLabel) + "</span>";
      html += '<span class="block-meta">' + visibleItems.length + " 条</span>";
      html += "</div><div class=\"time-block-body\">";

      visibleItems.forEach(function (it) {
        html += renderMessage(it, entry, "");
      });
      html += "</div></div>";
    });

    if (!visibleBlocks) {
      html += '<p class="empty-state">无对话（尝试取消「隐藏背景音」）</p>';
    }

    els.detailBody.innerHTML = html;

    els.detailBody.querySelectorAll(".time-block-head").forEach(function (head) {
      head.addEventListener("click", function () {
        head.parentElement.classList.toggle("collapsed");
      });
    });

    var vs = $("view-summary");
    if (vs && entry.summaryPath) {
      vs.addEventListener("click", function () {
        var sumEntry = Object.assign({}, entry, {
          type: "summary",
          path: entry.summaryPath,
          viewType: "summary"
        });
        state.activeDoc = null;
        state.activeDocPath = null;
        state.activeEntry = sumEntry;
        loadDayFile(entry.summaryPath).then(function (doc) {
          state.activeDoc = doc;
          state.activeDocPath = entry.summaryPath;
          renderSummaryDetail(sumEntry, doc);
        });
      });
    }

    var hb = $("hide-bg");
    if (hb) {
      hb.addEventListener("change", function () {
        state.hideBackground = hb.checked;
        renderRecordDetail(entry, doc);
      });
    }
  }

  function renderSummaryDetail(entry, doc) {
    var s = doc.summary || {};
    var html = '<div class="detail-header">';
    html += "<h4>" + esc(entry.user_name) + " · " + esc(entry.date) + "</h4>";
    html += '<div class="detail-sub">日总结 · ' + esc(doc.model || "") + " · 可用 Ctrl+F 搜索</div></div>";

    html += "<p><strong>" + esc(s.title || "日总结") + "</strong></p>";
    if (s.overview) html += "<p>" + esc(s.overview) + "</p>";

    if (s.keywords && s.keywords.length) {
      html += '<div class="detail-section"><h5>关键词</h5><p>' +
        s.keywords.map(function (k) { return esc(k); }).join(" · ") + "</p></div>";
    }

    if (s.events && s.events.length) {
      html += '<div class="detail-section"><h5>事件</h5>';
      s.events.forEach(function (ev) {
        html += "<p><em>" + esc(ev.time) + "</em> " + esc(ev.what_happened);
        if (ev.outcome) html += " → " + esc(ev.outcome);
        html += "</p>";
      });
      html += "</div>";
    }

    if (s.discussions && s.discussions.length) {
      html += '<div class="detail-section"><h5>讨论</h5>';
      s.discussions.forEach(function (d) {
        html += "<p><strong>" + esc(d.topic) + ":</strong> " + esc(d.summary) + "</p>";
      });
      html += "</div>";
    }

    html += '<p style="opacity:0.65;font-size:0.85rem;margin-top:1rem;">' +
      esc(doc.generated_at || "") + "</p>";

    els.detailBody.innerHTML = html;
  }

  function openDetailAt(index, scrollList) {
    if (index < 0 || index >= state.currentResults.length) return;

    state.activeIndex = index;
    state.activeEntry = state.currentResults[index].item;

    els.detailWrap.hidden = false;
    els.layout.classList.add("has-detail");

    renderResults(state.currentResults);
    updateNav();
    if (scrollList) scrollResultIntoView();
    refreshActiveDetail();
  }

  function navigateResult(delta) {
    if (!state.currentResults.length) return;
    var next = state.activeIndex + delta;
    if (next < 0 || next >= state.currentResults.length) return;
    openDetailAt(next, true);
  }

  function bindEvents() {
    var debounce;
    function scheduleSearch() {
      clearTimeout(debounce);
      debounce = setTimeout(runSearch, 180);
    }

    ["input", "change"].forEach(function (ev) {
      els.userFilter.addEventListener(ev, scheduleSearch);
      els.typeFilter.addEventListener(ev, scheduleSearch);
      els.dateFrom.addEventListener(ev, scheduleSearch);
      els.dateTo.addEventListener(ev, scheduleSearch);
    });

    els.navPrev.addEventListener("click", function () { navigateResult(-1); });
    els.navNext.addEventListener("click", function () { navigateResult(1); });

    document.addEventListener("keydown", function (e) {
      if (!state.currentResults.length || els.detailWrap.hidden) return;
      var tag = (e.target && e.target.tagName) || "";
      if (tag === "INPUT" || tag === "TEXTAREA" || tag === "SELECT") return;
      if (e.key === "ArrowLeft") {
        e.preventDefault();
        navigateResult(-1);
      } else if (e.key === "ArrowRight") {
        e.preventDefault();
        navigateResult(1);
      }
    });
  }

  function init() {
    els = {
      error: $("load-error"),
      userFilter: $("user-filter"),
      typeFilter: $("type-filter"),
      dateFrom: $("date-from"),
      dateTo: $("date-to"),
      stats: $("stats"),
      results: $("results"),
      empty: $("empty"),
      detailBody: $("detail-body"),
      detailWrap: $("detail-wrap"),
      layout: $("layout"),
      navPrev: $("nav-prev"),
      navNext: $("nav-next"),
      navPos: $("nav-pos")
    };

    Promise.all([
      fetchJson("id_list.json").catch(function () { return []; }),
      fetchJson("search-meta.json").catch(function () {
        return fetchJson("search-index.json").then(function (legacy) {
          state.index = legacy;
          var byUser = {};
          (legacy.entries || []).forEach(function (e) {
            if (!e.user_id) return;
            if (!byUser[e.user_id]) {
              byUser[e.user_id] = { user_id: e.user_id, user_name: e.user_name || e.user_id, entries: 0 };
            }
            byUser[e.user_id].entries++;
          });
          return {
            version: legacy.version,
            built_at: legacy.built_at,
            stats: legacy.stats,
            dates: legacy.dates || [],
            users: Object.keys(byUser).map(function (k) { return byUser[k]; })
          };
        });
      })
    ])
      .then(function (pair) {
        state.idList = pair[0] || [];
        state.meta = pair[1];

        if (state.meta && state.meta.users && state.meta.users.length) {
          // ok
        } else if (!state.entries.length) {
          showError("未找到 search-meta.json。请运行 scripts/build_chronicle_index.py");
        }

        populateUsers();

        if (state.meta && state.meta.dates && state.meta.dates.length) {
          var dates = state.meta.dates.slice().sort();
          els.dateFrom.min = dates[0];
          els.dateFrom.max = dates[dates.length - 1];
          els.dateTo.min = dates[0];
          els.dateTo.max = dates[dates.length - 1];
        }

        bindEvents();
        runSearch();
      })
      .catch(function (err) {
        showError(err.message);
      });
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
