// VidhikPath - Main JavaScript Functions

// Global variables
let currentTheme = "light"
const isRecording = false
let recognition = null
const processDocument = null // Declare processDocument variable

// Initialize app
document.addEventListener("DOMContentLoaded", () => {
  initializeApp()
})

function initializeApp() {
  // Initialize speech recognition if available
  if ("webkitSpeechRecognition" in window || "SpeechRecognition" in window) {
    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition
    recognition = new SpeechRecognition()
    recognition.continuous = false
    recognition.interimResults = false
    recognition.lang = "en-US"

    recognition.onresult = (event) => {
      const transcript = event.results[0][0].transcript
      const chatInput = document.getElementById("chatInput")
      if (chatInput) {
        chatInput.value = transcript
      }
    }

    recognition.onerror = (event) => {
      console.error("Speech recognition error:", event.error)
      showNotification("Speech recognition error. Please try again.", "error")
    }
  }

  // Load saved theme
  const savedTheme = localStorage.getItem("vidhikpath-theme") || "light"
  setTheme(savedTheme)

  // Initialize file upload handlers
  initializeFileHandlers()
}

// Theme management
function setTheme(theme) {
  currentTheme = theme
  document.body.classList.toggle("dark-mode", theme === "dark")
  localStorage.setItem("vidhikpath-theme", theme)

  // Update theme buttons
  const themeButtons = document.querySelectorAll(".theme-btn")
  themeButtons.forEach((btn) => {
    btn.classList.toggle("active", btn.textContent.toLowerCase().includes(theme))
  })
}

// Navigation functions
function switchFeature(feature) {
  // Hide all content
  const contents = document.querySelectorAll(".feature-content")
  contents.forEach((content) => content.classList.remove("active"))

  // Show selected content
  const targetContent = document.getElementById(feature + "Content")
  if (targetContent) {
    targetContent.classList.add("active")
  }

  // Update navigation buttons
  const navButtons = document.querySelectorAll(".nav-btn")
  navButtons.forEach((btn) => btn.classList.remove("active"))

  const activeButton = document.getElementById(feature + "Btn")
  if (activeButton) {
    activeButton.classList.add("active")
  }
}

// Profile modal functions
function openProfile() {
  const modal = document.getElementById("profileModal")
  if (modal) {
    modal.style.display = "flex"
  }
}

function closeProfile() {
  const modal = document.getElementById("profileModal")
  if (modal) {
    modal.style.display = "none"
  }
}

function saveProfile() {
  const name = document.getElementById("profileName")?.value

  // Here you would typically send this data to the server
  // For now, we'll just show a success message
  showNotification("Profile updated successfully!", "success")
  closeProfile()
}

function logout() {
  if (confirm("Are you sure you want to logout?")) {
    window.location.href = "/logout/"
  }
}

// Notification system
function showNotification(message, type = "info") {
  const notification = document.createElement("div")
  notification.className = `notification ${type}`
  notification.textContent = message

  // Style the notification
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
    `

  // Set background color based on type
  switch (type) {
    case "success":
      notification.style.backgroundColor = "#28A745"
      break
    case "error":
      notification.style.backgroundColor = "#DC3545"
      break
    case "warning":
      notification.style.backgroundColor = "#FFC107"
      notification.style.color = "#000"
      break
    default:
      notification.style.backgroundColor = "#007BFF"
  }

  document.body.appendChild(notification)

  // Remove after 3 seconds
  setTimeout(() => {
    notification.style.animation = "slideOutRight 0.3s ease-out"
    setTimeout(() => {
      if (notification.parentNode) {
        notification.parentNode.removeChild(notification)
      }
    }, 300)
  }, 3000)
}

// File upload handlers
function initializeFileHandlers() {
  // Document upload handler
  const fileInput = document.getElementById("fileInput")
  if (fileInput) {
    fileInput.addEventListener("change", handleDocumentUpload)
  }

  // Drag and drop for upload area
  const uploadArea = document.getElementById("uploadArea")
  if (uploadArea) {
    uploadArea.addEventListener("dragover", handleDragOver)
    uploadArea.addEventListener("drop", handleDrop)
  }

  // Camera button handler
  const cameraBtn = document.getElementById("cameraBtn")
  if (cameraBtn) {
    cameraBtn.addEventListener("click", handleCameraCapture)
  }
}

function handleDragOver(e) {
  e.preventDefault()
  e.currentTarget.style.borderColor = "var(--primary-color)"
  e.currentTarget.style.backgroundColor = "#FFF8F5"
}

function handleDrop(e) {
  e.preventDefault()
  const files = e.dataTransfer.files
  if (files.length > 0) {
    processDocument(files[0])
  }

  // Reset styles
  e.currentTarget.style.borderColor = "var(--border-color)"
  e.currentTarget.style.backgroundColor = "white"
}

function handleDocumentUpload(e) {
  const file = e.target.files[0]
  if (file) {
    processDocument(file)
  }
}

function handleCameraCapture() {
  // This would typically open camera interface
  // For now, we'll show a placeholder message
  showNotification("Camera feature will be implemented with device camera access", "info")
}

// Utility functions
function getCookie(name) {
  let cookieValue = null
  if (document.cookie && document.cookie !== "") {
    const cookies = document.cookie.split(";")
    for (let i = 0; i < cookies.length; i++) {
      const cookie = cookies[i].trim()
      if (cookie.substring(0, name.length + 1) === name + "=") {
        cookieValue = decodeURIComponent(cookie.substring(name.length + 1))
        break
      }
    }
  }
  return cookieValue
}

// Add CSS animations
const style = document.createElement("style")
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
`
document.head.appendChild(style)
