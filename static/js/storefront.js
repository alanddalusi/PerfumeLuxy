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
            // <picture>: every <source> must change too, otherwise it keeps winning over img.src.
            const sources = image.closest("picture")?.querySelectorAll("source") || [];
            sources.forEach((source, index) => {
                const srcset = thumbnail.dataset["srcset" + index];
                if (srcset) source.srcset = srcset; else source.remove();
            });
            if (thumbnail.dataset.srcset) image.srcset = thumbnail.dataset.srcset; else image.removeAttribute("srcset");
            image.src = thumbnail.href;
            image.alt = thumbnail.dataset.imageAlt;
            if (thumbnail.dataset.width) {
                image.width = Number(thumbnail.dataset.width);
                image.height = Number(thumbnail.dataset.height);
                image.style.setProperty("--img-max-w", thumbnail.dataset.width + "px");
                image.style.setProperty("--img-max-h", thumbnail.dataset.height + "px");
            }
            for (const item of thumbnails) item.removeAttribute("aria-current");
            thumbnail.setAttribute("aria-current", "true");
        });
    }
}
