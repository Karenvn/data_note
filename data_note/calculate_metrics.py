#!/usr/bin/env python


import math


def calc_ebp_metric(context):
    """
    Calculate the EBP metric string based on contig N50, scaffold N50 or % assembled, and QV.
    Returns a string like '6.C.Q40'.
    Assumes N50 values are in megabases.
    """

    assemblies_type = context.get("assemblies_type")
    
    if assemblies_type == "hap_asm":
        contig_n50 = context.get("hap1_contig_N50")  # Mb
        scaffold_n50 = context.get("hap1_scaffold_N50")  # Mb
        perc_assembled = context.get("hap1_perc_assembled")
        qv = context.get("hap1_QV")
    elif assemblies_type == "prim_alt":
        contig_n50 = context.get("contig_N50")
        scaffold_n50 = context.get("scaffold_N50")
        perc_assembled = context.get("perc_assembled")
        qv = context.get("prim_QV")
    else:
        return "?.?.Q?"
    
    print(f"Raw vaues for metrics are: {contig_n50} {scaffold_n50} {perc_assembled} and {qv}")
    # First part: log10(contig N50 in bp), rounded down
    try:
        ebp1 = str(int(math.log10(contig_n50 * 1_000_000)))
    except (TypeError, ValueError):
        ebp1 = "?"

    # Second part: 'C' if % assembled > 90 else log10(scaffold N50 in bp), rounded down
    try:
        if perc_assembled > 90:
            ebp2 = "C"
        else:
            ebp2 = str(int(math.log10(scaffold_n50 * 1_000_000)))
    except (TypeError, ValueError):
        ebp2 = "?"

    # Third part: QV, rounded down
    try:
        ebp3 = str(int(float(qv)))
    except (TypeError, ValueError):
        ebp3 = "?"

    return f"{ebp1}.{ebp2}.Q{ebp3}"
