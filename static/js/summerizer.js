// Enhanced Document Summarizer JavaScript - Improved Error Handling

// Debug flag - set to true for detailed logging
const DEBUG = true;

function debugLog(message, data = null) {
  if (DEBUG) {
    console.log(`[Summarizer Debug] ${message}`, data || '');
  }
}

// Get cookie value by name
function getCookie(name) {
  const value = `; ${document.cookie}`;
  const parts = value.split(`; ${name}=`);
  if (parts.length === 2) return parts.pop().split(";").shift();
}

// Show notification message
function showNotification(message, type = "info") {
  debugLog(`Showing notification: ${type}`, message);
  
  // Remove any existing notifications
  const existingNotifications = document.querySelectorAll('.notification');
  existingNotifications.forEach(n => n.remove());

  const notification = document.createElement("div");
  notification.className = `notification ${type}`;
  notification.textContent = message;

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
    max-width: 300px;
    word-wrap: break-word;
    box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
  `;

  // Set background color based on type
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

  // Auto-remove after 5 seconds for errors, 4 for others
  const duration = type === "error" ? 5000 : 4000;
  setTimeout(() => {
    notification.style.animation = "slideOutRight 0.3s ease-out";
    setTimeout(() => {
      if (notification.parentNode) {
        notification.parentNode.removeChild(notification);
      }
    }, 300);
  }, duration);
}

// Validate file before processing
function validateFile(file) {
  debugLog("Validating file", {
    name: file.name,
    size: file.size,
    type: file.type
  });

  if (!file) {
    showNotification("No file selected", "error");
    return false;
  }

  // Check file size (10MB limit)
  const maxSize = 10 * 1024 * 1024;
  if (file.size > maxSize) {
    showNotification("File too large. Maximum size is 10MB", "error");
    return false;
  }

  // Check file type
  const allowedTypes = [
    'application/pdf',
    'image/png', 
    'image/jpeg', 
    'image/jpg'
  ];
  
  const allowedExtensions = ['.pdf', '.png', '.jpg', '.jpeg'];
  const fileName = file.name.toLowerCase();
  const hasValidExtension = allowedExtensions.some(ext => fileName.endsWith(ext));

  if (!allowedTypes.includes(file.type) && !hasValidExtension) {
    showNotification("Unsupported file type. Please upload PDF, PNG, or JPG files.", "error");
    return false;
  }

  debugLog("File validation passed");
  return true;
}

// Format summary content for better display
function formatSummary(summary) {
  // Replace markdown-like formatting
  let formatted = summary
    .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')  // Bold text
    .replace(/^\* (.*?)$/gm, '<li>$1</li>')  // Bullet points
    .replace(/^- (.*?)$/gm, '<li>$1</li>')   // Dash bullet points
    .replace(/^(\d+)\. (.*?)$/gm, '<li>$2</li>');  // Numbered lists

  // Wrap consecutive list items in ul tags
  formatted = formatted.replace(/(<li>.*?<\/li>\s*)+/gs, function(match) {
    return '<ul>' + match + '</ul>';
  });

  // Replace line breaks with proper HTML
  formatted = formatted.replace(/\n\n/g, '</p><p>');
  formatted = formatted.replace(/\n/g, '<br>');
  
  // Wrap in paragraph tags if not already wrapped
  if (!formatted.includes('<p>') && !formatted.includes('<ul>')) {
    formatted = '<p>' + formatted + '</p>';
  }

  return formatted;
}



// Process document for summarization
async function processDocument(file) {
  debugLog("Starting document processing", {
    name: file.name,
    type: file.type,
    size: file.size
  });

  // Validate file first
  if (!validateFile(file)) {
    return;
  }

  const formData = new FormData();
  formData.append("document", file);

  // Add language parameter (you can add a language selector later)
  formData.append("language", "auto");

  // Show loading state
  const uploadArea = document.getElementById("uploadArea");
  if (!uploadArea) {
    debugLog("Upload area not found");
    showNotification("Upload area not found", "error");
    return;
  }

  const originalContent = uploadArea.innerHTML;
  uploadArea.innerHTML = `
    <div style="display: flex; flex-direction: column; align-items: center; gap: 15px;">
      <div class="loading-spinner"></div>
      <p>Processing document...</p>
      <small>This may take a few seconds depending on document size</small>
    </div>
  `;

  // Add loading spinner styles if not present
  addLoadingStyles();

  debugLog("Sending request to /api/summarize/");

  try {
    const response = await fetch("/api/summarize/", {
      method: "POST",
      headers: {
        "X-CSRFToken": getCookie("csrftoken"),
      },
      body: formData,
    });

    debugLog("Response received", {
      status: response.status,
      statusText: response.statusText,
      ok: response.ok
    });

    // Try to parse JSON even if response is not ok
    let data;
    try {
      data = await response.json();
      debugLog("Response data parsed", data);
    } catch (parseError) {
      debugLog("Failed to parse JSON response", parseError);
      throw new Error(`Server returned invalid response (Status: ${response.status})`);
    }

    // Restore upload area
    uploadArea.innerHTML = originalContent;
    
    // Re-initialize file handlers after restoring content
    initializeFileHandlers();

    if (response.ok) {
      if (data.status === "success" && data.summary) {
        displaySummary(data);
        showNotification(
          `Document summarized successfully! (${data.chunks_processed || 1} chunks processed)`,
          "success"
        );
      } else if (data.error) {
        showNotification(`Processing failed: ${data.error}`, "error");
      } else {
        showNotification("Unexpected response format", "error");
      }
    } else {
      // Handle specific error responses
      if (data.error) {
        showNotification(`Server error: ${data.error}`, "error");
      } else {
        showNotification(getErrorMessage(response.status), "error");
      }
    }

  } catch (error) {
    debugLog("Fetch error details", {
      message: error.message,
      stack: error.stack
    });
    
    // Restore upload area on error
    uploadArea.innerHTML = originalContent;
    initializeFileHandlers();
    
    // Show specific error messages
    if (error.name === 'TypeError' && error.message.includes('fetch')) {
      showNotification("Cannot connect to server. Please check your connection.", "error");
    } else {
      showNotification(`Error processing document: ${error.message}`, "error");
    }
  }
}

// Get user-friendly error message based on status code
function getErrorMessage(status) {
  switch (status) {
    case 400:
      return "Invalid file or request format";
    case 401:
      return "Authentication required";
    case 403:
      return "Access denied. Please check your permissions.";
    case 404:
      return "API endpoint not found. Please check configuration.";
    case 413:
      return "File too large";
    case 429:
      return "Too many requests. Please wait and try again.";
    case 500:
      return "Internal server error. Please try again later.";
    case 502:
      return "Server temporarily unavailable";
    case 503:
      return "Service temporarily unavailable";
    default:
      return `Server error (${status}). Please try again later.`;
  }
}

// Add loading styles
function addLoadingStyles() {
  if (!document.getElementById('loading-styles')) {
    const loadingStyles = document.createElement('style');
    loadingStyles.id = 'loading-styles';
    loadingStyles.textContent = `
      .loading-spinner {
        width: 40px;
        height: 40px;
        border: 4px solid #f3f3f3;
        border-top: 4px solid #B96902;
        border-radius: 50%;
        animation: spin 1s linear infinite;
      }
      @keyframes spin {
        0% { transform: rotate(0deg); }
        100% { transform: rotate(360deg); }
      }
    `;
    document.head.appendChild(loadingStyles);
  }
}

// Display summary results
function displaySummary(data) {
  debugLog("Displaying summary", data);
  
  const summaryResult = document.getElementById("summaryResult");
  const summaryContent = document.getElementById("summaryContent");
  
  if (!summaryResult || !summaryContent) {
    debugLog("Summary display elements not found");
    showNotification("Error: Summary display area not found", "error");
    return;
  }

  try {
    // Format and display the summary
    summaryContent.innerHTML = formatSummary(data.summary);
    summaryResult.style.display = "block";

    // Add language info if available
    if (data.detected_language || data.language_name) {
      const languageInfo = document.createElement('div');
      languageInfo.className = 'language-info';
      languageInfo.innerHTML = `
        <small style="color: #666; font-style: italic; display: block; margin-bottom: 10px;">
          ${data.language_name ? `Language: ${data.language_name}` : ''}
          ${data.file_type ? ` | File type: ${data.file_type.toUpperCase()}` : ''}
          ${data.chunks_processed ? ` | Processed: ${data.chunks_processed} sections` : ''}
        </small>
      `;
      summaryContent.insertBefore(languageInfo, summaryContent.firstChild);
    }

    // Scroll to results smoothly
    setTimeout(() => {
      summaryResult.scrollIntoView({ 
        behavior: 'smooth',
        block: 'start'
      });
    }, 100);
    
    debugLog("Summary displayed successfully");
  } catch (error) {
    debugLog("Error displaying summary", error);
    showNotification("Error displaying summary", "error");
  }
}

// Initialize file upload handlers
function initializeFileHandlers() {
  debugLog("Initializing file handlers");

  try {
    // File input change handler
    const fileInput = document.getElementById("fileInput");
    if (fileInput) {
      // Remove existing listeners to prevent duplicates
      fileInput.removeEventListener("change", handleFileInputChange);
      fileInput.addEventListener("change", handleFileInputChange);
      debugLog("File input handler attached");
    } else {
      debugLog("File input element not found");
    }

    // Upload area handlers
    const uploadArea = document.getElementById("uploadArea");
    if (uploadArea) {
      // Remove existing listeners
      uploadArea.removeEventListener("dragover", handleDragOver);
      uploadArea.removeEventListener("dragleave", handleDragLeave);
      uploadArea.removeEventListener("drop", handleDrop);
      uploadArea.removeEventListener("click", handleUploadAreaClick);

      // Add new listeners
      uploadArea.addEventListener("dragover", handleDragOver);
      uploadArea.addEventListener("dragleave", handleDragLeave);
      uploadArea.addEventListener("drop", handleDrop);
      uploadArea.addEventListener("click", handleUploadAreaClick);
      debugLog("Upload area handlers attached");
    } else {
      debugLog("Upload area element not found");
    }

    // Camera button handler
    const cameraBtn = document.getElementById("cameraBtn");
    if (cameraBtn) {
      cameraBtn.removeEventListener("click", handleCameraClick);
      cameraBtn.addEventListener("click", handleCameraClick);
      debugLog("Camera button handler attached");
    }

    // Clear button handler (if exists)
    const clearBtn = document.getElementById("clearBtn");
    if (clearBtn) {
      clearBtn.removeEventListener("click", handleClearClick);
      clearBtn.addEventListener("click", handleClearClick);
      debugLog("Clear button handler attached");
    }

  } catch (error) {
    debugLog("Error initializing file handlers", error);
    showNotification("Error initializing upload handlers", "warning");
  }
}

// Handle file input change
function handleFileInputChange(e) {
  debugLog("File input changed");
  try {
    const file = e.target.files[0];
    if (file) {
      debugLog("File selected", {
        name: file.name,
        size: file.size,
        type: file.type
      });
      processDocument(file);
    }
    // Reset file input to allow selecting the same file again
    e.target.value = '';
  } catch (error) {
    debugLog("Error handling file input change", error);
    showNotification("Error processing selected file", "error");
  }
}

// Handle drag over
function handleDragOver(e) {
  e.preventDefault();
  e.stopPropagation();
  const target = e.currentTarget;
  target.style.borderColor = "#B96902";
  target.style.backgroundColor = "rgba(185, 105, 2, 0.1)";
  target.style.transform = "scale(1.02)";
  target.style.transition = "all 0.2s ease";
}

// Handle drag leave
function handleDragLeave(e) {
  e.preventDefault();
  e.stopPropagation();
  const target = e.currentTarget;
  target.style.borderColor = "#B96902";
  target.style.backgroundColor = "";
  target.style.transform = "scale(1)";
}

// Handle file drop
function handleDrop(e) {
  e.preventDefault();
  e.stopPropagation();
  debugLog("Files dropped");
  
  try {
    // Reset styles
    const target = e.currentTarget;
    target.style.borderColor = "#B96902";
    target.style.backgroundColor = "";
    target.style.transform = "scale(1)";
    
    const files = e.dataTransfer.files;
    if (files.length > 0) {
      debugLog("Processing dropped file", {
        name: files[0].name,
        size: files[0].size,
        type: files[0].type
      });
      processDocument(files[0]);
    } else {
      showNotification("No files were dropped", "warning");
    }
  } catch (error) {
    debugLog("Error handling file drop", error);
    showNotification("Error processing dropped file", "error");
  }
}

// Handle upload area click
function handleUploadAreaClick(e) {
  try {
    // Don't trigger file input if clicking on buttons
    if (e.target.tagName === 'BUTTON' || e.target.closest('button')) {
      return;
    }
    
    debugLog("Upload area clicked");
    const fileInput = document.getElementById("fileInput");
    if (fileInput) {
      fileInput.click();
    } else {
      debugLog("File input not found");
      showNotification("File input not found", "error");
    }
  } catch (error) {
    debugLog("Error handling upload area click", error);
  }
}

// Handle camera button click
function handleCameraClick(e) {
  e.preventDefault();
  e.stopPropagation();
  debugLog("Camera button clicked");
  
  try {
    // Check if device supports camera
    if (navigator.mediaDevices && navigator.mediaDevices.getUserMedia) {
      showNotification("Camera feature coming soon!", "info");
      // TODO: Implement camera capture functionality
    } else {
      showNotification("Camera not supported on this device", "warning");
    }
  } catch (error) {
    debugLog("Error handling camera click", error);
    showNotification("Error accessing camera", "error");
  }
}

// Handle clear button click
function handleClearClick(e) {
  e.preventDefault();
  e.stopPropagation();
  debugLog("Clear button clicked");
  
  try {
    const summaryResult = document.getElementById("summaryResult");
    if (summaryResult) {
      summaryResult.style.display = "none";
      const summaryContent = document.getElementById("summaryContent");
      if (summaryContent) {
        summaryContent.innerHTML = "";
      }
      showNotification("Summary cleared", "info");
    }
  } catch (error) {
    debugLog("Error clearing summary", error);
  }
}

// Add required CSS animations and styles
function addAnimationStyles() {
  if (!document.getElementById('notification-animations')) {
    const animationStyles = document.createElement('style');
    animationStyles.id = 'notification-animations';
    animationStyles.textContent = `
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
      
      .upload-area {
        transition: all 0.3s ease;
        cursor: pointer;
      }
      
      .upload-area:hover {
        border-color: #B96902;
        background-color: rgba(185, 105, 2, 0.05);
      }
      
      .language-info {
        margin-bottom: 15px;
        padding-bottom: 10px;
        border-bottom: 1px solid #eee;
      }
      
      .notification {
        font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
        line-height: 1.4;
      }
      
      #summaryContent {
        line-height: 1.6;
      }
      
      #summaryContent ul {
        margin: 10px 0;
        padding-left: 20px;
      }
      
      #summaryContent li {
        margin: 5px 0;
      }
      
      #summaryContent strong {
        color: #B96902;
      }
    `;
    document.head.appendChild(animationStyles);
  }
}

// Initialize everything when DOM is ready
function initializeSummarizer() {
  debugLog("Initializing document summarizer");
  
  try {
    addAnimationStyles();
    initializeFileHandlers();
    
    // Check if required elements exist
    const requiredElements = ['uploadArea', 'summaryResult', 'summaryContent'];
    const missingElements = requiredElements.filter(id => !document.getElementById(id));
    
    if (missingElements.length > 0) {
      debugLog("Missing required elements", missingElements);
      showNotification("Some page elements are missing. Please refresh the page.", "warning");
    } else {
      debugLog("All required elements found");
      showNotification("Document summarizer ready!", "info");
    }
    
  } catch (error) {
    debugLog("Error during initialization", error);
    showNotification("Error initializing summarizer", "error");
  }
}

// Utility function to check if element exists
function elementExists(id) {
  return document.getElementById(id) !== null;
}

// Auto-initialize if DOM is already loaded
if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', initializeSummarizer);
} else {
  initializeSummarizer();
}

// Export functions for global access and debugging
window.processDocument = processDocument;
window.getCookie = getCookie;
window.showNotification = showNotification;
window.initializeFileHandlers = initializeFileHandlers;
window.checkApiHealth = checkApiHealth;
window.debugLog = debugLog;

// Add window error handler for debugging
window.addEventListener('error', function(e) {
  debugLog("Global error caught", {
    message: e.message,
    filename: e.filename,
    line: e.lineno,
    column: e.colno,
    error: e.error
  });
});

// Add these to summerizer.js:

function copyToClipboard() {
    const summaryContent = document.getElementById('summaryContent');
    const text = summaryContent.innerText;
    
    navigator.clipboard.writeText(text).then(() => {
        showNotification('Summary copied to clipboard!', 'success');
    }).catch(err => {
        showNotification('Failed to copy', 'error');
    });
}

function downloadSummary() {
    const summaryContent = document.getElementById('summaryContent');
    const text = summaryContent.innerText;
    
    const blob = new Blob([text], { type: 'text/plain' });
    const url = window.URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `summary_${new Date().getTime()}.txt`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    window.URL.revokeObjectURL(url);
    
    showNotification('Summary downloaded!', 'success');
}

function clearSummary() {
    const summaryResult = document.getElementById('summaryResult');
    const summaryContent = document.getElementById('summaryContent');
    
    if (summaryResult && summaryContent) {
        summaryResult.style.display = 'none';
        summaryContent.innerHTML = '';
        showNotification('Summary cleared', 'info');
    }
}