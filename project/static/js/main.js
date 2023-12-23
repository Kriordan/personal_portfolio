const modal = document.getElementById("modal");

window.onclick = function (event) {
  if (event.target == modal) {
    modal.style.display = "none";
    document.body.style.overflow = "auto";
  }
};

function openModal(formName) {
  modal.style.display = "block";
  document.body.style.overflow = "hidden";

  fetch("/get-form?form=" + formName)
    .then(function (response) {
      if (!response.ok) {
        throw new Error("Network response was not ok");
      }
      return response.text();
    })
    .then(function (html) {
      document.getElementById("modal-body").innerHTML = html;
    })
    .catch(function (error) {
      console.error("Problem with fetch operation:", error);
    });
}
