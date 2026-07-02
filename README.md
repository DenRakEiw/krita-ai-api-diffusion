# Krita AI API Diffusion

<img width="1898" height="1001" alt="krita" src="https://github.com/user-attachments/assets/47345a31-6931-4fdb-9188-fe9e2f5c61cb" />


A Krita plugin that brings the **FLUX** models from
[Black Forest Labs (BFL)](https://bfl.ai) **and Google's Nano Banana 2**
([Gemini image models](https://ai.google.dev)) directly into Krita — for
text-to-image, context-based inpainting and mask-based inpainting, with an
optional reference image. The interface is **multilingual**
(English / Deutsch / 中文 / ไทย).

## Features

- **Two providers side by side** — pick a **BFL FLUX** model or a
  **Google Nano Banana 2** model from the same dropdown; the plugin routes to
  the right API automatically.
- **New image (text → image)** — generate an image from a prompt.
- **Context Inpaint** — edits the current selection context-based
  (FLUX.2 `input_image` or Gemini image editing, no mask needed). Great for
  instructions like “remove the person” or “replace the sky”.
- **Mask Inpaint (FLUX.1 Fill)** — precise filling exactly inside the selection
  via `image` + `mask` (`flux-pro-1.0-fill`). FLUX only.
- **Reference image (optional)** — an additional image used as a template, e.g.
  a specific pair of sunglasses that a selected cat should wear.
- **Multilingual UI** — switch language at runtime under *Options*.
- Adaptive crop with context padding, feathered mask edges (no visible seams),
  correct color handling and readable error messages.

## Requirements

- **Krita 5.x** (includes Python/PyQt5 in the official builds).
- For FLUX: a **BFL API key** from <https://api.bfl.ai> (the BFL dashboard).
- For Nano Banana 2: a **Google AI Studio API key** from
  <https://aistudio.google.com/apikey>.
- You only need the key(s) for the provider(s) you actually use. Both are paid
  / metered services.

## Installation

### Option A — manual (recommended)

1. Download or clone the repository:
   ```bash
   git clone https://github.com/DenRakEiw/krita-ai-api-diffusion.git
   ```
2. Copy the `ai_api_diffusion` folder **and** the `ai_api_diffusion.desktop`
   file into Krita’s `pykrita` directory:

   | OS | Path |
   |----|------|
   | Windows | `%APPDATA%\krita\pykrita\` |
   | Linux   | `~/.local/share/krita/pykrita/` |
   | macOS   | `~/Library/Application Support/krita/pykrita/` |

   The result should look like this:
   ```
   pykrita/
   ├── ai_api_diffusion.desktop
   └── ai_api_diffusion/
       ├── __init__.py
       └── ai_api_diffusion_docker.py
   ```

   > If the `.desktop` file is missing, create it with this content:
   > ```ini
   > [Desktop Entry]
   > Type=Service
   > ServiceTypes=Krita/PythonPlugin
   > X-KDE-Library=ai_api_diffusion
   > X-Python-2-Compatible=false
   > Name=Krita AI API Diffusion
   > Comment=Plugin for Flux (BFL)
   > ```

3. **Start Krita.**
4. Open **Settings → Configure Krita → Python Plugin Manager**, enable
   **Krita AI API Diffusion**, then restart Krita.
5. Show the docker via **Settings → Dockers → Krita AI API Diffusion**.

### Option B — clone directly into pykrita

```bash
cd <pykrita-directory>
git clone https://github.com/DenRakEiw/krita-ai-api-diffusion.git ai_api_diffusion
```
Then copy the `.desktop` file one level up (into `pykrita/`) as shown above and
continue with steps 3–5.

## Setup

1. In the docker, switch to the **Options** tab.
2. Pick your **Language** (English / Deutsch / 中文 / ไทย) — applied instantly.
3. Enter your **API Key (BFL)** and click **Save**.
   (The key and language are stored in Krita’s settings.)

## Usage

### New image
1. **Generate** tab, choose a model (e.g. `flux-2-pro`).
2. Enter a prompt; optionally set width/height under **Options**.
3. Click **New image (text → image)** — the result is added as a new layer.

### Context Inpaint (FLUX.2)
1. Select the area to change with a selection tool.
2. Enter an edit instruction as the prompt, e.g. “remove the object”.
3. Click **Context Inpaint (FLUX.2)**.
4. Only the selected area is replaced (softly blended in).

### Mask Inpaint (FLUX.1 Fill)
1. Select an area (min. ~256 px — small selections are upscaled).
2. Optionally enter a prompt.
3. Click **Mask Inpaint (FLUX.1 Fill)** — precise filling inside the mask.

### With a reference image (example: sunglasses on a cat)
1. Select the head/eye area of the cat.
2. Click **Choose reference image …** and load the sunglasses image.
3. Choose model `flux-2-pro` or `flux-2-max` (they support multi-image).
4. Prompt: *“the cat is wearing these sunglasses”*.
5. Click **Context Inpaint (FLUX.2)**.

## Models

| Selection | Endpoint | Use |
|-----------|----------|-----|
| `flux-2-pro` | `flux-2-pro` | Default, good quality, multi-image |
| `flux-2-max` | `flux-2-max` | Highest quality, multi-image |
| `flux-2-flex` | `flux-2-flex` | Strong at typography/text |
| `flux-2-klein-9b` | `flux-2-klein-9b` | Fast, lightweight (no reference image) |
| Mask Inpaint | `flux-pro-1.0-fill` | Mask-based filling |

## Tips & troubleshooting

- **HTTP 422 “Image dimensions must be at least 256x256”** — selection too small.
  It is upscaled automatically; still, select a larger area for sharp results.
- **HTTP 402 / “insufficient credits”** — no credits on the BFL account.
- **HTTP 401 / 403** — API key wrong or not set (Options tab).
- **Payload too large / timeout** with reference images — lower `MAX_EDGE` in
  `ai_api_diffusion_docker.py` or shrink the reference image beforehand.
- Error messages appear in the status field at the bottom and as a dialog
  (truncated).

## Notes

- BFL result URLs are short-lived; the plugin downloads the images immediately.
- The reference image is only used with FLUX.2 (context inpaint / generation),
  **not** with FLUX.1 Fill.

## License

Use at your own risk. The FLUX models are subject to Black Forest Labs’ terms of
use and pricing.
