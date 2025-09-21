
// Global variables
let currentTheme = "light";
const isRecording = false;
let recognition = null;
const processDocument = null; // Declare processDocument variable placeholder

// Initialize app on DOM load
document.addEventListener("DOMContentLoaded", () => {
  initializeApp();
});

function initializeApp() {
  // Initialize speech recognition if supported
  if ("webkitSpeechRecognition" in window || "SpeechRecognition" in window) {
    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
    recognition = new SpeechRecognition();
    recognition.continuous = false;
    recognition.interimResults = false;
    recognition.lang = "en-US";

    recognition.onresult = (event) => {
      const transcript = event.results[0][0].transcript;
      const chatInput = document.getElementById("chatInput");
      if (chatInput) {
        chatInput.value = transcript;
      }
    };

    recognition.onerror = (event) => {
      console.error("Speech recognition error:", event.error);
      showNotification("Speech recognition error. Please try again.", "error");
    };
  }

  // Load saved theme from local storage or default to light
  const savedTheme = localStorage.getItem("vidhikpath-theme") || "light";
  setTheme(savedTheme);

  // Initialize file upload handlers
  initializeFileHandlers();
}

// Theme management: switch light/dark modes
function setTheme(theme) {
  currentTheme = theme;
  document.body.classList.toggle("dark-mode", theme === "dark");
  localStorage.setItem("vidhikpath-theme", theme);

  // Update theme toggle buttons' active state
  const themeButtons = document.querySelectorAll(".theme-btn");
  themeButtons.forEach((btn) => {
    btn.classList.toggle("active", btn.textContent.toLowerCase().includes(theme));
  });
}

// Navigation: switch visible feature content and active nav button
function switchFeature(feature) {
  // Hide all feature content areas
  const contents = document.querySelectorAll(".feature-content");
  contents.forEach((content) => content.classList.remove("active"));

  // Show selected feature content
  const targetContent = document.getElementById(feature + "Content");
  if (targetContent) {
    targetContent.classList.add("active");
  }

  // Update nav button active states
  const navButtons = document.querySelectorAll(".nav-btn");
  navButtons.forEach((btn) => btn.classList.remove("active"));

  const activeButton = document.getElementById(feature + "Btn");
  if (activeButton) {
    activeButton.classList.add("active");
  }
}

// Confirm and handle logout
function logout() {
  if (confirm("Are you sure you want to logout?")) {
    window.location.href = "/logout/";
  }
}

// Notification system for messages of various types
function showNotification(message, type = "info") {
  const notification = document.createElement("div");
  notification.className = `notification ${type}`;
  notification.textContent = message;

  // Style the notification element
  notification.style.cssText = `
      position: fixed;
      top: 20px;
      right: 20px;
      padding: 1rem 1.5rem;
      border-radius: 8px;
      color: white;
      font-weight: 600;
      z-index: 10000;
      animation: slideInRight 0.3s ease-out;
  `;

  // Set background color per notification type
  switch (type) {
    case "success":
      notification.style.backgroundColor = "#28A745";
      break;
    case "error":
      notification.style.backgroundColor = "#DC3545";
      break;
    case "warning":
      notification.style.backgroundColor = "#FFC107";
      notification.style.color = "#000";
      break;
    default:
      notification.style.backgroundColor = "#007BFF";
  }

  document.body.appendChild(notification);

  // Auto-remove notification after 3 seconds with fade-out animation
  setTimeout(() => {
    notification.style.animation = "slideOutRight 0.3s ease-out";
    setTimeout(() => {
      if (notification.parentNode) {
        notification.parentNode.removeChild(notification);
      }
    }, 300);
  }, 3000);
}

// File upload handlers: drag & drop, click, camera button
function initializeFileHandlers() {
  // File input change handler
  const fileInput = document.getElementById("fileInput");
  if (fileInput) {
    fileInput.addEventListener("change", handleDocumentUpload);
  }

  // Upload area drag & drop handlers
  const uploadArea = document.getElementById("uploadArea");
  if (uploadArea) {
    uploadArea.addEventListener("dragover", handleDragOver);
    uploadArea.addEventListener("drop", handleDrop);
  }

  // Camera button click handler
  const cameraBtn = document.getElementById("cameraBtn");
  if (cameraBtn) {
    cameraBtn.addEventListener("click", handleCameraCapture);
  }
}

// Handle drag over upload area for styling
function handleDragOver(e) {
  e.preventDefault();
  e.currentTarget.style.borderColor = "var(--primary-color)";
  e.currentTarget.style.backgroundColor = "#FFF8F5";
}

// Handle dropped files in upload area
function handleDrop(e) {
  e.preventDefault();
  const files = e.dataTransfer.files;
  if (files.length > 0) {
    processDocument(files[0]);
  }

  // Reset upload area styles
  e.currentTarget.style.borderColor = "var(--border-color)";
  e.currentTarget.style.backgroundColor = "white";
}

// Handle file selection via input
function handleDocumentUpload(e) {
  const file = e.target.files[0];
  if (file) {
    processDocument(file);
  }
}

// Placeholder camera capture handler
function handleCameraCapture() {
  // Placeholder action for camera use
  showNotification("Camera feature will be implemented with device camera access", "info");
}

// Utility: get named cookie from document.cookie
function getCookie(name) {
  let cookieValue = null;
  if (document.cookie && document.cookie !== "") {
    const cookies = document.cookie.split(";");
    for (let i = 0; i < cookies.length; i++) {
      const cookie = cookies[i].trim();
      if (cookie.substring(0, name.length + 1) === name + "=") {
        cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
        break;
      }
    }
  }
  return cookieValue;
}

// Add CSS animations dynamically to document head
const style = document.createElement("style");
style.textContent = `
    @keyframes slideInRight {
        from {
            transform: translateX(100%);
            opacity: 0;
        }
        to {
            transform: translateX(0);
            opacity: 1;
        }
    }
    
    @keyframes slideOutRight {
        from {
            transform: translateX(0);
            opacity: 1;
        }
        to {
            transform: translateX(100%);
            opacity: 0;
        }
    }
`;
document.head.appendChild(style);
