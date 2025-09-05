
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
                <div class="lawyer-type">${lawyer.lawyer_type}</div>
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
                <div class="lawyer-detail">
                    <span>languages_spoken:</span> ${lawyer.languages_spoken}
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
