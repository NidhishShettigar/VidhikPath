function openProfile() {
    document.getElementById("profileModal").style.display = "flex";
}

   function closeProfile() {
    window.location.href = "/chatbot/";  // Redirect to chatbot URL
}


function saveProfile() {
    const form = document.querySelector("form")
    const formData = new FormData(form)

    fetch("{% url 'profile' %}", {
        method: "POST",
        headers: {
            "X-CSRFToken": getCookie("csrftoken")
        },
        body: formData
    })
    .then(() => {
        showNotification("Profile updated successfully!", "success")
        closeProfile()
        location.reload() // reload to show new name/photo
    })
    .catch(() => showNotification("Update failed", "error"))
}



function logout() {
    if (confirm("Are you sure you want to logout?")) {
        window.location.href = "/logout/";
    }
}

function setTheme(theme) {
    // Apply theme class to body
    if (theme === "dark") {
        document.body.classList.add("dark-mode");
    } else {
        document.body.classList.remove("dark-mode");
    }

    // Save choice
    localStorage.setItem("vidhikpath-theme", theme);

    // Update active button
    const buttons = document.querySelectorAll(".theme-btn");
    buttons.forEach(btn => {
        const btnTheme = btn.textContent.toLowerCase().includes("dark") ? "dark" : "light";
        btn.classList.toggle("active", btnTheme === theme);
    });
}

// 🔥 Run on page load
document.addEventListener("DOMContentLoaded", () => {
    const savedTheme = localStorage.getItem("vidhikpath-theme") || "light";
    setTheme(savedTheme);
});


// Notification helper
function showNotification(msg, type="info") {
    const n = document.createElement("div");
    n.className = `notification ${type}`;
    n.textContent = msg;
    document.body.appendChild(n);
    setTimeout(() => n.remove(), 3000);
}
