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

function clearMessages() {
    const errorDiv = document.getElementById('errorMessage');
    const successDiv = document.getElementById('successMessage');
    errorDiv.textContent = '';
    successDiv.textContent = '';
    errorDiv.style.display = 'none';
    successDiv.style.display = 'none';
}

async function firebaseRegister() {
    clearMessages();

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

    try {
        console.log('signUp: starting with email', email);
        const userCredential = await auth.createUserWithEmailAndPassword(email, password);
        console.log('signUp: succeeded', userCredential.user.uid);

        console.log('lookup: current user', auth.currentUser ? auth.currentUser.email : 'none');
        await userCredential.user.updateProfile({ displayName: name });
        console.log('updateProfile: success');

        await auth.currentUser.sendEmailVerification();
        console.log('sendEmailVerification: success');

        const idToken = await auth.currentUser.getIdToken();
        console.log('verify-token: sending token to backend');

        const response = await fetch('/api/firebase/verify-token/', {
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
        });

        const data = await response.json();
        console.log('verify-token: response', response.status, data);

        if (!response.ok) {
            return showError('Registration failed: ' + (data.error || response.statusText));
        }

        if (!data.success) {
            return showError('Registration failed: ' + (data.error || 'Unable to verify token'));
        }

        showSuccess('Account created! Please verify email, then login.');
        const redirectUrl = data.redirect || '/login/';
        console.log('redirect: to', redirectUrl);
        setTimeout(() => window.location.href = redirectUrl, 3000);
    } catch (err) {
        console.log('firebaseRegister: error', err);
        if (err.code === 'auth/email-already-in-use' || (err.message && err.message.includes('EMAIL_EXISTS'))) {
            return showError('An account with this email already exists.');
        }
        showError('Registration failed: ' + (err.message || 'Unexpected error'));
    }
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
