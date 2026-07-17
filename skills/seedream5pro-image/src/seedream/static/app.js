const state = {
  mode: "normal",
  images: [],
  annotations: [],
  selectedId: null,
  nextId: 1,
  nextAnnotationId: 1,
  view: { x: 260, y: 160, scale: 0.75 },
  drag: null,
  pan: null,
  box: null,
  dragDepth: 0,
  isSpacePressed: false,
  saveStatus: "",
};

const viewport = document.getElementById("viewport");
const world = document.getElementById("world");
const zoomBadge = document.getElementById("zoomBadge");
const fileInput = document.getElementById("fileInput");
const intentInput = document.getElementById("intentInput");
const saveBtn = document.getElementById("saveBtn");
const clearPromptBtn = document.getElementById("clearPromptBtn");
const statusEl = document.getElementById("status");
const saveStatusEl = document.getElementById("saveStatus");
const imageList = document.getElementById("imageList");
const annotationPreview = document.getElementById("annotationPreview");

const ANNOTATION_COLORS = [
  "#ff5c8a",
  "#7c5cff",
  "#00a7e1",
  "#00b894",
  "#ff9f1c",
  "#e84393",
  "#2d9cdb",
  "#9b5de5",
  "#f15bb5",
  "#43aa8b",
];

function colorForAnnotation(index) {
  return ANNOTATION_COLORS[(index - 1) % ANNOTATION_COLORS.length];
}

function rgba(hex, alpha) {
  const value = hex.replace("#", "");
  const r = parseInt(value.slice(0, 2), 16);
  const g = parseInt(value.slice(2, 4), 16);
  const b = parseInt(value.slice(4, 6), 16);
  return `rgba(${r}, ${g}, ${b}, ${alpha})`;
}

function updateIntentEmptyState() {
  intentInput.classList.toggle("empty", getEditorIntent().length === 0);
}

function setStatus(text, isError = false) {
  statusEl.textContent = text;
  statusEl.classList.toggle("error", isError);
}

function updateSaveStatus(text, isError = false) {
  saveStatusEl.textContent = text;
  saveStatusEl.classList.toggle("error", isError);
}

function applyView() {
  world.style.transform = `translate(${state.view.x}px, ${state.view.y}px) scale(${state.view.scale})`;
  zoomBadge.textContent = `${Math.round(state.view.scale * 100)}%`;
}

function clientToWorld(clientX, clientY) {
  const rect = viewport.getBoundingClientRect();
  return {
    x: (clientX - rect.left - state.view.x) / state.view.scale,
    y: (clientY - rect.top - state.view.y) / state.view.scale,
  };
}

function worldToClient(x, y) {
  const rect = viewport.getBoundingClientRect();
  return {
    x: rect.left + state.view.x + x * state.view.scale,
    y: rect.top + state.view.y + y * state.view.scale,
  };
}

function clamp1000(value) {
  return Math.max(0, Math.min(1000, Math.round(value)));
}

function pointInImage(worldPoint, image) {
  return (
    worldPoint.x >= image.x &&
    worldPoint.x <= image.x + image.width &&
    worldPoint.y >= image.y &&
    worldPoint.y <= image.y + image.height
  );
}

function imageAt(worldPoint) {
  for (let i = state.images.length - 1; i >= 0; i -= 1) {
    if (pointInImage(worldPoint, state.images[i])) {
      return state.images[i];
    }
  }
  return null;
}

function normalizedPoint(worldPoint, image) {
  return {
    x: clamp1000(((worldPoint.x - image.x) / image.width) * 1000),
    y: clamp1000(((worldPoint.y - image.y) / image.height) * 1000),
  };
}

function normalizedBox(a, b, image) {
  const x1 = Math.max(image.x, Math.min(a.x, b.x));
  const y1 = Math.max(image.y, Math.min(a.y, b.y));
  const x2 = Math.min(image.x + image.width, Math.max(a.x, b.x));
  const y2 = Math.min(image.y + image.height, Math.max(a.y, b.y));
  return {
    x1: clamp1000(((x1 - image.x) / image.width) * 1000),
    y1: clamp1000(((y1 - image.y) / image.height) * 1000),
    x2: clamp1000(((x2 - image.x) / image.width) * 1000),
    y2: clamp1000(((y2 - image.y) / image.height) * 1000),
  };
}

function normalizedToNaturalPoint(image, x, y) {
  return {
    x: (x / 1000) * image.naturalWidth,
    y: (y / 1000) * image.naturalHeight,
  };
}

function drawRoundedLabel(ctx, text, x, y, color) {
  ctx.font = "600 18px Inter, sans-serif";
  const metrics = ctx.measureText(text);
  const width = metrics.width + 22;
  const height = 30;
  ctx.fillStyle = "rgba(15, 23, 42, 0.78)";
  ctx.beginPath();
  ctx.roundRect(x, y, width, height, 14);
  ctx.fill();
  ctx.fillStyle = color;
  ctx.fillText(text, x + 11, y + 21);
}

function canvasToDataUrl(canvas) {
  try {
    return canvas.toDataURL("image/jpeg", 0.88);
  } catch {
    return "";
  }
}

function makePointPreview(image, ann) {
  const source = image.element;
  if (!source) return "";

  const point = normalizedToNaturalPoint(image, ann.x, ann.y);
  const cropSize = Math.round(Math.min(image.naturalWidth, image.naturalHeight) * 0.34);
  const sx = Math.max(0, Math.min(image.naturalWidth - cropSize, point.x - cropSize / 2));
  const sy = Math.max(0, Math.min(image.naturalHeight - cropSize, point.y - cropSize / 2));
  const outW = 220;
  const outH = 220;
  const scale = outW / cropSize;
  const px = (point.x - sx) * scale;
  const py = (point.y - sy) * scale;

  const canvas = document.createElement("canvas");
  canvas.width = outW;
  canvas.height = outH;
  const ctx = canvas.getContext("2d");
  ctx.drawImage(source, sx, sy, cropSize, cropSize, 0, 0, outW, outH);

  ctx.fillStyle = rgba(ann.color, 0.18);
  ctx.strokeStyle = ann.color;
  ctx.lineWidth = 4;
  ctx.beginPath();
  ctx.arc(px, py, 13, 0, Math.PI * 2);
  ctx.fill();
  ctx.stroke();
  ctx.lineWidth = 2;
  ctx.beginPath();
  ctx.moveTo(px - 23, py);
  ctx.lineTo(px + 23, py);
  ctx.moveTo(px, py - 23);
  ctx.lineTo(px, py + 23);
  ctx.stroke();
  drawRoundedLabel(ctx, `<point>${ann.x} ${ann.y}</point>`, 10, 10, ann.color);
  return canvasToDataUrl(canvas);
}

function makeBoxPreview(image, ann) {
  const source = image.element;
  if (!source) return "";

  const sx = (ann.x1 / 1000) * image.naturalWidth;
  const sy = (ann.y1 / 1000) * image.naturalHeight;
  const sw = Math.max(1, ((ann.x2 - ann.x1) / 1000) * image.naturalWidth);
  const sh = Math.max(1, ((ann.y2 - ann.y1) / 1000) * image.naturalHeight);
  const longSide = 220;
  const outW = sw >= sh ? longSide : Math.max(90, Math.round((sw / sh) * longSide));
  const outH = sh >= sw ? longSide : Math.max(90, Math.round((sh / sw) * longSide));

  const canvas = document.createElement("canvas");
  canvas.width = outW;
  canvas.height = outH;
  const ctx = canvas.getContext("2d");
  ctx.fillStyle = "#0f172a";
  ctx.fillRect(0, 0, canvas.width, canvas.height);
  ctx.drawImage(source, sx, sy, sw, sh, 0, 0, outW, outH);
  ctx.strokeStyle = ann.color;
  ctx.lineWidth = 8;
  ctx.strokeRect(4, 4, canvas.width - 8, canvas.height - 8);
  drawRoundedLabel(ctx, `<bbox>${ann.x1} ${ann.y1} ${ann.x2} ${ann.y2}</bbox>`, 10, 10, ann.color);
  return canvasToDataUrl(canvas);
}

function buildAnnotation(type, image, payload) {
  const id = state.nextAnnotationId;
  const color = colorForAnnotation(id);
  const ann = { id, type, imageId: image.id, color, ...payload };
  ann.previewUrl = type === "point" ? makePointPreview(image, ann) : makeBoxPreview(image, ann);
  state.nextAnnotationId += 1;
  return ann;
}

function getEditorIntent() {
  function walk(node) {
    if (node.nodeType === Node.TEXT_NODE) {
      return node.textContent || "";
    }
    if (node.nodeType !== Node.ELEMENT_NODE) {
      return "";
    }
    if (node.classList?.contains("annotation-inline")) {
      return ` ${node.dataset.token || ""} `;
    }
    if (node.tagName === "BR") {
      return "\n";
    }
    return [...node.childNodes].map(walk).join("");
  }
  return walk(intentInput)
    .replace(/\u00a0/g, " ")
    .replace(/[ \t]{2,}/g, " ")
    .replace(/\n{3,}/g, "\n\n")
    .trim();
}

function activeAnnotationsInPrompt() {
  const activeIds = new Set(
    [...intentInput.querySelectorAll(".annotation-inline")].map((chip) => Number(chip.dataset.annotationId))
  );
  return state.annotations.filter((ann) => activeIds.has(ann.id));
}

function annotationIdsInPrompt() {
  return new Set([...intentInput.querySelectorAll(".annotation-inline")].map((chip) => Number(chip.dataset.annotationId)));
}

function syncAnnotationsFromPrompt() {
  const activeIds = annotationIdsInPrompt();
  const before = state.annotations.length;
  state.annotations = state.annotations.filter((ann) => activeIds.has(ann.id));
  updateIntentEmptyState();
  if (state.annotations.length !== before) {
    renderImages();
  }
}

function placeCaretAtEnd(el) {
  const range = document.createRange();
  range.selectNodeContents(el);
  range.collapse(false);
  const selection = window.getSelection();
  selection.removeAllRanges();
  selection.addRange(range);
}

function selectionIsInsidePrompt() {
  const selection = window.getSelection();
  return selection.rangeCount > 0 && intentInput.contains(selection.getRangeAt(0).commonAncestorContainer);
}

function insertNodeIntoPrompt(node) {
  intentInput.focus();
  if (!selectionIsInsidePrompt()) {
    placeCaretAtEnd(intentInput);
  }

  const selection = window.getSelection();
  const range = selection.getRangeAt(0);
  range.deleteContents();
  range.insertNode(document.createTextNode(" "));
  range.collapse(false);
  range.insertNode(node);
  range.collapse(false);
  range.insertNode(document.createTextNode(" "));
  range.collapse(false);
  selection.removeAllRanges();
  selection.addRange(range);
  updateIntentEmptyState();
}

function makeAnnotationChip(ann, image) {
  const chip = document.createElement("span");
  chip.className = "annotation-inline";
  chip.contentEditable = "false";
  chip.dataset.annotationId = String(ann.id);
  chip.dataset.imageId = ann.imageId;
  chip.dataset.token = ann.token;
  chip.style.borderColor = ann.color;
  chip.style.background = `linear-gradient(135deg, ${rgba(ann.color, 0.15)}, #ffffff 62%)`;
  chip.style.boxShadow = `0 8px 18px ${rgba(ann.color, 0.18)}`;

  const thumb = document.createElement("span");
  thumb.className = "annotation-inline-thumb";
  thumb.style.borderColor = ann.color;
  if (ann.previewUrl) {
    const img = document.createElement("img");
    img.src = ann.previewUrl;
    img.alt = ann.type;
    thumb.appendChild(img);
  }

  const body = document.createElement("span");
  body.className = "annotation-inline-body";
  const title = document.createElement("span");
  title.className = "annotation-inline-title";
  title.innerHTML = `<i style="background:${ann.color}"></i>${escapeHtml(image.label)} ${ann.type === "point" ? "点击" : "框选"} #${ann.id}`;
  const token = document.createElement("code");
  token.textContent = ann.token;
  body.appendChild(title);
  body.appendChild(token);

  chip.appendChild(thumb);
  chip.appendChild(body);
  return chip;
}

function appendAnnotationChip(ann, image) {
  insertNodeIntoPrompt(makeAnnotationChip(ann, image));
}

function removePromptAnnotation(ann) {
  if (!ann) return;
  intentInput.querySelectorAll(".annotation-inline").forEach((chip) => {
    if (Number(chip.dataset.annotationId) === ann.id || chip.dataset.token === ann.token) {
      chip.remove();
    }
  });
  updateIntentEmptyState();
}

function deleteAnnotation(annotationId) {
  const ann = state.annotations.find((item) => item.id === annotationId);
  if (!ann) return;
  removePromptAnnotation(ann);
  state.annotations = state.annotations.filter((item) => item.id !== annotationId);
  renderImages();
  setStatus(`已删除标注 #${ann.id}，并同步清理聊天框。`);
}

function selectImage(id) {
  state.selectedId = id;
  renderImages();
}

function renderImages() {
  world.innerHTML = "";
  for (const image of state.images) {
    const node = document.createElement("div");
    node.className = `canvas-image${image.id === state.selectedId ? " selected" : ""}`;
    node.style.left = `${image.x}px`;
    node.style.top = `${image.y}px`;
    node.style.width = `${image.width}px`;
    node.style.height = `${image.height}px`;
    node.dataset.id = image.id;

    const img = document.createElement("img");
    img.src = image.dataUrl;
    img.alt = image.name;
    node.appendChild(img);

    const label = document.createElement("div");
    label.className = "image-label";
    label.textContent = image.label;
    node.appendChild(label);
    world.appendChild(node);
  }

  for (const ann of state.annotations) {
    const image = state.images.find((item) => item.id === ann.imageId);
    if (!image) continue;
    const marker = document.createElement("div");
    marker.dataset.annotationId = String(ann.id);
    if (ann.type === "point") {
      marker.className = "marker";
      marker.style.left = `${image.x + (ann.x / 1000) * image.width}px`;
      marker.style.top = `${image.y + (ann.y / 1000) * image.height}px`;
      marker.style.borderColor = ann.color;
      marker.style.background = rgba(ann.color, 0.22);
      marker.style.boxShadow = `0 0 0 5px ${rgba(ann.color, 0.12)}`;
    } else {
      marker.className = "box-marker";
      marker.style.left = `${image.x + (ann.x1 / 1000) * image.width}px`;
      marker.style.top = `${image.y + (ann.y1 / 1000) * image.height}px`;
      marker.style.width = `${((ann.x2 - ann.x1) / 1000) * image.width}px`;
      marker.style.height = `${((ann.y2 - ann.y1) / 1000) * image.height}px`;
      marker.style.borderColor = ann.color;
      marker.style.background = rgba(ann.color, 0.12);
      marker.style.boxShadow = `0 0 0 4px ${rgba(ann.color, 0.1)}`;
    }
    marker.title =
      ann.type === "point"
        ? `${image.label}<point>${ann.x} ${ann.y}</point>`
        : `${image.label}<bbox>${ann.x1} ${ann.y1} ${ann.x2} ${ann.y2}</bbox>`;
    const deleteBtn = document.createElement("button");
    deleteBtn.type = "button";
    deleteBtn.className = "marker-delete";
    deleteBtn.title = "删除此标注";
    deleteBtn.textContent = "×";
    deleteBtn.addEventListener("pointerdown", (event) => {
      event.preventDefault();
      event.stopPropagation();
    });
    deleteBtn.addEventListener("click", (event) => {
      event.preventDefault();
      event.stopPropagation();
      deleteAnnotation(ann.id);
    });
    marker.appendChild(deleteBtn);
    world.appendChild(marker);
  }

  renderImageList();
  renderAnnotationPreview();
}

function renderImageList() {
  imageList.innerHTML = "";
  if (!state.images.length) {
    imageList.textContent = "暂无图片。";
    return;
  }
  for (const image of state.images) {
    const item = document.createElement("div");
    item.className = "image-item";
    const meta = document.createElement("div");
    meta.className = "image-item-meta";
    meta.innerHTML = `<b>${escapeHtml(image.label)}</b><span>${escapeHtml(image.name)} (${image.naturalWidth}x${image.naturalHeight})</span>`;

    const actions = document.createElement("div");
    actions.className = "image-item-actions";
    const focusBtn = document.createElement("button");
    focusBtn.type = "button";
    focusBtn.textContent = "定位";
    focusBtn.addEventListener("click", () => focusImage(image));
    const deleteBtn = document.createElement("button");
    deleteBtn.type = "button";
    deleteBtn.className = "danger";
    deleteBtn.textContent = "删除";
    deleteBtn.addEventListener("click", () => deleteImage(image.id));

    actions.appendChild(focusBtn);
    actions.appendChild(deleteBtn);
    item.appendChild(meta);
    item.appendChild(actions);
    imageList.appendChild(item);
  }
}

function focusImage(image) {
  state.selectedId = image.id;
  const rect = viewport.getBoundingClientRect();
  state.view.x = rect.width / 2 - (image.x + image.width / 2) * state.view.scale;
  state.view.y = rect.height / 2 - (image.y + image.height / 2) * state.view.scale;
  applyView();
  renderImages();
  setStatus(`已定位到 ${image.label}。`);
}

function deleteImage(imageId) {
  const image = state.images.find((item) => item.id === imageId);
  if (!image) return;

  const removedAnnotations = state.annotations.filter((ann) => ann.imageId === imageId);
  for (const ann of removedAnnotations) {
    removePromptAnnotation(ann);
  }

  state.annotations = state.annotations.filter((ann) => ann.imageId !== imageId);
  state.images = state.images.filter((item) => item.id !== imageId);
  if (state.selectedId === imageId) {
    state.selectedId = state.images.at(-1)?.id || null;
  }
  renderImages();
  setStatus(`已删除 ${image.label}，并清理了相关标注。`);
}

function isTypingTarget(target) {
  return (
    target instanceof HTMLElement &&
    (target.isContentEditable ||
      target.tagName === "INPUT" ||
      target.tagName === "TEXTAREA" ||
      target.tagName === "SELECT")
  );
}

function startPanning(event) {
  state.pan = {
    clientX: event.clientX,
    clientY: event.clientY,
    viewX: state.view.x,
    viewY: state.view.y,
  };
  viewport.classList.add("dragging");
  viewport.setPointerCapture(event.pointerId);
}

function shouldPanCanvas(event) {
  return event.button === 1 || event.button === 2 || state.isSpacePressed;
}

function renderAnnotationPreview() {
  annotationPreview.innerHTML = "";
  annotationPreview.classList.toggle("empty", state.annotations.length === 0);
  if (!state.annotations.length) {
    annotationPreview.textContent = "暂无点选/框选预览。";
    return;
  }

  for (const ann of state.annotations) {
    const image = state.images.find((item) => item.id === ann.imageId);
    if (!image) continue;

    const card = document.createElement("div");
    card.className = "annotation-card";
    card.style.borderColor = ann.color;
    card.style.background = `linear-gradient(135deg, ${rgba(ann.color, 0.12)}, #ffffff 52%)`;

    const thumb = document.createElement("div");
    thumb.className = "annotation-thumb";
    thumb.style.borderColor = ann.color;
    thumb.style.boxShadow = `0 8px 20px ${rgba(ann.color, 0.22)}`;
    if (ann.previewUrl) {
      const img = document.createElement("img");
      img.src = ann.previewUrl;
      img.alt = ann.type;
      thumb.appendChild(img);
    }

    const info = document.createElement("div");
    info.className = "annotation-info";
    const title = document.createElement("div");
    title.className = "annotation-title";
    title.innerHTML = `<span style="background:${ann.color}"></span>${escapeHtml(image.label)} ${ann.type === "point" ? "点击" : "框选"} #${ann.id}`;
    const token = document.createElement("code");
    token.textContent =
      ann.token ||
      (ann.type === "point"
        ? `${image.label}<point>${ann.x} ${ann.y}</point>`
        : `${image.label}<bbox>${ann.x1} ${ann.y1} ${ann.x2} ${ann.y2}</bbox>`);
    info.appendChild(title);
    info.appendChild(token);

    const actions = document.createElement("div");
    actions.className = "annotation-actions";
    const deleteBtn = document.createElement("button");
    deleteBtn.type = "button";
    deleteBtn.className = "danger";
    deleteBtn.textContent = "删除标注";
    deleteBtn.addEventListener("click", () => deleteAnnotation(ann.id));
    actions.appendChild(deleteBtn);

    card.appendChild(thumb);
    card.appendChild(info);
    card.appendChild(actions);
    annotationPreview.appendChild(card);
  }
}

function setMode(mode) {
  state.mode = mode;
  document.querySelectorAll(".tool").forEach((btn) => {
    btn.classList.toggle("active", btn.dataset.mode === mode);
  });
  setStatus(
    mode === "normal"
      ? "普通模式：拖动图片，拖空白平移画布。"
      : mode === "point"
        ? "点击模式：点击图片位置会追加 <point>。"
        : "框选模式：在图片上拖框会追加 <bbox>。"
  );
}

function addImageFromFile(file, dataUrl, label, pos) {
  return new Promise((resolve) => {
    const probe = new Image();
    probe.onload = () => {
      const maxSide = 360;
      const ratio = Math.min(1, maxSide / Math.max(probe.naturalWidth, probe.naturalHeight));
      const id = `img-${state.nextId}`;
      const image = {
        id,
        label: label || `图${state.nextId}`,
        name: file.name,
        dataUrl,
        element: probe,
        naturalWidth: probe.naturalWidth,
        naturalHeight: probe.naturalHeight,
        x: pos?.x ?? (80 + (state.nextId - 1) * 40),
        y: pos?.y ?? (80 + (state.nextId - 1) * 40),
        width: pos?.width ?? Math.round(probe.naturalWidth * ratio),
        height: pos?.height ?? Math.round(probe.naturalHeight * ratio),
      };
      state.nextId += 1;
      state.images.push(image);
      selectImage(id);
      setStatus(`已上传 ${image.label}，可拖拽或点选/框选。`);
      resolve(image);
    };
    probe.src = dataUrl;
  });
}

function addFiles(files) {
  for (const file of files) {
    if (!file.type.startsWith("image/")) continue;
    const reader = new FileReader();
    reader.onload = () => addImageFromFile(file, reader.result);
    reader.readAsDataURL(file);
  }
}

fileInput.addEventListener("change", () => {
  addFiles([...fileInput.files]);
  fileInput.value = "";
});

function hasImageFiles(dataTransfer) {
  const items = [...(dataTransfer?.items || [])];
  if (items.length) {
    return items.some((item) => item.kind === "file" && item.type.startsWith("image/"));
  }
  return [...(dataTransfer?.files || [])].some((file) => file.type.startsWith("image/"));
}

viewport.addEventListener("dragenter", (event) => {
  if (!hasImageFiles(event.dataTransfer)) return;
  event.preventDefault();
  state.dragDepth += 1;
  viewport.classList.add("drop-active");
});

viewport.addEventListener("dragover", (event) => {
  if (!hasImageFiles(event.dataTransfer)) return;
  event.preventDefault();
  event.dataTransfer.dropEffect = "copy";
});

viewport.addEventListener("dragleave", (event) => {
  if (!hasImageFiles(event.dataTransfer)) return;
  state.dragDepth = Math.max(0, state.dragDepth - 1);
  if (state.dragDepth === 0) {
    viewport.classList.remove("drop-active");
  }
});

viewport.addEventListener("drop", (event) => {
  if (!hasImageFiles(event.dataTransfer)) return;
  event.preventDefault();
  state.dragDepth = 0;
  viewport.classList.remove("drop-active");
  const files = [...event.dataTransfer.files].filter((file) => file.type.startsWith("image/"));
  addFiles(files);
  setStatus(`正在读取 ${files.length} 张拖拽图片...`);
});

document.querySelectorAll(".tool").forEach((btn) => {
  btn.addEventListener("click", () => setMode(btn.dataset.mode));
});

intentInput.addEventListener("input", syncAnnotationsFromPrompt);

document.addEventListener("keydown", (event) => {
  if (event.code === "Space" && !isTypingTarget(event.target)) {
    event.preventDefault();
    state.isSpacePressed = true;
    viewport.classList.add("pan-ready");
    return;
  }

  if (event.key !== "Delete" && event.key !== "Backspace") return;
  if (isTypingTarget(event.target)) return;
  if (!state.selectedId) return;

  event.preventDefault();
  deleteImage(state.selectedId);
});

document.addEventListener("keyup", (event) => {
  if (event.code !== "Space") return;
  state.isSpacePressed = false;
  viewport.classList.remove("pan-ready");
});

viewport.addEventListener("contextmenu", (event) => {
  event.preventDefault();
});

viewport.addEventListener("wheel", (event) => {
  event.preventDefault();
  const before = clientToWorld(event.clientX, event.clientY);
  const factor = event.deltaY < 0 ? 1.08 : 0.92;
  state.view.scale = Math.max(0.12, Math.min(4, state.view.scale * factor));

  const rect = viewport.getBoundingClientRect();
  state.view.x = event.clientX - rect.left - before.x * state.view.scale;
  state.view.y = event.clientY - rect.top - before.y * state.view.scale;
  applyView();
});

viewport.addEventListener("pointerdown", (event) => {
  const worldPoint = clientToWorld(event.clientX, event.clientY);
  const image = imageAt(worldPoint);

  if (image) selectImage(image.id);

  if (shouldPanCanvas(event)) {
    event.preventDefault();
    startPanning(event);
    return;
  }

  if (!image && event.button === 0) {
    event.preventDefault();
    startPanning(event);
    return;
  }

  if (state.mode === "normal" && image) {
    state.drag = {
      imageId: image.id,
      startX: worldPoint.x,
      startY: worldPoint.y,
      imageX: image.x,
      imageY: image.y,
    };
    viewport.setPointerCapture(event.pointerId);
    return;
  }

  if (state.mode === "point" && image) {
    const p = normalizedPoint(worldPoint, image);
    const ann = buildAnnotation("point", image, { x: p.x, y: p.y });
    ann.token = `${image.label}<point>${p.x} ${p.y}</point>`;
    state.annotations.push(ann);
    appendAnnotationChip(ann, image);
    renderImages();
    setStatus(`已添加 ${ann.token}`);
    return;
  }

  if (state.mode === "bbox" && image) {
    const selection = document.createElement("div");
    selection.className = "selection-box";
    const color = colorForAnnotation(state.nextAnnotationId);
    selection.style.borderColor = color;
    selection.style.background = rgba(color, 0.14);
    selection.style.boxShadow = `0 0 0 4px ${rgba(color, 0.1)}`;
    viewport.appendChild(selection);
    state.box = {
      imageId: image.id,
      start: worldPoint,
      current: worldPoint,
      selection,
    };
    viewport.setPointerCapture(event.pointerId);
  }
});

viewport.addEventListener("pointermove", (event) => {
  const worldPoint = clientToWorld(event.clientX, event.clientY);

  if (state.drag) {
    const image = state.images.find((item) => item.id === state.drag.imageId);
    if (!image) return;
    image.x = state.drag.imageX + worldPoint.x - state.drag.startX;
    image.y = state.drag.imageY + worldPoint.y - state.drag.startY;
    renderImages();
    return;
  }

  if (state.pan) {
    state.view.x = state.pan.viewX + event.clientX - state.pan.clientX;
    state.view.y = state.pan.viewY + event.clientY - state.pan.clientY;
    applyView();
    return;
  }

  if (state.box) {
    state.box.current = worldPoint;
    const a = worldToClient(state.box.start.x, state.box.start.y);
    const b = worldToClient(worldPoint.x, worldPoint.y);
    state.box.selection.style.left = `${Math.min(a.x, b.x) - viewport.getBoundingClientRect().left}px`;
    state.box.selection.style.top = `${Math.min(a.y, b.y) - viewport.getBoundingClientRect().top}px`;
    state.box.selection.style.width = `${Math.abs(a.x - b.x)}px`;
    state.box.selection.style.height = `${Math.abs(a.y - b.y)}px`;
  }
});

viewport.addEventListener("pointerup", (event) => {
  if (state.drag) {
    state.drag = null;
    viewport.releasePointerCapture(event.pointerId);
  }
  if (state.pan) {
    state.pan = null;
    viewport.classList.remove("dragging");
    viewport.releasePointerCapture(event.pointerId);
  }
  if (state.box) {
    const image = state.images.find((item) => item.id === state.box.imageId);
    const dx = Math.abs(state.box.current.x - state.box.start.x);
    const dy = Math.abs(state.box.current.y - state.box.start.y);
    state.box.selection.remove();
    if (image && dx > 4 && dy > 4) {
      const b = normalizedBox(state.box.start, state.box.current, image);
      const ann = buildAnnotation("bbox", image, b);
      ann.token = `${image.label}<bbox>${b.x1} ${b.y1} ${b.x2} ${b.y2}</bbox>`;
      state.annotations.push(ann);
      appendAnnotationChip(ann, image);
      setStatus(`已添加 ${ann.token}`);
    }
    state.box = null;
    viewport.releasePointerCapture(event.pointerId);
    renderImages();
  }
});

clearPromptBtn.addEventListener("click", () => {
  intentInput.innerHTML = "";
  state.annotations = [];
  state.nextAnnotationId = 1;
  renderImages();
  updateIntentEmptyState();
  setStatus("已清空指令和标注。");
});

function annotationTokenForLabel(ann, label) {
  if (ann.type === "point") {
    return `${label}<point>${ann.x} ${ann.y}</point>`;
  }
  return `${label}<bbox>${ann.x1} ${ann.y1} ${ann.x2} ${ann.y2}</bbox>`;
}

function buildModelInputFromPrompt() {
  const assignedImages = new Map();
  const inputImages = [];

  function assignImage(image) {
    if (!image) return "";
    if (!assignedImages.has(image.id)) {
      const inputLabel = `图${inputImages.length + 1}`;
      assignedImages.set(image.id, inputLabel);
      inputImages.push({ ...image, inputLabel });
    }
    return assignedImages.get(image.id);
  }

  function remapImageLabels(text) {
    return text.replace(/图\d+/g, (label) => {
      const image = state.images.find((item) => item.label === label);
      return image ? assignImage(image) : label;
    });
  }

  function walk(node) {
    if (node.nodeType === Node.TEXT_NODE) {
      return remapImageLabels(node.textContent || "");
    }
    if (node.nodeType !== Node.ELEMENT_NODE) {
      return "";
    }
    if (node.classList?.contains("annotation-inline")) {
      const ann = state.annotations.find((item) => item.id === Number(node.dataset.annotationId));
      const image = ann ? state.images.find((item) => item.id === ann.imageId) : null;
      const inputLabel = assignImage(image);
      if (!ann || !inputLabel) return "";
      return ` ${annotationTokenForLabel(ann, inputLabel)} `;
    }
    if (node.tagName === "BR") {
      return "\n";
    }
    return [...node.childNodes].map(walk).join("");
  }

  const prompt = walk(intentInput)
    .replace(/\u00a0/g, " ")
    .replace(/[ \t]{2,}/g, " ")
    .replace(/\n{3,}/g, "\n\n")
    .trim();

  return { prompt, images: inputImages };
}

async function saveSession() {
  if (!state.images.length) {
    setStatus("请先上传至少一张图片。", true);
    return;
  }
  const prompt = getEditorIntent();
  if (!prompt) {
    setStatus("请输入编辑意图，或先用点击/框选模式生成 grounding。", true);
    return;
  }

  saveBtn.disabled = true;
  updateSaveStatus("正在保存...");

  const modelInput = buildModelInputFromPrompt();
  const userIntent = getEditorIntent();

  // 保存时发送所有图片（保持原始标签和位置），新图片追加到 session，已有图片不丢失
  const allImages = state.images.map((image) => ({
    inputLabel: image.label,
    name: image.name,
    dataUrl: image.dataUrl,
    naturalWidth: image.naturalWidth,
    naturalHeight: image.naturalHeight,
    x: image.x,
    y: image.y,
    width: image.width,
    height: image.height,
  }));

  // 发送标注数据（直接使用前端状态，避免后端重新解析导致 ID 不一致）
  const annotationsData = state.annotations.map((ann) => {
    const image = state.images.find((item) => item.id === ann.imageId);
    return {
      id: ann.id,
      type: ann.type,
      image_label: image ? image.label : "",
      normalized_coords: ann.type === "point"
        ? [ann.x, ann.y]
        : [ann.x1, ann.y1, ann.x2, ann.y2],
      token: ann.token,
    };
  });

  try {
    // 保存时使用原始标签的 prompt（与 images 标签一致），modelInput.prompt 仅用于生成 API
    const resp = await fetch("/api/save", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        prompt: userIntent,
        user_intent: userIntent,
        intent_html: intentInput.innerHTML,
        images: allImages,
        annotations: annotationsData,
      }),
    });

    const data = await resp.json().catch(() => ({}));
    if (!resp.ok) {
      throw new Error(data.error || `HTTP ${resp.status}`);
    }
    updateSaveStatus("保存成功！");
    setStatus("编辑意图和图片已保存。");
  } catch (err) {
    console.error(err);
    updateSaveStatus(`保存失败：${err.message}`, true);
    setStatus(`保存失败：${err.message}`, true);
  } finally {
    saveBtn.disabled = false;
  }
}

saveBtn.addEventListener("click", saveSession);

async function loadSessionInfo() {
  try {
    const resp = await fetch("/api/session-info");
    if (!resp.ok) return;
    const data = await resp.json().catch(() => ({}));
    // 先加载所有图片（等待图片加载完成，确保 state.images 已就绪，同时恢复位置）
    const loadPromises = [];
    if (data.images && Array.isArray(data.images)) {
      for (const imgData of data.images) {
        loadPromises.push(
          addImageFromFile(
            { name: imgData.name || "preloaded.png", type: "image/png" },
            imgData.dataUrl,
            imgData.inputLabel || undefined,
            { x: imgData.x, y: imgData.y, width: imgData.width, height: imgData.height }
          )
        );
      }
    }
    await Promise.all(loadPromises);

    // 恢复已保存的标注（此时 images 已就绪，可正确匹配 label）
    if (data.annotations && Array.isArray(data.annotations)) {
      for (const annData of data.annotations) {
        const image = state.images.find((item) => item.label === annData.image_label);
        if (!image) continue;
        const color = colorForAnnotation(annData.id);
        const coords = annData.normalized_coords;
        let ann;
        if (annData.type === "point") {
          ann = {
            id: annData.id,
            type: "point",
            imageId: image.id,
            color,
            x: coords[0],
            y: coords[1],
            token: annData.token,
            previewUrl: makePointPreview(image, { x: coords[0], y: coords[1], color }),
          };
        } else {
          ann = {
            id: annData.id,
            type: "bbox",
            imageId: image.id,
            color,
            x1: coords[0],
            y1: coords[1],
            x2: coords[2],
            y2: coords[3],
            token: annData.token,
            previewUrl: makeBoxPreview(image, { x1: coords[0], y1: coords[1], x2: coords[2], y2: coords[3], color }),
          };
        }
        state.annotations.push(ann);
        if (annData.id >= state.nextAnnotationId) {
          state.nextAnnotationId = annData.id + 1;
        }
      }
    }
    // 恢复已保存的编辑意图（完整 HTML，含标注 chips）
    if (data.intent_html) {
      intentInput.innerHTML = data.intent_html;
      updateIntentEmptyState();
      // 重新扫描 annotations 状态
      syncAnnotationsFromPrompt();
    }
    if (data.status === "saved") {
      updateSaveStatus("上次已保存");
    }
    renderImages();
  } catch (err) {
    console.warn("加载 session 信息失败:", err);
  }
}

function escapeHtml(text) {
  const div = document.createElement("div");
  div.textContent = text;
  return div.innerHTML;
}

applyView();
renderImages();
setMode("normal");
updateIntentEmptyState();
loadSessionInfo();