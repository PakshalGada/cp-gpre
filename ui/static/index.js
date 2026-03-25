document.addEventListener("DOMContentLoaded", () => {
  // Navbar scroll shadow
  const navbar = document.getElementById("navbar");
  if (navbar) {
    window.addEventListener("scroll", () => {
      navbar.classList.toggle("scrolled", window.scrollY > 8);
    });
  }

  const path = window.location.pathname;
  document.querySelectorAll(".nav-link").forEach((link) => {
    link.classList.remove("active");
    const page = link.dataset.page;
    if (
      (page === "home" && (path === "/" || path === "/index")) ||
      (page === "resource" && path.startsWith("/resource")) ||
      (page === "practice" && path.startsWith("/practice"))
    ) {
      link.classList.add("active");
    }
  });
});
