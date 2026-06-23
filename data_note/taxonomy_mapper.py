#!/usr/bin/env python3

"""
Taxonomy mapping for handling merged tax_ids and assembly selection overrides.
"""

# Manual assembly overrides for problematic cases
ASSEMBLY_OVERRIDES = {
    "PRJEB67613": {  # Schoenobius gigantella
        "primary": {
            "accession": "GCA_963935595.1",
            "name": "ilSchGiga1.1"
        },
        "alternate": {
            "accession": "GCA_963935585.1", 
            "name": "ilSchGiga1.1 alternate haplotype"
        },
        "reason": "Assemblies incorrectly labeled with Wolbachia tax_id 753421"
    }
}

# Tax_id mappings for simpler cases
TAX_ID_MAPPINGS = {
    # Schoenobius - even though we override assemblies, keep for tax_id allowance
    "1870291": {
        "allowed_tax_ids": ["753421", "3139313"],
        "reason": "Tax ID 1870291 merged into 753421; assemblies mislabeled"
    },
    
    # Lagenorhynchus/Leucopleurus acutus case  
    "90246": {
        "allowed_tax_ids": ["3371109"],
        "reason": "Taxonomic reclassification from Lagenorhynchus to Leucopleurus"
    },
    
    # Your existing special case
    "111406": {
        "allowed_tax_ids": ["295696"],
        "reason": "PRJEB68026 uses merged tax_id"
    },

    # Netelia thomsonii (PRJEB65668) - umbrella tax_id outdated
    "2884248": {
        "allowed_tax_ids": ["3458737"],
        "reason": "Assemblies use updated tax_id 3458737; umbrella project lists 2884248"
    },

    # Maea johnstoni / Magelona johnstoni (PRJEB71422) - umbrella and assembly records use duplicate species tax_ids
    "1436028": {
        "allowed_tax_ids": ["3698974"],
        "reason": "Assemblies use duplicate species tax_id 3698974; umbrella project lists 1436028"
    }
}

# BioProject-specific tax_id overrides (when umbrella tax_id is incorrect)
BIOPROJECT_TAX_ID_OVERRIDES = {
    "PRJEB65668": {
        "tax_id": "3458737",
        "reason": "Umbrella BioProject tax_id outdated; use updated tax_id for Netelia inedita"
    }
}

# BTK datasets are tied to the assembly data used to run BlobToolKit. Keep these
# explicit so newer assembly revisions do not silently reuse older BTK outputs.
BTK_ACCESSION_OVERRIDES = {
    "GCA_964261635.2": {
        "accession": "GCA_964261635.1",
        "reason": "aLisHel1.2 adds mitochondrial sequence; BTK dataset is for the unchanged nuclear assembly in aLisHel1.1",
    },
    "GCA_964263255.2": {
        "accession": "GCA_964263255.1",
        "reason": "aLisVul1.2 adds mitochondrial sequence; BTK dataset is for the unchanged nuclear assembly in aLisVul1.1",
    },
    "GCA_965112325.2": {
        "accession": "GCA_965112325.1",
        "reason": "PRJEB82199 uses cjHerHutc3.2 as the latest assembly; BTK dataset is available for cjHerHutc3.1",
    },
}

def has_assembly_override(bioproject_id):
    """Check if a bioproject has manual assembly overrides."""
    return bioproject_id in ASSEMBLY_OVERRIDES

def get_assembly_override(bioproject_id):
    """Get the manual assembly override for a bioproject."""
    return ASSEMBLY_OVERRIDES.get(bioproject_id)

def get_allowed_tax_ids(primary_tax_id):
    """Get all allowed tax_ids for a given primary tax_id."""
    allowed = {str(primary_tax_id)}
    
    mapping = TAX_ID_MAPPINGS.get(str(primary_tax_id))
    if mapping:
        allowed.update(mapping["allowed_tax_ids"])
    
    return allowed

def has_tax_id_override(bioproject_id):
    """Check if a bioproject has a tax_id override."""
    return bioproject_id in BIOPROJECT_TAX_ID_OVERRIDES

def get_tax_id_override(bioproject_id):
    """Get the tax_id override for a bioproject."""
    return BIOPROJECT_TAX_ID_OVERRIDES.get(bioproject_id)

def get_btk_accession_override(assembly_accession):
    """Get a manual BlobToolKit assembly accession override."""
    return BTK_ACCESSION_OVERRIDES.get(assembly_accession)

def should_exclude_by_name(assembly_name):
    """Check if an assembly should be excluded based on name patterns."""
    name_lower = assembly_name.lower()
    endosymbiont_patterns = ["wolbachia", "rickettsia", "spiroplasma"]
    
    for pattern in endosymbiont_patterns:
        if pattern in name_lower:
            return True
    return False
