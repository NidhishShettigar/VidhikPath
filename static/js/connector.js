// Search lawyers by location and type
function getCookie(name) {
    let cookieValue = null;
    if (document.cookie && document.cookie !== "") {
        const cookies = document.cookie.split(";");
        for (let i = 0; i < cookies.length; i++) {
            const cookie = cookies[i].trim();
            if (cookie.substring(0, name.length + 1) === (name + "=")) {
                cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                break;
            }
        }
    }
    return cookieValue;
}

function searchLawyers() {
  const location = document.getElementById("locationInput").value;
  const type = document.getElementById("typeInput").value;

  if (!location.trim()) {
    showNotification("Please enter a location", "error");
    return;
  }

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
    if (data.error) {
      showNotification(data.error, "error");
      return;
    }

    displayLawyers(data.lawyers || []);

  
    if (!data.lawyers || data.lawyers.length === 0) {
      showNotification("No lawyers found matching your criteria", "info");
    }
  })
    .catch((error) => {
      console.error("Error:", error);
      showNotification("Error searching lawyers", "error");
    });
}

// Helper function to get city from LocationIQ API
async function getCityFromLocationIQ(lat, lng) {
    const API_KEY = "pk.7ec65c5c3bb595eec965903be71432a1";
    const url = `https://us1.locationiq.com/v1/reverse.php?key=${API_KEY}&lat=${lat}&lon=${lng}&format=json`;

    try {
        const res = await fetch(url);
        const data = await res.json();

        if (data && data.address) {
            const city = (
                data.address.city ||
                data.address.town ||
                data.address.village ||
                data.address.suburb ||
                data.address.municipality ||
                data.address.county ||
                data.address.state_district ||
                data.address.state ||
                "Unknown"
            );
            
            return city;
        }
    } catch (error) {
        console.error("LocationIQ error:", error);
    }
    return null;
}

// Use current geolocation to find lawyers nearby
function useCurrentLocation() {
  if (!navigator.geolocation) {
    showNotification("Geolocation not supported by this browser", "error");
    return;
  }

  showNotification("Getting your location...", "info");

  navigator.geolocation.getCurrentPosition(
    async (position) => {
      const lat = position.coords.latitude;
      const lng = position.coords.longitude;
      const type = document.getElementById("typeInput")?.value || "";

      showNotification("Detecting your city...", "info");

      // Use LocationIQ to get accurate city name
      const detectedCity = await getCityFromLocationIQ(lat, lng);

      if (!detectedCity || detectedCity === "Unknown") {
        showNotification("Could not detect city automatically. Please enter manually.", "error");
        return;
      }

      // Update location input with detected city
      const locationInput = document.getElementById("locationInput");
      if (locationInput) {
        locationInput.value = detectedCity;
      }

      // Send detected city to backend to search lawyers
      fetch("/api/find-lawyers/", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-CSRFToken": getCookie("csrftoken"),
        },
        body: JSON.stringify({
          location: detectedCity,
          lawyer_type: type,
          use_current_location: true,
          latitude: lat,
          longitude: lng,
        }),
      })
        .then((response) => response.json())
        .then((data) => {
  if (data.error) {
    showNotification(data.error, "error");
    return;
  }

  displayLawyers(data.lawyers || []);

  
  if (!data.lawyers || data.lawyers.length === 0) {
    showNotification("No lawyers found matching your criteria", "info");
  }
})
        .catch((error) => {
          console.error("Error:", error);
          showNotification("Error finding lawyers in your area", "error");
        });
    },

    // Geolocation errors
    (error) => {
      let errorMsg = "Error getting location: ";
      switch (error.code) {
        case error.PERMISSION_DENIED:
          errorMsg += "Please allow location access in your browser";
          break;
        case error.POSITION_UNAVAILABLE:
          errorMsg += "Location information unavailable";
          break;
        case error.TIMEOUT:
          errorMsg += "Location request timed out";
          break;
        default:
          errorMsg += error.message;
      }
      showNotification(errorMsg, "error");
    },

    {
      enableHighAccuracy: true,
      timeout: 10000,
      maximumAge: 0,
    }
  );
}

// Display lawyer search results in the UI
function displayLawyers(lawyers) {
  const resultsContainer = document.getElementById("lawyersResults");

  if (!lawyers || lawyers.length === 0) {
    resultsContainer.innerHTML = '<p class="no-results">No lawyers found matching your criteria.</p>';
    return;
  }

  const cardsHTML = lawyers
  .map(
    (lawyer) => `
        <div class="lawyer-card">
            <div class="lawyer-header">
                <div class="lawyer-name">${lawyer.name || 'N/A'}</div>
                <div class="lawyer-type">${lawyer.lawyer_type || 'N/A'}</div>
            </div>
            
            <div class="lawyer-details">
                <div class="lawyer-detail">
                    <span>Location:</span> ${lawyer.location || 'N/A'}
                </div>
                <div class="lawyer-detail">
                    <span>Experience:</span> ${lawyer.experience || 0} years
                </div>
                <div class="lawyer-detail">
                    <span>Email:</span> ${lawyer.email || 'N/A'}
                </div>
                <div class="lawyer-detail">
                    <span>Languages:</span> ${Array.isArray(lawyer.languages_spoken) ? 
                      lawyer.languages_spoken.join(', ') : 
                      (lawyer.languages_spoken || 'N/A')}
                </div>
                <div class="lawyer-detail">
                    <span>Contact:</span> ${lawyer.phone || 'N/A'}
                </div>
            </div>
        </div>
    `
  )
  .join("");

resultsContainer.innerHTML = cardsHTML; 
}

// Open default email client to contact lawyer
function contactLawyer(email) {
  window.location.href = `mailto:${email}?subject=Legal Consultation Request from VidhikPath`;
}

// Placeholder for lawyer profile feature
function viewProfile(email) {
  showNotification("Lawyer profile feature coming soon!", "info");
}

// Simple notification function
function showNotification(message, type = "info") {
    console.log(message); // no UI change
}