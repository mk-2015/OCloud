let createUserForm = document.getElementById("createUserForm");

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
        showToast("User created successfully!", "success");
        createUserForm.reset();
	window.location.href = "/login.html";
    } else {
        let errorData = await result.json();
        let errorMessage = errorData.error || "An error occurred while creating the user.";

        let errorDiv = document.getElementById("message");
        errorDiv.textContent = errorMessage;
    }
});
