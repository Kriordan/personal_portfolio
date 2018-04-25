$('.takes').on('click', function(e) {
  $('.Bookshelf-takes').toggleClass('is-open');
  e.preventDefault();
});

$(document).foundation();