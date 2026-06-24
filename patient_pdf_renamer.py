#!/usr/bin/env python3

from pdf_renamer.app import main
from pdf_renamer.extraction import extract_document_details_with_ollama
from pdf_renamer.ocr import extract_document_text

if __name__ == "__main__":
    main()
