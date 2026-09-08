function setupCombo(root, options, opts) {
  opts = opts || {};
  const hidden = root.querySelector("input[type=hidden]");
  const btn = root.querySelector(".combo-btn");
  const menu = root.querySelector(".combo-menu");
  const filter = root.querySelector(".combo-filter");
  const list = root.querySelector(".combo-list");
  const placeholder = opts.placeholder || "Выберите";
  let items = options.slice();

  function labelOf(v) {
    const hit = items.find(x => String(x.value).toLowerCase() === String(v).toLowerCase());
    return hit ? hit.label : (v || placeholder);
  }
  function render(q) {
    const qq = (q || "").toLowerCase().trim();
    list.innerHTML = "";
    const shown = items.filter(x => !qq || x.label.toLowerCase().includes(qq) || String(x.value).toLowerCase().includes(qq));
    shown.forEach(x => {
      const b = document.createElement("button");
      b.type = "button";
      b.className = "combo-opt" + (hidden.value === x.value ? " on" : "");
      b.textContent = x.label;
      b.addEventListener("click", () => pick(x.value));
      list.appendChild(b);
    });
    if (!shown.length) {
      const empty = document.createElement("div");
      empty.className = "combo-empty";
      empty.textContent = qq && opts.allowCustom ? "Enter — использовать «" + q.trim() + "»" : (qq ? "Нет совпадений" : "Сначала выберите марку");
      list.appendChild(empty);
    }
  }
  function pick(v) {
    hidden.value = v;
    btn.textContent = labelOf(v);
    close();
    if (opts.onChange) opts.onChange(v);
  }
  function open() {
    document.querySelectorAll(".combo.open").forEach(el => { if (el !== root) el.classList.remove("open"); });
    root.classList.add("open");
    btn.setAttribute("aria-expanded", "true");
    filter.value = "";
    render("");
    filter.focus();
  }
  function close() {
    root.classList.remove("open");
    btn.setAttribute("aria-expanded", "false");
  }
  btn.addEventListener("click", () => root.classList.contains("open") ? close() : open());
  filter.addEventListener("input", () => render(filter.value));
  filter.addEventListener("keydown", (e) => {
    if (e.key === "Enter") {
      e.preventDefault();
      const first = list.querySelector(".combo-opt");
      if (first) first.click();
      else if (opts.allowCustom && filter.value.trim()) pick(filter.value.trim());
    }
  });
  document.addEventListener("click", (e) => { if (!root.contains(e.target)) close(); });
  btn.textContent = hidden.value ? labelOf(hidden.value) : placeholder;
  root._setOptions = (next) => {
    items = next.slice();
    if (hidden.value && !items.some(x => x.value === hidden.value)) hidden.value = "";
    btn.textContent = hidden.value ? labelOf(hidden.value) : placeholder;
    if (root.classList.contains("open")) render(filter.value);
  };
}

function brandOptions(brands) {
  return (brands || []).map(b => ({ value: b, label: b.charAt(0).toUpperCase() + b.slice(1) }));
}
function modelOptions(models) {
  return (models || []).map(m => ({ value: m, label: m }));
}
