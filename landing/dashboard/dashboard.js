"use strict";

const $ = (id) => document.getElementById(id);
const state = { csrf: "", mode: "login", machines: [] };
const format = new Intl.NumberFormat("fa-IR", { maximumFractionDigits: 3 });
const numericFields = new Set(["temperature_min", "temperature_max", "rpm_max", "pressure_max", "purity_pct", "moisture_pct", "temperature_c", "screw_rpm", "pressure_bar", "total_kg", "rejected_kg"]);
const batchColumns = ["machine_id", "polymer", "purity_pct", "moisture_pct", "code", "produced_on", "phase", "temperature_c", "screw_rpm", "pressure_bar", "total_kg", "rejected_kg"];
const errors = {
  401: "ایمیل یا رمز عبور نادرست است، یا نشست شما پایان یافته. دوباره وارد شوید.",
  403: "نشست را تازه‌سازی کنید و دوباره تلاش کنید.",
  404: "رکورد در فضای کارخانه‌ی شما پیدا نشد.",
  413: "حجم فایل نباید بیشتر از یک مگابایت باشد.",
  415: "فایل باید CSV با رمزگذاری UTF-8 باشد.",
  422: "داده نامعتبر است. تاریخ، ستون‌های CSV، واحدها و محدوده‌ی دستگاه را بررسی کنید.",
  429: "تلاش‌های ورود زیاد است؛ یک دقیقه بعد دوباره امتحان کنید.",
};

function status(message, error = false) {
  $("status").textContent = message;
  $("status").classList.toggle("error", error);
}

function signedOut() {
  state.csrf = "";
  state.machines = [];
  $("auth").hidden = false;
  $("workspace").hidden = true;
  $("logout").hidden = true;
  $("batch-rows").replaceChildren();
  $("recommendation-list").replaceChildren();
  $("machine-list").replaceChildren();
  for (const id of ["batch-form", "machine-form", "recommendation-form", "csv-form", "filters"]) $(id).reset();
  $("batch-form").elements.produced_on.value = localDate;
  $("factory-title").textContent = "خط تولید شما";
  $("model-evaluation").textContent = "";
}

async function api(path, { method = "GET", data, csv } = {}) {
  const headers = {};
  if (method !== "GET") headers["X-CSRF-Token"] = state.csrf;
  if (data) headers["Content-Type"] = "application/json";
  if (csv) headers["Content-Type"] = "text/csv";
  const response = await fetch(`/api/${path}`, {
    method, headers, credentials: "same-origin",
    body: data ? JSON.stringify(data) : csv,
  });
  const result = await response.json();
  if (!response.ok) {
    if (response.status === 401) signedOut();
    let message = errors[response.status] || "عملیات انجام نشد؛ دوباره تلاش کنید.";
    if (response.status === 409) {
      if (path === "recommendations") message = "داده‌ی کافی در دامنه‌ی ورودی نیست. حداقل ۸ بچ تأییدشده با نرخ رد زیر ۵٪ برای همان دستگاه و پلیمر لازم است.";
      else if (path.includes("approve")) message = "پیشنهاد قبلاً تأیید شده یا داده‌ی آموزشی تغییر کرده است؛ در صورت نیاز پیشنهاد تازه بگیرید.";
      else message = "ایمیل، نام دستگاه یا کد بچ تکراری است؛ هیچ داده‌ی جدیدی ذخیره نشد.";
    }
    if (path === "batches/import" && response.status === 422) message += ` ${result.detail || ""}`;
    throw new Error(message);
  }
  return result;
}

function values(form) {
  return Object.fromEntries([...new FormData(form)].map(([key, value]) => [key, numericFields.has(key) ? Number(value) : value]));
}

function element(tag, text, className) {
  const node = document.createElement(tag);
  if (text !== undefined) node.textContent = text;
  if (className) node.className = className;
  return node;
}

function machineName(id) {
  return state.machines.find((machine) => machine.id === id)?.name || "دستگاه";
}

function renderMachines(machines) {
  state.machines = machines;
  document.querySelectorAll(".machine-select, #filter-machine").forEach((select) => {
    const selected = select.value;
    const placeholder = element("option", select.id === "filter-machine" ? "همه‌ی دستگاه‌ها" : "انتخاب دستگاه");
    placeholder.value = "";
    select.replaceChildren(placeholder);
    machines.forEach((machine) => {
      const option = element("option", machine.name);
      option.value = machine.id;
      select.append(option);
    });
    if (machines.some((machine) => machine.id === selected)) select.value = selected;
  });
  $("machine-list").replaceChildren(...machines.map((machine) => {
    const li = element("li", `${machine.name} · ${format.format(machine.temperature_min)}–${format.format(machine.temperature_max)} °C · ${format.format(machine.rpm_max)} rpm · ${format.format(machine.pressure_max)} bar`);
    li.append(element("code", machine.id));
    return li;
  }));
}

function filters() {
  const params = new URLSearchParams();
  for (const [key, value] of new FormData($("filters"))) if (value) params.set(key, value);
  return params.toString();
}

function renderKpis(kpis) {
  for (const phase of ["baseline", "pilot"]) {
    const row = kpis[phase];
    $(`${phase}-rate`).textContent = row.reject_pct === null ? "بدون داده" : `${format.format(row.reject_pct)}٪`;
    $(`${phase}-volume`).textContent = `${format.format(row.count)} بچ · ${format.format(row.total_kg)} kg تولید`;
  }
  $("rate-change").textContent = kpis.reduction_percentage_points === null ? "—" : format.format(kpis.reduction_percentage_points);
  $("target-status").textContent = kpis.pilot_below_target === null ? "برای بررسی هدف، داده‌ی پایلوت ثبت کنید." : kpis.pilot_below_target ? "نرخ ثبت‌شده‌ی پایلوت زیر ۵٪ است؛ کنترل کیفیت و مقایسه‌ی همسان همچنان ضروری است." : "نرخ ثبت‌شده‌ی پایلوت هنوز به کمتر از ۵٪ نرسیده است.";
}

function renderBatches(result) {
  $("history-empty").hidden = result.items.length > 0;
  $("history-count").textContent = `${format.format(result.items.length)} از ${format.format(result.total)} بچ — حداکثر ۲۰۰ ردیف جدید؛ برای موارد قدیمی‌تر فیلتر تاریخ بگذارید.`;
  $("batch-rows").replaceChildren(...result.items.map((batch) => {
    const tr = element("tr");
    const title = element("td", batch.code);
    title.append(element("small", batch.produced_on));
    const machine = element("td", machineName(batch.machine_id));
    machine.append(element("small", batch.polymer));
    const quality = element("td");
    const button = element("button", batch.quality_verified ? "تأییدشده — لغو تأیید" : "تأیید کیفیت", "btn btn-ghost btn-sm");
    button.type = "button";
    button.dataset.batchId = batch.id;
    button.dataset.verified = String(batch.quality_verified);
    quality.append(button);
    tr.append(title, machine, element("td", batch.phase === "pilot" ? "پایلوت" : "خط مبنا"),
      element("td", `${format.format(batch.total_kg)} / ${format.format(batch.rejected_kg)}`),
      element("td", `${format.format(batch.rejected_kg / batch.total_kg * 100)}٪`), quality);
    return tr;
  }));
}

function renderRecommendations(rows) {
  $("recommendation-empty").hidden = rows.length > 0;
  $("recommendation-list").replaceChildren(...rows.map((row) => {
    const card = element("article", undefined, "recommendation-card");
    card.append(element("h3", `${machineName(row.machine_id)} · ${row.polymer}`),
      element("p", `خلوص ${format.format(row.purity_pct)}٪ · رطوبت ${format.format(row.moisture_pct)}٪`),
      element("p", `${format.format(row.temperature_c)} °C · ${format.format(row.screw_rpm)} rpm · ${format.format(row.pressure_bar)} bar`),
      element("p", `${format.format(row.training_count)} نمونه‌ی تاریخی`), element("code", row.model_version));
    const metrics = row.evaluation;
    card.append(element("p", `خطای ارزیابی داخلی دما ${format.format(metrics.holdout_mae.temperature_c)} °C · سرعت ${format.format(metrics.holdout_mae.screw_rpm)} rpm · فشار ${format.format(metrics.holdout_mae.pressure_bar)} bar`, "muted"));
    if (row.approved_at) card.append(element("p", "تأیید اپراتور ثبت شد — بدون اعمال روی دستگاه", "approved"));
    else {
      const approve = element("button", "ثبت تأیید اپراتور", "btn btn-ghost btn-sm");
      approve.type = "button";
      approve.dataset.recommendationId = row.id;
      card.append(approve);
    }
    return card;
  }));
}

async function refreshMetrics() {
  const query = filters();
  const [kpis, batches] = await Promise.all([api(`kpis?${query}`), api(`batches?${query}`)]);
  renderKpis(kpis);
  renderBatches(batches);
}

async function enterWorkspace() {
  const session = await api("session");
  state.csrf = session.csrf;
  $("factory-title").textContent = session.factory_name;
  $("auth").hidden = true;
  $("workspace").hidden = false;
  $("logout").hidden = false;
  renderMachines(await api("machines"));
  await refreshMetrics();
  renderRecommendations(await api("recommendations"));
  status(state.machines.length ? "فضای کارخانه آماده است." : "برای شروع، دستگاه و محدوده‌ی مجاز آن را ثبت کنید.");
}

function handle(formId, task) {
  $(formId).addEventListener("submit", async (event) => {
    event.preventDefault();
    const form = event.currentTarget;
    const submit = form.querySelector('[type="submit"]');
    submit.disabled = true;
    try { await task(form); }
    catch (error) { status(error.message || "ارتباط با سرویس برقرار نشد.", true); }
    finally { submit.disabled = false; }
  });
}

for (const mode of ["login", "register"]) {
  $(`choose-${mode}`).addEventListener("click", () => {
    state.mode = mode;
    $("factory-field").hidden = mode !== "register";
    $("auth-form").elements.factory_name.required = mode === "register";
    $("auth-form").elements.password.autocomplete = mode === "register" ? "new-password" : "current-password";
    for (const option of ["login", "register"]) {
      $(`choose-${option}`).setAttribute("aria-pressed", String(option === mode));
      $(`choose-${option}`).classList.toggle("btn-primary", option === mode);
      $(`choose-${option}`).classList.toggle("btn-ghost", option !== mode);
    }
  });
}

handle("auth-form", async (form) => {
  const data = values(form);
  if (state.mode === "login") delete data.factory_name;
  const result = await api(state.mode, { method: "POST", data });
  state.csrf = result.csrf;
  form.elements.password.value = "";
  await enterWorkspace();
});
handle("machine-form", async (form) => {
  await api("machines", { method: "POST", data: values(form) });
  form.reset();
  renderMachines(await api("machines"));
  status("دستگاه ثبت شد. اکنون می‌توانید بچ تولید ثبت کنید.");
});
handle("batch-form", async (form) => {
  await api("batches", { method: "POST", data: values(form) });
  form.elements.code.value = "";
  await refreshMetrics();
  status("بچ ثبت شد؛ بعد از بررسی واقعی، کیفیت آن را در تاریخچه تأیید کنید.");
});
handle("filters", async () => {
  await refreshMetrics();
  status("فیلترها اعمال شدند.");
});
handle("csv-form", async (form) => {
  const file = form.elements.csv.files[0];
  if (file.size > 1048576) throw new Error(errors[413]);
  const result = await api("batches/import", { method: "POST", csv: file });
  form.reset();
  await refreshMetrics();
  status(`${format.format(result.imported)} بچ وارد شد؛ کیفیت داده‌های واردشده هنوز تأیید نشده است.`);
});
handle("recommendation-form", async (form) => {
  const result = await api("recommendations", { method: "POST", data: values(form) });
  const evaluation = result.evaluation;
  $("model-evaluation").textContent = `ارزیابی زمانی داخلی با ${format.format(evaluation.holdout_count)} نمونه: خطای مطلق میانگین دما ${format.format(evaluation.holdout_mae.temperature_c)} °C، سرعت ${format.format(evaluation.holdout_mae.screw_rpm)} rpm و فشار ${format.format(evaluation.holdout_mae.pressure_bar)} bar. این ارزیابی جایگزین پایلوت صنعتی نیست.`;
  renderRecommendations(await api("recommendations"));
  status("پیشنهاد آزمایشی ثبت شد و در انتظار تأیید اپراتور است.");
});

$("batch-rows").addEventListener("click", async (event) => {
  const button = event.target.closest("button[data-batch-id]");
  if (!button || !window.confirm("نتیجه‌ی کیفیت این بچ را بررسی کرده‌اید و می‌خواهید وضعیت تأیید را تغییر دهید؟")) return;
  button.disabled = true;
  try {
    await api(`batches/${button.dataset.batchId}/quality`, { method: "PATCH", data: { quality_verified: button.dataset.verified !== "true" } });
    await refreshMetrics();
    status("وضعیت تأیید کیفیت به‌روز شد.");
  } catch (error) { status(error.message, true); }
  finally { button.disabled = false; }
});
$("recommendation-list").addEventListener("click", async (event) => {
  const button = event.target.closest("button[data-recommendation-id]");
  if (!button || !window.confirm("ایمنی و تناسب تنظیمات پیشنهادی را بررسی کرده‌اید؟ فقط تأیید شما ثبت می‌شود؛ تنظیمات روی دستگاه اعمال نمی‌شود.")) return;
  button.disabled = true;
  try {
    await api(`recommendations/${button.dataset.recommendationId}/approve`, { method: "POST" });
    renderRecommendations(await api("recommendations"));
    status("تأیید اپراتور ثبت شد. هیچ فرمانی به دستگاه ارسال نشد.");
  } catch (error) { status(error.message, true); }
  finally { button.disabled = false; }
});
$("logout").addEventListener("click", async () => {
  try { await api("logout", { method: "POST" }); signedOut(); status("از حساب خارج شدید."); }
  catch (error) { status(error.message, true); }
});
$("csv-template").addEventListener("click", () => {
  const url = URL.createObjectURL(new Blob(["\uFEFF" + batchColumns.join(",") + "\n"], { type: "text/csv;charset=utf-8" }));
  const link = element("a");
  link.href = url;
  link.download = "granovo-batch-template.csv";
  link.click();
  URL.revokeObjectURL(url);
});

const today = new Date();
const localDate = `${today.getFullYear()}-${String(today.getMonth() + 1).padStart(2, "0")}-${String(today.getDate()).padStart(2, "0")}`;
$("batch-form").elements.produced_on.value = localDate;
$("batch-form").elements.produced_on.max = localDate;
enterWorkspace().catch((error) => {
  signedOut();
  status(error.message.includes("نشست") ? "برای شروع وارد شوید یا کارخانه‌ی جدید ثبت کنید." : "سرویس در دسترس نیست؛ داشبورد به API هم‌مبدأ نیاز دارد.", !error.message.includes("نشست"));
});
