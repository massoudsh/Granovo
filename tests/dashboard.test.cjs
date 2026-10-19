const { test } = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const vm = require("node:vm");

class Element {
  constructor(tag = "div") {
    this.tagName = tag;
    this.textContent = "";
    this.children = [];
    this.dataset = {};
    this.events = {};
    this.hidden = false;
    this.value = "";
    this.elements = Object.fromEntries(["password", "factory_name", "produced_on", "code"].map((key) => [key, {}]));
    this.classList = { toggle() {} };
  }
  addEventListener(name, callback) { this.events[name] = callback; }
  replaceChildren(...nodes) { this.children = nodes; }
  append(...nodes) { this.children.push(...nodes); }
  reset() { this.resetCount = (this.resetCount || 0) + 1; }
  setAttribute(name, value) { this[name] = value; }
  querySelector() { return this.submit || (this.submit = new Element("button")); }
  set innerHTML(_) { throw new Error("Unsafe HTML rendering"); }
}

async function dashboard() {
  const nodes = new Map();
  const document = {
    getElementById(id) {
      if (!nodes.has(id)) nodes.set(id, new Element());
      return nodes.get(id);
    },
    createElement(tag) { return new Element(tag); },
    querySelectorAll() { return []; },
  };
  const context = vm.createContext({
    document, Intl, URL, URLSearchParams, Blob, Date,
    FormData: class { constructor(form) { return new Map(Object.entries(form.data || {})); } },
    window: { confirm() { return true; } },
    fetch: async () => ({ ok: false, status: 401, json: async () => ({ detail: "Sign in required" }) }),
  });
  vm.runInContext(fs.readFileSync("landing/dashboard/dashboard.js", "utf8"), context);
  await new Promise(setImmediate);
  return { context, nodes, run: (code) => vm.runInContext(code, context) };
}

test("expired session shows sign-in and clears private workspace", async () => {
  const { nodes, run } = await dashboard();
  assert.equal(nodes.get("auth").hidden, false);
  assert.equal(nodes.get("workspace").hidden, true);
  assert.equal(nodes.get("logout").hidden, true);
  assert.equal(run("state.csrf"), "");
  assert.ok(nodes.get("batch-form").resetCount >= 1);
});

test("KPI cards distinguish no data from zero and negative reduction", async () => {
  const { nodes, run } = await dashboard();
  run(`renderKpis({daily:[],baseline:{reject_pct:0,count:1,total_kg:10},pilot:{reject_pct:null,count:0,total_kg:0},reduction_percentage_points:null,pilot_below_target:null})`);
  assert.notEqual(nodes.get("baseline-rate").textContent, "بدون داده");
  assert.equal(nodes.get("pilot-rate").textContent, "بدون داده");
  assert.equal(nodes.get("rate-change").textContent, "—");
  run(`renderKpis({daily:[],baseline:{reject_pct:4,count:1,total_kg:10},pilot:{reject_pct:8,count:1,total_kg:10},reduction_percentage_points:-4,pilot_below_target:false})`);
  assert.match(nodes.get("target-status").textContent, /هنوز/);
});

test("daily quality trend renders weighted rates and handles empty ranges", async () => {
  const { nodes, run } = await dashboard();
  const summary = `baseline:{reject_pct:14,count:2,total_kg:1000},pilot:{reject_pct:null,count:0,total_kg:0},reduction_percentage_points:null,pilot_below_target:null`;
  run(`renderKpis({${summary},daily:[{produced_on:"2025-01-01",phase:"baseline",count:2,total_kg:1000,rejected_kg:140,reject_pct:14}]})`);
  assert.equal(nodes.get("daily-empty").hidden, true);
  const cells = nodes.get("daily-rows").children[0].children;
  assert.equal(cells[0].textContent, "2025-01-01");
  assert.equal(cells[1].textContent, "خط مبنا");
  assert.match(cells[5].textContent, /٪/);
  run(`renderKpis({${summary},daily:[]})`);
  assert.equal(nodes.get("daily-empty").hidden, false);
  assert.equal(nodes.get("daily-rows").children.length, 0);
});

test("batch rendering treats factory-supplied text as text, not HTML", async () => {
  const { nodes, run } = await dashboard();
  run(`state.machines = [{id:"m",name:"<img src=x onerror=alert(1)>"}]; renderBatches({total:1,items:[{id:"b",code:"<script>bad()</script>",produced_on:"2025-01-01",machine_id:"m",polymer:"PP",phase:"pilot",total_kg:100,rejected_kg:0,quality_verified:false}]})`);
  const cells = nodes.get("batch-rows").children[0].children;
  assert.equal(cells[0].textContent, "<script>bad()</script>");
  assert.equal(cells[1].textContent, "<img src=x onerror=alert(1)>");
  assert.equal(cells[5].children[0].dataset.batchId, "b");
  assert.equal(nodes.get("history-empty").hidden, true);
});

test("recommendations display evaluation and only pending records expose approval", async () => {
  const { nodes, run } = await dashboard();
  const record = `{id:"r",machine_id:"m",polymer:"PP",purity_pct:95,moisture_pct:1,temperature_c:200,screw_rpm:150,pressure_bar:80,training_count:8,model_version:"knn3-v1-test",evaluation:{holdout_mae:{temperature_c:2,screw_rpm:2,pressure_bar:1}}}`;
  run(`renderRecommendations([${record}])`);
  let children = nodes.get("recommendation-list").children[0].children;
  assert.equal(children.at(-1).dataset.recommendationId, "r");
  run(`renderRecommendations([{...${record},approved_at:123}])`);
  children = nodes.get("recommendation-list").children[0].children;
  assert.match(children.at(-1).textContent, /بدون اعمال/);
  assert.equal(children.some((node) => node.tagName === "button"), false);
});

test("API writes include CSRF token and encode data as JSON", async () => {
  const { context, run } = await dashboard();
  let captured;
  context.fetch = async (url, options) => {
    captured = { url, ...options };
    return { ok: true, json: async () => ({ ok: true }) };
  };
  run('state.csrf = "test-only-placeholder"');
  await run('api("batches", {method:"POST",data:{code:"B1"}})');
  assert.equal(captured.url, "/api/batches");
  assert.equal(captured.headers["X-CSRF-Token"], "test-only-placeholder");
  assert.equal(captured.headers["Content-Type"], "application/json");
  assert.equal(captured.body, '{"code":"B1"}');
  assert.equal(captured.credentials, "same-origin");
});

test("registration loads the factory workspace and subsequent batch submission refreshes KPIs", async () => {
  const { context, nodes, run } = await dashboard();
  const requests = [];
  const emptyKpis = { daily: [], baseline: { reject_pct: null, count: 0, total_kg: 0 }, pilot: { reject_pct: null, count: 0, total_kg: 0 }, reduction_percentage_points: null, pilot_below_target: null };
  context.fetch = async (url, options) => {
    requests.push({ url, ...options });
    let result;
    if (url === "/api/register") result = { csrf: "first-test-token" };
    else if (url === "/api/session") result = { csrf: "second-test-token", factory_name: "Factory A" };
    else if (url === "/api/machines") result = [{ id: "m", name: "Machine A" }];
    else if (url.startsWith("/api/kpis")) result = emptyKpis;
    else if (url.startsWith("/api/batches?")) result = { items: [], total: 0 };
    else if (url === "/api/recommendations") result = [];
    else if (url === "/api/batches" && options.method === "POST") result = { id: "b" };
    else throw new Error(`Unexpected request ${url}`);
    return { ok: true, json: async () => result };
  };
  const auth = nodes.get("auth-form");
  auth.data = { email: "operator@example.com", password: "test-only-password", factory_name: "Factory A" };
  run('state.mode = "register"');
  await auth.events.submit({ preventDefault() {}, currentTarget: auth });
  assert.equal(nodes.get("workspace").hidden, false);
  assert.equal(nodes.get("auth").hidden, true);
  assert.equal(nodes.get("factory-title").textContent, "Factory A");
  assert.equal(auth.elements.password.value, "");
  assert.equal(auth.submit.disabled, false);
  const form = nodes.get("batch-form");
  form.data = { machine_id: "m", code: "B1", total_kg: "100", rejected_kg: "1" };
  await form.events.submit({ preventDefault() {}, currentTarget: form });
  const request = requests.find((entry) => entry.url === "/api/batches");
  assert.equal(request.headers["X-CSRF-Token"], "second-test-token");
  assert.equal(JSON.parse(request.body).total_kg, 100);
  assert.equal(form.elements.code.value, "");
  assert.equal(form.submit.disabled, false);
  assert.match(nodes.get("status").textContent, /بچ ثبت شد/);
});

test("form serialization converts only numeric fields", async () => {
  const { context, run } = await dashboard();
  context.form = { data: { code: "001", total_kg: "100.5", purity_pct: "95", machine_id: "123" } };
  const result = run("values(form)");
  assert.equal(result.code, "001");
  assert.equal(result.total_kg, 100.5);
  assert.equal(result.purity_pct, 95);
  assert.equal(result.machine_id, "123");
});
