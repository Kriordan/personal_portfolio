// While logged in, run these functions from:
// https://www.youtube.com/feed/library

function getPlaylistHrefs() {
  const hrefArr = [];
  document
    .querySelectorAll(
      "ytd-item-section-renderer:nth-of-type(3) ytd-grid-playlist-renderer #video-title"
    )
    .forEach((el) => hrefArr.push(el.href));
  return hrefArr;
}

function stripPlaylistIds(hrefArr) {
  return hrefArr.map((href) => {
    const url = new URL(href);
    const paramString = new URLSearchParams(url.search);
    return paramString.get("list");
  });
}

const hrefs = getPlaylistHrefs();
const playlistIds = stripPlaylistIds(hrefs);
