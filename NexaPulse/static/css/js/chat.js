// Mobile nav toggle (works on home + dashboard)
const navToggle = document.getElementById("navToggle");
if (navToggle) {
  const navLinks = document.querySelector(".nav-links");
  const navActions = document.querySelector(".nav-actions");

  navToggle.addEventListener("click", () => {
    navLinks.classList.toggle("open");
    navActions.classList.toggle("open");
    navToggle.classList.toggle("active");
  });
}

// Doctor dashboard: queue click + fake submit
const queueItems = document.querySelectorAll(".queue-item");
if (queueItems.length > 0) {
  queueItems.forEach((item) => {
    item.addEventListener("click", () => {
      queueItems.forEach((i) => i.classList.remove("active"));
      item.classList.add("active");
      // later: fetch question details with fetch('/api/question/<id>')
    });
  });
}

const responseForm = document.getElementById("responseForm");
if (responseForm) {
  responseForm.addEventListener("submit", (e) => {
    e.preventDefault();

    const formData = new FormData(responseForm);
    const payload = {
      answer: formData.get("answer"),
      mark_urgent: formData.get("mark_urgent") === "on",
      offer_chat: formData.get("offer_chat") === "on",
      offer_slot: formData.get("offer_slot") === "on",
    };

    // TODO: send to backend:
    // fetch('/api/respond', { method: 'POST', headers: {'Content-Type':'application/json'}, body: JSON.stringify(payload) })

    alert("Response submitted (demo).");
    responseForm.reset();
  });
}
