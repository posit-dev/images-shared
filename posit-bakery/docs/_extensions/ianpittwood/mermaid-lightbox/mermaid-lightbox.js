(function () {
  "use strict";

  var inlineCounter = 0;

  function createLightboxContent(svgEl) {
    // Clone the SVG and scale it to fill the lightbox container.
    // CSS width/height on SVGs is unreliable (overridden by browser/Quarto
    // stylesheets), so we use SVG attributes instead.
    var clone = svgEl.cloneNode(true);

    var vb = clone.getAttribute("viewBox");
    var vbW, vbH;
    if (vb) {
      var parts = vb.split(/[\s,]+/);
      vbW = parseFloat(parts[2]);
      vbH = parseFloat(parts[3]);
    } else {
      vbW =
        parseFloat(clone.getAttribute("width")) ||
        svgEl.getBoundingClientRect().width;
      vbH =
        parseFloat(clone.getAttribute("height")) ||
        svgEl.getBoundingClientRect().height;
      if (vbW && vbH) {
        clone.setAttribute("viewBox", "0 0 " + vbW + " " + vbH);
      }
    }

    // Mermaid sets an inline max-width style that caps the SVG at its original
    // pixel size. Strip all inline styles and set scaling based on aspect ratio.
    clone.removeAttribute("width");
    clone.removeAttribute("height");
    clone.removeAttribute("style");
    clone.setAttribute("preserveAspectRatio", "xMidYMid meet");

    // Scale by the largest dimension: wide diagrams fill width, tall ones fill height
    var isLandscape = vbW && vbH && vbW >= vbH;
    if (isLandscape) {
      clone.style.setProperty("width", "100%", "important");
      clone.style.setProperty("max-width", "100%", "important");
      clone.style.setProperty("height", "auto", "important");
    } else {
      clone.style.setProperty("height", "calc(100vh - 120px)", "important");
      clone.style.setProperty("width", "auto", "important");
      clone.style.setProperty("max-width", "100%", "important");
    }

    // Create a hidden container for GLightbox inline content
    var id = "mermaid-lightbox-inline-" + ++inlineCounter;
    var container = document.createElement("div");
    container.id = id;
    container.style.display = "none";
    container.appendChild(clone);
    document.body.appendChild(container);

    return { id: id, isLandscape: isLandscape, vbW: vbW, vbH: vbH };
  }

  function getCaption(cell) {
    var figcaption = cell.querySelector("figcaption");
    return figcaption ? figcaption.textContent.trim() : "";
  }

  function findMermaidSvg(cell) {
    var figures = cell.querySelectorAll("figure");
    for (var i = 0; i < figures.length; i++) {
      var svg = figures[i].querySelector(":scope > div > svg, :scope > svg");
      if (svg) return svg;
    }
    return null;
  }

  function wireLightbox(cell) {
    var svg = findMermaidSvg(cell);
    if (!svg) return false;

    var caption = getCaption(cell);
    var result = createLightboxContent(svg);

    var link = document.createElement("a");
    link.href = "#" + result.id;
    link.classList.add("glightbox");
    link.setAttribute("data-type", "inline");
    // Landscape diagrams fill 90vw; portrait diagrams get a width calculated
    // from their aspect ratio to fit the viewport height
    if (result.isLandscape) {
      link.setAttribute("data-width", "90vw");
    } else if (result.vbW && result.vbH) {
      // Calculate width that maintains aspect ratio at ~85vh height
      var targetH = window.innerHeight * 0.85;
      var proportionalW = (result.vbW / result.vbH) * targetH;
      // Add padding for GLightbox chrome
      var panelW = Math.min(proportionalW + 60, window.innerWidth * 0.9);
      link.setAttribute("data-width", Math.round(panelW) + "px");
    }
    if (caption) {
      link.setAttribute("data-title", caption);
    }

    svg.parentNode.insertBefore(link, svg);
    link.appendChild(svg);

    cell.classList.add("mermaid-lightbox-target");
    return true;
  }

  function processCells() {
    var cells = document.querySelectorAll(".cell:not(.mermaid-lightbox-target)");
    var wired = 0;
    cells.forEach(function (cell) {
      if (!cell.querySelector("pre.mermaid-js") && !findMermaidSvg(cell)) return;
      if (wireLightbox(cell)) wired++;
    });
    return wired;
  }

  function init() {
    var lightbox = null;

    function refreshLightbox() {
      if (typeof GLightbox === "undefined") return;
      if (lightbox) lightbox.destroy();
      lightbox = GLightbox({
        selector: ".glightbox",
        openEffect: "fade",
        closeEffect: "fade",
      });
    }

    if (processCells() > 0) {
      refreshLightbox();
    }

    var observer = new MutationObserver(function () {
      if (processCells() > 0) {
        refreshLightbox();
      }
    });

    observer.observe(document.body, {
      childList: true,
      subtree: true,
    });

    setTimeout(function () {
      observer.disconnect();
      if (processCells() > 0) {
        refreshLightbox();
      }
    }, 10000);
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
