function zoom(img) {
    if (img.classList.contains("zoomed")) {
        img.classList.remove("zoomed");
        img.style.maxWidth = "200px";
        img.style.maxHeight = "150px";
    } else {
        img.classList.add("zoomed");
        img.style.maxWidth = "100%";
        img.style.maxHeight = "none";
    }
}
