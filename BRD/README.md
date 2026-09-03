# BRD Generation Module
This module handles automated Business Requirements Document (BRD) generation from MS Access projects.
It performs static analysis, extracts project facts, calls the local Ollama LLM (`deepseek-r1:1.5b`),
and renders an A4-styled standalone HTML document at `BRD/output/<project-name>/BRD.html`.
