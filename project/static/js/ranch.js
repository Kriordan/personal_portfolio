const imageInput = document.querySelector('.RanchImages-input--file')
const imageInputLabel = document.querySelector('.RanchImages-fileLabel')

imageInput.addEventListener('change', () => {
  if(imageInput.files.length > 0) {
    imageInputLabel.classList.add('file-added')
  }
})