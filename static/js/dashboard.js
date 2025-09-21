// Declare variables before use
let recognition;
let isRecording = false;
const webkitSpeechRecognition = window.webkitSpeechRecognition; // Declare webkitSpeechRecognition

// Get cookie value by name
function getCookie(name) {
  const value = `; ${document.cookie}`;
  const parts = value.split(`; ${name}=`);
  if (parts.length === 2) return parts.pop().split(";").shift();
}

// Show notification message of a given type: success, error, info, warning
function showNotification(message, type) {
  const notificationDiv = document.createElement("div");
  notificationDiv.className = `notification ${type}`;
  notificationDiv.textContent = message;

  document.body.appendChild(notificationDiv);

  setTimeout(() => {
    notificationDiv.remove();
  }, 3000);
}

// Chat functionality initialization
function initializeChat() {
  const sendBtn = document.getElementById("sendBtn");
  const chatInput = document.getElementById("chatInput");
  const voiceBtn = document.getElementById("voiceBtn");

  if (sendBtn) {
    sendBtn.addEventListener("click", sendMessage);
  }

  if (chatInput) {
    chatInput.addEventListener("keypress", (e) => {
      if (e.key === "Enter") {
        sendMessage();
      }
    });
  }

  if (voiceBtn) {
    voiceBtn.addEventListener("click", toggleVoiceRecording);
  }

  // Initialize speech recognition if supported
  if (webkitSpeechRecognition) {
    recognition = new webkitSpeechRecognition();
    recognition.continuous = false;
    recognition.interimResults = false;
    recognition.lang = "en-US";

    recognition.onresult = (event) => {
      const message = event.results[0][0].transcript.trim();
      document.getElementById("chatInput").value = message;
      sendMessage();
    };

    recognition.onerror = (event) => {
      console.error("Speech recognition error:", event.error);
      showNotification("Speech recognition error", "error");
    };
  }
}

// Send chat message to server
function sendMessage() {
  const chatInput = document.getElementById("chatInput");
  const message = chatInput.value.trim();

  if (!message) return;

  // Add user message to chat UI
  addMessageToChat(message, "user");

  // Clear input box
  chatInput.value = "";

  // Show bot typing indicator
  showTypingIndicator();

  // Get selected language for chat
  const language = document.getElementById("languageSelect").value;

  // POST message to chat API
  fetch("/api/chat/", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "X-CSRFToken": getCookie("csrftoken"),
    },
    body: JSON.stringify({
      message: message,
      language: language,
    }),
  })
    .then((response) => response.json())
    .then((data) => {
      hideTypingIndicator();
      addMessageToChat(data.response, "bot");
    })
    .catch((error) => {
      hideTypingIndicator();
      console.error("Error:", error);
      addMessageToChat("Sorry, I encountered an error. Please try again.", "bot");
    });
}

// Add a message div to the chat messages container
function addMessageToChat(message, sender) {
  const chatMessages = document.getElementById("chatMessages");
  const messageDiv = document.createElement("div");
  messageDiv.className = `message ${sender}-message`;

  // Use marked.js to convert markdown to HTML
  const htmlContent = marked.parse(message);

  // Insert parsed HTML into the message div
  messageDiv.innerHTML = htmlContent;

  chatMessages.appendChild(messageDiv);
  chatMessages.scrollTop = chatMessages.scrollHeight;
}

// Display typing indicator
function showTypingIndicator() {
  const chatMessages = document.getElementById("chatMessages");
  const typingDiv = document.createElement("div");
  typingDiv.className = "message bot-message typing-indicator";
  typingDiv.id = "typingIndicator";
  typingDiv.innerHTML = '<p>VidhikAI is typing... <span class="loading"></span></p>';

  chatMessages.appendChild(typingDiv);
  chatMessages.scrollTop = chatMessages.scrollHeight;
}

// Remove typing indicator from chat
function hideTypingIndicator() {
  const typingIndicator = document.getElementById("typingIndicator");
  if (typingIndicator) {
    typingIndicator.remove();
  }
}

// Start or stop voice recording for speech recognition
function toggleVoiceRecording() {
  const voiceBtn = document.getElementById("voiceBtn");

  if (!recognition) {
    showNotification("Speech recognition not supported in this browser", "error");
    return;
  }

  if (isRecording) {
    recognition.stop();
    voiceBtn.textContent = "Voice";
    voiceBtn.style.backgroundColor = "var(--secondary-color)";
    isRecording = false;
  } else {
    recognition.start();
    voiceBtn.textContent = "Stop";
    voiceBtn.style.backgroundColor = "var(--error-color)";
    isRecording = true;
  }
}

// // Process uploaded document for summarization
// function processDocument(file) {
//   const formData = new FormData();
//   formData.append("document", file);

//   // Show loading state on upload area
//   const uploadArea = document.getElementById("uploadArea");
//   const originalContent = uploadArea.innerHTML;
//   uploadArea.innerHTML = '<div class="loading"></div><p>Processing document...</p>';

//   fetch("/api/summarize/", {
//     method: "POST",
//     headers: {
//       "X-CSRFToken": getCookie("csrftoken"),
//     },
//     body: formData,
//   })
//     .then((response) => response.json())
//     .then((data) => {
//       // Restore upload area content
//       uploadArea.innerHTML = originalContent;

//       if (data.summary) {
//         // Display summary result
//         const summaryResult = document.getElementById("summaryResult");
//         const summaryContent = document.getElementById("summaryContent");

//         summaryContent.textContent = data.summary;
//         summaryResult.style.display = "block";

//         showNotification("Document summarized successfully!", "success");
//       } else {
//         showNotification("Error processing document", "error");
//       }
//     })
//     .catch((error) => {
//       uploadArea.innerHTML = originalContent;
//       console.error("Error:", error);
//       showNotification("Error processing document", "error");
//     });
// }


// Switch between dashboard features
function switchFeature(feature) {
  const features = document.querySelectorAll(".feature");
  features.forEach((f) => (f.style.display = "none"));

  const activeFeature = document.getElementById(feature);
  if (activeFeature) {
    activeFeature.style.display = "block";
  }
}

// Initialize dashboard features on DOM load
document.addEventListener("DOMContentLoaded", () => {
  initializeChat();

  // Set default visible feature to chatbot
  switchFeature("chatbot");
});
