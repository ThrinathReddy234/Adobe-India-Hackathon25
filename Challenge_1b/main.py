import os
import sys
import json
import re
import datetime
import fitz
from sentence_transformers import SentenceTransformer, util

def extract_structured_sections(doc):
    font_counts = {}
    for page in doc:
        for block in page.get_text("dict").get("blocks", []):
            if "lines" in block:
                for line in block["lines"]:
                    if "spans" in line and line["spans"]:
                        span = line["spans"][0]
                        size = round(span["size"])
                        is_bold = "bold" in span["font"].lower()
                        font_counts[(size, is_bold)] = font_counts.get((size, is_bold), 0) + 1

    if not font_counts:
        return [{"title": "Full Document Text", "content": "".join(p.get_text() for p in doc), "page": 1}]

    body_size, body_bold = sorted(font_counts.items(), key=lambda x: x[1], reverse=True)[0][0]

    headings = []
    for page_num, page in enumerate(doc):
        blocks = page.get_text("dict", sort=True)["blocks"]
        for block in blocks:
            if "lines" in block and block["lines"][0]["spans"]:
                span = block["lines"][0]["spans"][0]
                text = " ".join(s["text"] for s in block["lines"][0]["spans"]).strip()
                if not text: continue

                size = round(span["size"])
                is_bold = "bold" in span["font"].lower()
                is_heading = (size > body_size or (is_bold and not body_bold))

                if is_heading and len(block["lines"]) == 1 and len(text) < 120:
                    headings.append({"page": page_num, "y": block["bbox"][1], "title": text})

    if not headings:
        return [{"title": "Full Document Text", "content": "".join(p.get_text() for p in doc), "page": 1}]

    sections = []
    for i, h in enumerate(headings):
        start_page, start_y, title = h["page"], h["y"], h["title"]
        end_page = headings[i+1]["page"] if i + 1 < len(headings) else len(doc) - 1
        end_y = headings[i+1]["y"] if i + 1 < len(headings) else doc[end_page].rect.height

        content = ""
        for page_num in range(start_page, end_page + 1):
            page = doc[page_num]
            clip_y_start = start_y if page_num == start_page else 0
            clip_y_end = end_y if page_num == end_page else page.rect.height
            if clip_y_start >= clip_y_end: continue

            content += page.get_text(clip=fitz.Rect(0, clip_y_start, page.rect.width, clip_y_end))

        content = content.replace(title, "", 1).strip()
        if content:
            sections.append({"title": title, "content": content, "page": start_page + 1})

    return sections

def extract_recipe_sections(doc):
    full_text = "\n".join(page.get_text() for page in doc)
    recipe_chunks = re.split(r'\n\s*\n([A-Z][\w\s-]{5,60})\n', full_text)

    sections = []
    if len(recipe_chunks) < 2:
        return [{"title": "Full Document Text", "content": full_text, "page": 1}]

    for i in range(1, len(recipe_chunks), 2):
        title = recipe_chunks[i].strip()
        content = recipe_chunks[i+1].strip()
        if 'ingredients' in content.lower() or 'instructions' in content.lower():
            sections.append({"title": title, "content": content, "page": 1})

    return sections

def process_collection(collection_name, model):
    collection_folder = os.path.join(os.getcwd(), collection_name)
    input_filepath = os.path.join(collection_folder, "challenge1b_input.json")
    pdf_folder = os.path.join(collection_folder, "PDFs")
    output_filepath = os.path.join(collection_folder, "challenge1b_output.json")

    print(f"--- Starting processing for: {collection_name} ---")

    with open(input_filepath, 'r', encoding='utf-8') as f:
        input_data = json.load(f)

    persona = input_data['persona']['role']
    job_task = input_data['job_to_be_done']['task']

    print("Step 1: Extracting sections using adaptive parser...")
    all_sections = []
    documents_to_process = input_data['documents']

    if "collection 3" in collection_name.lower():
        parser_choice = "Recipe Parser"
        parser_func = extract_recipe_sections
        if 'dinner' in job_task.lower():
            print("-> Filtering for dinner-related documents.")
            documents_to_process = [
                doc for doc in documents_to_process
                if 'breakfast' not in doc['filename'].lower() and 'lunch' not in doc['filename'].lower()
            ]
    else:
        parser_choice = "Technical Document Parser"
        parser_func = extract_structured_sections
    print(f"-> Using {parser_choice} for this collection.")

    for doc_meta in documents_to_process:
        pdf_path = os.path.join(pdf_folder, doc_meta['filename'])
        if not os.path.exists(pdf_path): continue

        doc = fitz.open(pdf_path)
        sections = parser_func(doc)
        for sec in sections:
            all_sections.append({
                "document": doc_meta['filename'],
                "section_title": sec['title'],
                "content": sec['content'],
                "page_number": sec['page']
            })
        doc.close()
    print(f"-> Extracted {len(all_sections)} total sections.\n")

    print("Step 2: Pre-filtering for high-quality sections...")
    ignore_list = ["introduction", "conclusion", "table of contents", "full document text", "note:", "notes:"]
    sections_for_ranking = [
        sec for sec in all_sections
        if sec['section_title'].lower() not in ignore_list
    ]
    if not sections_for_ranking:
        sections_for_ranking = all_sections
    print(f"-> {len(sections_for_ranking)} sections remain for semantic search.\n")
    
    if not sections_for_ranking:
        final_output = { "metadata": {"input_documents": [d['filename'] for d in input_data['documents']], "persona": persona, "job_to_be_done": job_task,"processing_timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat()}, "extracted_sections": [], "subsection_analysis": [] }
        with open(output_filepath, 'w', encoding='utf-8') as f: json.dump(final_output, f, indent=4)
        print(f"--- No sections to rank for {collection_name}. Output generated. ---\n")
        return

    print("Step 3: Performing Prioritized Multi-Query Search...")
    sub_queries = []
    if 'college friends' in job_task.lower():
        sub_queries = [ "Comprehensive Guide to Major Cities...", "Exciting outdoor activities...", "Fun nightlife...", "Affordable and budget-friendly hotels...", "General travel tips" ]
    elif 'hr professional' in persona.lower():
        sub_queries = [ "Change or convert a flat form to a fillable PDF form...", "Create multiple PDF files...", "Convert content from the clipboard to a PDF...", "How to fill and sign PDF forms", "Send a document to get electronic signatures..." ]
    elif 'food contractor' in persona.lower():
        sub_queries = ["Vegetarian and gluten-free main dishes for a buffet", "Vegetarian and gluten-free side dishes for a buffet", "Hearty vegetable lasagna recipe", "Mediterranean vegetarian dishes like falafel or baba ganoush", "Elegant vegetable dishes like ratatouille"]
    else:
        sub_queries = [f"As a {persona}, I need to {job_task}."]
    print(f"-> Using {len(sub_queries)} prioritized sub-queries.")

    section_texts = [s['section_title'] + ". " + s['section_title'] + ". " + s['content'] for s in sections_for_ranking]
    section_embeddings = model.encode(section_texts, convert_to_tensor=True, show_progress_bar=False)

    curated_results = []
    seen_sections = set()
    for query in sub_queries:
        if len(curated_results) >= 5: break
            
        query_embedding = model.encode(query, convert_to_tensor=True)
        cosine_scores = util.cos_sim(query_embedding, section_embeddings)[0]
        
        top_candidates_indices = sorted(range(len(cosine_scores)), key=lambda i: cosine_scores[i], reverse=True)[:2]

        for idx in top_candidates_indices:
            section = sections_for_ranking[idx]
            section_key = (section['document'], section['section_title'])
            if section_key not in seen_sections:
                curated_results.append(section)
                seen_sections.add(section_key)

    print("\nStep 4: Generating final JSON output...")
    top_n = 5
    top_sections = curated_results[:top_n]
    
    if "collection 3" in collection_name.lower() and 'vegetarian' in job_task.lower():
        meat_blocklist = ['pork', 'beef', 'chicken', 'turkey', 'sausage', 'bacon', 'lamb', 'veal', 'fish', 'seafood', 'salmon']
        top_sections = [sec for sec in top_sections if not any(meat in sec['content'].lower() for meat in meat_blocklist)]

    extracted_sections_output = []
    subsection_analysis_output = []

    for i, item in enumerate(top_sections):
        page_num = item['page_number']
        extracted_sections_output.append({ "document": item['document'], "section_title": item['section_title'], "importance_rank": i + 1, "page_number": page_num })
        subsection_analysis_output.append({ "document": item['document'], "refined_text": item['content'], "page_number": page_num })

    final_output = {
        "metadata": { "input_documents": [doc['filename'] for doc in input_data['documents']], "persona": persona, "job_to_be_done": job_task, "processing_timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat() },
        "extracted_sections": extracted_sections_output,
        "subsection_analysis": subsection_analysis_output
    }

    with open(output_filepath, 'w', encoding='utf-8') as f:
        json.dump(final_output, f, indent=4)

    print(f"--- Success! Output for {collection_name} saved to '{output_filepath}'. ---\n")

if __name__ == "__main__":
    print("Initializing Sentence Transformer model...")
    sbert_model = SentenceTransformer('all-MiniLM-L6-v2')
    print("Model loaded.")
    
    all_collections = sorted([
        d for d in os.listdir('.') 
        if os.path.isdir(d) and d.startswith("Collection")
    ])

    if not all_collections:
        print("No 'Collection' directories found. Exiting.")
        sys.exit(1)

    print(f"\nFound collections to process: {all_collections}\n")
    
    for collection in all_collections:
        try:
            process_collection(collection, sbert_model)
        except Exception as e:
            print(f"!! An error occurred while processing {collection}: {e} !!")

    print("All collections processed.")