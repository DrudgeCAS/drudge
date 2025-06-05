#!/bin/bash
# 
#    INSTRUCTIONS:
#      0) Check the ENV_NAME doesn't collide with previously defined environments
#         - List current environments with `conda env list`
#      1) Run this With `source install_in.sh`
# 

ENV_NAME=drudge

# Ensure latest conda installed 
conda update -n base -c defaults conda

# Conda env creation
echo "Creating Conda Environment"
conda create --name $ENV_NAME python=3.9 -y
conda activate $ENV_NAME

# Choose the correct conda package list
if [[ "$(uname -m)" == "x86_64" ]]; then
    # conda install --name $ENV_NAME --file install/env_x86.txt -y
    conda install conda-forge::gcc==14.2.0 -y
    conda install conda-forge::gxx_linux-64==14.2.0 -y
else
    # echo "CONDA ENVIRONMENT FOR arm64 NOT YET VERIFIED"
    # conda install --name $ENV_NAME --file install/env_arm.txt -y
    echo ""
fi

conda install IPython==8.15.0 -y
conda install sympy==1.13.2 -y
conda install pyspark==3.4.1 -y
conda install jinja2 -y 
conda install pytest -y
conda install coveralls -y

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
# echo "Moving cpp files"
# cp build/lib.linux-x86_64-cpython-39/drudge/wickcore.cpython-39-x86_64-linux-gnu.so drudge/
# cp build/lib.linux-x86_64-cpython-39/drudge/canonpy.cpython-39-x86_64-linux-gnu.so drudge/

# Add Dummy Spark
echo "Getting Dummy Spark"
git clone https://github.com/DrudgeCAS/DummyRDD ../dummyRDD/

echo "Moving Dummy Spark"
cp -r ../dummyRDD/dummy_spark .

# Remove unneeded folder
rm -rf ../dummyRDD/

echo "Installation Complete!"
echo "Assuming you ran this with '\''source'\'' you'\''re now inside the drudge folder. To get started using drudge you'll want to do 3 things after opening your chosen IDE to your code location:"
echo "   1) Ensure your Python Interpreter is set to the Conda Environment Python we just created"
echo "   2) Ensure this conda environment is activated with '\''conda activate drudge '\'' in the terminal which runs your program"
echo "   3) Set your pythonpath to the build directory of this repository like '\''export PYTHONPATH=\$PYTHONPATH:/path/to/drudge/build'\''"
echo " "
echo "Have Fun!"
