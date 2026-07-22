let createUserForm = document.getElementById("createUserForm");

function getCsrfToken() {
  const match = document.cookie.match(/(?:^|;\s*)csrf_token=([^;]*)/);
  return match ? decodeURIComponent(match[1]) : '';
}

(async () => {
  await fetch('/api/csrf-token');
})();

createUserForm.addEventListener("submit", async (event) => {
    event.preventDefault();
    let result = await fetch("/api/create_user", {
        method: "POST",
        headers: {
            "Content-Type": "application/json",
            "X-CSRF-Token": getCsrfToken()
        },
        body: JSON.stringify({
            username: document.getElementById("username").value,
            password: document.getElementById("password").value,
            email: document.getElementById("email").value
        })
    });

    if (result.status === 201) {
        alert("User created successfully!");
        createUserForm.reset();
	window.location.href = "/omedia/userdashboard.html";
    } else {
        let errorData = await result.json();
        let errorMessage = errorData.error || "An error occurred while creating the user.";

        let errorDiv = document.getElementById("error");
        errorDiv.textContent = errorMessage;
        errorDiv.style.display = "block";
    }
});
