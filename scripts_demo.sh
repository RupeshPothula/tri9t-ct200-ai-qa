#!/usr/bin/env bash
set -e
curl -F "file=@data/ct200_manual.pdf" "http://127.0.0.1:8000/documents/ingest?document_id=ct200"
curl -F "file=@data/ct200_manual_v2.pdf" "http://127.0.0.1:8000/documents/ingest?document_id=ct200"
curl "http://127.0.0.1:8000/documents/ct200/versions"
