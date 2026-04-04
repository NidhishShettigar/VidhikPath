// Declare variables before use
let recognition;
let isRecording = false;
const webkitSpeechRecognition = window.webkitSpeechRecognition;
let chatHistory = []; // In-memory chat history for the session
const marked = window.marked; // Declare marked variable

// Initialize chat history from sessionStorage
function initializeChatHistory() {
  const stored = sessionStorage.getItem("chatHistory");
  if (stored) {
    try {
      chatHistory = JSON.parse(stored);
      console.log("Loaded chat history:", chatHistory.length, "messages");
      // Restore chat messages to UI
      restoreChatUI();
    } catch (e) {
      console.error("Failed to parse chat history:", e);
      chatHistory = [];
    }
  } else {
    console.log("No previous chat history found");
  }
}

// Restore chat messages to UI from history
function restoreChatUI() {
  const chatMessages = document.getElementById("chatMessages");
  // Clear existing messages except welcome message
  const welcomeMsg = chatMessages.querySelector(".message.bot-message");
  chatMessages.innerHTML = "";
  if (welcomeMsg) {
    chatMessages.appendChild(welcomeMsg);
  }
  
  // Add all messages from history
  chatHistory.forEach(msg => {
    const messageDiv = document.createElement("div");
    messageDiv.className = `message ${msg.role}-message`;
    const htmlContent = marked.parse(msg.content);
    messageDiv.innerHTML = htmlContent;
    chatMessages.appendChild(messageDiv);
  });
  
  chatMessages.scrollTop = chatMessages.scrollHeight;
}

// Save chat history to sessionStorage
function saveChatHistory() {
  try {
    sessionStorage.setItem("chatHistory", JSON.stringify(chatHistory));
    console.log("Saved chat history:", chatHistory.length, "messages");
  } catch (e) {
    console.error("Failed to save chat history:", e);
  }
}

// Add message to history
function addToHistory(message, role) {
  chatHistory.push({
    role: role,
    content: message,
    timestamp: new Date().toISOString(),
  });
  saveChatHistory();
}

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

  // Add styles inline if notification class doesn't exist
  notificationDiv.style.cssText = `
    position: fixed;
    top: 20px;
    right: 20px;
    padding: 1rem 1.5rem;
    background: ${type === 'error' ? '#ef4444' : type === 'success' ? '#10b981' : '#3b82f6'};
    color: white;
    border-radius: 8px;
    box-shadow: 0 4px 6px rgba(0,0,0,0.1);
    z-index: 9999;
    animation: slideIn 0.3s ease-out;
  `;

  document.body.appendChild(notificationDiv);

  setTimeout(() => {
    notificationDiv.remove();
  }, 4000);
}

// Chat functionality initialization
function initializeChat() {
  console.log("Initializing chat...");
  initializeChatHistory(); // Load chat history on init

  const sendBtn = document.getElementById("sendBtn");
  const chatInput = document.getElementById("chatInput");
  const voiceBtn = document.getElementById("voiceBtn");

  if (sendBtn) {
    console.log("Send button found, attaching event listener");
    sendBtn.addEventListener("click", function(e) {
      e.preventDefault();
      console.log("Send button clicked");
      sendMessage();
    });
  } else {
    console.error("Send button not found!");
  }

  if (chatInput) {
    chatInput.addEventListener("keypress", (e) => {
      if (e.key === "Enter") {
        e.preventDefault();
        console.log("Enter key pressed");
        sendMessage();
      }
    });
  } else {
    console.error("Chat input not found!");
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
      isRecording = false;
      const voiceBtn = document.getElementById("voiceBtn");
      if (voiceBtn) {
        voiceBtn.textContent = "Voice";
        voiceBtn.style.backgroundColor = "var(--secondary-color)";
      }
    };

    recognition.onend = () => {
      isRecording = false;
      const voiceBtn = document.getElementById("voiceBtn");
      if (voiceBtn) {
        voiceBtn.textContent = "Voice";
        voiceBtn.style.backgroundColor = "";
      }
    };
  }
}

// Send message function
function sendMessage() {
  console.log("sendMessage() called");
  const chatInput = document.getElementById("chatInput");
  const message = chatInput.value.trim();

  console.log("Message:", message);

  if (!message) {
    console.log("Empty message, returning");
    return;
  }

  // Add user message to chat UI
  addMessageToChat(message, "user");

  // Add to history
  addToHistory(message, "user");

  // Clear input box
  chatInput.value = "";

  // Show bot typing indicator
  showTypingIndicator();

  // Get selected language for chat
  const languageSelect = document.getElementById("languageSelect");
  const language = languageSelect ? languageSelect.value : "english";

  console.log("Sending request to API with language:", language);
  console.log("Chat history length:", chatHistory.length);

  fetch("/api/chat/", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "X-CSRFToken": getCookie("csrftoken"),
    },
    body: JSON.stringify({
      message: message,
      language: language,
      history: chatHistory, // Send chat history to backend
    }),
  })
    .then((response) => {
      console.log("Response status:", response.status);
      return response.json();
    })
    .then((data) => {
      console.log("Response data:", data);
      hideTypingIndicator();
      
      if (data.error) {
        console.error("API error:", data.error);
        showNotification(data.error, "error");
      }
      
      addMessageToChat(data.response, "bot");
      addToHistory(data.response, "bot");
    })
    .catch((error) => {
      hideTypingIndicator();
      console.error("Fetch error:", error);
      const errorMsg = "Sorry, I encountered an error. Please try again.";
      addMessageToChat(errorMsg, "bot");
      showNotification("Connection error. Please check your network.", "error");
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
  typingDiv.innerHTML = '<p>VidhikAI is typing<span class="dots">...</span></p>';

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
    voiceBtn.style.backgroundColor = "";
    isRecording = false;
  } else {
    try {
      recognition.start();
      voiceBtn.textContent = "Stop";
      voiceBtn.style.backgroundColor = "#ef4444";
      isRecording = true;
    } catch (error) {
      console.error("Error starting recognition:", error);
      showNotification("Could not start voice recognition", "error");
    }
  }
}

// Clear chat history
function clearChatHistory() {
  if (confirm("Are you sure you want to clear the chat history?")) {
    chatHistory = [];
    sessionStorage.removeItem("chatHistory");
    const chatMessages = document.getElementById("chatMessages");
    chatMessages.innerHTML = `
      <div class="message bot-message">
        <p>Hello! I'm VidhikAI, your legal assistant. How can I help you with legal matters today?</p>
      </div>
    `;
    showNotification("Chat history cleared", "success");
  }
}

// Initialize dashboard features on DOM load
document.addEventListener("DOMContentLoaded", () => {
  console.log("DOM loaded, initializing chat");
  initializeChat();
});
