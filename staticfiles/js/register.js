// Firebase config
const firebaseConfig = {
    apiKey: "AIzaSyDFXCASnsC1Yi_bpwDuwhkicYNNzhR-v9s",
    authDomain: "vidhikpath-e9e56.firebaseapp.com",
    projectId: "vidhikpath-e9e56",
    storageBucket: "vidhikpath-e9e56.firebasestorage.app",
    messagingSenderId: "1028848699647",
    appId: "1:1028848699647:web:f3e9567bd975a03b4064ca",
    measurementId: "G-H129B0J3HP"
};

// Init Firebase
firebase.initializeApp(firebaseConfig);
const auth = firebase.auth();

function toggleLawyerFields() {
    const lawyerFields = document.getElementById('lawyerFields');
    const isLawyer = document.querySelector('input[name="userType"]:checked').value === 'lawyer';
    lawyerFields.style.display = isLawyer ? 'block' : 'none';
}

function firebaseRegister() {
    const name = document.getElementById('name').value.trim();
    const email = document.getElementById('email').value.trim();
    const password = document.getElementById('password').value;
    const userType = document.querySelector('input[name="userType"]:checked').value;
    const agreeTerms = document.getElementById('agreeTerms').checked;

    if (!name || !email || !password) return showError('Please fill in all required fields');
    if (!agreeTerms) return showError('Please agree to the Terms and Privacy Policy');
    if (password.length < 6) return showError('Password must be at least 6 characters long');

    const userData = {
        name,
        user_type: userType,
        phone: document.getElementById('phone').value.trim(),
        location: document.getElementById('location').value.trim()
    };

    if (userType === 'lawyer') {
        userData.lawyer_type = document.getElementById('lawyerType').value;
        userData.experience = parseInt(document.getElementById('experience').value) || 0;
        userData.license_number = document.getElementById('licenseNumber').value.trim();
        userData.education = document.getElementById('education').value.trim();
        const languages = document.getElementById('languagesSpoken').value.trim();
        userData.languages_spoken = languages ? languages.split(',').map(l => l.trim()) : [];
    }

    auth.createUserWithEmailAndPassword(email, password)
        .then(userCredential => userCredential.user.updateProfile({ displayName: name }))
        .then(() => auth.currentUser.sendEmailVerification())
        .then(() => auth.currentUser.getIdToken())
        .then(idToken => fetch('/api/firebase/verify-token/', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': getCookie('csrftoken')
            },
            body: JSON.stringify({
                idToken,
                userData,
                refreshToken: auth.currentUser.refreshToken
            })
        }))
        .then(res => res.json())
        .then(data => {
            if (data.success) {
                showSuccess('Account created! Please verify email, then login.');
                setTimeout(() => window.location.href = '/login/', 3000);
            } else {
                showError('Registration failed: ' + data.error);
            }
        })
        .catch(err => showError('Registration failed: ' + err.message));
}

function showError(message) {
    const errorDiv = document.getElementById('errorMessage');
    const successDiv = document.getElementById('successMessage');
    errorDiv.textContent = message;
    errorDiv.style.display = 'block';
    successDiv.style.display = 'none';
}

function showSuccess(message) {
    const successDiv = document.getElementById('successMessage');
    const errorDiv = document.getElementById('errorMessage');
    successDiv.textContent = message;
    successDiv.style.display = 'block';
    errorDiv.style.display = 'none';
}

function getCookie(name) {
    let cookieValue = null;
    if (document.cookie && document.cookie !== '') {
        const cookies = document.cookie.split(';');
        for (let cookie of cookies) {
            cookie = cookie.trim();
            if (cookie.startsWith(name + '=')) {
                cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                break;
            }
        }
    }
    return cookieValue;
}

// Init
document.addEventListener('DOMContentLoaded', toggleLawyerFields);
