// Forum functionality
function createPost() {
  const content = document.getElementById("postContent").value.trim()
  const imageFile = document.getElementById("postImage").files[0]

  if (!content) {
    showNotification("Please enter some content for your post", "warning")
    return
  }

  const formData = new FormData()
  formData.append("content", content)
  if (imageFile) {
    formData.append("image", imageFile)
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
      // Clear form
      document.getElementById("postContent").value = ""
      document.getElementById("postImage").value = ""

      // Add new post to top of feed
      addPostToFeed(data)

      showNotification("Post created successfully!", "success")
    })
    .catch((error) => {
      console.error("Error:", error)
      showNotification("Error creating post", "error")
    })
}

function addPostToFeed(postData) {
  const forumPosts = document.getElementById("forumPosts")
  const imageHtml = postData.image ? `<img src="/media/${postData.image}" alt="Post image" class="post-image">` : ''
  
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
          👍 <span class="like-count">${postData.likes_count}</span>
        </button>
        <button class="action-btn reply-btn" onclick="toggleReply('${postData.id}')">💬 Reply</button>
        <button class="action-btn share-btn" onclick="sharePost('${postData.id}')">📤 Share</button>
      </div>
      
      <div class="reply-section" id="replySection${postData.id}" style="display: none;">
        <textarea placeholder="Write a reply..." id="replyText${postData.id}"></textarea>
        <button class="btn btn-sm btn-primary" onclick="submitReply('${postData.id}')">Reply</button>
      </div>
      
      <div class="replies" id="replies${postData.id}"></div>
    </div>
  `

  forumPosts.insertAdjacentHTML("afterbegin", postHTML)
}

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
      if (data.error) {
        showNotification(data.error, "error")
        return
      }

      const likeBtn = document.querySelector(`[data-post-id="${postId}"] .like-btn`)
      const likeCount = likeBtn.querySelector(".like-count")

      likeCount.textContent = data.likes_count
      likeBtn.classList.toggle("liked", data.liked)
      
      if (data.liked) {
        likeBtn.style.color = "#8a4b01"
      } else {
        likeBtn.style.color = "#B96902"
      }
    })
    .catch((error) => {
      console.error("Error:", error)
      showNotification("Error liking post", "error")
    })
}

function toggleReply(postId) {
  const replySection = document.getElementById(`replySection${postId}`)
  const isVisible = replySection.style.display !== "none"

  replySection.style.display = isVisible ? "none" : "block"

  if (!isVisible) {
    const textarea = document.getElementById(`replyText${postId}`)
    textarea.focus()
  }
}

function submitReply(postId) {
  const replyText = document.getElementById(`replyText${postId}`).value.trim()

  if (!replyText) {
    showNotification("Please enter a reply", "warning")
    return
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
        showNotification(data.error, "error")
        return
      }

      // Clear reply text
      document.getElementById(`replyText${postId}`).value = ""

      // Add reply to replies section
      const repliesContainer = document.getElementById(`replies${postId}`)
      const replyHTML = `
        <div class="reply">
          <strong>${data.user}:</strong> ${data.content}
          <small>${data.created_at}</small>
        </div>
      `

      repliesContainer.insertAdjacentHTML("beforeend", replyHTML)

      // Hide reply section
      document.getElementById(`replySection${postId}`).style.display = "none"

      showNotification("Reply posted successfully!", "success")
    })
    .catch((error) => {
      console.error("Error:", error)
      showNotification("Error posting reply", "error")
    })
}

function sharePost(postId) {
  const postUrl = `${window.location.origin}/forum/post/${postId}/`
  
  if (navigator.share) {
    navigator.share({
      title: "VidhikPath Forum Post",
      text: "Check out this post on VidhikPath",
      url: postUrl,
    }).catch((error) => {
      console.log('Error sharing:', error)
      fallbackShare(postUrl)
    })
  } else {
    fallbackShare(postUrl)
  }
}

function fallbackShare(url) {
  if (navigator.clipboard) {
    navigator.clipboard.writeText(url).then(() => {
      showNotification("Link copied to clipboard!", "success")
    }).catch(() => {
      // Fallback for older browsers
      const textArea = document.createElement("textarea")
      textArea.value = url
      document.body.appendChild(textArea)
      textArea.select()
      document.execCommand('copy')
      document.body.removeChild(textArea)
      showNotification("Link copied to clipboard!", "success")
    })
  } else {
    showNotification("Sharing not supported on this browser", "warning")
  }
}

// Utility function to get CSRF token
function getCookie(name) {
  let cookieValue = null
  if (document.cookie && document.cookie !== '') {
    const cookies = document.cookie.split(';')
    for (let i = 0; i < cookies.length; i++) {
      const cookie = cookies[i].trim()
      if (cookie.substring(0, name.length + 1) === (name + '=')) {
        cookieValue = decodeURIComponent(cookie.substring(name.length + 1))
        break
      }
    }
  }
  return cookieValue
}

// Notification function (you may need to implement this based on your existing notification system)
function showNotification(message, type) {
  // Create notification element
  const notification = document.createElement('div')
  notification.className = `notification ${type}`
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
  `
  
  // Set background color based on type
  switch(type) {
    case 'success':
      notification.style.backgroundColor = '#4CAF50'
      break
    case 'error':
      notification.style.backgroundColor = '#f44336'
      break
    case 'warning':
      notification.style.backgroundColor = '#ff9800'
      break
    default:
      notification.style.backgroundColor = '#2196F3'
  }
  
  notification.textContent = message
  document.body.appendChild(notification)
  
  // Remove notification after 3 seconds
  setTimeout(() => {
    notification.style.opacity = '0'
    setTimeout(() => {
      if (notification.parentNode) {
        document.body.removeChild(notification)
      }
    }, 300)
  }, 3000)
}

// Function to switch features (if needed for your dashboard)
function switchFeature(feature) {
  const features = document.querySelectorAll(".feature")
  features.forEach((f) => (f.style.display = "none"))

  const activeFeature = document.getElementById(feature)
  if (activeFeature) {
    activeFeature.style.display = "block"
  }
}

// Initialize forum when DOM is loaded
document.addEventListener("DOMContentLoaded", () => {
  // Initialize any existing likes styling
  document.querySelectorAll('.like-btn').forEach(btn => {
    const postId = btn.closest('.forum-post').dataset.postId
    // You could fetch current like status here if needed
  })
  
  // Handle image preview for new posts
  const imageInput = document.getElementById('postImage')
  if (imageInput) {
    imageInput.addEventListener('change', function() {
      if (this.files && this.files[0]) {
        const fileName = this.files[0].name
        showNotification(`Image selected: ${fileName}`, 'success')
      }
    })
  }
})