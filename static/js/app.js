const toggle = document.querySelector('.menu-button');
document.querySelectorAll('#navigation a').forEach(link => {
  const path = new URL(link.href).pathname;
  if (path === '/' ? location.pathname === '/' : location.pathname.startsWith(path)) link.setAttribute('aria-current', 'page');
});
toggle?.addEventListener('click', () => {
  const expanded = toggle.getAttribute('aria-expanded') === 'true';
  toggle.setAttribute('aria-expanded', String(!expanded));
  document.getElementById('navigation').classList.toggle('open', !expanded);
});
document.querySelectorAll('img[data-fallback]').forEach(img => {
  const fallback = () => {
    const block = document.createElement('span');
    block.className = 'image-placeholder';
    block.textContent = 'Иллюстрация пока недоступна';
    img.replaceWith(block);
  };
  img.addEventListener('error', fallback, { once: true });
  if (img.complete && !img.naturalWidth) fallback();
});
