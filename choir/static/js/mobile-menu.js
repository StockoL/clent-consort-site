/* ==========================================================================
   NAVIGATION MENU TOGGLE (Mobile Responsiveness)
   ========================================================================== */

const initMobileMenu = () => {
  const menuToggle = document.querySelector(".menu-toggle");
  const navList = document.getElementById("nav-list");

  if (!menuToggle || !navList) return;

  const toggleMenu = () => {
    const isExpanded = menuToggle.getAttribute("aria-expanded") === "true";
    menuToggle.setAttribute("aria-expanded", !isExpanded);
    navList.classList.toggle("is-open");
  };

  menuToggle.addEventListener("click", toggleMenu);

  document.addEventListener("click", (event) => {
    const isClickInsideMenu = navList.contains(event.target);
    const isClickOnToggle = menuToggle.contains(event.target);
    const isMenuOpen = navList.classList.contains("is-open");

    if (!isClickInsideMenu && !isClickOnToggle && isMenuOpen) {
      toggleMenu();
    }
  });

  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape" && navList.classList.contains("is-open")) {
      toggleMenu();
    }
  });
};

document.addEventListener("DOMContentLoaded", initMobileMenu);
