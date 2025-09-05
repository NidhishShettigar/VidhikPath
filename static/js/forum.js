
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
      // Clear form inputs
      document.getElementById("postContent").value = "";
      document.getElementById("postImage").value = "";

      // Add new post to top of feed
      addPostToFeed(data);

      showNotification("Post created successfully!", "success");
    })
    .catch((error) => {
      console.error("Error:", error);
      showNotification("Error creating post", "error");
    });
}

// Add a post's HTML to the forum feed
function addPostToFeed(postData) {
  const forumPosts = document.getElementById("forumPosts");
  const imageHtml = postData.image
    ? `<img src="/media/${postData.image}" alt="Post image" class="post-image">`
    : "";

  const postHTML = `
    <div class="forum-post" data-post-id="${postData.id}">
      <div class="post-header">
        <div class="post-user">${postData.user}</div>
        <div class="post-time">${postData.created_at}</div>
      </div>
      
      <div class="post-content">
        <p>${postData.content}</p>
        ${imageHtml}
      </div>
      
      <div class="post-actions">
        <button class="action-btn like-btn" onclick="likePost('${postData.id}')">
          Like <span class="like-count">${postData.likes_count}</span>
        </button>
        <button class="action-btn reply-btn" onclick="toggleReply('${postData.id}')">Reply</button>
        <button class="action-btn share-btn" onclick="sharePost('${postData.id}')">Share</button>
      </div>
      
      <div class="reply-section" id="replySection${postData.id}" style="display: none;">
        <textarea placeholder="Write a reply..." id="replyText${postData.id}"></textarea>
        <button class="btn btn-sm btn-primary" onclick="submitReply('${postData.id}')">Reply</button>
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
    body: JSON.stringify({ post_id: postId }),
  })
    .then((response) => response.json())
    .then((data) => {
      if (data.error) {
        showNotification(data.error, "error");
        return;
      }

      const likeBtn = document.querySelector(`[data-post-id="${postId}"] .like-btn`);
      const likeCount = likeBtn.querySelector(".like-count");

      likeCount.textContent = data.likes_count;
      likeBtn.classList.toggle("liked", data.liked);
      
      // Style color change depending on like status
      if (data.liked) {
        likeBtn.style.color = "#8a4b01";
      } else {
        likeBtn.style.color = "#B96902";
      }
    })
    .catch((error) => {
      console.error("Error:", error);
      showNotification("Error liking post", "error");
    });
}

// Toggle reply section visibility
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
      if (data.error) {
        showNotification(data.error, "error");
        return;
      }

      // Clear reply textarea
      document.getElementById(`replyText${postId}`).value = "";

      // Append new reply HTML to replies section
      const repliesContainer = document.getElementById(`replies${postId}`);
      const replyHTML = `
        <div class="reply">
          <strong>${data.user}:</strong> ${data.content}
          <small>${data.created_at}</small>
        </div>
      `;

      repliesContainer.insertAdjacentHTML("beforeend", replyHTML);

      // Hide reply section
      document.getElementById(`replySection${postId}`).style.display = "none";

      showNotification("Reply posted successfully!", "success");
    })
    .catch((error) => {
      console.error("Error:", error);
      showNotification("Error posting reply", "error");
    });
}

// Share a post: uses Web Share API or clipboard fallback
function sharePost(postId) {
  const postUrl = `${window.location.origin}/forum/post/${postId}/`;

  if (navigator.share) {
    navigator.share({
      title: "VidhikPath Forum Post",
      text: "Check out this post on VidhikPath",
      url: postUrl,
    }).catch((error) => {
      console.log('Error sharing:', error);
      fallbackShare(postUrl);
    });
  } else {
    fallbackShare(postUrl);
  }
}

// Fallback share method: copy link to clipboard or alert user
function fallbackShare(url) {
  if (navigator.clipboard) {
    navigator.clipboard.writeText(url).then(() => {
      showNotification("Link copied to clipboard!", "success");
    }).catch(() => {
      // Older browser fallback for copying text
      const textArea = document.createElement("textarea");
      textArea.value = url;
      document.body.appendChild(textArea);
      textArea.select();
      document.execCommand('copy');
      document.body.removeChild(textArea);
      showNotification("Link copied to clipboard!", "success");
    });
  } else {
    showNotification("Sharing not supported on this browser", "warning");
  }
}

// Utility to get CSRF token from cookies
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

// Display a notification message on the page
function showNotification(message, type) {
  const notification = document.createElement('div');
  notification.className = `notification ${type}`;
  notification.style.cssText = `
    position: fixed;
    top: 20px;
    right: 20px;
    padding: 10px 20px;
    border-radius: 5px;
    color: white;
    font-weight: bold;
    z-index: 1000;
    transition: opacity 0.3s ease;
  `;

  switch(type) {
    case 'success':
      notification.style.backgroundColor = '#4CAF50';
      break;
    case 'error':
      notification.style.backgroundColor = '#f44336';
      break;
    case 'warning':
      notification.style.backgroundColor = '#ff9800';
      break;
    default:
      notification.style.backgroundColor = '#2196F3';
  }

  notification.textContent = message;
  document.body.appendChild(notification);

  // Auto-remove notification after 3 seconds with fade out
  setTimeout(() => {
    notification.style.opacity = '0';
    setTimeout(() => {
      if (notification.parentNode) {
        document.body.removeChild(notification);
      }
    }, 300);
  }, 3000);
}

// Switch visible feature section on the dashboard
function switchFeature(feature) {
  const features = document.querySelectorAll(".feature");
  features.forEach((f) => (f.style.display = "none"));

  const activeFeature = document.getElementById(feature);
  if (activeFeature) {
    activeFeature.style.display = "block";
  }
}

// Initialize forum related event listeners when DOM loaded
document.addEventListener("DOMContentLoaded", () => {
  // Optionally initialize any existing likes styling here

  // Handle image file selection for new posts
  const imageInput = document.getElementById('postImage');
  if (imageInput) {
    imageInput.addEventListener('change', function() {
      if (this.files && this.files[0]) {
        const fileName = this.files[0].name;
        showNotification(`Image selected: ${fileName}`, 'success');
      }
    });
  }
});
