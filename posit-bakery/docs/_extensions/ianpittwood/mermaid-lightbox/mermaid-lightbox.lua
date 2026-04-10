-- Mermaid Lightbox: adds click-to-zoom lightbox to all mermaid diagrams.
-- Loading this filter enables lightbox for every mermaid diagram in the document.

local has_mermaid = false

local function div_contains_mermaid(el)
  local found = false
  pandoc.walk_block(el, {
    RawBlock = function(raw)
      if raw.format == "html" and raw.text:match('<pre class="mermaid') then
        found = true
      end
    end
  })
  return found
end

function Div(el)
  if el.classes:includes("cell") and div_contains_mermaid(el) then
    has_mermaid = true
  end
  return el
end

function Pandoc(doc)
  if not has_mermaid then
    return doc
  end

  if not quarto.doc.is_format("html:js") then
    return doc
  end

  quarto.doc.add_html_dependency({
    name = "glightbox",
    version = "3.3.1",
    stylesheets = {"resources/css/glightbox.min.css"},
    scripts = {"resources/js/glightbox.min.js"}
  })

  quarto.doc.add_html_dependency({
    name = "mermaid-lightbox-styles",
    version = "1.0.0",
    stylesheets = {"mermaid-lightbox.css"}
  })

  quarto.doc.add_html_dependency({
    name = "mermaid-lightbox-script",
    version = "1.0.0",
    scripts = {
      {
        path = "mermaid-lightbox.js",
        afterBody = true
      }
    }
  })

  return doc
end

return {
  {Div = Div, Pandoc = Pandoc}
}
