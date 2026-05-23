// Authentication handling for the entire application

class AuthManager {
    constructor() {
        this.token = localStorage.getItem('token');
        this.user = JSON.parse(localStorage.getItem('user') || 'null');
        this.init();
    }

    init() {
        this.setupEventListeners();
        this.checkAuth();
    }

    setupEventListeners() {
        // Login form
        const loginForm = document.getElementById('loginForm');
        if (loginForm) {
            loginForm.addEventListener('submit', (e) => this.handleLogin(e));
        }

        // Signup form
        const signupForm = document.getElementById('signupForm');
        if (signupForm) {
            signupForm.addEventListener('submit', (e) => this.handleSignup(e));
        }

        // Logout button
        const logoutBtn = document.getElementById('logoutBtn');
        if (logoutBtn) {
            logoutBtn.addEventListener('click', () => this.logout());
        }
    }

    async handleLogin(event) {
        event.preventDefault();

        const email = document.getElementById('email').value;
        const password = document.getElementById('password').value;

        if (!email || !password) {
            this.showError('Please fill in all fields');
            return;
        }

        this.showLoader(true);

        try {
            const response = await fetch('/api/auth/login', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({ email, password })
            });

            const data = await response.json();

            if (data.success) {
                this.setToken(data.token);
                this.setUser(data.user);
                this.showSuccess('Login successful! Redirecting...');
                setTimeout(() => {
                    window.location.href = '/dashboard';
                }, 1500);
            } else {
                this.showError(data.error || 'Login failed');
            }
        } catch (error) {
            console.error('Login error:', error);
            this.showError('Connection error. Please try again.');
        } finally {
            this.showLoader(false);
        }
    }

    async handleSignup(event) {
        event.preventDefault();

        const name = document.getElementById('name').value;
        const email = document.getElementById('email').value;
        const password = document.getElementById('password').value;
        const confirmPassword = document.getElementById('confirmPassword').value;

        if (!email || !password) {
            this.showError('Please fill in all fields');
            return;
        }

        if (password !== confirmPassword) {
            this.showError('Passwords do not match');
            return;
        }

        if (password.length < 6) {
            this.showError('Password must be at least 6 characters');
            return;
        }

        this.showLoader(true);

        try {
            const response = await fetch('/api/auth/register', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({ email, password, name })
            });

            const data = await response.json();

            if (data.success) {
                this.setToken(data.token);
                this.setUser(data.user);
                this.showSuccess('Account created! Redirecting...');
                setTimeout(() => {
                    window.location.href = '/dashboard';
                }, 1500);
            } else {
                this.showError(data.error || 'Signup failed');
            }
        } catch (error) {
            console.error('Signup error:', error);
            this.showError('Connection error. Please try again.');
        } finally {
            this.showLoader(false);
        }
    }

    async logout() {
        this.clearToken();
        this.clearUser();
        window.location.href = '/';
    }

    async checkAuth() {
        const token = this.getToken();
        if (!token) {
            // Only redirect if not on login page
            if (!window.location.pathname.includes('login.html') &&
                window.location.pathname !== '/') {
                window.location.href = '/';
            }
            return;
        }

        try {
            const response = await fetch('/api/auth/verify', {
                headers: {
                    'Authorization': `Bearer ${token}`
                }
            });
            const data = await response.json();

            if (!data.success) {
                this.clearToken();
                this.clearUser();
                if (!window.location.pathname.includes('login.html') &&
                    window.location.pathname !== '/') {
                    window.location.href = '/';
                }
            } else {
                this.setUser(data.user);
            }
        } catch (error) {
            console.error('Auth check error:', error);
        }
    }

    // Token management
    setToken(token) {
        this.token = token;
        localStorage.setItem('token', token);
    }

    getToken() {
        return this.token || localStorage.getItem('token');
    }

    clearToken() {
        this.token = null;
        localStorage.removeItem('token');
    }

    // User management
    setUser(user) {
        this.user = user;
        localStorage.setItem('user', JSON.stringify(user));
    }

    getUser() {
        return this.user;
    }

    clearUser() {
        this.user = null;
        localStorage.removeItem('user');
    }

    // UI helpers
    showLoader(show) {
        const loader = document.getElementById('loader');
        const submitBtn = document.querySelector('button[type="submit"]');

        if (loader) {
            loader.style.display = show ? 'block' : 'none';
        }

        if (submitBtn) {
            submitBtn.disabled = show;
        }
    }

    showError(message) {
        const errorDiv = document.getElementById('errorMessage');
        if (errorDiv) {
            errorDiv.innerHTML = `<i class="fas fa-exclamation-circle"></i> ${message}`;
            errorDiv.style.display = 'block';
            setTimeout(() => {
                errorDiv.style.display = 'none';
            }, 5000);
        }
    }

    showSuccess(message) {
        const successDiv = document.getElementById('successMessage');
        if (successDiv) {
            successDiv.innerHTML = `<i class="fas fa-check-circle"></i> ${message}`;
            successDiv.style.display = 'block';
            setTimeout(() => {
                successDiv.style.display = 'none';
            }, 3000);
        }
    }
}

// Initialize auth manager
const auth = new AuthManager();

// Export for use in other files
window.auth = auth;