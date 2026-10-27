
document.addEventListener("DOMContentLoaded", function () {
    const form = document.getElementById("feedbackForm");

    if (!form) {
        return;
    }

    form.addEventListener("submit", function (event) {
        const fields = [
            "teaching",
            "clarity",
            "interaction",
            "punctuality",
            "facilities"
        ];

        for (const field of fields) {
            const selected = form.querySelector(
                'input[name="' + field + '"]:checked'
            );

            if (!selected) {
                event.preventDefault();
                alert("Please rate every category before submitting.");
                return;
            }
        }

        if (!form.checkValidity()) {
            event.preventDefault();
            form.reportValidity();
        }
    });
});
