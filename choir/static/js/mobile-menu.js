/* ==========================================================================
   NAVIGATION MENU TOGGLE (Mobile Responsiveness)
   ========================================================================== */
/**
 * Opens and closes the phone menu: the toggle's aria-expanded drives the
 * hamburger-to-cross animation (blocks/site-header.css), and a backdrop
 * dims the page underneath. The menu closes on Escape, on a tap on the
 * backdrop or anywhere outside it, and when a menu link is followed.
 */
const initMobileMenu = () => {
  const menuToggle = document.querySelector(".menu-toggle");
  const navList = document.getElementById("nav-list");
  const backdrop = document.querySelector("[data-nav-backdrop]");

  if (!menuToggle || !navList) return;

  const isOpen = () => navList.classList.contains("is-open");

  const setOpen = (open) => {
    menuToggle.setAttribute("aria-expanded", open);
    navList.classList.toggle("is-open", open);
    if (backdrop) backdrop.hidden = !open;
  };

  menuToggle.addEventListener("click", () => setOpen(!isOpen()));

  document.addEventListener("click", (event) => {
    if (!isOpen()) return;
    const insideMenu = navList.contains(event.target);
    const onToggle = menuToggle.contains(event.target);

    if (!insideMenu && !onToggle) {
      setOpen(false);
    } else if (insideMenu && event.target.closest("a")) {
      // Following a link (including one to this page) closes the menu
      setOpen(false);
    }
  });

  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape" && isOpen()) {
      setOpen(false);
      menuToggle.focus();
    }
  });
};

document.addEventListener("DOMContentLoaded", initMobileMenu);
