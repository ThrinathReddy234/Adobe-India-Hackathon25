import fitz
import json
import os
import re
from collections import Counter, defaultdict
from pathlib import Path

INPUT_DIR = Path("/app/input")
OUTPUT_DIR = Path("/app/output")

class PdfProcessor:
    def __init__(self, pdf_path):
        self.pdf_path = pdf_path
        self.doc = fitz.open(pdf_path)
        self.title = ""
        self.outline = []
        self.font_styles = defaultdict(int)
        self._profile_document()

    def _profile_document(self):
        for page in self.doc:
            blocks = page.get_text("dict", sort=True)["blocks"]
            for block in blocks:
                if "lines" in block:
                    for line in block["lines"]:
                        if "spans" in line and line["spans"]:
                            size = round(line["spans"][0]["size"])
                            bold = "bold" in line["spans"][0]["font"].lower()
                            self.font_styles[(size, bold)] += 1
        
        if self.font_styles:
            sorted_styles = sorted(self.font_styles.items(), key=lambda item: item[1], reverse=True)
            self.body_text_style = sorted_styles[0][0]
        else:
            self.body_text_style = (12, False)

    def extract_title_and_headings(self):
        if len(self.doc) == 1:
            self._process_single_page_doc()
        else:
            self._process_multi_page_doc()

    def _process_single_page_doc(self):
        page = self.doc[0]
        blocks = page.get_text("dict", sort=True)["blocks"]
        page_width = page.rect.width
        body_size = self.body_text_style[0]
        
        is_poster_like = len(blocks) < 25

        candidates = []
        for block in blocks:
            if "lines" in block:
                for line in block["lines"]:
                    if "spans" in line and line["spans"]:
                        text = "".join(s["text"] for s in line["spans"]).strip()
                        if text:
                            size = round(line["spans"][0]["size"])
                            h_center = (block['bbox'][0] + block['bbox'][2]) / 2
                            is_centered = abs(h_center - page_width / 2) < page_width * 0.20
                            candidates.append({"text": text, "size": size, "y": block["bbox"][1], "centered": is_centered})
        
        if not candidates: return
        
        candidates.sort(key=lambda x: x["y"])
        
        if is_poster_like:
            self.title = ""
            candidates.sort(key=lambda x: x["size"], reverse=True)
            heading_candidates = [c for c in candidates if "www." not in c["text"].lower() and ".com" not in c["text"].lower()]
            if heading_candidates:
                self.outline.append({"level": "H1", "text": heading_candidates[0]["text"], "page": 0})
        else:
            if candidates:
                self.title = candidates[0]["text"]
            
            heading_candidates = [
                c for c in candidates 
                if c["size"] > body_size and c["centered"] and c["text"].lower() != self.title.lower()
            ]
            if heading_candidates:
                heading_candidates.sort(key=lambda x: x["size"], reverse=True)
                self.outline.append({"level": "H1", "text": heading_candidates[0]["text"], "page": 0})

    def _is_toc_page(self, page):
        toc_text = page.get_text().lower()
        if "table of contents" in toc_text:
            lines = toc_text.split('\n')
            toc_lines = [line for line in lines if re.search(r'\d+\s*$', line)]
            if len(toc_lines) > 5:
                return True
        return False

    def _process_multi_page_doc(self):
        first_page_blocks = self.doc[0].get_text("dict", sort=True)["blocks"]
        max_font_size = 0
        title_candidates = []
        if first_page_blocks:
            for block in first_page_blocks:
                if "lines" in block:
                    for line in block["lines"]:
                        if "spans" in line and line["spans"]:
                           max_font_size = max(max_font_size, round(line["spans"][0]["size"]))
            
            seen_titles = set()
            for block in first_page_blocks:
                if "lines" in block:
                    for line in block["lines"]:
                        if "spans" in line and line["spans"] and round(line["spans"][0]["size"]) >= max_font_size * 0.95:
                            line_text = "".join(span["text"] for span in line["spans"]).strip()
                            if line_text and line_text not in seen_titles:
                                title_candidates.append((block["bbox"][1], line_text))
                                seen_titles.add(line_text)
        
        title_candidates.sort(key=lambda x: x[0])
        self.title = " ".join(item[1] for item in title_candidates)

        candidates = []
        body_size, body_bold = self.body_text_style
        for page_num, page in enumerate(self.doc):
            if page_num == 0 or self._is_toc_page(page): 
                continue

            page_height = page.rect.height
            margin_y = page_height * 0.10
            
            blocks = page.get_text("dict", sort=True)["blocks"]
            for block in blocks:
                if "lines" in block and margin_y < block["bbox"][1] < (page_height - margin_y):
                    line_text = "".join(span["text"] for line in block["lines"] for span in line["spans"]).strip()
                    if not line_text: continue

                    span = block["lines"][0]["spans"][0]
                    f_size, f_bold = round(span["size"]), "bold" in span["font"].lower()
                    
                    is_heading_style = (f_size > body_size) or (f_bold and not body_bold)
                    is_table_header = "version date remarks" in line_text.lower()
                    
                    if is_heading_style and not is_table_header and line_text.lower() not in self.title.lower():
                        candidates.append({
                            "text": line_text, "style": (f_size, f_bold), "page": page_num, "y": block["bbox"][1]
                        })
        
        style_map = {}
        for cand in candidates:
            text = cand["text"]
            if re.match(r"^\d\.\d", text):
                if "H2" not in style_map: style_map["H2"] = cand["style"]
            elif re.match(r"^\d\.", text):
                if "H1" not in style_map: style_map["H1"] = cand["style"]

        if not style_map:
            heading_styles = sorted(list(set(c["style"] for c in candidates)), key=lambda s: s[0], reverse=True)
            for i, style in enumerate(heading_styles[:3]):
                style_map[f"H{i+1}"] = style

        level_map = {style: level for level, style in style_map.items()}

        for cand in candidates:
            level = None
            text, style = cand["text"], cand["style"]
            
            if re.match(r"^\d\.\d\.\d", text): level = "H3"
            elif re.match(r"^\d\.\d", text): level = "H2"
            elif re.match(r"^\d\.", text): level = "H1"
            elif style in level_map: level = level_map[style]
            
            if level:
                self.outline.append({
                    "level": level, "text": text, "page": cand["page"], "y": cand["y"]
                })

    def process(self):
        self.extract_title_and_headings()
        self.outline.sort(key=lambda x: (x.get("page", 0), x.get("y", 0)))
        
        final_outline = []
        if self.outline:
            current_heading = self.outline[0]
            for i in range(1, len(self.outline)):
                next_heading = self.outline[i]
                if (next_heading["page"] == current_heading["page"] and
                    re.match(r"^\d\.", current_heading["text"]) and not re.match(r"^\d\.", next_heading["text"])):
                     current_heading["text"] += next_heading["text"]
                else:
                    final_outline.append(current_heading)
                    current_heading = next_heading
            final_outline.append(current_heading)

            seen_text = set()
            deduped_outline = []
            for item in final_outline:
                text_key = item["text"].strip()
                if text_key and text_key not in seen_text:
                    item.pop("y", None)
                    deduped_outline.append(item)
                    seen_text.add(text_key)
            self.outline = deduped_outline

    def to_json(self):
        title = self.title.strip()
        for item in self.outline:
            item["text"] = item["text"].strip() + " "
            
        return {
            "title": f"{title} " if title else "",
            "outline": self.outline
        }

def main():
    if not OUTPUT_DIR.exists():
        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    for pdf_file in INPUT_DIR.glob("*.pdf"):
        print(f"Processing {pdf_file.name}...")
        try:
            processor = PdfProcessor(pdf_file)
            processor.process()
            output_data = processor.to_json()

            output_filename = OUTPUT_DIR / f"{pdf_file.stem}.json"
            with open(output_filename, 'w', encoding='utf-8') as f:
                json.dump(output_data, f, indent=4, ensure_ascii=False)
            print(f"Successfully generated {output_filename.name}")
        except Exception as e:
            print(f"Error processing {pdf_file.name}: {e}")

if __name__ == "__main__":
    main()
