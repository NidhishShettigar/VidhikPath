let currentUserFirebaseUid = null

document.addEventListener("DOMContentLoaded", () => {
  const userElement = document.querySelector("[data-user-firebase-uid]")
  if (userElement) {
    currentUserFirebaseUid = userElement.getAttribute("data-user-firebase-uid")
  }
})

function createPost() {
  const content = document.getElementById("postContent").value.trim()
  const imageFile = document.getElementById("postImage").files[0]

  if (!content && !imageFile) {
    showNotification("Please enter content or upload an image", "warning")
    return
  }

  if (imageFile && imageFile.size > 5 * 1024 * 1024) {
    showNotification("Image size should not exceed 5MB", "error")
    return
  }

  if (imageFile && !imageFile.type.startsWith("image/")) {
    showNotification("Please upload a valid image file", "error")
    return
  }

  const formData = new FormData()
  formData.append("content", content)
  if (imageFile) {
    formData.append("image", imageFile)
  }

  const createBtn = document.getElementById("createPostBtn")
  const originalText = createBtn.textContent
  createBtn.textContent = "Posting..."
  createBtn.disabled = true

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
        showNotification(data.error, "error")
        return
      }

      document.getElementById("postContent").value = ""
      document.getElementById("postImage").value = ""
      document.getElementById("charCount").textContent = "0"
      removeImagePreview()

      addPostToFeed(data)
      showNotification("Post created successfully!", "success")
    })
    .catch((error) => {
      console.error("Error:", error)
      showNotification("Error creating post", "error")
    })
    .finally(() => {
      createBtn.textContent = originalText
      createBtn.disabled = false
    })
}

function addPostToFeed(postData) {
  const forumPosts = document.getElementById("forumPosts")
  const postId = String(postData.id).trim()
  const firebaseUid = String(postData.firebase_uid).trim()

  const imageHtml = postData.image
    ? `<img src="${postData.image}" alt="Post image" class="post-image" onclick="openImageModal('${postData.image}')">`
    : ""

  const isOwnPost = firebaseUid === currentUserFirebaseUid
  const optionsHtml = isOwnPost
    ? `<div class="post-options">
        <button class="action-btn edit-btn" onclick="editPost('${postId}')">Edit</button>
        <button class="action-btn delete-btn" onclick="confirmDeletePost('${postId}')">Delete</button>
      </div>`
    : ""

  const postHTML = `
    <div class="forum-post" data-post-id="${postId}" data-firebase-uid="${firebaseUid}">
      <div class="post-header">
        <div class="post-user">${escapeHtml(postData.user)}</div>
        <div class="post-time">${postData.created_at}</div>
        ${optionsHtml}
      </div>
      
      <div class="post-content" id="postContent${postId}">
        ${postData.content ? `<p>${escapeHtml(postData.content)}</p>` : ""}
        ${imageHtml}
      </div>
      
      <div class="edit-post-section" id="editSection${postId}" style="display: none;">
        <textarea id="editText${postId}" maxlength="5000" oninput="updateCharCount(this, 'editCharCount${postId}')">${escapeHtml(postData.content || "")}</textarea>
        <div style="display: flex; justify-content: space-between; align-items: center; margin-top: 5px;">
          <small style="color: #6B4C36;">
            <span id="editCharCount${postId}">${(postData.content || "").length}</span>/5000 characters
          </small>
          <div>
            <button class="btn btn-sm btn-secondary" onclick="cancelEditPost('${postId}')">Cancel</button>
            <button class="btn btn-sm btn-primary" onclick="saveEditPost('${postId}')">Save</button>
          </div>
        </div>
      </div>
      
      <div class="post-actions">
        <button class="action-btn like-btn" onclick="likePost('${postId}')" data-post-id="${postId}">
          👍 <span class="like-count">${postData.likes_count || 0}</span>
        </button>
        <button class="action-btn reply-btn" onclick="toggleReply('${postId}')">💬 Reply</button>
        <button class="action-btn share-btn" onclick="sharePost('${postId}')">Share</button>
      </div>
      
      <div class="reply-section" id="replySection${postId}" style="display: none;">
        <textarea placeholder="Write a respectful reply..." id="replyText${postId}" maxlength="1000" oninput="updateCharCount(this, 'replyCharCount${postId}')"></textarea>
        <div style="display: flex; justify-content: space-between; align-items: center; margin-top: 5px;">
          <small style="color: #6B4C36;">
            <span id="replyCharCount${postId}">0</span>/1000 characters
          </small>
          <button class="btn btn-sm btn-primary" onclick="submitReply('${postId}')">Reply</button>
        </div>
      </div>
      
      <div class="replies" id="replies${postId}"></div>
    </div>
  `

  forumPosts.insertAdjacentHTML("afterbegin", postHTML)
}

function escapeHtml(text) {
  if (!text) return ""
  const div = document.createElement("div")
  div.textContent = text
  return div.innerHTML
}

function updateCharCount(textarea, counterId) {
  const count = textarea.value.length
  const maxLength = textarea.maxLength
  const counterElement = document.getElementById(counterId)

  if (counterElement) {
    counterElement.textContent = count
    if (count > maxLength * 0.9) {
      counterElement.style.color = "#f44336"
    } else if (count > maxLength * 0.7) {
      counterElement.style.color = "#ff9800"
    } else {
      counterElement.style.color = "#6B4C36"
    }
  }
}

function likePost(postId) {
  postId = String(postId).trim()

  if (!postId || postId === "undefined" || postId === "null" || postId === "") {
    showNotification("Unable to identify post", "error")
    return
  }

  const button = document.querySelector(`.forum-post[data-post-id="${postId}"] .like-btn`)
  if (button) button.disabled = true

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
        showNotification(data.error, "error")
        return
      }

      const likeBtn = document.querySelector(`.forum-post[data-post-id="${postId}"] .like-btn`)
      if (likeBtn) {
        const likeCount = likeBtn.querySelector(".like-count")
        if (likeCount) likeCount.textContent = data.likes_count
        if (data.liked) {
          likeBtn.classList.add("liked")
        } else {
          likeBtn.classList.remove("liked")
        }
      }
      showNotification(data.liked ? "Post liked!" : "Like removed", "success")
    })
    .catch((error) => {
      console.error("Error:", error)
      showNotification("Error liking post", "error")
    })
    .finally(() => {
      if (button) button.disabled = false
    })
}

function toggleReply(postId) {
  postId = String(postId).trim()
  const replySection = document.getElementById(`replySection${postId}`)
  if (!replySection) {
    showNotification("Reply section not found", "error")
    return
  }

  const isVisible = replySection.style.display !== "none"
  replySection.style.display = isVisible ? "none" : "block"

  if (!isVisible) {
    const textarea = document.getElementById(`replyText${postId}`)
    if (textarea) textarea.focus()
  }
}

function submitReply(postId) {
  postId = String(postId).trim()
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

      document.getElementById(`replyText${postId}`).value = ""
      const charCountElement = document.getElementById(`replyCharCount${postId}`)
      if (charCountElement) charCountElement.textContent = "0"

      const repliesContainer = document.getElementById(`replies${postId}`)
      const replyHTML = createReplyHTML(data, postId, null)
      repliesContainer.insertAdjacentHTML("beforeend", replyHTML)
      document.getElementById(`replySection${postId}`).style.display = "none"

      showNotification("Reply posted successfully!", "success")
    })
    .catch((error) => {
      console.error("Error:", error)
      showNotification("Error posting reply", "error")
    })
}

function createReplyHTML(replyData, postId, parentReplyId, depth = 0) {
  const replyId = String(replyData.reply_id).trim()
  postId = String(postId).trim()
  const firebaseUid = String(replyData.firebase_uid).trim()
  const marginLeft = depth * 30

  const isOwnReply = firebaseUid === currentUserFirebaseUid
  const optionsHtml = isOwnReply
    ? `<div class="reply-options">
        <button class="reply-edit-btn" style="background: none; border: none; color: #B96902; cursor: pointer; font-size: 12px; margin-right: 5px;" onclick="editReply('${postId}', '${replyId}', ${parentReplyId ? `'${parentReplyId}'` : "null"})">Edit</button>
        <button class="reply-delete-btn" style="background: none; border: none; color: #f44336; cursor: pointer; font-size: 12px;" onclick="confirmDeleteReply('${postId}', '${replyId}', ${parentReplyId ? `'${parentReplyId}'` : "null"})">Delete</button>
      </div>`
    : ""

  return `
    <div class="reply" data-reply-id="${replyId}" data-firebase-uid="${firebaseUid}" style="margin-left: ${marginLeft}px; border-left: 2px solid #E2C9A6; padding-left: 15px; margin-top: 10px;">
      <div class="reply-header" style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 5px;">
        <div>
          <strong>${escapeHtml(replyData.user)}:</strong>
          <small style="color: #999; margin-left: 10px;">${replyData.created_at}</small>
        </div>
        ${optionsHtml}
      </div>
      <div class="reply-content" id="replyContent${replyId}" style="margin-bottom: 10px;">
        ${escapeHtml(replyData.content)}
      </div>
      <div class="edit-reply-section" id="editReplySection${replyId}" style="display: none;">
        <textarea id="editReplyText${replyId}" maxlength="1000" style="width: 100%; padding: 8px; border: 1px solid #E2C9A6; border-radius: 4px;" oninput="updateCharCount(this, 'editReplyCharCount${replyId}')">${escapeHtml(replyData.content)}</textarea>
        <div style="display: flex; justify-content: space-between; align-items: center; margin-top: 5px;">
          <small style="color: #6B4C36;">
            <span id="editReplyCharCount${replyId}">${replyData.content.length}</span>/1000 characters
          </small>
          <div>
            <button class="btn btn-xs btn-secondary" onclick="cancelEditReply('${replyId}')">Cancel</button>
            <button class="btn btn-xs btn-primary" onclick="saveEditReply('${postId}', '${replyId}', ${parentReplyId ? `'${parentReplyId}'` : "null"})">Save</button>
          </div>
        </div>
      </div>
      <button class="nested-reply-btn" style="background: none; border: none; color: #B96902; cursor: pointer; font-size: 12px; margin-top: 5px;" onclick="toggleNestedReply('${postId}', '${replyId}')">↳ Reply</button>
      <div class="nested-reply-section" id="nestedReplySection${replyId}" style="display: none; margin-top: 10px;">
        <textarea placeholder="Reply to ${escapeHtml(replyData.user)}..." id="nestedReplyText${replyId}" maxlength="1000" style="width: 100%; padding: 8px; border: 1px solid #E2C9A6; border-radius: 4px;" oninput="updateCharCount(this, 'nestedReplyCharCount${replyId}')"></textarea>
        <div style="display: flex; justify-content: space-between; align-items: center; margin-top: 5px;">
          <small style="color: #6B4C36;">
            <span id="nestedReplyCharCount${replyId}">0</span>/1000 characters
          </small>
          <button class="btn btn-xs btn-primary" onclick="submitNestedReply('${postId}', '${replyId}', ${depth + 1})">Reply</button>
        </div>
      </div>
      <div class="nested-replies" id="nestedReplies${replyId}"></div>
    </div>
  `
}

function previewImage(input) {
  if (input.files && input.files[0]) {
    const file = input.files[0]

    if (file.size > 5 * 1024 * 1024) {
      showNotification("Image size should not exceed 5MB", "error")
      input.value = ""
      return
    }

    if (!file.type.startsWith("image/")) {
      showNotification("Please upload a valid image file", "error")
      input.value = ""
      return
    }

    const reader = new FileReader()
    reader.onload = (e) => {
      document.getElementById("previewImg").src = e.target.result
      document.getElementById("imagePreview").style.display = "block"
    }
    reader.readAsDataURL(file)
  }
}

function removeImagePreview() {
  document.getElementById("imagePreview").style.display = "none"
  document.getElementById("postImage").value = ""
}

function openImageModal(src) {
  document.getElementById("modalImage").src = src
  document.getElementById("imageModal").style.display = "block"
}

function closeImageModal() {
  document.getElementById("imageModal").style.display = "none"
}

function sharePost(postId) {
  const postUrl = `${window.location.origin}${window.location.pathname}#post-${postId}`

  if (navigator.share) {
    navigator
      .share({
        title: "VidhikPath Forum Post",
        text: "Check out this post on VidhikPath",
        url: postUrl,
      })
      .catch(() => fallbackShare(postUrl))
  } else {
    fallbackShare(postUrl)
  }
}

function fallbackShare(url) {
  if (navigator.clipboard) {
    navigator.clipboard
      .writeText(url)
      .then(() => {
        showNotification("Link copied to clipboard!", "success")
      })
      .catch(() => {
        const textArea = document.createElement("textarea")
        textArea.value = url
        document.body.appendChild(textArea)
        textArea.select()
        document.execCommand("copy")
        document.body.removeChild(textArea)
        showNotification("Link copied to clipboard!", "success")
      })
  } else {
    showNotification("Sharing not supported on this browser", "warning")
  }
}

let pendingDeleteAction = null

function showConfirmModal(title, message, action) {
  document.getElementById("confirmTitle").textContent = title
  document.getElementById("confirmMessage").textContent = message
  pendingDeleteAction = action
  document.getElementById("confirmModal").style.display = "block"
}

function closeConfirmModal() {
  document.getElementById("confirmModal").style.display = "none"
  pendingDeleteAction = null
}

function confirmDelete() {
  if (pendingDeleteAction) {
    pendingDeleteAction()
  }
  closeConfirmModal()
}

function editPost(postId) {
  postId = String(postId).trim()
  const postContent = document.getElementById("postContent" + postId)
  const editSection = document.getElementById("editSection" + postId)

  if (postContent && editSection) {
    postContent.style.display = "none"
    editSection.style.display = "block"
  }
}

function cancelEditPost(postId) {
  postId = String(postId).trim()
  const postContent = document.getElementById("postContent" + postId)
  const editSection = document.getElementById("editSection" + postId)

  if (postContent && editSection) {
    postContent.style.display = "block"
    editSection.style.display = "none"
  }
}

function saveEditPost(postId) {
  postId = String(postId).trim()
  const newContent = document.getElementById("editText" + postId).value.trim()

  fetch("/api/forum/edit/", {
    method: "PUT",
    headers: {
      "Content-Type": "application/json",
      "X-CSRFToken": getCookie("csrftoken"),
    },
    body: JSON.stringify({
      post_id: postId,
      content: newContent,
    }),
  })
    .then((response) => response.json())
    .then((data) => {
      if (data.error) {
        showNotification(data.error, "error")
        return
      }

      const postContentElement = document.querySelector(`#postContent${postId} p`)
      if (postContentElement) {
        postContentElement.textContent = newContent
      }

      showNotification("Post updated successfully!", "success")
      cancelEditPost(postId)
    })
    .catch((error) => {
      console.error("Error:", error)
      showNotification("Error updating post", "error")
    })
}

function confirmDeletePost(postId) {
  showConfirmModal("Delete Post", "Are you sure you want to delete this post? This action cannot be undone.", () =>
    deletePostConfirmed(postId),
  )
}

function deletePostConfirmed(postId) {
  postId = String(postId).trim()
  fetch("/api/forum/delete/", {
    method: "DELETE",
    headers: {
      "Content-Type": "application/json",
      "X-CSRFToken": getCookie("csrftoken"),
    },
    body: JSON.stringify({ post_id: postId }),
  })
    .then((res) => res.json())
    .then((data) => {
      if (data.error) {
        showNotification(data.error, "error")
        return
      }
      const postElement = document.querySelector(`.forum-post[data-post-id="${postId}"]`)
      if (postElement) {
        postElement.remove()
      }
      showNotification("Post deleted successfully", "success")
    })
    .catch((err) => {
      console.error("Error:", err)
      showNotification("Error deleting post", "error")
    })
}

function editReply(postId, replyId, parentReplyId) {
  replyId = String(replyId).trim()
  const replyContent = document.getElementById("replyContent" + replyId)
  const editSection = document.getElementById("editReplySection" + replyId)

  if (replyContent && editSection) {
    replyContent.style.display = "none"
    editSection.style.display = "block"
  }
}

function cancelEditReply(replyId) {
  replyId = String(replyId).trim()
  const replyContent = document.getElementById("replyContent" + replyId)
  const editSection = document.getElementById("editReplySection" + replyId)

  if (replyContent && editSection) {
    replyContent.style.display = "block"
    editSection.style.display = "none"
  }
}

function saveEditReply(postId, replyId, parentReplyId) {
  postId = String(postId).trim()
  replyId = String(replyId).trim()
  const newContent = document.getElementById("editReplyText" + replyId).value.trim()

  if (!newContent) {
    showNotification("Reply cannot be empty", "warning")
    return
  }

  const endpoint = parentReplyId ? "/api/forum/nested-reply/edit/" : "/api/forum/reply/edit/"
  const payload = parentReplyId
    ? { post_id: postId, parent_reply_id: parentReplyId, nested_reply_id: replyId, content: newContent }
    : { post_id: postId, reply_id: replyId, content: newContent }

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
        showNotification(data.error, "error")
        return
      }

      const replyContentElement = document.getElementById("replyContent" + replyId)
      if (replyContentElement) {
        replyContentElement.textContent = newContent
      }

      showNotification("Reply updated successfully!", "success")
      cancelEditReply(replyId)
    })
    .catch((error) => {
      console.error("Error:", error)
      showNotification("Error updating reply", "error")
    })
}

function confirmDeleteReply(postId, replyId, parentReplyId) {
  showConfirmModal("Delete Reply", "Are you sure you want to delete this reply?", () =>
    deleteReplyConfirmed(postId, replyId, parentReplyId),
  )
}

function deleteReplyConfirmed(postId, replyId, parentReplyId) {
  postId = String(postId).trim()
  replyId = String(replyId).trim()
  const endpoint = parentReplyId ? "/api/forum/nested-reply/delete/" : "/api/forum/reply/delete/"
  const payload = parentReplyId
    ? { post_id: postId, parent_reply_id: parentReplyId, nested_reply_id: replyId }
    : { post_id: postId, reply_id: replyId }

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
        showNotification(data.error, "error")
        return
      }

      const replyElement = document.querySelector(`[data-reply-id="${replyId}"]`)
      if (replyElement) {
        replyElement.remove()
      }
      showNotification("Reply deleted successfully!", "success")
    })
    .catch((error) => {
      console.error("Error:", error)
      showNotification("Error deleting reply", "error")
    })
}

function toggleNestedReply(postId, parentReplyId) {
  parentReplyId = String(parentReplyId).trim()
  const section = document.getElementById("nestedReplySection" + parentReplyId)
  if (section) {
    const isVisible = section.style.display !== "none"
    section.style.display = isVisible ? "none" : "block"

    if (!isVisible) {
      const textarea = document.getElementById("nestedReplyText" + parentReplyId)
      if (textarea) textarea.focus()
    }
  }
}

function submitNestedReply(postId, parentReplyId, depth) {
  postId = String(postId).trim()
  parentReplyId = String(parentReplyId).trim()
  const content = document.getElementById("nestedReplyText" + parentReplyId).value.trim()

  if (!content) {
    showNotification("Please enter a reply", "warning")
    return
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
      depth: depth || 1,
    }),
  })
    .then((response) => response.json())
    .then((data) => {
      if (data.error) {
        showNotification(data.error, "error")
        return
      }

      document.getElementById("nestedReplyText" + parentReplyId).value = ""
      const charCountElement = document.getElementById("nestedReplyCharCount" + parentReplyId)
      if (charCountElement) charCountElement.textContent = "0"
      document.getElementById("nestedReplySection" + parentReplyId).style.display = "none"

      const nestedRepliesContainer = document.getElementById("nestedReplies" + parentReplyId)
      const nestedReplyHTML = createReplyHTML(data, postId, parentReplyId, depth)

      nestedRepliesContainer.insertAdjacentHTML("beforeend", nestedReplyHTML)

      showNotification("Reply posted successfully!", "success")
    })
    .catch((error) => {
      console.error("Error:", error)
      showNotification(error.message || "Error posting nested reply", "error")
    })
}

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

function showNotification(message, type) {
  const existingNotifications = document.querySelectorAll(".notification")
  existingNotifications.forEach((notification) => notification.remove())

  const notification = document.createElement("div")
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

  switch (type) {
    case "success":
      notification.style.backgroundColor = "#4CAF50"
      break
    case "error":
      notification.style.backgroundColor = "#f44336"
      break
    case "warning":
      notification.style.backgroundColor = "#ff9800"
      break
    case "info":
      notification.style.backgroundColor = "#2196F3"
      break
    default:
      notification.style.backgroundColor = "#2196F3"
  }

  notification.textContent = message
  document.body.appendChild(notification)

  setTimeout(() => {
    notification.style.opacity = "0"
    setTimeout(() => {
      if (notification.parentNode) {
        document.body.removeChild(notification)
      }
    }, 300)
  }, 3000)
}
