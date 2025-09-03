// VidhikPath Dashboard Specific Functions

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

// Process uploaded document for summarization
function processDocument(file) {
  const formData = new FormData();
  formData.append("document", file);

  // Show loading state on upload area
  const uploadArea = document.getElementById("uploadArea");
  const originalContent = uploadArea.innerHTML;
  uploadArea.innerHTML = '<div class="loading"></div><p>Processing document...</p>';

  fetch("/api/summarize/", {
    method: "POST",
    headers: {
      "X-CSRFToken": getCookie("csrftoken"),
    },
    body: formData,
  })
    .then((response) => response.json())
    .then((data) => {
      // Restore upload area content
      uploadArea.innerHTML = originalContent;

      if (data.summary) {
        // Display summary result
        const summaryResult = document.getElementById("summaryResult");
        const summaryContent = document.getElementById("summaryContent");

        summaryContent.textContent = data.summary;
        summaryResult.style.display = "block";

        showNotification("Document summarized successfully!", "success");
      } else {
        showNotification("Error processing document", "error");
      }
    })
    .catch((error) => {
      uploadArea.innerHTML = originalContent;
      console.error("Error:", error);
      showNotification("Error processing document", "error");
    });
}

// Search lawyers by location and type
function searchLawyers() {
  const location = document.getElementById("locationInput").value;
  const type = document.getElementById("typeInput").value;

  fetch("/api/find-lawyers/", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "X-CSRFToken": getCookie("csrftoken"),
    },
    body: JSON.stringify({
      location: location,
      lawyer_type: type,
      use_current_location: false,
    }),
  })
    .then((response) => response.json())
    .then((data) => {
      displayLawyers(data.lawyers);
    })
    .catch((error) => {
      console.error("Error:", error);
      showNotification("Error searching lawyers", "error");
    });
}

// Use current geolocation to find lawyers nearby
function useCurrentLocation() {
  if (!navigator.geolocation) {
    showNotification("Geolocation not supported by this browser", "error");
    return;
  }

  navigator.geolocation.getCurrentPosition(
    (position) => {
      const lat = position.coords.latitude;
      const lng = position.coords.longitude;

      // Show info notification while searching
      showNotification("Using current location...", "info");

      // Request lawyers nearby using lat/lng
      fetch("/api/find-lawyers/", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-CSRFToken": getCookie("csrftoken"),
        },
        body: JSON.stringify({
          latitude: lat,
          longitude: lng,
          use_current_location: true,
        }),
      })
        .then((response) => response.json())
        .then((data) => {
          displayLawyers(data.lawyers);
        })
        .catch((error) => {
          console.error("Error:", error);
          showNotification("Error finding nearby lawyers", "error");
        });
    },
    (error) => {
      showNotification("Error getting location: " + error.message, "error");
    }
  );
}

// Display lawyer search results in the UI
function displayLawyers(lawyers) {
  const resultsContainer = document.getElementById("lawyersResults");

  if (lawyers.length === 0) {
    resultsContainer.innerHTML = '<p class="no-results">No lawyers found matching your criteria.</p>';
    return;
  }

  resultsContainer.innerHTML = lawyers
    .map(
      (lawyer) => `
        <div class="lawyer-card">
            <div class="lawyer-header">
                <div class="lawyer-name">${lawyer.name}</div>
                <div class="lawyer-type">${lawyer.type}</div>
            </div>
            
            <div class="lawyer-details">
                <div class="lawyer-detail">
                    <span>Location:</span> ${lawyer.location}
                </div>
                <div class="lawyer-detail">
                    <span>Experience:</span> ${lawyer.experience} years
                </div>
                <div class="lawyer-detail">
                    <span>Email:</span> ${lawyer.email}
                </div>
            </div>
            
            <div class="lawyer-actions">
                <button class="btn btn-primary btn-sm" onclick="contactLawyer('${lawyer.email}')">Contact</button>
                <button class="btn btn-secondary btn-sm" onclick="viewProfile('${lawyer.email}')">View Profile</button>
            </div>
        </div>
    `
    )
    .join("");
}

// Open default email client to contact lawyer
function contactLawyer(email) {
  window.location.href = `mailto:${email}?subject=Legal Consultation Request from VidhikPath`;
}

// Placeholder for lawyer profile feature
function viewProfile(email) {
  showNotification("Lawyer profile feature coming soon!", "info");
}

// Create a new forum post
function createPost() {
  const content = document.getElementById("postContent").value.trim();
  const imageFile = document.getElementById("postImage").files[0];

  if (!content) {
    showNotification("Please enter some content for your post", "warning");
    return;
  }

  const formData = new FormData();
  formData.append("content", content);
  if (imageFile) {
    formData.append("image", imageFile);
  }

  fetch("/api/forum/post/", {
    method: "POST",
    headers: {
      "X-CSRFToken": getCookie("csrftoken"),
    },
    body: formData,
  })
    .then((response) => response.json())
    .then((data) => {
      // Clear post form fields
      document.getElementById("postContent").value = "";
      document.getElementById("postImage").value = "";

      // Add new post to top of forum feed
      addPostToFeed(data);

      showNotification("Post created successfully!", "success");
    })
    .catch((error) => {
      console.error("Error:", error);
      showNotification("Error creating post", "error");
    });
}

// Add a new post HTML to the forum feed
function addPostToFeed(postData) {
  const forumPosts = document.getElementById("forumPosts");
  const postHTML = `
        <div class="forum-post" data-post-id="${postData.id}">
            <div class="post-header">
                <div class="post-user">${postData.user}</div>
                <div class="post-time">${postData.created_at}</div>
            </div>
            
            <div class="post-content">
                <p>${postData.content}</p>
            </div>
            
            <div class="post-actions">
                <button class="action-btn like-btn" onclick="likePost(${postData.id})">
                    Like <span class="like-count">${postData.likes_count}</span>
                </button>
                <button class="action-btn reply-btn" onclick="toggleReply(${postData.id})">Reply</button>
                <button class="action-btn share-btn" onclick="sharePost(${postData.id})">Share</button>
            </div>
            
            <div class="reply-section" id="replySection${postData.id}" style="display: none;">
                <textarea placeholder="Write a reply..." id="replyText${postData.id}"></textarea>
                <button class="btn btn-sm btn-primary" onclick="submitReply(${postData.id})">Reply</button>
            </div>
            
            <div class="replies" id="replies${postData.id}"></div>
        </div>
    `;

  forumPosts.insertAdjacentHTML("afterbegin", postHTML);
}

// Like or unlike a post
function likePost(postId) {
  fetch("/api/forum/like/", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "X-CSRFToken": getCookie("csrftoken"),
    },
    body: JSON.stringify({
      post_id: postId,
    }),
  })
    .then((response) => response.json())
    .then((data) => {
      const likeBtn = document.querySelector(`[data-post-id="${postId}"] .like-btn`);
      const likeCount = likeBtn.querySelector(".like-count");

      likeCount.textContent = data.likes_count;
      likeBtn.classList.toggle("liked", data.liked);
    })
    .catch((error) => {
      console.error("Error:", error);
      showNotification("Error liking post", "error");
    });
}

// Toggle visibility of reply input section for a post
function toggleReply(postId) {
  const replySection = document.getElementById(`replySection${postId}`);
  const isVisible = replySection.style.display !== "none";

  replySection.style.display = isVisible ? "none" : "block";

  if (!isVisible) {
    const textarea = document.getElementById(`replyText${postId}`);
    textarea.focus();
  }
}

// Submit a reply to a post
function submitReply(postId) {
  const replyText = document.getElementById(`replyText${postId}`).value.trim();

  if (!replyText) {
    showNotification("Please enter a reply", "warning");
    return;
  }

  fetch("/api/forum/reply/", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "X-CSRFToken": getCookie("csrftoken"),
    },
    body: JSON.stringify({
      post_id: postId,
      content: replyText,
    }),
  })
    .then((response) => response.json())
    .then((data) => {
      // Clear reply textarea
      document.getElementById(`replyText${postId}`).value = "";

      // Add reply to replies list
      const repliesContainer = document.getElementById(`replies${postId}`);
      const replyHTML = `
            <div class="reply">
                <strong>${data.user}:</strong> ${data.content}
                <small>${data.created_at}</small>
            </div>
        `;

      repliesContainer.insertAdjacentHTML("beforeend", replyHTML);

      // Hide reply input section
      document.getElementById(`replySection${postId}`).style.display = "none";

      showNotification("Reply posted successfully!", "success");
    })
    .catch((error) => {
      console.error("Error:", error);
      showNotification("Error posting reply", "error");
    });
}

// Share a post via Web Share API or fallback to clipboard copy
function sharePost(postId) {
  if (navigator.share) {
    navigator.share({
      title: "VidhikPath Forum Post",
      text: "Check out this post on VidhikPath",
      url: window.location.href,
    });
  } else {
    navigator.clipboard.writeText(window.location.href).then(() => {
      showNotification("Link copied to clipboard!", "success");
    });
  }
}

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
