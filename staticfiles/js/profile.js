// Get CSRF token from cookie
function getCookie(name) {
  let cookieValue = null;
  if (document.cookie && document.cookie !== '') {
    const cookies = document.cookie.split(';');
    for (let i = 0; i < cookies.length; i++) {
      const cookie = cookies[i].trim();
      if (cookie.substring(0, name.length + 1) === (name + '=')) {
        cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
        break;
      }
    }
  }
  return cookieValue;
}

// Open profile modal
function openProfile() {
  document.getElementById("profileModal").style.display = "flex";
}

// Close profile modal
function closeProfile() {
  if (window.history.length > 1) {
    window.history.back();
  } else if (document.referrer && document.referrer !== window.location.href) {
    window.location.href = document.referrer;
  } else {
    window.location.href = "/chatbot/";
  }
}

// Save profile via form submission with fetch API
function saveProfile() {
  const form = document.querySelector("#profileForm");
  const formData = new FormData(form);

  // Use the correct endpoint that matches your URL configuration
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
      setTimeout(() => {
        closeProfile();
        location.reload();  // Refresh UI to reflect changes
      }, 1000);
    } else {
      showNotification("Update failed: " + (data.error || "Unknown error"), "error");
    }
  })
  .catch(error => {
    console.error("Error:", error);
    showNotification("Update failed: " + error.message, "error");
  });
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

  setTimeout(() => n.remove(), 3000);
}