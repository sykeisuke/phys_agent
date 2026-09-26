import os 

MODES = [
    "B0_Dstlnu",
    "B0_Dsttaunu",
    "B0_JpsiKst",
    "B0_Kstl",
    "charged",
    "mixed"
]

for mode in MODES:
    basf2_command = f"basf2 generic_template.py {mode}"
    bsub_command = f"bsub -q s -n 2 -o {mode}_mdst.log '{basf2_command}'"
    os.system(bsub_command)