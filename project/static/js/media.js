const player = document.querySelector(".Media-youtubePlayer");

document.addEventListener("click", function (e) {
  const youtubeCard = e.target.closest(".Media-youtubeCard");
  if (!youtubeCard) return;
  if (youtubeCard.dataset.youtubeid != undefined) {
    const iframe = buildYoutubeIframe(youtubeCard.dataset.youtubeid);
    const oldIframe = document.querySelector(".Media-youtubePlayerIframe");
    if (oldIframe) {
      player.removeChild(oldIframe);
    }
    player.appendChild(iframe);
    player.style.height = "500px";
    player.style.opacity = 1;
  }
});

function buildYoutubeIframe(playlistId) {
  const iframe = document.createElement("iframe");
  iframe.classList.add("Media-youtubePlayerIframe");
  iframe.width = "560";
  iframe.height = "315";
  iframe.src = `https://www.youtube.com/embed/videoseries?list=${playlistId}`;
  iframe.frameborder = "0";
  iframe.allow =
    "accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture";
  iframe.setAttribute("allowFullScreen", "");
  return iframe;
}
