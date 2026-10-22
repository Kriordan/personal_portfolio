import assert from "node:assert/strict";
import { test } from "node:test";
import capture, {
  allowedRequest,
  pageFailure,
} from "../project/jobwizard/browserless_capture.mjs";
import extract from "../project/jobwizard/browserless_extract.mjs";

test("remote browser restricts redirects, embeds and resources to explicit HTTPS hosts", () => {
  const origin = "https://jobs.ashbyhq.com",
    hosts = ["jobs.ashbyhq.com", "cdn.ashbyprd.com"];
  const allowed = (url, type = "image", main = false) =>
    allowedRequest(url, type, main, origin, hosts);
  assert.ok(allowed(`${origin}/acme/a`, "document", true));
  assert.ok(allowed("https://cdn.ashbyprd.com/image.png"));
  for (const url of [
    "http://jobs.ashbyhq.com/a",
    "file:///etc/passwd",
    "https://127.0.0.1/",
    "https://jobs.ashbyhq.com.evil.test/",
    "https://user:pass@jobs.ashbyhq.com/",
    "https://jobs.ashbyhq.com:444/",
  ])
    assert.equal(allowed(url), false);
  assert.equal(allowed("https://cdn.ashbyprd.com/", "document", true), false);
  assert.equal(allowed(`${origin}/embed`, "document"), false);
  assert.equal(allowed(`${origin}/socket`, "websocket"), false);
});

test("Gem resources cannot broaden navigation to its CDN or arbitrary domains", () => {
  const origin = "https://jobs.gem.com";
  const hosts = ["jobs.gem.com", "static.gem.com", "usercontent.zscdn.net", "maxcdn.bootstrapcdn.com"];
  assert.ok(allowedRequest("https://static.gem.com/assets/logo.png", "image", false, origin, hosts));
  assert.ok(allowedRequest("https://maxcdn.bootstrapcdn.com/bootstrap/3.3.7/css/bootstrap.min.css", "stylesheet", false, origin, hosts));
  assert.equal(allowedRequest("https://static.gem.com/other", "document", true, origin, hosts), false);
  assert.equal(allowedRequest("https://jobs.gem.com.evil.test/", "image", false, origin, hosts), false);
  assert.equal(allowedRequest("https://www.googletagmanager.com/gtag/js", "script", false, origin, hosts), false);
});

test("HTTP 200 alone does not establish a live job description", () => {
  const state = {
    status: 200,
    title: "Careers",
    text: "",
    descriptionLength: 0,
  };
  assert.equal(
    pageFailure({ ...state, text: "This job is no longer available" }),
    "page_expired",
  );
  assert.equal(
    pageFailure({ ...state, title: "Just a moment…" }),
    "page_blocked",
  );
  assert.equal(pageFailure({ ...state, status: 404 }), "page_expired");
  assert.equal(pageFailure({ ...state, status: 503 }), "page_unavailable");
  assert.equal(pageFailure({ ...state, status: 403 }), "page_blocked");
  assert.equal(
    pageFailure({
      ...state,
      text: "What to expect when a position is no longer available",
      descriptionLength: 2000,
    }),
    null,
  );
});

function pageFixture(state, status = 200) {
  const calls = [];
  return {
    calls,
    setViewport: async (x) => calls.push(["viewport", x]),
    setRequestInterception: async () => {},
    on: () => {},
    goto: async () => ({ status: () => status }),
    evaluate: async (_, arg) => (arg ? state : { width: 1280, height: 9000 }),
    addStyleTag: async () => {},
    screenshot: async (options) => {
      calls.push(["screenshot", options]);
      return "AAAA";
    },
  };
}
const context = { url: "https://jobs.ashbyhq.com/acme/abc", profile: "ashby" };
test("expired pages never reach screenshot capture", async () => {
  const page = pageFixture({
    title: "Careers",
    text: "This job is no longer available",
    descriptionLength: 0,
  });
  assert.equal((await capture({ page, context })).data.error, "page_expired");
  assert.equal(page.calls.filter(([name]) => name === "screenshot").length, 0);
});
test("a stable visible description produces exactly one full-page capture", async () => {
  const page = pageFixture({
    title: "Engineer",
    text: "Real job",
    descriptionLength: 1000,
    content: "x".repeat(1000),
    height: 9000,
    visible: true,
    heading: true,
    fonts: true,
  });
  const result = await capture({ page, context });
  assert.equal(result.data.image, "AAAA");
  const screenshots = page.calls.filter(([name]) => name === "screenshot");
  assert.equal(screenshots.length, 1);
  assert.deepEqual(screenshots[0][1], {
    type: "png",
    clip: { x: 0, y: 0, width: 1280, height: 9000 },
    captureBeyondViewport: true,
    encoding: "base64",
  });
});

test("text extraction does not depend on font loading or screenshot pixel bounds", async () => {
  const page = pageFixture({});
  const source = {heading: "Engineer", description: "Final description", jsonld: []};
  page.evaluate = async (_, arg) => Object.hasOwn(arg, "image") ? {
    title: "Engineer", text: "Job", descriptionLength: 1000,
    content: "x".repeat(1000), height: 50000, visible: true,
    heading: true, fonts: false,
  } : source;
  assert.deepEqual((await extract({page, context})).data, source);
  assert.equal(page.calls.filter(([name]) => name === "screenshot").length, 0);
});

test("blocked pages do not produce source data for summarization", async () => {
  const page = pageFixture({title: "Access denied", text: "", descriptionLength: 0});
  assert.equal((await extract({page, context})).data.error, "page_blocked");
  assert.equal(page.calls.filter(([name]) => name === "screenshot").length, 0);
});
