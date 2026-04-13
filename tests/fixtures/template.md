---
title: "Example data note for {{ species }}"
---

# {{ species }}

- BioProject: `{{ bioproject }}`
- ToLID: `{{ tolid }}`
- Taxon: `{{ tax_id }}`
- Assemblies type: `{{ assemblies_type }}`
- JIRA: `{{ jira or "N/A" }}`

## Parent projects

{{ formatted_parent_projects or "N/A" }}

## Summary

{{ auto_text or "No automatic summary available." }}
