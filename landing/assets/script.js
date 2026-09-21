document.getElementById("year").textContent = new Date().getFullYear();

const header = document.querySelector(".site-header");
const navToggle = document.getElementById("navToggle");

navToggle.addEventListener("click", () => {
  const isOpen = header.classList.toggle("nav-open");
  navToggle.setAttribute("aria-expanded", String(isOpen));
});

document.querySelectorAll(".nav a").forEach((link) => {
  link.addEventListener("click", () => {
    header.classList.remove("nav-open");
    navToggle.setAttribute("aria-expanded", "false");
  });
});

const contactForm = document.getElementById("contactForm");
const formStatus = document.getElementById("formStatus");

contactForm.addEventListener("submit", (event) => {
  event.preventDefault();
  const data = new FormData(contactForm);
  const subject = `درخواست دمو از ${data.get("company")}`;
  const body = [
    `نام: ${data.get("name")}`,
    `کارخانه: ${data.get("company")}`,
    `ایمیل: ${data.get("email")}`,
    "",
    data.get("message"),
  ].join("\n");
  window.location.href = `mailto:hello@granovo.ir?subject=${encodeURIComponent(subject)}&body=${encodeURIComponent(body)}`;
  formStatus.textContent = "پیام شما در نرم‌افزار ایمیل آماده‌ی ارسال شد.";
});
