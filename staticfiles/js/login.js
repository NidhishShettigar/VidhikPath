// Firebase configuration
const firebaseConfig = {
    apiKey: "AIzaSyDFXCASnsC1Yi_bpwDuwhkicYNNzhR-v9s",
    authDomain: "vidhikpath-e9e56.firebaseapp.com",
    projectId: "vidhikpath-e9e56",
    storageBucket: "vidhikpath-e9e56.firebasestorage.app",
    messagingSenderId: "1028848699647",
    appId: "1:1028848699647:web:f3e9567bd975a03b4064ca",
    measurementId: "G-H129B0J3HP"
};

// Initialize Firebase
firebase.initializeApp(firebaseConfig);
const auth = firebase.auth();

function firebaseLogin() {
    const email = document.getElementById('email').value;
    const password = document.getElementById('password').value;
    
    if (!email || !password) {
        showError('Please enter both email and password');
        return;
    }
    
    auth.signInWithEmailAndPassword(email, password)
        .then((userCredential) => {
            return userCredential.user.getIdToken();
        })
        .then((idToken) => {
            // Send token to Django backend for verification and session creation
            return fetch('/api/firebase/verify-token/', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': getCookie('csrftoken')
                },
                body: JSON.stringify({ 
                    idToken: idToken,
                    refreshToken: firebase.auth().currentUser.refreshToken
                })
            });
        })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                window.location.href = data.redirect || '/dashboard/';
            } else {
                showError('Login failed: ' + data.error);
            }
        })
        .catch((error) => {
            showError('Login failed: ' + error.message);
        });
}

function showPasswordReset() {
    document.getElementById('passwordResetModal').style.display = 'flex';
}

function hidePasswordReset() {
    document.getElementById('passwordResetModal').style.display = 'none';
}

function sendPasswordReset() {
    const email = document.getElementById('resetEmail').value;
    
    if (!email) {
        alert('Please enter your email address');
        return;
    }
    
    fetch('/api/firebase/password-reset/', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': getCookie('csrftoken')
        },
        body: JSON.stringify({ email: email })
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            alert('Password reset email sent!');
            hidePasswordReset();
        } else {
            alert('Error: ' + data.message);
        }
    });
}

function showError(message) {
    const errorDiv = document.getElementById('errorMessage');
    errorDiv.textContent = message;
    errorDiv.style.display = 'block';
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

// Enter key support
document.addEventListener('keypress', function(e) {
    if (e.key === 'Enter') {
        firebaseLogin();
    }
});
