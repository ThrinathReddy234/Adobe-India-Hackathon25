# Adobe Hackathon - Challenge 1A: Document Outline Extractor

This project is a submission for **Challenge 1A** of the _"Connecting the Dots"_ hackathon conducted by Adobe. It presents a containerized solution that automatically extracts a structured outline—including **Title**, **H1**, **H2**, and **H3**—from any given PDF document.

---

## Approach

This solution emphasizes **efficiency**, **accuracy**, and **performance compliance** with hackathon constraints.

### Single-Pass PDF Processing
- Parses the PDF in **one pass** to satisfy the **≤10 seconds** execution limit.
- Extracts all text blocks along with their **font size, font weight, position**, and **font profile frequencies**.

### Hybrid Heuristic Logic
- **Body Text Identification**: Dominant font style is assumed to represent body text.
- **Title Detection**: The largest font near the top of the first page is considered the document title.
- **Heading Recognition**:
  - Uses **numbering patterns** (e.g., `1.`, `2.1`, etc.) to detect structured headings.
  - Applies **visual cues** such as larger or bolder fonts to infer heading hierarchy (H1, H2, H3) when patterns are missing.

---

## Tech Stack

| Component     | Description                                                   |
|---------------|---------------------------------------------------------------|
| **Python 3.10** | Core language for all scripts                                 |
| **PyMuPDF**    | Lightweight and efficient PDF parser used for layout analysis |
| **Docker**     | Containerizes the app for portability and environment control |

- No external machine learning models required.
- Entire solution is under **200MB**, meeting model size constraints.

---

## Build & Run Instructions

### Build the Docker Image

From the root project directory (`Challenge_1a/`), run:

```bash
docker build --platform linux/amd64 -t pdf-extractor:latest .