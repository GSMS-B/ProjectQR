/**
 * QRSecure - Authentication Module
 * Handles token management and auth state
 */

const QRSecureAuth = {
    // Token key in localStorage
    TOKEN_KEY: 'qrsecure_token',
    USER_KEY: 'qrsecure_user',

    /**
     * Get the current access token
     */
    getToken() {
        return localStorage.getItem(this.TOKEN_KEY);
    },

    /**
     * Get the current user info
     */
    getUser() {
        const userData = localStorage.getItem(this.USER_KEY);
        return userData ? JSON.parse(userData) : null;
    },

    /**
     * Check if user is authenticated
     */
    isAuthenticated() {
        return !!this.getToken();
    },

    /**
     * Store authentication data
     */
    setAuth(token, user) {
        localStorage.setItem(this.TOKEN_KEY, token);
        localStorage.setItem(this.USER_KEY, JSON.stringify(user));
    },

    /**
     * Clear authentication data
     */
    clearAuth() {
        localStorage.removeItem(this.TOKEN_KEY);
        localStorage.removeItem(this.USER_KEY);
    },

    /**
     * Logout the user
     */
    async logout() {
        try {
            await fetch('/api/auth/logout', {
                method: 'POST',
                headers: this.getAuthHeaders()
            });
        } catch (e) {
            // Ignore logout API errors
        }
        this.clearAuth();
        window.location.href = '/login';
    },

    /**
     * Get headers with authorization token
     */
    getAuthHeaders() {
        const token = this.getToken();
        return {
            'Content-Type': 'application/json',
            ...(token ? { 'Authorization': `Bearer ${token}` } : {})
        };
    },

    /**
     * Verify the current token is valid
     */
    async verifyToken() {
        const token = this.getToken();
        if (!token) return false;

        try {
            const response = await fetch('/api/auth/verify', {
                headers: this.getAuthHeaders()
            });
            const data = await response.json();
            return data.valid === true;
        } catch (e) {
            return false;
        }
    },

    /**
     * Require authentication - redirect to login if not authenticated
     */
    async requireAuth() {
        if (!this.isAuthenticated()) {
            window.location.href = '/login';
            return false;
        }

        // Verify token is still valid
        const isValid = await this.verifyToken();
        if (!isValid) {
            this.clearAuth();
            window.location.href = '/login';
            return false;
        }

        return true;
    }
};

// Export for use in other files
window.QRSecureAuth = QRSecureAuth;
