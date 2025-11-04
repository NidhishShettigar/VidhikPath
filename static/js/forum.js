// FIXED forum.js - All issues resolved

// Create a new forum post with image support
function createPost() {
  const content = document.getElementById("postContent").value.trim();
  const imageFile = document.getElementById("postImage").files[0];

  if (!content && !imageFile) {
    showNotification("Please enter content or upload an image", "warning");
    return;
  }

  // Validate image size (5MB max)
  if (imageFile && imageFile.size > 5 * 1024 * 1024) {
    showNotification("Image size should not exceed 5MB", "error");
    return;
  }

  // Validate image type
  if (imageFile && !imageFile.type.startsWith('image/')) {
    showNotification("Please upload a valid image file", "error");
    return;
  }

  const formData = new FormData();
  formData.append("content", content);
  if (imageFile) {
    formData.append("image", imageFile);
  }

  const createBtn = document.getElementById("createPostBtn");
  const originalText = createBtn.textContent;
  createBtn.textContent = "Posting...";
  createBtn.disabled = true;

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
      
      document.getElementById("postContent").value = "";
      document.getElementById("postImage").value = "";
      document.getElementById("charCount").textContent = "0";
      removeImagePreview();

      addPostToFeed(data);
      showNotification("Post created successfully!", "success");
    })
    .catch((error) => {
      console.error("Error:", error);
      showNotification("Error creating post", "error");
    })
    .finally(() => {
      createBtn.textContent = originalText;
      createBtn.disabled = false;
    });
}

// Add a post to the forum feed - FIXED with proper data attributes
function addPostToFeed(postData) {
  const forumPosts = document.getElementById("forumPosts");
  
  const imageHtml = postData.image
    ? `<img src="${postData.image}" alt="Post image" class="post-image" onclick="openImageModal('${postData.image}')">`
    : "";

  const postHTML = `
    <div class="forum-post" data-post-id="${postData.id}">
      <div class="post-header">
        <div class="post-user">${escapeHtml(postData.user)}</div>
        <div class="post-time">${postData.created_at}</div>
        <div class="post-options">
          <button class="action-btn edit-btn" onclick="editPost('${postData.id}')">Edit</button>
          <button class="action-btn delete-btn" onclick="confirmDeletePost('${postData.id}')">Delete</button>
        </div>
      </div>
      
      <div class="post-content" id="postContent${postData.id}">
        ${postData.content ? `<p>${escapeHtml(postData.content)}</p>` : ''}
        ${imageHtml}
      </div>
      
      <div class="edit-post-section" id="editSection${postData.id}" style="display: none;">
        <textarea id="editText${postData.id}" maxlength="5000" oninput="updateCharCount(this, 'editCharCount${postData.id}')">${postData.content || ''}</textarea>
        <div style="display: flex; justify-content: space-between; align-items: center; margin-top: 5px;">
          <small style="color: #6B4C36;">
            <span id="editCharCount${postData.id}">${(postData.content || '').length}</span>/5000 characters
          </small>
          <div>
            <button class="btn btn-sm btn-secondary" onclick="cancelEditPost('${postData.id}')">Cancel</button>
            <button class="btn btn-sm btn-primary" onclick="saveEditPost('${postData.id}')">Save</button>
          </div>
        </div>
      </div>
      
      <div class="post-actions">
        <button class="action-btn like-btn" onclick="likePost('${postData.id}', event)" data-post-id="${postData.id}">
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

function escapeHtml(text) {
  if (!text) return '';
  const div = document.createElement('div');
  div.textContent = text;
  return div.innerHTML;
}

function updateCharCount(textarea, counterId) {
  const count = textarea.value.length;
  const maxLength = textarea.maxLength;
  const counterElement = document.getElementById(counterId);
  
  if (counterElement) {
    counterElement.textContent = count;
    
    if (count > maxLength * 0.9) {
      counterElement.style.color = '#f44336';
    } else if (count > maxLength * 0.7) {
      counterElement.style.color = '#ff9800';
    } else {
      counterElement.style.color = '#6B4C36';
    }
  }
}

// FIXED: Like function with proper post ID extraction
function likePost(postId, evt) {
  // Ensure we have a valid post ID
  if (!postId || postId === 'undefined' || postId === 'null') {
    // Try to get from button's data attribute as fallback
    if (evt) {
      const button = evt.target.closest('.like-btn');
      if (button) {
        postId = button.getAttribute('data-post-id');
        if (!postId) {
          const postElement = button.closest('[data-post-id]');
          if (postElement) {
            postId = postElement.getAttribute('data-post-id');
          }
        }
      }
    }
  }

  if (!postId || postId === 'undefined' || postId === 'null') {
    showNotification("Post ID is required", "error");
    console.error("No valid post ID found. Check HTML data-post-id attributes.");
    return;
  }

  console.log("Liking post:", postId); // Debug log

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

    document.getElementById(`replyText${postId}`).value = "";
    const charCountElement = document.getElementById(`replyCharCount${postId}`);
    if (charCountElement) {
      charCountElement.textContent = "0";
    }

    const repliesContainer = document.getElementById(`replies${postId}`);
    const replyHTML = createReplyHTML(data, postId, null);

    repliesContainer.insertAdjacentHTML("beforeend", replyHTML);
    document.getElementById(`replySection${postId}`).style.display = "none";

    showNotification("Reply posted successfully!", "success");
  })
  .catch((error) => {
    console.error("Error:", error);
    showNotification("Error posting reply", "error");
  });
}

// FIXED: Create reply HTML with proper nested structure and edit/delete buttons
function createReplyHTML(replyData, postId, parentReplyId, depth = 0) {
  const replyId = replyData.reply_id;
  const marginLeft = depth * 30; // Indent based on depth
  
  return `
    <div class="reply" data-reply-id="${replyId}" style="margin-left: ${marginLeft}px; border-left: 2px solid #E2C9A6; padding-left: 15px; margin-top: 10px;">
      <div class="reply-header" style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 5px;">
        <div>
          <strong>${escapeHtml(replyData.user)}:</strong>
          <small style="color: #999; margin-left: 10px;">${replyData.created_at}</small>
        </div>
        <div class="reply-options">
          <button class="reply-edit-btn" style="background: none; border: none; color: #B96902; cursor: pointer; font-size: 12px; margin-right: 5px;" onclick="editReply('${postId}', '${replyId}', ${parentReplyId ? `'${parentReplyId}'` : 'null'})">Edit</button>
          <button class="reply-delete-btn" style="background: none; border: none; color: #f44336; cursor: pointer; font-size: 12px;" onclick="confirmDeleteReply('${postId}', '${replyId}', ${parentReplyId ? `'${parentReplyId}'` : 'null'})">Delete</button>
        </div>
      </div>
      <div class="reply-content" id="replyContent${replyId}" style="margin-bottom: 10px;">
        ${escapeHtml(replyData.content)}
      </div>
      <div class="edit-reply-section" id="editReplySection${replyId}" style="display: none;">
        <textarea id="editReplyText${replyId}" maxlength="1000" style="width: 100%; padding: 8px; border: 1px solid #E2C9A6; border-radius: 4px;" oninput="updateCharCount(this, 'editReplyCharCount${replyId}')">${replyData.content}</textarea>
        <div style="display: flex; justify-content: space-between; align-items: center; margin-top: 5px;">
          <small style="color: #6B4C36;">
            <span id="editReplyCharCount${replyId}">${replyData.content.length}</span>/1000 characters
          </small>
          <div>
            <button class="btn btn-xs btn-secondary" onclick="cancelEditReply('${replyId}')">Cancel</button>
            <button class="btn btn-xs btn-primary" onclick="saveEditReply('${postId}', '${replyId}', ${parentReplyId ? `'${parentReplyId}'` : 'null'})">Save</button>
          </div>
        </div>
      </div>
      <button class="nested-reply-btn" style="background: none; border: none; color: #B96902; cursor: pointer; font-size: 12px; margin-top: 5px;" onclick="toggleNestedReply('${postId}', '${replyId}')">↳ Reply</button>
      <div class="nested-reply-section" id="nestedReplySection${replyId}" style="display: none; margin-top: 10px;">
        <textarea 
          placeholder="Reply to ${escapeHtml(replyData.user)}..." 
          id="nestedReplyText${replyId}"
          maxlength="1000"
          style="width: 100%; padding: 8px; border: 1px solid #E2C9A6; border-radius: 4px;"
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

function previewImage(input) {
  if (input.files && input.files[0]) {
    const file = input.files[0];
    
    if (file.size > 5 * 1024 * 1024) {
      showNotification("Image size should not exceed 5MB", "error");
      input.value = "";
      return;
    }
    
    if (!file.type.startsWith('image/')) {
      showNotification("Please upload a valid image file", "error");
      input.value = "";
      return;
    }
    
    const reader = new FileReader();
    reader.onload = function(e) {
      document.getElementById('previewImg').src = e.target.result;
      document.getElementById('imagePreview').style.display = 'block';
    }
    reader.readAsDataURL(file);
  }
}

function removeImagePreview() {
  document.getElementById('imagePreview').style.display = 'none';
  document.getElementById('postImage').value = '';
}

function openImageModal(src) {
  document.getElementById('modalImage').src = src;
  document.getElementById('imageModal').style.display = 'block';
}

function closeImageModal() {
  document.getElementById('imageModal').style.display = 'none';
}

function sharePost(postId) {
  const postUrl = `${window.location.origin}/forum/post/${postId}/`;

  if (navigator.share) {
    navigator.share({
      title: "VidhikPath Forum Post",
      text: "Check out this post on VidhikPath",
      url: postUrl,
    }).catch((error) => {
      fallbackShare(postUrl);
    });
  } else {
    fallbackShare(postUrl);
  }
}

function fallbackShare(url) {
  if (navigator.clipboard) {
    navigator.clipboard.writeText(url).then(() => {
      showNotification("Link copied to clipboard!", "success");
    }).catch(() => {
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

// FIXED: Reply edit/delete with parent tracking
function editReply(postId, replyId, parentReplyId) {
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

function saveEditReply(postId, replyId, parentReplyId) {
  const newContent = document.getElementById('editReplyText' + replyId).value.trim();
  if (!newContent) {
    showNotification('Reply cannot be empty', 'warning');
    return;
  }
  
  const endpoint = parentReplyId ? '/api/forum/nested-reply/edit/' : '/api/forum/reply/edit/';
  const payload = parentReplyId 
    ? { post_id: postId, parent_reply_id: parentReplyId, nested_reply_id: replyId, content: newContent }
    : { post_id: postId, reply_id: replyId, content: newContent };
  
  fetch(endpoint, {
    method: "PUT",
    headers: {
      "Content-Type": "application/json",
      "X-CSRFToken": getCookie("csrftoken"),
    },
    body: JSON.stringify(payload),
  })
    .then((response) => response.json())
    .then((data) => {
      if (data.error) {
        showNotification(data.error, "error");
        return;
      }
      
      const replyContentElement = document.getElementById('replyContent' + replyId);
      if (replyContentElement) {
        replyContentElement.textContent = newContent;
      }
      
      showNotification('Reply updated successfully!', 'success');
      cancelEditReply(replyId);
    })
    .catch((error) => {
      console.error("Error:", error);
      showNotification("Error updating reply", "error");
    });
}

function confirmDeleteReply(postId, replyId, parentReplyId) {
  showConfirmModal(
    'Delete Reply',
    'Are you sure you want to delete this reply?',
    () => deleteReplyConfirmed(postId, replyId, parentReplyId)
  );
}

function deleteReplyConfirmed(postId, replyId, parentReplyId) {
  const endpoint = parentReplyId ? '/api/forum/nested-reply/delete/' : '/api/forum/reply/delete/';
  const payload = parentReplyId
    ? { post_id: postId, parent_reply_id: parentReplyId, nested_reply_id: replyId }
    : { post_id: postId, reply_id: replyId };
  
  fetch(endpoint, {
    method: "DELETE",
    headers: {
      "Content-Type": "application/json",
      "X-CSRFToken": getCookie("csrftoken"),
    },
    body: JSON.stringify(payload),
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

function toggleNestedReply(postId, parentReplyId) {
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

function submitNestedReply(postId, parentReplyId, depth) {
  const content = document.getElementById('nestedReplyText' + parentReplyId).value.trim();
  if (!content) {
    showNotification('Please enter a reply', 'warning');
    return;
  }
  
  console.log("Submitting nested reply:", { postId, parentReplyId, content, depth }); // Debug
  
  fetch("/api/forum/nested-reply/", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "X-CSRFToken": getCookie("csrftoken"),
    },
    body: JSON.stringify({
      post_id: postId.toString(),
      parent_reply_id: parentReplyId.toString(),
      content: content,
      depth: depth || 1
    }),
  })
    .then((response) => {
      if (!response.ok) {
        return response.json().then(data => {
          throw new Error(data.error || `HTTP ${response.status}`);
        });
      }
      return response.json();
    })
    .then((data) => {
      if (data.error) {
        showNotification(data.error, "error");
        return;
      }
      
      document.getElementById('nestedReplyText' + parentReplyId).value = '';
      const charCountElement = document.getElementById('nestedReplyCharCount' + parentReplyId);
      if (charCountElement) {
        charCountElement.textContent = '0';
      }
      document.getElementById('nestedReplySection' + parentReplyId).style.display = 'none';
      
      const nestedRepliesContainer = document.getElementById('nestedReplies' + parentReplyId);
      const nestedReplyHTML = createReplyHTML(data, postId, parentReplyId, depth);
      
      nestedRepliesContainer.insertAdjacentHTML('beforeend', nestedReplyHTML);
      
      showNotification('Reply posted successfully!', 'success');
    })
    .catch((error) => {
      console.error("Error:", error);
      showNotification(error.message || "Error posting nested reply", "error");
    });
}

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

function showNotification(message, type) {
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

  setTimeout(() => {
    notification.style.opacity = '0';
    setTimeout(() => {
      if (notification.parentNode) {
        document.body.removeChild(notification);
      }
    }, 300);
  }, 3000);
}

document.addEventListener("DOMContentLoaded", () => {
  const imageInput = document.getElementById('postImage');
  if (imageInput) {
    imageInput.addEventListener('change', function() {
      if (this.files && this.files[0]) {
        previewImage(this);
      }
    });
  }

  const postContent = document.getElementById('postContent');
  if (postContent) {
    postContent.addEventListener('input', function() {
      updateCharCount(this, 'charCount');
    });
  }

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