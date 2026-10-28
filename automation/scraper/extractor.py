"""Extract LinkedIn post identifiers from response text and the rendered page."""

import re
import httpx
from bs4 import BeautifulSoup
from datetime import datetime, timezone, timedelta

from playwright.async_api import Page

from automation.models.post import PostRecord, PostReference

URN_REGEX = re.compile(r"urn:li:(activity|ugcPost|share):(\d{18,20})")
ACTIVITY_SLUG_REGEX = re.compile(r"activity-(\d{18,20})")

READ_DOM_AND_FIBER_JS = r"""
() => {
  const urnRe = /urn:li:(activity|ugcPost|share):(\d{18,20})/g;
  const slugRe = /activity-(\d{18,20})/g;
  const seen = new Set();
  const out = [];

  function add(type, id) {
    if (!id || seen.has(id)) return;
    seen.add(id);
    out.push({ type, id });
  }

  function scanString(str) {
    if (!str || typeof str !== 'string') return;
    let m;
    urnRe.lastIndex = 0;
    while ((m = urnRe.exec(str)) !== null) add(m[1], m[2]);
    slugRe.lastIndex = 0;
    while ((m = slugRe.exec(str)) !== null) add('activity', m[1]);
  }

  scanString(document.body ? document.body.innerHTML : '');
  const root = document.querySelector('main') || document.body;
  if (root) {
    for (const el of root.querySelectorAll('*')) {
      for (const key of Object.keys(el)) {
        if (key.startsWith('__reactProps$') || key.startsWith('__reactFiber$')) {
          try {
            const serialized = JSON.stringify(el[key], (k, v) => {
              if (k.startsWith('_') || typeof v === 'function' || v instanceof Node) return undefined;
              return v;
            });
            scanString(serialized);
          } catch (error) {
            // A single unserializable React node should not stop extraction.
          }
        }
      }
    }
  }
  return out;
}
"""


class PostExtractor:
    """Pure parsing and record conversion, kept separate from browser navigation."""

    def extract_urns_from_text(self, text: str) -> list[PostReference]:
        found: dict[str, PostReference] = {}
        for match in URN_REGEX.finditer(text):
            post_type, post_id = match.groups()
            found[post_id] = PostReference(type=post_type, id=post_id)

        for match in ACTIVITY_SLUG_REGEX.finditer(text):
            post_id = match.group(1)
            found.setdefault(post_id, PostReference(type="activity", id=post_id))

        return list(found.values())

    async def extract_from_page(self, page: Page) -> list[PostReference]:
        raw_items = await page.evaluate(READ_DOM_AND_FIBER_JS)
        return [PostReference.model_validate(item) for item in raw_items]

    def extract_content_date_from_url(self,url):
      response = httpx.get(
          url,
          headers={"User-Agent": "Mozilla/5.0"},
          follow_redirects=True,
          timeout=20,
      )        
      response.raise_for_status()
      soup = BeautifulSoup(response.text, "html.parser")
      # Extract post ID from URL
      match = re.search(r"activity:(\d+)", url)
      post_id = match.group(1) if match else None

      # Decode approximate timestamp from activity ID
      date = None

      if post_id:
          timestamp_ms = int(post_id) >> 22

          ist = timezone(timedelta(hours=5, minutes=30))

          date = datetime.fromtimestamp(
              timestamp_ms / 1000,
              tz=timezone.utc,
          ).astimezone(ist).isoformat()

      # Extract post content
      content = None

      for selector in [
          ".update-components-text",
          ".feed-shared-update-v2__description",
          ".feed-shared-text",
      ]:
          tag = soup.select_one(selector)

          if tag:
              content = tag.get_text("\n", strip=True)
              if content:
                  break

      # Fallback to Open Graph description
      if not content:
          tag = soup.find("meta", property="og:description")
          if tag:
              content = tag.get("content")

      return content,date


    def to_record(self, item: PostReference, base_url: str) -> PostRecord:
        normalized_base = base_url.rstrip("/")
        post_url = f"{normalized_base}/feed/update/urn:li:{item.type}:{item.id}/"
        post_content, posted_date =  self.extract_content_date_from_url(post_url)
        return PostRecord(post_id=item.id, post_url=post_url, post_content=post_content, posted_date = posted_date) if posted_date else None
