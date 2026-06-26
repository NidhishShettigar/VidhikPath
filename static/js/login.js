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

// Initialize Firebase
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
            try {
                // Decode token without verifying to inspect claims
                const decoded = (function decodeJwt(t){
                    try {
                        const parts = t.split('.');
                        if (parts.length < 2) return null;
                        const payload = parts[1].replace(/-/g, '+').replace(/_/g, '/');
                        const json = decodeURIComponent(atob(payload).split('').map(function(c){
                            return '%' + ('00' + c.charCodeAt(0).toString(16)).slice(-2);
                        }).join(''));
                        return JSON.parse(json);
                    } catch(e){ console.warn('decodeJwt failed', e); return null; }
                })(idToken);

                console.log('Decoded ID token payload:', decoded || '(failed to decode)');
                if (decoded) {
                    console.log('ID token aud:', decoded.aud, 'iss:', decoded.iss, 'sub:', decoded.sub);
                }
            } catch(e){ console.warn('token decode/log failed', e); }

            // Log current initialized project
            try { console.log('Current Project after login:', firebase.app().options && firebase.app().options.projectId); } catch(e){}

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
