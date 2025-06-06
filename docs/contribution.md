---
layout: default
title: Contributing
permalink: /contributing.html
---

# Contributing to WEC-Grid

First off, thank you for considering contributing! We welcome improvements in any of the following areas:

1. **Bug Reports & Issue Triage**  
   - If you find a bug or experience unexpected behavior, please [open an issue](https://github.com/acep-uaf/WEC-Grid/issues).  
   - Provide as much detail as possible:  
     - Environment (OS, Python/Julia versions, PSS®E version)  
     - Steps to reproduce  
     - Error messages / stack traces

2. **Feature Requests**  
   - Want a new diagram type, dynamic‐simulation support, or expanded WEC device library?  
   - Create an issue labeled “enhancement” and describe your use case.

3. **Pull Requests (PRs)**  
   - Fork the repo, create a new branch (`feature/my-feature` or `bugfix/issue-123`), and code away.  
   - Ensure that:  
     - All tests pass (`pytest` for Python; custom test scripts).  
     - You update `CHANGELOG.md` with a short summary of changes.  
     - You follow the existing code style (PEP8 for Python, Juliet style for Julia).

4. **Documentation & Examples**  
   - Add new Markdown pages under `/docs` or improve existing ones.  
   - Submit new Jupyter notebooks under `notebooks/`.  
   - If you add images, place them in `/images` and reference them with relative paths (`/WEC-Grid/images/...`).

5. **Citing WEC-Grid**  
   - If you use WEC-Grid in a publication, please cite:  
     ```bibtex
     @article{BarajasRitchie2025WECGrid,
       title   = {{WEC-Grid}: A Software Tool for Integrating Wave Energy Converter Models into Power System Simulations},
       author  = {Barajas-Ritchie, A. and Cotilla-Sanchez, E.},
       journal = {SoftwareX},
       year    = {2025},
       volume  = {23},
       pages   = {100861},
       doi     = {10.1016/j.softx.2025.100861},
     }
     ```

---

## Code of Conduct

Please adhere to this project’s [Code of Conduct](CODE_OF_CONDUCT.md) to ensure a welcoming environment. (If you don’t have one yet, create `CODE_OF_CONDUCT.md` in the repo root.)

---

Thank you for helping WEC-Grid grow! 😊

[⬅ Back to Home](index.html)