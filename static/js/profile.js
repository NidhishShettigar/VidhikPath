// Open profile modal
function openProfile() {
  document.getElementById("profileModal").style.display = "flex";
}

// Close profile modal and redirect to chatbot page
function closeProfile() {
  window.location.href = "/chatbot/";  // Redirect to chatbot URL
}

// Save profile via form submission with fetch API
function saveProfile() {
  const form = document.querySelector("form");
  const formData = new FormData(form);

  fetch("{% url 'profile' %}", {
    method: "POST",
    headers: {
      "X-CSRFToken": getCookie("csrftoken")
    },
    body: formData
  })
  .then(() => {
    showNotification("Profile updated successfully!", "success");
    closeProfile();
    location.reload();  // Reload to show updated name/photo
  })
  .catch(() => showNotification("Update failed", "error"));
}

// Confirm and handle logout
function logout() {
  if (confirm("Are you sure you want to logout?")) {
    window.location.href = "/logout/";
  }
}

// Set theme to 'light' or 'dark'
function setTheme(theme) {
  // Apply or remove dark-mode class on body
  if (theme === "dark") {
    document.body.classList.add("dark-mode");
  } else {
    document.body.classList.remove("dark-mode");
  }

  // Save theme choice to localStorage
  localStorage.setItem("vidhikpath-theme", theme);

  // Update active state of theme buttons
  const buttons = document.querySelectorAll(".theme-btn");
  buttons.forEach(btn => {
    const btnTheme = btn.textContent.toLowerCase().includes("dark") ? "dark" : "light";
    btn.classList.toggle("active", btnTheme === theme);
  });
}

// On page load, apply saved theme or default to light
document.addEventListener("DOMContentLoaded", () => {
  const savedTheme = localStorage.getItem("vidhikpath-theme") || "light";
  setTheme(savedTheme);
});

// Notification helper: show message on page
function showNotification(msg, type="info") {
  const n = document.createElement("div");
  n.className = `notification ${type}`;
  n.textContent = msg;
  document.body.appendChild(n);

  // Remove notification after 3 seconds
  setTimeout(() => n.remove(), 3000);
}
