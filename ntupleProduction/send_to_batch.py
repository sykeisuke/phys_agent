import os


script_name = "Dstlnu_ntupleProd.py"

#default settings run over desired sample
for mode in ["e", "mu"]:
    basf2_command = f"basf2 {script_name} {mode}"
    bsub_command = f"bsub -q s -n 2 -o Dst{mode}nu.log '{basf2_command}'"
    os.system(bsub_command)

# run over mixed backgrounds 
for mode in ["e", "mu"]:
    basf2_command = f"basf2 {script_name} {mode} -i ../data/mixed_mdst.root -o ../data/mixed_Dst{mode}nu_ntuple.root"
    bsub_command = f"bsub -q s -n 2 -o Dst{mode}nu.log '{basf2_command}'"
    os.system(bsub_command)