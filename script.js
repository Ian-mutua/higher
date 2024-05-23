document.addEventListener('DOMContentLoaded', () => {
    const form = document.getElementById('trade-form');
    const balanceSpan = document.getElementById('balance');
    const notificationP = document.getElementById('notification');

    // Event listener for form submission
    form.addEventListener('submit', async (event) => {
        event.preventDefault();

        // Send form data to Flask server
        const formData = new FormData(form);
        const response = await fetch('/trade', {
            method: 'POST',
            body: formData
        });

        if (response.ok) {
            const result = await response.json();
            notificationP.textContent = result.message;
        } else {
            notificationP.textContent = 'Error occurred while trading.';
        }
    });
});
