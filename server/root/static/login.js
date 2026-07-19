const form = document.getElementById('loginForm');
const message = document.getElementById('message');

form.addEventListener('submit', async (event) => {
  event.preventDefault();
  const payload = {
    username: document.getElementById('loginUsername').value,
    password: document.getElementById('loginPassword').value,
  };

  const response = await fetch('/api/login', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
  const data = await response.json();

  if (response.ok) {
    if (data.role === 'admin') {
      window.location.href = '/omedia/admin.html';
    } else {
      window.location.href = '/omedia/userdashboard.html';
    }
  } else {
    message.textContent = data.error || 'Login failed';
  }
});
