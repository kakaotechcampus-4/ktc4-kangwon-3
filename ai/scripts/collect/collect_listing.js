(async () => {
  const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
  const host = location.hostname;
  const site = host.includes("temu") ? "temu" : host.includes("aliexpress") ? "aliexpress" : host;
  const MARKERS = ["제품 세부 정보", "상점 정보", "관심 상품 둘러보기", "인기 추천", "리뷰", "설명", "사양", "구매자 질문", "면책 조항", "추천 상품", "개요", "상품 정보", "고객 이용 후기", "함께 볼 만한 상품", "연관 상품", "Product details", "Store Information", "Explore your interests", "Description", "Specifications", "Reviews", "Customer Questions", "More to love", "Related products", "Overview"];
  const DETAIL_START = ["제품 세부 정보", "상품 정보", "개요", "Product details", "Specifications", "Description", "Overview"];
  const DETAIL_END = ["관심 상품 둘러보기", "인기 추천", "구매자 질문", "면책 조항", "함께 볼 만한 상품", "Explore your interests", "Customer Questions", "More to love", "Related products"];
  const EXPANDERS = ["더보기", "더 보기", "자세한 내용 보기", "See all details", "View more", "View More", "See more", "Show more"];
  const startY = window.scrollY;
  const step = Math.max(400, Math.floor(window.innerHeight * 0.8));
  const scrollToBottom = async () => {
    let atBottom = 0;
    for (let i = 0; i < 500; i++) {
      window.scrollBy(0, step);
      await sleep(250);
      const h = document.documentElement.scrollHeight;
      if (window.scrollY + window.innerHeight >= h - 10) {
        atBottom += 1;
        if (atBottom >= 5) break;
      } else {
        atBottom = 0;
      }
    }
  };
  const abs = (u) => {
    try { return new URL(u, location.href).href; } catch (e) { return null; }
  };
  const allElements = (root, out, depth) => {
    if (depth > 6) return out;
    root.querySelectorAll("*").forEach((el) => {
      out.push(el);
      if (el.shadowRoot) allElements(el.shadowRoot, out, depth + 1);
    });
    return out;
  };
  // shadow root의 textContent는 <style>·<script> 내용까지 섞여 나온다. 글 노드만 모은다.
  const shadowText = (root) => {
    const skip = /^(STYLE|SCRIPT|NOSCRIPT|TEMPLATE)$/;
    const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT, {
      acceptNode: (n) => (n.parentElement && skip.test(n.parentElement.tagName) ? NodeFilter.FILTER_REJECT : NodeFilter.FILTER_ACCEPT),
    });
    const parts = [];
    let n;
    while ((n = walker.nextNode())) parts.push(n.nodeValue);
    return parts.join(String.fromCharCode(10));
  };
  const findMarkers = () => {
    const found = [];
    allElements(document, [], 0).forEach((el) => {
      if (!/^(H1|H2|H3|H4|DIV|SPAN|P|A|BUTTON|LI)$/.test(el.tagName)) return;
      if (el.childElementCount > 2) return;
      const t = (el.innerText || el.textContent || "").trim();
      if (!t || t.length > 30) return;
      const hit = MARKERS.find((m) => t === m || t.startsWith(m + " ") || t.startsWith(m + "("));
      if (!hit) return;
      const r = el.getBoundingClientRect();
      if (r.width === 0 && r.height === 0) return;
      found.push({ text: hit, raw: t, top: Math.round(r.top + window.scrollY) });
    });
    found.sort((a, b) => a.top - b.top);
    return found;
  };
  const detailRange = (markers) => {
    const start = markers.find((m) => DETAIL_START.includes(m.text));
    const end = markers.find((m) => DETAIL_END.includes(m.text) && (!start || m.top > start.top));
    return { low: start ? start.top : 0, high: end ? end.top : Number.MAX_SAFE_INTEGER };
  };
  await scrollToBottom();
  await sleep(1500);
  const before = detailRange(findMarkers());
  const textAsPasted = document.body.innerText;
  const expanded = [];
  allElements(document, [], 0).forEach((el) => {
    if (!/^(BUTTON|DIV|SPAN|A)$/.test(el.tagName)) return;
    if (el.childElementCount > 1) return;
    const href = el.getAttribute("href");
    if (el.tagName === "A" && href && !href.startsWith("#") && !href.startsWith("javascript")) return;
    const t = (el.innerText || el.textContent || "").trim();
    if (!EXPANDERS.includes(t)) return;
    const r = el.getBoundingClientRect();
    if (r.width === 0 && r.height === 0) return;
    const top = Math.round(r.top + window.scrollY);
    if (top < before.low - 50 || top > before.high) return;
    try {
      el.scrollIntoView({ block: "center" });
      el.click();
      expanded.push({ text: t, top: top });
    } catch (e) {}
  });
  if (expanded.length) {
    await sleep(2000);
    await scrollToBottom();
    await sleep(2000);
  }
  const seen = new Map();
  const addImage = (u, w, h, top, alt, where, lazy) => {
    if (!u || u.startsWith("data:") || u.startsWith("blob:") || u === location.href) return;
    if (!lazy && Math.max(w, h) < 200) return;
    if (!seen.has(u)) {
      seen.set(u, { src: u, width: Math.round(w), height: Math.round(h), top: Math.round(top), alt: (alt || "").slice(0, 80), where: where, lazy: !!lazy });
    }
  };
  const firstSrcset = (s) => (s || "").split(",")[0].trim().split(/\s+/)[0];
  const grab = (root, frameTop, where) => {
    allElements(root, [], 0).forEach((el) => {
      const r = el.getBoundingClientRect();
      const top = r.top + frameTop;
      if (el.tagName === "IMG") {
        const raw = el.currentSrc || el.src || firstSrcset(el.srcset) || el.getAttribute("data-src") || el.getAttribute("data-lazy-src") || el.getAttribute("data-original") || "";
        const lazy = !el.currentSrc && !el.src;
        addImage(abs(raw), el.naturalWidth || r.width, el.naturalHeight || r.height, top, el.alt, where, lazy);
        return;
      }
      if (el.tagName === "SOURCE" && el.srcset) {
        const pr = el.parentElement ? el.parentElement.getBoundingClientRect() : r;
        addImage(abs(firstSrcset(el.srcset)), pr.width, pr.height, pr.top + frameTop, "", where + ":source", false);
        return;
      }
      if (r.width >= 150 && r.height >= 150) {
        const bg = getComputedStyle(el).backgroundImage;
        const m = bg && bg !== "none" ? bg.match(/url\(["']?([^"')]+)["']?\)/) : null;
        if (m) addImage(abs(m[1]), r.width, r.height, top, "", where + ":bg", false);
      }
    });
  };
  grab(document, window.scrollY, "main");
  const frames = [];
  const walkFrames = (root, baseTop, depth) => {
    if (depth > 4) return;
    allElements(root, [], 0).filter((el) => el.tagName === "IFRAME").forEach((f) => {
      const fr = f.getBoundingClientRect();
      const top = Math.round(fr.top + baseTop);
      const info = { depth: depth, src: f.src || f.getAttribute("data-src") || "", top: top, height: Math.round(fr.height), same_origin: false, images: 0 };
      try {
        const inner = f.contentDocument;
        if (inner) {
          info.same_origin = true;
          const n = seen.size;
          grab(inner, top, "frame" + depth);
          info.images = seen.size - n;
          info.body_chars = inner.body && inner.body.innerText ? inner.body.innerText.length : 0;
          info.body_children = inner.body ? inner.body.childElementCount : -1;
          walkFrames(inner, top, depth + 1);
        }
      } catch (e) {
        info.error = String(e).slice(0, 80);
      }
      frames.push(info);
    });
  };
  walkFrames(document, window.scrollY, 1);
  const markers = findMarkers();
  const range = detailRange(markers);
  const probe = [];
  allElements(document, [], 0).forEach((el) => {
    const r = el.getBoundingClientRect();
    const top = r.top + window.scrollY;
    if (top < range.low || top >= range.high || r.height < 300) return;
    probe.push({ tag: el.tagName, id: el.id || "", cls: String(el.className || "").slice(0, 60), top: Math.round(top), w: Math.round(r.width), h: Math.round(r.height), kids: el.childElementCount, shadow: !!el.shadowRoot, text_chars: (el.innerText || "").length });
  });
  const images = [...seen.values()].sort((a, b) => a.top - b.top);
  const text = document.body.innerText;
  const detailParts = [];
  allElements(document, [], 0).forEach((el) => {
    if (!el.shadowRoot) return;
    const r = el.getBoundingClientRect();
    const top = r.top + window.scrollY;
    if (top < range.low || top >= range.high) return;
    const t = shadowText(el.shadowRoot).split(String.fromCharCode(10)).map((l) => l.trim()).filter((l) => l).join(String.fromCharCode(10));
    if (t) detailParts.push(t);
  });
  const detailText = detailParts.join(String.fromCharCode(10, 10));
  const cleanUrl = location.origin + location.pathname;
  const data = {
    site: site,
    url: cleanUrl,
    title: document.title,
    collected_at: new Date().toISOString(),
    page_height: document.documentElement.scrollHeight,
    detail_range: range,
    expanded: expanded,
    frames: frames,
    markers: markers,
    probe: probe.slice(0, 80),
    text: text,
    text_as_pasted: textAsPasted,
    detail_text: detailText,
    images: images,
  };
  const name = site + "_" + new Date().toISOString().replace(/[:.]/g, "-").slice(0, 19) + ".json";
  const blob = new Blob([JSON.stringify(data, null, 1)], { type: "application/json" });
  const a = document.createElement("a");
  a.href = URL.createObjectURL(blob);
  a.download = name;
  document.body.appendChild(a);
  a.click();
  a.remove();
  window.scrollTo(0, startY);
  const inRange = images.filter((i) => i.top >= range.low && i.top < range.high).length;
  console.log("[collect_listing]", name, data);
  alert("저장: " + name + "\n글 " + text.length + "자, 이미지 " + images.length + "장 (상세 구역 안 " + inRange + "장), 표지 " + markers.length + "개, 펼침 " + expanded.length + "개, 프레임 " + frames.length + "개");
})();
