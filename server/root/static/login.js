const form = document.getElementById('loginForm');
const message = document.getElementById('message');
const submitBtn = form.querySelector('button[type="submit"]');
let lockoutTimer = null;

function startLockoutCountdown(seconds) {
  if (lockoutTimer) clearInterval(lockoutTimer);
  submitBtn.disabled = true;
  let remaining = seconds;
  const tick = () => {
    const m = Math.floor(remaining / 60);
    const s = remaining % 60;
    message.textContent = `Locked out. Try again in ${m}:${String(s).padStart(2, '0')}`;
    if (remaining <= 0) {
      clearInterval(lockoutTimer);
      lockoutTimer = null;
      submitBtn.disabled = false;
      message.textContent = '';
    }
    remaining--;
  };
  tick();
  lockoutTimer = setInterval(tick, 1000);
}

(async () => {
  await fetch('/api/csrf-token');
})();

form.addEventListener('submit', async (event) => {
  event.preventDefault();
  if (lockoutTimer) return;

  const payload = {
    username: document.getElementById('loginUsername').value,
    password: document.getElementById('loginPassword').value,
  };

  const response = await fetch('/api/login', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', 'X-CSRF-Token': getCsrfToken() },
    body: JSON.stringify(payload),
  });
  const data = await response.json();

  if (response.ok) {
    if (data.token) localStorage.setItem('omedia_token', data.token);
    if (data.role === 'admin') {
      window.location.href = '/omedia/admin.html';
    } else {
      window.location.href = '/omedia/userdashboard.html';
    }
  } else {
    message.textContent = data.error || 'Login failed';
    if (data.retry_after) {
      startLockoutCountdown(data.retry_after);
    }
  }
});
