(() => {
  const games = document.querySelector('[data-draw-reference]');
  if (!games) return;
  const expires = Math.min(...Array.from(games.querySelectorAll('[data-cutoff]'), game => Date.parse(game.dataset.cutoff)));
  const easternDate = date => date.toLocaleDateString('en-US', { timeZone: 'America/New_York' });
  const shownDate = easternDate(new Date(games.dataset.asOf));
  const check = () => {
    if (Date.now() >= expires || easternDate(new Date()) !== shownDate) {
      games.hidden = true;
      document.querySelector('[data-draw-expired]').hidden = false;
    }
  };
  check();
  setInterval(check, 1000);
})();
