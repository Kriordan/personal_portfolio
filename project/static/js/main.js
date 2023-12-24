const modal = document.getElementById("modal");

window.onclick = function (event) {
  if (event.target == modal) {
    modal.style.display = "none";
    document.body.style.overflow = "auto";
  }
};

function openModal() {
  modal.style.display = "block";
  document.body.style.overflow = "hidden";
}

function closeModal() {
  modal.style.display = "none";
  document.body.style.overflow = "auto";
}
