const filters = document.querySelector("[data-filters]");
if (filters && window.matchMedia("(min-width: 64rem)").matches) {
    filters.open = true;
}

const comparisonForm = document.getElementById("sf-compare");
if (comparisonForm) {
    const choices = [...document.querySelectorAll('input[form="sf-compare"]')];
    const status = document.getElementById("sf-compare-status");
    const submit = comparisonForm.querySelector("button");
    function updateComparison() {
        const count = choices.filter(choice => choice.checked).length;
        submit.disabled = count < 2 || count > 3;
        status.textContent = count > 3
            ? "Puedes comparar un máximo de tres perfumes."
            : count > 0 ? `${count} de 3 perfumes seleccionados.` : "Selecciona dos o tres perfumes.";
    }
    for (const choice of choices) choice.addEventListener("change", updateComparison);
    window.addEventListener("pageshow", updateComparison);
    updateComparison();
}

for (const gallery of document.querySelectorAll("[data-gallery]")) {
    const image = gallery.querySelector("[data-gallery-main]");
    const thumbnails = gallery.querySelectorAll("[data-gallery-image]");
    for (const thumbnail of thumbnails) {
        thumbnail.addEventListener("click", event => {
            if (event.ctrlKey || event.metaKey || event.shiftKey || event.altKey) return;
            event.preventDefault();
            image.src = thumbnail.href;
            image.alt = thumbnail.dataset.imageAlt;
            for (const item of thumbnails) item.removeAttribute("aria-current");
            thumbnail.setAttribute("aria-current", "true");
        });
    }
}
