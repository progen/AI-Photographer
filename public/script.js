const templateGrid = document.getElementById("templateGrid");
const templateInput = document.getElementById("templateInput");
const form = document.getElementById("generationForm");
const generateButton = document.getElementById("generateButton");
const statusBar = document.getElementById("statusBar");
const statusMessage = document.getElementById("statusMessage");
const resultPanel = document.getElementById("resultPanel");
const resultMeta = document.getElementById("resultMeta");
const resultImage = document.getElementById("resultImage");
const resultNote = document.getElementById("resultNote");

let selectedCard = null;

async function loadTemplates() {
  try {
    const response = await fetch("/api/templates");
    if (!response.ok) {
      throw new Error(`Failed to load templates (${response.status})`);
    }
    const templates = await response.json();
    renderTemplates(templates);
  } catch (error) {
    templateGrid.innerHTML = `<p role="alert">Could not load templates. ${error.message}</p>`;
    console.error(error);
  }
}

function renderTemplates(templates) {
  templateGrid.innerHTML = "";
  templates.forEach((template) => {
    const card = document.createElement("article");
    card.className = "template-card";
    card.setAttribute("role", "listitem");
    card.dataset.templateId = template.id;
    card.innerHTML = `
      <h3>${template.name}</h3>
      <p>${template.description}</p>
      <p class="guidance">${template.guidance}</p>
    `;

    card.addEventListener("click", () => selectTemplate(card));
    card.addEventListener("keydown", (event) => {
      if (event.key === "Enter" || event.key === " ") {
        event.preventDefault();
        selectTemplate(card);
      }
    });
    card.tabIndex = 0;

    templateGrid.appendChild(card);
  });
}

function selectTemplate(card) {
  if (selectedCard) {
    selectedCard.classList.remove("selected");
  }
  selectedCard = card;
  selectedCard.classList.add("selected");
  templateInput.value = card.dataset.templateId;
}

function setLoadingState(isLoading, message = "Generating with Gemini...") {
  generateButton.disabled = isLoading;
  statusBar.hidden = !isLoading;
  statusMessage.textContent = message;
}

function showResult(data) {
  if (data.imageBase64) {
    resultImage.src = `data:${data.mimeType};base64,${data.imageBase64}`;
    resultPanel.classList.add("active");
    resultMeta.textContent = `Template: ${data.templateName}`;
    resultNote.textContent = data.note
      ? data.note
      : data.source === "mock"
      ? "Mock response shown because Gemini API credentials are not configured."
      : "Generated with Gemini 2.7 Flash.";
  } else {
    resultPanel.classList.remove("active");
    resultMeta.textContent = "";
    resultNote.textContent = "";
  }
}

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  if (!templateInput.value) {
    alert("Please select a template before generating.");
    return;
  }

  setLoadingState(true);
  resultPanel.classList.remove("active");

  const formData = new FormData(form);

  try {
    const response = await fetch("/api/generate", {
      method: "POST",
      body: formData,
    });

    if (!response.ok) {
      const errorPayload = await response.json().catch(() => ({}));
      const errorMessage = errorPayload.error || response.statusText || "Unknown error";
      throw new Error(errorMessage);
    }

    const result = await response.json();
    showResult(result);
  } catch (error) {
    console.error("Generation failed", error);
    resultPanel.classList.add("active");
    resultMeta.textContent = "Generation failed";
    resultNote.textContent = error.message;
    resultImage.removeAttribute("src");
  } finally {
    setLoadingState(false, "Generating with Gemini...");
  }
});

loadTemplates();
