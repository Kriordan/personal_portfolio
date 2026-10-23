import { preparePage } from './browserless_capture.mjs';

// Runs inside Browserless. Return data only; never click/apply/follow model instructions.
export default async function extract({ page, context }) {
  const fail = (error) => ({ type: 'application/json', data: { error } });
  try {
    const prepared = await preparePage(page, context, false);
    if (prepared.error) return fail(prepared.error);
    const result = await page.evaluate(readListingDocument, prepared.profile);
    return { type: 'application/json', data: result };
  } catch (error) {
    return fail(error.name === 'TimeoutError' ? 'capture_timeout' : 'extraction_failed');
  }
}

export function readListingDocument({ description, heading }) {
  const clean = (value) => (value ?? '').replace(/\s+/g, ' ').trim();
  const visible = (node) => {
    const rect = node.getBoundingClientRect();
    const style = getComputedStyle(node);
    return rect.width > 0 && rect.height > 0 && style.visibility !== 'hidden' && style.visibility !== 'collapse';
  };
  const candidates = [...document.querySelectorAll(description)].filter(visible);
  const roots = candidates.filter((node) => !candidates.some((parent) => parent !== node && parent.contains(node)));
  if (!roots.length) return { error: 'page_not_ready' };
  const original = roots.flatMap((root) => [root, ...root.querySelectorAll('*')]);
  const excluded = new Set(original.filter((node) => {
    const style = getComputedStyle(node);
    return style.display === 'none' || style.visibility === 'hidden' || node.hidden;
  }));
  const blocks = new Map();
  for (const root of roots) {
    const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT);
    let node;
    while ((node = walker.nextNode())) {
      const parent = node.parentElement;
      if (!parent || parent.closest('script,style,form,button,select,textarea,nav,footer,[hidden],[aria-hidden="true"]')) continue;
      let current = parent, hidden = false;
      while (current && root.contains(current)) {
        if (excluded.has(current)) hidden = true;
        current = current.parentElement;
      }
      if (hidden) continue;
      const text = clean(node.textContent);
      const block = parent.closest('p,li,h1,h2,h3,h4,h5,h6,div') || parent;
      if (text) blocks.set(block, [...(blocks.get(block) || []), text]);
    }
  }
  const descriptionText = [...blocks.values()].map((parts) => parts.join(' ')).join('\n');
  const jsonld = [...document.querySelectorAll('script[type="application/ld+json"]')].map((node) => node.textContent || '');
  if (descriptionText.length > 80000 || jsonld.join('').length > 160000) return { error: 'source_too_large' };
  const headings = [...document.querySelectorAll(heading)]
    .filter(visible).map((node) => clean(node.innerText)).filter(Boolean);
  const companyNodes = [...document.querySelectorAll('[data-automation-id="companyName"],.company-name,.job__company,.ashby-job-posting-header .ashby-job-posting-company-name')];
  const logos = [...document.querySelectorAll('header img[alt], .posting-headline img[alt], .main-header-logo img[alt], img[data-automation-id="logo"]')];
  let headerRoot = document.querySelector(heading);
  while (headerRoot?.parentElement && !headerRoot.contains(roots[0])) headerRoot = headerRoot.parentElement;
  const sectionText = headerRoot?.innerText || '';
  const boundary = sectionText.indexOf(roots[0].innerText.trim().slice(0, 80));
  const headerText = clean(boundary > 0 ? sectionText.slice(0, boundary) : headings[0]);
  if (headerText.length > 8000) return { error: 'source_too_large' };
  const careersCompany = [...document.querySelectorAll('h1')].map((node) => clean(node.innerText)).filter((text) => /^Careers at .+/.test(text)).map((text) => text.replace(/^Careers at /, ''));
  return {
    final_url: location.href,
    heading: headings[0] || '',
    company_candidates: [...careersCompany, ...companyNodes.filter(visible).map((node) => clean(node.innerText)), ...logos.filter(visible).map((node) => clean(node.alt).replace(/ logo$/i, ''))].filter(Boolean).slice(0, 10),
    page_title: clean(document.title),
    header_text: headerText,
    description: descriptionText,
    jsonld,
  };
}
