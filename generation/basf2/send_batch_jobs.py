import os 

MODES = [
#     "B_Ds1Kmunu",
#     "B_DsK1munu",
#     "B0_DsstKstmunu",
    #"B0_Dstlnu",
#    "B0_Dststlnu",
#    "B0_Dsttaunu",
    #"B0_JpsiKst",
#    "B0_Kstll",
    "charged",
    "mixed"
]

for mode in MODES:
    basf2_command = f"basf2 generic_template.py {mode}"
    bsub_command = f"bsub -q s -n 2 -o ./log/{mode}_mdst.log '{basf2_command}'"
    if mode in ['charged', 'mixed']:
     bsub_command = f"bsub -q l -n 2 -o ./log/{mode}_mdst.log '{basf2_command}'"
    os.system(bsub_command)
    print(bsub_command)
