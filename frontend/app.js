const API_BASE = "http://localhost:8000"; // Your FastAPI URL

let signupRole = "user";
let loginRole = "user";
let session = null; // { role: "user" | "merchant", data: {...} }

// Helper: Extract a specific cookie by name
function getCookie(name) {
    const value = `; ${document.cookie}`;
    const parts = value.split(`; ${name}=`);
    if (parts.length === 2) return parts.pop().split(';').shift();
    return null;
}

function csrfHeaders() {
    return { "X-CSRF-Token": getCookie("csrf_token") };
}

// --- View switching ---

function showView(viewId) {
    document.querySelectorAll(".view").forEach(el => el.classList.add("hidden"));
    document.getElementById(viewId).classList.remove("hidden");
}

// --- Role / tab toggles ---

function setAuthTab(tab) {
    document.querySelectorAll(".tab-btn").forEach(btn => btn.classList.toggle("active", btn.dataset.tab === tab));
    document.getElementById("login-panel").classList.toggle("hidden", tab !== "login");
    document.getElementById("signup-panel").classList.toggle("hidden", tab !== "signup");
}

function setSignupRole(role) {
    signupRole = role;
    document.querySelectorAll("#signup-panel .role-btn").forEach(btn => btn.classList.toggle("active", btn.dataset.role === role));
    document.getElementById("signup-user-fields").classList.toggle("hidden", role !== "user");
    document.getElementById("signup-merchant-fields").classList.toggle("hidden", role !== "merchant");
}

function setLoginRole(role) {
    loginRole = role;
    document.querySelectorAll("#login-panel .role-btn").forEach(btn => btn.classList.toggle("active", btn.dataset.role === role));
}

// --- Signup ---

async function signup() {
    const username = document.getElementById("signup-username").value;
    const password = document.getElementById("signup-password").value;
    const statusEl = document.getElementById("signup-status");

    const endpoint = signupRole === "user" ? "/users/signup" : "/merchants/signup";
    const payload = signupRole === "user"
        ? {
            username,
            password,
            dob_year: parseInt(document.getElementById("signup-dob-year").value),
            gender: parseInt(document.getElementById("signup-gender").value),
            job: document.getElementById("signup-job").value,
            city_name: document.getElementById("signup-city").value,
            lat: parseFloat(document.getElementById("signup-lat").value),
            long: parseFloat(document.getElementById("signup-long").value),
        }
        : {
            username,
            password,
            category: document.getElementById("signup-category").value,
            lat: parseFloat(document.getElementById("signup-merchant-lat").value),
            long: parseFloat(document.getElementById("signup-merchant-long").value),
        };

    try {
        const response = await fetch(`${API_BASE}${endpoint}`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            credentials: "include",
            body: JSON.stringify(payload),
        });
        const data = await response.json();

        if (response.ok) {
            const id = signupRole === "user" ? data.user_id : data.merchant_id;
            statusEl.innerText = `✅ ${signupRole} created (id: ${id}). You can log in now.`;
            statusEl.style.color = "green";
            setAuthTab("login");
            setLoginRole(signupRole);
            document.getElementById("login-username").value = username;
        } else {
            statusEl.innerText = `❌ Error: ${data.detail}`;
            statusEl.style.color = "red";
        }
    } catch (error) {
        console.error("Signup failed:", error);
        statusEl.innerText = "❌ Signup request failed. Is the API running?";
        statusEl.style.color = "red";
    }
}

// --- Login / Logout ---

async function login() {
    const username = document.getElementById("login-username").value;
    const password = document.getElementById("login-password").value;
    const statusEl = document.getElementById("auth-status");

    const endpoint = loginRole === "user" ? "/users/login" : "/merchants/login";

    try {
        const response = await fetch(`${API_BASE}${endpoint}`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            credentials: "include",
            body: JSON.stringify({ username, password }),
        });
        const data = await response.json();

        if (response.ok) {
            statusEl.innerText = "";
            enterDashboard(loginRole, data);
        } else {
            statusEl.innerText = `❌ Error: ${data.detail}`;
            statusEl.style.color = "red";
        }
    } catch (error) {
        console.error("Login failed:", error);
        statusEl.innerText = "❌ Login request failed. Is the API running?";
        statusEl.style.color = "red";
    }
}

async function logout() {
    try {
        await fetch(`${API_BASE}/auth/logout`, {
            method: "POST",
            headers: csrfHeaders(),
            credentials: "include",
        });
    } catch (error) {
        console.error("Logout request failed:", error);
    }
    session = null;
    document.getElementById("topbar-session").classList.add("hidden");
    document.getElementById("login-username").value = "";
    document.getElementById("login-password").value = "";
    showView("auth-view");
}

// --- Session bootstrap: detect an existing cookie session on page load ---

async function restoreSession() {
    try {
        const userResp = await fetch(`${API_BASE}/users/me`, { credentials: "include" });
        if (userResp.ok) {
            enterDashboard("user", await userResp.json());
            return;
        }
    } catch (error) { /* not logged in as a user, fall through */ }

    try {
        const merchantResp = await fetch(`${API_BASE}/merchants/me`, { credentials: "include" });
        if (merchantResp.ok) {
            enterDashboard("merchant", await merchantResp.json());
            return;
        }
    } catch (error) { /* not logged in as a merchant either */ }

    showView("auth-view");
}

// --- Dashboards ---

function enterDashboard(role, data) {
    session = { role, data };

    document.getElementById("topbar-session").classList.remove("hidden");
    document.getElementById("session-label").innerText =
        role === "user" ? `👤 ${data.username} (User #${data.user_id})` : `🏪 ${data.username} (Merchant #${data.merchant_id})`;

    if (role === "user") {
        renderUserProfile(data);
        showView("user-dashboard");
        loadUserTransactions();
    } else {
        renderMerchantProfile(data);
        showView("merchant-dashboard");
        loadMerchantTransactions();
    }
}

function renderUserProfile(data) {
    const dl = document.getElementById("user-profile");
    dl.innerHTML = "";
    const fields = [
        ["Username", data.username],
        ["User ID", data.user_id],
        ["Job", data.job],
        ["City", data.city_id],
        ["DOB Year", data.dob_year],
    ];
    fields.forEach(([label, value]) => {
        dl.innerHTML += `<dt>${label}</dt><dd>${value}</dd>`;
    });
}

function renderMerchantProfile(data) {
    const dl = document.getElementById("merchant-profile");
    dl.innerHTML = "";
    const fields = [
        ["Username", data.username],
        ["Merchant ID", data.merchant_id],
        ["Category", data.category],
    ];
    fields.forEach(([label, value]) => {
        dl.innerHTML += `<dt>${label}</dt><dd>${value}</dd>`;
    });
}

// --- Transaction simulation (user side) ---

async function submitTransaction() {
    if (!session || session.role !== "user") return alert("Please log in as a user first!");

    const merchantId = document.getElementById("tx-merchant").value;
    const amount = document.getElementById("tx-amount").value;

    const payload = {
        user_id: session.data.user_id,
        merchant_id: parseInt(merchantId),
        amt: parseFloat(amount),
        unix_time: Math.floor(Date.now() / 1000),
    };

    try {
        const response = await fetch(`${API_BASE}/transaction`, {
            method: "POST",
            headers: {
                "Content-Type": "application/json",
                ...csrfHeaders(),
            },
            credentials: "include",
            body: JSON.stringify(payload),
        });
        const data = await response.json();

        if (response.ok) {
            displayResult(data);
            loadUserTransactions();
        } else {
            alert(`Error: ${data.detail}`);
        }
    } catch (error) {
        console.error("Transaction failed:", error);
    }
}

function displayResult(data) {
    const box = document.getElementById("result-box");
    box.classList.remove("hidden");

    document.getElementById("res-status").innerText = data.transaction_status;
    document.getElementById("res-status").style.color = data.transaction_status === "APPROVED" ? "green" : "red";
    document.getElementById("res-prob").innerText = (data.fraud_probability * 100).toFixed(2);
    document.getElementById("res-time").innerText = data.inference_time_ms;

    const riskList = document.getElementById("res-risk");
    riskList.innerHTML = "";
    const entries = Object.entries(data.top_risk_factors || {});
    if (entries.length === 0) {
        riskList.innerHTML = "<li>None</li>";
    } else {
        entries.forEach(([feature, value]) => {
            const li = document.createElement("li");
            li.innerText = `${feature}: ${value}`;
            riskList.appendChild(li);
        });
    }
}

// --- Transaction history ---

function statusBadge(status) {
    const cls = status === "APPROVED" ? "badge-ok" : status === "BLOCKED" ? "badge-bad" : "badge-warn";
    return `<span class="badge ${cls}">${status || "PENDING"}</span>`;
}

async function fetchMyTransactions() {
    const response = await fetch(`${API_BASE}/transactions/mine`, { credentials: "include" });
    if (!response.ok) return [];
    return response.json();
}

async function loadUserTransactions() {
    const rows = await fetchMyTransactions();
    const body = document.getElementById("user-tx-body");
    body.innerHTML = rows.length
        ? rows.map(tx => `
            <tr>
                <td>${new Date(tx.unix_time * 1000).toLocaleString()}</td>
                <td>#${tx.merchant_id}</td>
                <td>$${tx.amt.toFixed(2)}</td>
                <td>${statusBadge(tx.status)}</td>
                <td>${tx.fraud_probability != null ? (tx.fraud_probability * 100).toFixed(1) + "%" : "-"}</td>
            </tr>
        `).join("")
        : `<tr><td colspan="5" class="empty-row">No transactions yet.</td></tr>`;
}

async function loadMerchantTransactions() {
    const rows = await fetchMyTransactions();
    const body = document.getElementById("merchant-tx-body");
    body.innerHTML = rows.length
        ? rows.map(tx => `
            <tr>
                <td>${new Date(tx.unix_time * 1000).toLocaleString()}</td>
                <td>#${tx.user_id}</td>
                <td>$${tx.amt.toFixed(2)}</td>
                <td>${statusBadge(tx.status)}</td>
                <td>${tx.fraud_probability != null ? (tx.fraud_probability * 100).toFixed(1) + "%" : "-"}</td>
            </tr>
        `).join("")
        : `<tr><td colspan="5" class="empty-row">No transactions yet.</td></tr>`;

    const flagged = rows.filter(tx => tx.status === "BLOCKED" || tx.status === "FLAGGED_FOR_REVIEW").length;
    const volume = rows.reduce((sum, tx) => sum + tx.amt, 0);
    document.getElementById("stat-total").innerText = rows.length;
    document.getElementById("stat-flagged").innerText = flagged;
    document.getElementById("stat-volume").innerText = `$${volume.toFixed(2)}`;
}

// --- Boot ---

restoreSession();
