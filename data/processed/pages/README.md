NOT YET IMPLEMENTED as a separate per-page file/table structure. Page
text currently lives inline inside data/raw/**/*_extracted_text.txt with
[PAGE N] markers, and is NOT yet split into individual document_pages
rows (no document_pages DB table exists in backend/app/models/models.py
as of this session). See docs/limitations.md.
