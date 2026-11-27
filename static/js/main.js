// Небольшое мобильное меню. Остальная работа сайта выполняется на сервере Flask.
const menuButton = document.querySelector('.menu-button');
const navigation = document.querySelector('.navigation');

if (menuButton && navigation) {
  menuButton.addEventListener('click', () => {
    const isOpen = navigation.classList.toggle('is-open');
    menuButton.setAttribute('aria-expanded', String(isOpen));
  });
}
