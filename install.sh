#!/bin/bash
# 
#    INSTRUCTIONS:
#      0) Check the ENV_NAME doesn't collide with previously defined environments
#         - List current environments with `conda env list`
#      1) Run this With `source install_in.sh`
# 

ENV_NAME=drudge

# Conda env creation
echo "Creating Conda Environment"
conda create --name $ENV_NAME python=3.9 -y

# Choose the correct conda package list
if [[ "$(uname -m)" == "x86_64" ]]; then
    conda install --name $ENV_NAME --file install/env_x86.txt -y
else
    echo "CONDA ENVIRONMENT FOR arm64 NOT YET VERIFIED"
    conda install --name $ENV_NAME --file install/env_arm.txt -y
fi

# Force Conda into Base, then into created environment
echo "Initializing Conda"
conda init
conda activate $ENV_NAME


# Clone repository
echo "Cloning Submodules"
git submodule update --init --recursive


# Setup Vars
echo "Setting env vars"
export PYTHONPATH=$(pwd)
export DUMMY_SPARK=1

# Build cpp files
echo "Building cpp files"
python3 setup.py build
python3 setup.py install

# Copy the cpp files where needed
echo "Moving cpp files"
cp build/lib.linux-x86_64-cpython-39/drudge/wickcore.cpython-39-x86_64-linux-gnu.so drudge/
cp build/lib.linux-x86_64-cpython-39/drudge/canonpy.cpython-39-x86_64-linux-gnu.so drudge/

# Add Dummy Spark
echo "Getting Dummy Spark"
git clone https://github.com/DrudgeCAS/DummyRDD ../dummyRDD/

echo "Moving Dummy Spark"
cp -r ../dummyRDD/dummy_spark .

# Remove unneeded folder
rm -rf ../dummyRDD/

echo "Installation Complete!"
echo 'Assuming you ran this with '\''source'\'' you'\''re now inside the drudge folder. To get started with development simply type '\''code .'\'' and you'\''ll open a vscode window at this location'

