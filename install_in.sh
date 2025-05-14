#!/bin/bash
# 
#    INSTRUCTIONS:
#      1) Run this With `source install_in.sh`
# 
ENV_NAME=drudge_testing

# Conda env creation
echo "Creating Conda Environment"
conda create --name $ENV_NAME python=3.9 -y
conda install --name $ENV_NAME --file env.txt -y

conda init
conda activate $ENV_NAME


# Get Dummy Spark
echo "Getting Dummy Spark"
git clone https://github.com/DrudgeCAS/DummyRDD ./dummyRDD/

# Clone repository
#echo "Cloning Repositories"
#git clone --recurse-submodules https://github.com/DrudgeCAS/drudge ./drudge/
#cd drudge
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
echo "Moving Dummy Spark"
cp -r ../dummyRDD/dummy_spark .


echo "DONE!!!"
echo  'Assuming you ran this with '\''source'\'' you'\''re now inside the drudge folder. To get started with development simply type '\''code .'\'' and you'\''ll open a vscode window at this location'

