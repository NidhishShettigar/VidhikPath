// Open profile modal
function openProfile() {
  document.getElementById("profileModal").style.display = "flex";
}

// Close profile modal
function closeProfile() {
  if (window.history.length > 1) {
    // Go back if history exists
    window.history.back();
  } else if (document.referrer && document.referrer !== window.location.href) {
    // Otherwise, use referrer if available
    window.location.href = document.referrer;
  } else {
    // Fallback: go to chatbot
    window.location.href = "/chatbot/";
  }
}


// Save profile via form submission with fetch API
function saveProfile() {
  const form = document.querySelector("#profileForm");
  const formData = new FormData(form);

  fetch("/api/profile/update/", {
    method: "POST",
    headers: {
      "X-CSRFToken": getCookie("csrftoken")
    },
    body: formData
  })
  .then(response => response.json())
  .then(data => {
    if (data.success) {
      showNotification("Profile updated successfully!", "success");
      closeProfile();
      location.reload();  // Refresh UI to reflect changes
    } else {
      showNotification("Update failed: " + (data.error || ""), "error");
    }
  })
  .catch(() => showNotification("Update failed", "error"));
}


// Confirm and handle logout
function logout() {
  if (confirm("Are you sure you want to logout?")) {
    window.location.href = "/logout/";
  }
}

// Notification helper: show message on page
function showNotification(msg, type="info") {
  const n = document.createElement("div");
  n.className = `notification ${type}`;
  n.textContent = msg;
  document.body.appendChild(n);

  // Remove notification after 3 seconds
  setTimeout(() => n.remove(), 3000);
}
