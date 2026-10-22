// Executed by Browserless /function, never in the user's browser. No cookies,
// profiles, proxies, CAPTCHA solving, form submissions or automatic recapture.
const profiles = {
  greenhouse: {
    description: ".job__description, #content",
    heading: "h1",
    hosts: ["job-boards.cdn.greenhouse.io", "recruiting.cdn.greenhouse.io"],
  },
  lever: {
    description: ".posting-page .content",
    heading: ".posting-headline h2",
    hosts: ["cdn.lever.co", "lever-client-logos.s3.amazonaws.com"],
  },
  ashby: {
    description: ".ashby-job-posting-description",
    heading: "h1",
    hosts: ["app.ashbyhq.com", "cdn.ashbyprd.com"],
  },
  workday: {
    description: '[data-automation-id="jobPostingDescription"]',
    heading: '[data-automation-id="jobPostingHeader"]',
    hosts: ["www.myworkday.com", "www.myworkdaycdn.com"],
  },
};

export function allowedRequest(url, type, mainNavigation, origin, hosts) {
  try {
    const target = new URL(url);
    if (
      target.protocol !== "https:" ||
      target.port ||
      target.username ||
      target.password
    )
      return false;
    if (mainNavigation) return target.origin === origin;
    if (["document", "media", "websocket"].includes(type)) return false;
    return hosts.includes(target.hostname);
  } catch {
    return false;
  }
}

export function pageFailure({ status, title, text, descriptionLength }) {
  if (status === 404 || status === 410) return "page_expired";
  if (
    status === 401 ||
    status === 403 ||
    status === 429 ||
    /just a moment|access denied|verify you are human|sign in to continue/i.test(
      title,
    )
  )
    return "page_blocked";
  if (status < 200 || status >= 400) return "page_unavailable";
  if (
    descriptionLength < 300 &&
    /job (?:is )?no longer available|job (?:has been|is) (?:closed|filled)|position (?:is )?no longer available|job not found|posting has expired/i.test(
      text,
    )
  )
    return "page_expired";
  return null;
}

export default async function capture({ page, context }) {
  const fail = (error) => ({ type: "application/json", data: { error } });
  try {
    const profile = profiles[context.profile];
    if (!profile) return fail("unsupported_target");
    const origin = new URL(context.url).origin;
    const hosts = [
      new URL(context.url).hostname,
      ...profile.hosts,
      "fonts.googleapis.com",
      "fonts.gstatic.com",
    ];
    let blockedNavigation = false,
      stylesheetFailed = false;
    await page.setViewport({ width: 1280, height: 900, deviceScaleFactor: 1 });
    await page.setRequestInterception(true);
    page.on("request", (request) => {
      const main =
        request.isNavigationRequest() && request.frame() === page.mainFrame();
      if (
        !allowedRequest(
          request.url(),
          request.resourceType(),
          main,
          origin,
          hosts,
        )
      ) {
        if (main) blockedNavigation = true;
        return request.abort();
      }
      return request.continue();
    });
    page.on("requestfailed", (request) => {
      if (request.resourceType() === "stylesheet") stylesheetFailed = true;
    });
    page.on("response", (response) => {
      if (
        response.request().resourceType() === "stylesheet" &&
        response.status() >= 400
      )
        stylesheetFailed = true;
    });
    let response;
    try {
      response = await page.goto(context.url, {
        waitUntil: "domcontentloaded",
        timeout: 9000,
      });
    } catch (error) {
      return fail(
        blockedNavigation
          ? "page_blocked"
          : error.name === "TimeoutError"
            ? "capture_timeout"
            : "page_unavailable",
      );
    }
    const status = response?.status() ?? 0;
    let previous = "",
      stableSince = 0,
      ready = false;
    const deadline = Date.now() + 6000;
    while (Date.now() < deadline) {
      const state = await page.evaluate(({ description, heading }) => {
        const node = document.querySelector(description);
        const rect = node?.getBoundingClientRect();
        const text = node?.innerText?.trim() ?? "";
        return {
          title: document.title,
          text: document.body.innerText.slice(0, 2000),
          descriptionLength: text.length,
          // Compare the content, not just its length: placeholders can be replaced.
          content: text,
          height: Math.ceil(document.documentElement.scrollHeight),
          visible: !!rect && rect.width > 0 && rect.height > 100,
          heading: !!document.querySelector(heading)?.innerText?.trim(),
          fonts: document.fonts.status === "loaded",
        };
      }, profile);
      const failure = pageFailure({ ...state, status });
      if (failure) return fail(failure);
      if (state.height * 1280 > 24000000) return fail("image_too_large");
      const signature = JSON.stringify([state.content, state.height]);
      if (
        state.descriptionLength >= 300 &&
        state.visible &&
        state.heading &&
        state.fonts
      ) {
        if (signature !== previous) stableSince = Date.now();
        else if (Date.now() - stableSince >= 1250) {
          ready = true;
          break;
        }
      } else stableSince = Date.now();
      previous = signature;
      await new Promise((resolve) => setTimeout(resolve, 250));
    }
    if (!ready || stylesheetFailed) return fail("page_not_ready");
    // A static snapshot excludes interactive embeds. This recipe also avoids the
    // full-page resizing/scrolling defect seen in the REST screenshot evaluation.
    await page.addStyleTag({
      content:
        "iframe,video{display:none !important}*{animation:none !important;transition:none !important;caret-color:transparent !important}",
    });
    const size = await page.evaluate(() => ({
      width: Math.max(innerWidth, document.documentElement.scrollWidth),
      height: Math.max(innerHeight, document.documentElement.scrollHeight),
    }));
    if (size.width * size.height > 24000000) return fail("image_too_large");
    const image = await page.screenshot({
      type: "png",
      fullPage: true,
      encoding: "base64",
    });
    if (image.length > Math.ceil((8 * 1024 * 1024) / 3) * 4)
      return fail("image_too_large");
    return {
      type: "application/json",
      data: { image, width: size.width, height: size.height },
    };
  } catch (error) {
    return fail(
      error.name === "TimeoutError" ? "capture_timeout" : "capture_failed",
    );
  }
}
