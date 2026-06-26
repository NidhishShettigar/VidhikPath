// Determine Firebase configuration: prefer rendered server-side config (single source of truth)
let firebaseConfig = null;
try {
    const el = document.getElementById('firebase-config');
    if (el) {
        firebaseConfig = JSON.parse(el.textContent || '{}');
    }
} catch (e) {
    console.error('Failed to parse rendered firebase config:', e);
}

// Fallback to embedded config if template did not provide one
if (!firebaseConfig || !firebaseConfig.projectId) {
    firebaseConfig = {
        apiKey: "AIzaSyDFXCASnsC1Yi_bpwDuwhkicYNNzhR-v9s",
        authDomain: "vidhikpath-c22cb.firebaseapp.com",
        projectId: "vidhikpath-c22cb",
        storageBucket: "vidhikpath-c22cb.firebasestorage.app",
        messagingSenderId: "1028848699647",
        appId: "1:1028848699647:web:f3e9567bd975a03b4064ca",
        measurementId: "G-H129B0J3HP"
    };
}

// Debug: log config before initialization
try { console.log('Firebase Config:', firebaseConfig); } catch(e){}

// If there are existing apps, log them and delete to ensure a single app
if (window.firebase && Array.isArray(firebase.apps) && firebase.apps.length) {
    try {
        console.log('Existing firebase apps before init:', firebase.apps.map(a=>a.options && a.options.projectId ? a.options.projectId : (a.name||'<unnamed>')));
    } catch(e){ console.warn('Error enumerating existing firebase apps', e); }
    try {
        firebase.apps.forEach(app => {
            try { app.delete(); } catch(err) { console.warn('firebase.app().delete() failed for', app, err); }
        });
    } catch(e) { console.warn('Error deleting existing firebase apps', e); }
}

// Init Firebase
firebase.initializeApp(firebaseConfig);

// Log app options after initialization
try { console.log('Firebase App Options:', firebase.app().options); } catch(e) { console.warn('firebase.app().options error', e); }
try { console.log('Firebase apps count after init:', (firebase.apps && firebase.apps.length) || 0); } catch(e){}

// Environment checks: service worker, local/session storage
try {
    const lsKeys = Object.keys(localStorage || {}).filter(k=>/firebase|auth|gcm/i.test(k));
    const ssKeys = Object.keys(sessionStorage || {}).filter(k=>/firebase|auth|gcm/i.test(k));
    console.log('localStorage firebase-like keys:', lsKeys);
    console.log('sessionStorage firebase-like keys:', ssKeys);
} catch(e){ console.warn('storage check failed', e); }
if (navigator && navigator.serviceWorker && navigator.serviceWorker.getRegistrations) {
    navigator.serviceWorker.getRegistrations().then(regs=>{
        try { console.log('serviceWorker registrations:', regs.map(r=>r.scope)); } catch(e){}
    }).catch(()=>{});
}
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

    const registerButton = document.getElementById('registerButton');
    if (registerButton) {
        registerButton.disabled = true;
        registerButton.textContent = 'Registering...';
    }

    try {
        console.log('signUp: starting with email', email);
        const userCredential = await auth.createUserWithEmailAndPassword(email, password);
        console.log('signUp: succeeded', userCredential.user.uid);

        if (!auth.currentUser) {
            console.log('lookup: auth.currentUser missing after sign-up');
            return showError('Registration failed: Unable to access authenticated user.');
        }

        console.log('lookup: current user', auth.currentUser.email);
        await userCredential.user.updateProfile({ displayName: name });
        console.log('updateProfile: success');

        await auth.currentUser.sendEmailVerification();
        console.log('sendEmailVerification: success');

        await auth.currentUser.reload();
        console.log('lookup: reloaded current user', auth.currentUser.email);

        const idToken = await auth.currentUser.getIdToken(true);
        console.log('verify-token: sending token to backend');

        // Decode token locally (no verification) to inspect claims
        try {
            const decodeJwt = function(t){
                try {
                    const parts = t.split('.');
                    if (parts.length < 2) return null;
                    const payload = parts[1].replace(/-/g, '+').replace(/_/g, '/');
                    const json = decodeURIComponent(atob(payload).split('').map(function(c){
                        return '%' + ('00' + c.charCodeAt(0).toString(16)).slice(-2);
                    }).join(''));
                    return JSON.parse(json);
                } catch(e){ console.warn('decodeJwt failed', e); return null; }
            };
            const decoded = decodeJwt(idToken);
            console.log('Decoded ID token payload (registration):', decoded || '(failed to decode)');
            if (decoded) {
                console.log('ID token aud:', decoded.aud, 'iss:', decoded.iss, 'sub:', decoded.sub);
            }
        } catch(e){ console.warn('token decode failed', e); }

        try { console.log('Current Project after register:', firebase.app().options && firebase.app().options.projectId); } catch(e){}

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

        let data;
        try {
            data = await response.json();
        } catch (jsonErr) {
            console.log('verify-token: invalid JSON response', jsonErr);
            return showError('Registration failed: Unable to parse verification response.');
        }

        console.log('verify-token: response', response.status, data);

        if (!response.ok) {
            return showError('Registration failed: ' + (data.error || response.statusText));
        }

        if (data.success !== true) {
            return showError('Registration failed: ' + (data.error || 'Unable to verify token')); 
        }

        showSuccess('Account created! Please verify email, then login.');
        const redirectUrl = data.redirect || '/login/';
        console.log('redirect: to', redirectUrl);
        setTimeout(() => window.location.href = redirectUrl, 2000);
    } catch (err) {
        console.log('firebaseRegister: error', err);
        if (err.code === 'auth/email-already-in-use' || (err.message && err.message.includes('EMAIL_EXISTS'))) {
            return showError('An account with this email already exists.');
        }
        showError('Registration failed: ' + (err.message || 'Unexpected error'));
    } finally {
        if (registerButton) {
            registerButton.disabled = false;
            registerButton.textContent = 'Create Account';
        }
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
