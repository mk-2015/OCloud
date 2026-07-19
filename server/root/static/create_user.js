let createUserForm = document.getElementById("createUserForm");

createUserForm.addEventListener("submit", async (event) => {
    event.preventDefault();
    let result = await fetch("/api/create_user", {
        method: "POST",
        headers: {
            "Content-Type": "application/json"
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
