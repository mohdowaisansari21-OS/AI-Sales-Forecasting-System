/**
 * auth.js - shared login/session helper for both login.html and index.html.
 *
 * Uses sessionStorage (not localStorage) so a session ends when the tab
 * closes, rather than persisting indefinitely on a shared machine.
 */
const AUTH_API_BASE = "http://127.0.0.1:8000";
const TOKEN_KEY = "sf_token";
const USERNAME_KEY = "sf_username";

const Auth = {
  getToken() {
    return sessionStorage.getItem(TOKEN_KEY);
  },

  getUsername() {
    return sessionStorage.getItem(USERNAME_KEY);
  },

  isLoggedIn() {
    return Boolean(this.getToken());
  },

  setSession(token, username) {
    sessionStorage.setItem(TOKEN_KEY, token);
    sessionStorage.setItem(USERNAME_KEY, username);
  },

  clearSession() {
    sessionStorage.removeItem(TOKEN_KEY);
    sessionStorage.removeItem(USERNAME_KEY);
  },

  logout() {
    this.clearSession();
    window.location.href = "login.html";
  },

  /** Redirect to the login page if there's no session. Call at the top of protected pages. */
  requireLogin() {
    if (!this.isLoggedIn()) {
      window.location.href = "login.html";
    }
  },

  /** Merge Authorization header into a fetch() options object. */
  authHeaders(extra) {
    const token = this.getToken();
    return {
      ...(extra || {}),
      "Content-Type": "application/json",
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    };
  },

  async _post(path, body) {
    const response = await fetch(`${AUTH_API_BASE}${path}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    const data = await response.json().catch(() => ({}));
    if (!response.ok) {
      throw new Error(data.detail || `Request failed (${response.status})`);
    }
    return data;
  },

  /** identifier = username OR email */
  async login(identifier, password) {
    const data = await this._post("/api/auth/login", { identifier, password });
    this.setSession(data.token, data.username);
    return data;
  },

  /** Step 1 of signup: creates an unverified account and emails an OTP. No session yet. */
  async register({ firstName, lastName, email, username, password }) {
    return this._post("/api/auth/register", {
      first_name: firstName,
      last_name: lastName,
      email,
      username,
      password,
    });
  },

  /** Step 2 of signup: confirms the OTP and logs the user in. */
  async verifyOtp(email, otp) {
    const data = await this._post("/api/auth/verify-otp", { email, otp });
    this.setSession(data.token, data.username);
    return data;
  },

  async resendOtp(email) {
    return this._post("/api/auth/resend-otp", { email });
  },

  async forgotPassword(email) {
    return this._post("/api/auth/forgot-password", { email });
  },

  async resetPassword(email, token, newPassword) {
    return this._post("/api/auth/reset-password", { email, token, new_password: newPassword });
  },
};
