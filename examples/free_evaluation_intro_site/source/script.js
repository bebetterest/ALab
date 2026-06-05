const toggle = document.querySelector("#theme-toggle");

if (toggle) {
  toggle.addEventListener("click", () => {
    const enabled = document.body.classList.toggle("night");
    toggle.setAttribute("aria-pressed", String(enabled));
    toggle.textContent = enabled ? "切换白天氛围" : "切换夜间氛围";
  });
}
