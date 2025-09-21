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
      if (data.error) {
        showNotification(data.error, "error");
        return;
      }
      
      // Clear form inputs
      document.getElementById("postContent").value = "";
      document.getElementById("postImage").value = "";
      document.getElementById("charCount").textContent = "0";
      removeImagePreview();

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
    ? `<img src="/media/${postData.image}" alt="Post image" class="post-image" onclick="openImageModal(this.src)">`
    : "";

  const postHTML = `
    <div class="forum-post" data-post-id="${postData.id}">
      <div class="post-header">
        <div class="post-user">${postData.user}</div>
        <div class="post-time">${postData.created_at}</div>
        <div class="post-options">
          <button class="action-btn edit-btn" onclick="editPost('${postData.id}')">Edit</button>
          <button class="action-btn delete-btn" onclick="confirmDeletePost('${postData.id}')">Delete</button>
        </div>
      </div>
      
      <div class="post-content" id="postContent${postData.id}">
        <p>${postData.content}</p>
        ${imageHtml}
      </div>
      
      <div class="edit-post-section" id="editSection${postData.id}" style="display: none;">
        <textarea id="editText${postData.id}" maxlength="5000" oninput="updateCharCount(this, 'editCharCount${postData.id}')">${postData.content}</textarea>
        <div style="display: flex; justify-content: space-between; align-items: center; margin-top: 5px;">
          <small style="color: #6B4C36;">
            <span id="editCharCount${postData.id}">${postData.content.length}</span>/5000 characters
          </small>
          <div>
            <button class="btn btn-sm btn-secondary" onclick="cancelEditPost('${postData.id}')">Cancel</button>
            <button class="btn btn-sm btn-primary" onclick="saveEditPost('${postData.id}')">Save</button>
          </div>
        </div>
      </div>
      
      <div class="post-actions">
        <button class="action-btn like-btn" onclick="likePost('${postData.id}')">
          👍 <span class="like-count">${postData.likes_count || 0}</span>
        </button>
        <button class="action-btn reply-btn" onclick="toggleReply('${postData.id}')">💬 Reply</button>
        <button class="action-btn share-btn" onclick="sharePost('${postData.id}')">Share</button>
      </div>
      
      <div class="reply-section" id="replySection${postData.id}" style="display: none;">
        <textarea placeholder="Write a respectful reply..." id="replyText${postData.id}" maxlength="1000" oninput="updateCharCount(this, 'replyCharCount${postData.id}')"></textarea>
        <div style="display: flex; justify-content: space-between; align-items: center; margin-top: 5px;">
          <small style="color: #6B4C36;">
            <span id="replyCharCount${postData.id}">0</span>/1000 characters
          </small>
          <button class="btn btn-sm btn-primary" onclick="submitReply('${postData.id}')">Reply</button>
        </div>
      </div>
      
      <div class="replies" id="replies${postData.id}"></div>
    </div>
  `;

  forumPosts.insertAdjacentHTML("afterbegin", postHTML);
}

// Character count update function
function updateCharCount(textarea, counterId) {
  const count = textarea.value.length;
  const maxLength = textarea.maxLength;
  const counterElement = document.getElementById(counterId);
  
  if (counterElement) {
    counterElement.textContent = count;
    
    // Change color based on character count
    if (count > maxLength * 0.9) {
      counterElement.style.color = '#f44336';
    } else if (count > maxLength * 0.7) {
      counterElement.style.color = '#ff9800';
    } else {
      counterElement.style.color = '#6B4C36';
    }
  }
}

// Like or unlike a post - FIXED
function likePost(postId) {
  // Ensure postId is provided and valid
  if (!postId) {
    showNotification("Post ID is required", "error");
    return;
  }

  fetch("/api/forum/like/", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "X-CSRFToken": getCookie("csrftoken"),
    },
    body: JSON.stringify({ post_id: postId.toString() }),
  })
    .then((response) => response.json())
    .then((data) => {
      if (data.error) {
        showNotification(data.error, "error");
        return;
      }

      const likeBtn = document.querySelector(`[data-post-id="${postId}"] .like-btn`);
      if (likeBtn) {
        const likeCount = likeBtn.querySelector(".like-count");
        if (likeCount) {
          likeCount.textContent = data.likes_count;
        }
        
        likeBtn.classList.toggle("liked", data.liked);
        
        // Style color change depending on like status
        if (data.liked) {
          likeBtn.style.color = "#8a4b01";
        } else {
          likeBtn.style.color = "#B96902";
        }
      }
    })
    .catch((error) => {
      console.error("Error:", error);
      showNotification("Error liking post", "error");
    });
}

// Toggle reply section visibility - FIXED
function toggleReply(postId) {
  if (!postId) {
    showNotification("Post ID is required", "error");
    return;
  }

  const replySection = document.getElementById(`replySection${postId}`);
  if (!replySection) {
    showNotification("Reply section not found", "error");
    return;
  }

  const isVisible = replySection.style.display !== "none";
  replySection.style.display = isVisible ? "none" : "block";

  if (!isVisible) {
    const textarea = document.getElementById(`replyText${postId}`);
    if (textarea) {
      textarea.focus();
    }
  }
}

// Submit a reply to a post - FIXED
function submitReply(postId) {
  if (!postId) {
    showNotification("Post ID is required", "error");
    return;
  }

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
      post_id: postId.toString(),
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
    const charCountElement = document.getElementById(`replyCharCount${postId}`);
    if (charCountElement) {
      charCountElement.textContent = "0";
    }

    // Append new reply HTML to replies section
    const repliesContainer = document.getElementById(`replies${postId}`);
    const replyHTML = createReplyHTML(data, 0); // 0 depth for main reply

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

// Create reply HTML with nested structure - NEW ENHANCED FUNCTION
function createReplyHTML(replyData, depth = 0) {
  const indentClass = depth > 0 ? `nested-reply-depth-${Math.min(depth, 3)}` : '';
  const replyId = replyData.reply_id;
  const postId = replyData.post_id || replyData.parent_post_id;
  
  return `
    <div class="reply ${indentClass}" data-reply-id="${replyId}" data-depth="${depth}">
      <div class="reply-header">
        <strong>${replyData.user}:</strong>
        <small>${replyData.created_at}</small>
        <div class="reply-options">
          <button class="reply-edit-btn" onclick="editReply('${postId}', '${replyId}', ${depth})">Edit</button>
          <button class="reply-delete-btn" onclick="confirmDeleteReply('${postId}', '${replyId}', ${depth})">Delete</button>
        </div>
      </div>
      <div class="reply-content" id="replyContent${replyId}">
        ${replyData.content}
      </div>
      <div class="edit-reply-section" id="editReplySection${replyId}" style="display: none;">
        <textarea id="editReplyText${replyId}" maxlength="1000" oninput="updateCharCount(this, 'editReplyCharCount${replyId}')">${replyData.content}</textarea>
        <div style="display: flex; justify-content: space-between; align-items: center; margin-top: 5px;">
          <small style="color: #6B4C36;">
            <span id="editReplyCharCount${replyId}">${replyData.content.length}</span>/1000 characters
          </small>
          <div>
            <button class="btn btn-xs btn-secondary" onclick="cancelEditReply('${replyId}')">Cancel</button>
            <button class="btn btn-xs btn-primary" onclick="saveEditReply('${postId}', '${replyId}', ${depth})">Save</button>
          </div>
        </div>
      </div>
      <button class="nested-reply-btn" onclick="toggleNestedReply('${postId}', '${replyId}', ${depth + 1})">↳ Reply</button>
      <div class="nested-reply-section" id="nestedReplySection${replyId}" style="display: none;">
        <textarea 
          placeholder="Reply to ${replyData.user}..." 
          id="nestedReplyText${replyId}"
          maxlength="1000"
          oninput="updateCharCount(this, 'nestedReplyCharCount${replyId}')"
        ></textarea>
        <div style="display: flex; justify-content: space-between; align-items: center; margin-top: 5px;">
          <small style="color: #6B4C36;">
            <span id="nestedReplyCharCount${replyId}">0</span>/1000 characters
          </small>
          <button class="btn btn-xs btn-primary" onclick="submitNestedReply('${postId}', '${replyId}', ${depth + 1})">Reply</button>
        </div>
      </div>
      <div class="nested-replies" id="nestedReplies${replyId}"></div>
    </div>
  `;
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

// Image preview functions
function previewImage(input) {
  if (input.files && input.files[0]) {
    const reader = new FileReader();
    reader.onload = function(e) {
      document.getElementById('previewImg').src = e.target.result;
      document.getElementById('imagePreview').style.display = 'block';
    }
    reader.readAsDataURL(input.files[0]);
  }
}

function removeImagePreview() {
  document.getElementById('imagePreview').style.display = 'none';
  document.getElementById('postImage').value = '';
}

// Image modal functions
function openImageModal(src) {
  document.getElementById('modalImage').src = src;
  document.getElementById('imageModal').style.display = 'block';
}

function closeImageModal() {
  document.getElementById('imageModal').style.display = 'none';
}

// Confirmation modal functions
let pendingDeleteAction = null;

function showConfirmModal(title, message, action) {
  document.getElementById('confirmTitle').textContent = title;
  document.getElementById('confirmMessage').textContent = message;
  pendingDeleteAction = action;
  document.getElementById('confirmModal').style.display = 'block';
}

function closeConfirmModal() {
  document.getElementById('confirmModal').style.display = 'none';
  pendingDeleteAction = null;
}

function confirmDelete() {
  if (pendingDeleteAction) {
    pendingDeleteAction();
  }
  closeConfirmModal();
}

// Edit/Delete post functions
function editPost(postId) {
  const postContent = document.getElementById('postContent' + postId);
  const editSection = document.getElementById('editSection' + postId);
  
  if (postContent && editSection) {
    postContent.style.display = 'none';
    editSection.style.display = 'block';
  }
}

function cancelEditPost(postId) {
  const postContent = document.getElementById('postContent' + postId);
  const editSection = document.getElementById('editSection' + postId);
  
  if (postContent && editSection) {
    postContent.style.display = 'block';
    editSection.style.display = 'none';
  }
}

function saveEditPost(postId) {
  const newContent = document.getElementById('editText' + postId).value.trim();
  if (!newContent) {
    showNotification('Content cannot be empty', 'warning');
    return;
  }
  
  // API call to save edited post
  fetch("/api/forum/edit/", {
    method: "PUT",
    headers: {
      "Content-Type": "application/json",
      "X-CSRFToken": getCookie("csrftoken"),
    },
    body: JSON.stringify({
      post_id: postId,
      content: newContent
    }),
  })
    .then((response) => response.json())
    .then((data) => {
      if (data.error) {
        showNotification(data.error, "error");
        return;
      }
      
      // Update the post content in the DOM
      const postContentElement = document.querySelector(`#postContent${postId} p`);
      if (postContentElement) {
        postContentElement.textContent = newContent;
      }
      
      showNotification('Post updated successfully!', 'success');
      cancelEditPost(postId);
    })
    .catch((error) => {
      console.error("Error:", error);
      showNotification("Error updating post", "error");
    });
}

function confirmDeletePost(postId) {
  showConfirmModal(
    'Delete Post',
    'Are you sure you want to delete this post? This action cannot be undone.',
    () => deletePostConfirmed(postId)
  );
}

function deletePostConfirmed(postId) {
  fetch("/api/forum/delete/", {
    method: "DELETE",
    headers: {
      "Content-Type": "application/json",
      "X-CSRFToken": getCookie("csrftoken"),
    },
    body: JSON.stringify({ post_id: postId }),
  })
    .then((res) => {
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      return res.json();
    })
    .then((data) => {
      if (data.error) {
        showNotification(data.error, "error");
        return;
      }
      const postElement = document.querySelector(`[data-post-id="${postId}"]`);
      if (postElement) {
        postElement.remove();
      }
      showNotification("Post deleted successfully", "success");
    })
    .catch((err) => {
      console.error("Error:", err);
      showNotification("Error deleting post", "error");
    });
}

// Reply edit/delete functions - ENHANCED
function editReply(postId, replyId, depth = 0) {
  const replyContent = document.getElementById('replyContent' + replyId);
  const editSection = document.getElementById('editReplySection' + replyId);
  
  if (replyContent && editSection) {
    replyContent.style.display = 'none';
    editSection.style.display = 'block';
  }
}

function cancelEditReply(replyId) {
  const replyContent = document.getElementById('replyContent' + replyId);
  const editSection = document.getElementById('editReplySection' + replyId);
  
  if (replyContent && editSection) {
    replyContent.style.display = 'block';
    editSection.style.display = 'none';
  }
}

function saveEditReply(postId, replyId, depth = 0) {
  const newContent = document.getElementById('editReplyText' + replyId).value.trim();
  if (!newContent) {
    showNotification('Reply cannot be empty', 'warning');
    return;
  }
  
  // API call to save edited reply
  fetch("/api/forum/reply/edit/", {
    method: "PUT",
    headers: {
      "Content-Type": "application/json",
      "X-CSRFToken": getCookie("csrftoken"),
    },
    body: JSON.stringify({
      post_id: postId,
      reply_id: replyId,
      content: newContent,
      depth: depth
    }),
  })
    .then((response) => response.json())
    .then((data) => {
      if (data.error) {
        showNotification(data.error, "error");
        return;
      }
      
      // Update the reply content in the DOM
      const replyContentElement = document.getElementById('replyContent' + replyId);
      if (replyContentElement) {
        replyContentElement.innerHTML = newContent;
      }
      
      showNotification('Reply updated successfully!', 'success');
      cancelEditReply(replyId);
    })
    .catch((error) => {
      console.error("Error:", error);
      showNotification("Error updating reply", "error");
    });
}

function confirmDeleteReply(postId, replyId, depth = 0) {
  showConfirmModal(
    'Delete Reply',
    'Are you sure you want to delete this reply?',
    () => deleteReplyConfirmed(postId, replyId, depth)
  );
}

function deleteReplyConfirmed(postId, replyId, depth = 0) {
  fetch("/api/forum/reply/delete/", {
    method: "DELETE",
    headers: {
      "Content-Type": "application/json",
      "X-CSRFToken": getCookie("csrftoken"),
    },
    body: JSON.stringify({
      post_id: postId,
      reply_id: replyId,
      depth: depth
    }),
  })
    .then((response) => response.json())
    .then((data) => {
      if (data.error) {
        showNotification(data.error, "error");
        return;
      }
      
      const replyElement = document.querySelector(`[data-reply-id="${replyId}"]`);
      if (replyElement) {
        replyElement.remove();
      }
      showNotification('Reply deleted successfully!', 'success');
    })
    .catch((error) => {
      console.error("Error:", error);
      showNotification("Error deleting reply", "error");
    });
}

// Enhanced nested reply functions with infinite depth
function toggleNestedReply(postId, parentReplyId, depth = 1) {
  const section = document.getElementById('nestedReplySection' + parentReplyId);
  if (section) {
    const isVisible = section.style.display !== 'none';
    section.style.display = isVisible ? 'none' : 'block';
    
    if (!isVisible) {
      const textarea = document.getElementById('nestedReplyText' + parentReplyId);
      if (textarea) {
        textarea.focus();
      }
    }
  }
}

function submitNestedReply(postId, parentReplyId, depth = 1) {
  const content = document.getElementById('nestedReplyText' + parentReplyId).value.trim();
  if (!content) {
    showNotification('Please enter a reply', 'warning');
    return;
  }
  
  fetch("/api/forum/nested-reply/", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "X-CSRFToken": getCookie("csrftoken"),
    },
    body: JSON.stringify({
      post_id: postId,
      parent_reply_id: parentReplyId,
      content: content,
      depth: depth
    }),
  })
    .then((response) => response.json())
    .then((data) => {
      if (data.error) {
        showNotification(data.error, "error");
        return;
      }
      
      // Clear the textarea and hide the section
      document.getElementById('nestedReplyText' + parentReplyId).value = '';
      const charCountElement = document.getElementById('nestedReplyCharCount' + parentReplyId);
      if (charCountElement) {
        charCountElement.textContent = '0';
      }
      document.getElementById('nestedReplySection' + parentReplyId).style.display = 'none';
      
      // Add the nested reply to the DOM using the enhanced HTML creator
      const nestedRepliesContainer = document.getElementById('nestedReplies' + parentReplyId);
      const nestedReplyHTML = createReplyHTML(data, depth);
      
      nestedRepliesContainer.insertAdjacentHTML('beforeend', nestedReplyHTML);
      
      showNotification('Reply posted successfully!', 'success');
    })
    .catch((error) => {
      console.error("Error:", error);
      showNotification("Error posting nested reply", "error");
    });
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
  // Remove any existing notifications first
  const existingNotifications = document.querySelectorAll('.notification');
  existingNotifications.forEach(notification => notification.remove());

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
    case 'info':
      notification.style.backgroundColor = '#2196F3';
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
  // Handle image file selection for new posts
  const imageInput = document.getElementById('postImage');
  if (imageInput) {
    imageInput.addEventListener('change', function() {
      if (this.files && this.files[0]) {
        const fileName = this.files[0].name;
        showNotification(`Image selected: ${fileName}`, 'success');
        previewImage(this);
      }
    });
  }

  // Initialize character counting for main post textarea
  const postContent = document.getElementById('postContent');
  if (postContent) {
    postContent.addEventListener('input', function() {
      updateCharCount(this, 'charCount');
    });
  }

  // Close modals when clicking outside
  window.onclick = function(event) {
    const imageModal = document.getElementById('imageModal');
    const confirmModal = document.getElementById('confirmModal');
    
    if (event.target === imageModal) {
      closeImageModal();
    }
    if (event.target === confirmModal) {
      closeConfirmModal();
    }
  };
});