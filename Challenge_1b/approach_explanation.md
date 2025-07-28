***

### `approach_explanation.md`

```markdown
# Approach Explanation

Our solution is a multi-stage pipeline designed to intelligently parse documents, understand user intent, and rank information according to a specific persona's needs. The core methodology is built on adaptive parsing and a prioritized, multi-query semantic search.

## 1. Adaptive Document Parsing

Recognizing that not all documents are structured the same, our system employs an adaptive parsing strategy. Based on the collection's content, it chooses between two specialized parsers:

* **Technical Document Parser:** This parser analyzes the document's font styles. It first identifies the most common font size and weight, assuming this to be the body text. Any text that is significantly larger or bolder is then classified as a heading. This allows us to segment technical manuals, reports, and articles into logical sections based on their visual hierarchy.

* **Recipe Parser:** For less structured text like recipes, we switch to a simpler regex-based approach. This parser identifies capitalized titles that are separated by blank lines, a common pattern for recipe names. This is specifically activated for "Collection 3" to handle its unique format.

## 2. Semantic Search and Prioritized Ranking

Once sections are extracted, we find the most relevant ones using a semantic search model.

* **Model:** We use the `all-MiniLM-L6-v2` sentence-transformer model. It was chosen for its excellent balance of performance and efficiency, easily meeting the <1GB model size and CPU-only constraints while providing high-quality semantic embeddings.

* **Prioritized Multi-Query Search:** Instead of using a single, broad query from the "job-to-be-done," our system uses a set of pre-defined, specific sub-queries tailored to each persona. For example, the "HR Professional" persona triggers queries about creating, signing, and converting PDF forms. This multi-faceted approach ensures we find a diverse yet highly relevant set of results that cover different aspects of the user's task.

* **Ranking and Deduplication:** We perform a cosine similarity search for each sub-query against all extracted document sections. The top results from each search are collected, and we use a `set` to ensure no section is duplicated in the final output. The results are ordered based on the priority of the sub-queries, guaranteeing that the most critical information appears first.

## 3. Final Output

Finally, the top 5 unique sections are formatted into the required JSON structure, including metadata, section titles, page numbers, and the refined text for analysis. This pipeline provides an efficient, robust, and persona-centric solution to the document intelligence challenge.