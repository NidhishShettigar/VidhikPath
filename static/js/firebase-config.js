// Firebase configuration
import { initializeApp } from 'firebase/app';
import { 
    getAuth, 
    signInWithEmailAndPassword, 
    createUserWithEmailAndPassword,
    signOut,
    onAuthStateChanged 
} from 'firebase/auth';

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
const app = initializeApp(firebaseConfig);
const auth = getAuth(app);

// Firebase Auth functions
export const firebaseLogin = async (email, password) => {
    try {
        const userCredential = await signInWithEmailAndPassword(auth, email, password);
        const token = await userCredential.user.getIdToken();
        
        // Send token to Django backend
        const response = await fetch('/api/firebase-login/', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${token}`,
                'X-CSRFToken': getCsrfToken()
            },
            body: JSON.stringify({ token })
        });
        
        if (response.ok) {
            window.location.href = '/dashboard/';
        } else {
            throw new Error('Backend authentication failed');
        }
    } catch (error) {
        console.error('Login error:', error);
        throw error;
    }
};

export const firebaseRegister = async (email, password, additionalData) => {
    try {
        const userCredential = await createUserWithEmailAndPassword(auth, email, password);
        const token = await userCredential.user.getIdToken();
        
        // Send registration data to Django
        const response = await fetch('/api/firebase-register/', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${token}`,
                'X-CSRFToken': getCsrfToken()
            },
            body: JSON.stringify({
                token,
                ...additionalData
            })
        });
        
        if (response.ok) {
            window.location.href = '/dashboard/';
        } else {
            throw new Error('Registration failed');
        }
    } catch (error) {
        console.error('Registration error:', error);
        throw error;
    }
};

export const firebaseLogout = async () => {
    try {
        await signOut(auth);
        
        // Also logout from Django
        await fetch('/logout/', {
            method: 'POST',
            headers: {
                'X-CSRFToken': getCsrfToken()
            }
        });
        
        window.location.href = '/login/';
    } catch (error) {
        console.error('Logout error:', error);
    }
};

// Auto-login check
export const setupAuthStateListener = () => {
    onAuthStateChanged(auth, async (user) => {
        if (user) {
            const token = await user.getIdToken();
            
            // Send token to Django for session creation
            fetch('/api/verify-token/', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'Authorization': `Bearer ${token}`,
                    'X-CSRFToken': getCsrfToken()
                },
                body: JSON.stringify({ token })
            });
        }
    });
};

// Helper function to get CSRF token
function getCsrfToken() {
    return document.querySelector('[name=csrfmiddlewaretoken]')?.value || '';
}

export { auth };