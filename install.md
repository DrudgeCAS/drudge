---
title: Install
layout: page
---

# Execution by Docker

Due to the relatively complex dependencies on things like a new C++ compiler,
Python, and Apache Spark, Docker is recommended for users of the
drudge/gristmill stack.  On Linux platforms, no performance overhead is
expected.

All Docker images are built from the Git repository
[drudge-docker](https://github.com/tschijnmo/drudge-docker), and the built
images are all pushed into the Docker repository
[tschijnmo/drudge](https://cloud.docker.com/repository/registry-1.docker.io/tschijnmo/drudge).
To pull the latest image for drudge and gristmill,

```
docker pull tschijnmo/drudge:drudge
docker pull tschijnmo/drudge:gristmill
```

can do the job, with the gristmill step able to be omitted if gristmill is not
needed.  The initial pulling might take a few GBs of data.  However, later
updates are expected to be relatively small.  The docker images have got all
dependencies, as well as the latest drudge/gristmill installed.

For both images, the directory `/home/work` is for holding the working files
for a job.  For instance, if we have a script `script.py` in the current
working directory, running

```
docker run -it --rm -v $PWD:/home/work tschijnmo/drudge:gristmill
```

will launch a container with all the drudge/gristmill stack, with the current
working directory on the host machine mounted at `/home/work`.  Then in a
interactive shell in this container, the script can be executed by `python3
script.py`.  All outputs written to the `/home/work` directory will be directly
visible on the host machine.  If no interactive shell is desired,

```
docker run --rm -v $PWD:/home/work tschijnmo/drudge:gristmill python3 script.py
```

can also execute the script directly.


# Local Installation (Development)

For development, the drudge stack can also be downloaded, compiled, and
installed from source.  For most non-developmental users, execution by Docker
is recommended.

## Conda

Conda is _strongly_ recommended for building and running this program locally. Conda is a utility for managing environments, which are like containers that hold a specific set of software installations. Just like a docker container can maintain exact versions and configurations of dependencies, so can Conda. The install script utilizes conda and will not run without it. To get conda simply go [here](https://www.anaconda.com/docs/getting-started/miniconda/install) and follow the instructions for your operating system. Once it is installed you may proceed

## Install Script (Linux-x86_64)

**These instructions function only for Linux x86_64 machines**. If you are using a mac or a different architecture, skip straight to the manual installation instructions.

There exists an install script at `drudge/install/install.sh`. You must run this script by executing 
```
source install/install.sh
```
You must use `source` as it executes the commands in the current process (as you) rather than opening a subshell in which conda usually breaks. Simply running this line should be enough to get you into shape. At this point if you'd like to utilize vscode you can simply run 

```
code .
```

to open a vscode window to the drudge location. 

Should anything go wrong, work your way through the manual installation instructions below

## Manual Installation

These instructions follow directly the existing install script, but provide a more interactive experience if needed. Enter the root drudge directory before proceeding, this is the base directory of the github repository.

### Create your Conda Environment
```
conda create --name $ENV_NAME python=3.9 -y
conda install --name $ENV_NAME -- file install/$ENV_TYPE.txt -y

conda init
conda activate $ENV_NAME
```

#### Parameters:
  - `$ENV_NAME`: This is the name of your environment, replace it with an environment name that does not already exist. Check the existing environment names with `conda env list`
  - `$ENV_TYPE.txt`: This is the desired environment dependencies file. There are two in the `install/` folder, `env_x86.txt` and `env_arm.txt`. To know which one you need simply run `uname -m` and it will return either `x86_64` or `arm64`, 
    - `arm64 -> env_arm.txt`
    - `x86_64 -> env_x86.txt`
    - If you get something other than `arm64` or `x86_64` feel free to try to install either file anyway and let us know if it doesn't work 

### Clone Submodules
```
git submodule update --init --recursive
```
This installs necessary dependencies` github repositories

### Set Environment Variables and Build
```
export PYTHONPATH=$(pwd)
export DUMMY_SPARK=1

python3 setup.py build
python3 setup.py install
```
The first two lines set necessary environment variables, so python knows where to find our python imports, and to utilize local dummy_spark instead of apache spark (which isn't quite working on python3.9 yet).

The next two lines build the c++ files into cpython files which can be imported and executed by our python program. By default python cannot import or utilize c++ files, this step is necessary for a fully functioning drudge

### Copy the built cpython files
```
cp build/lib.linux-x86_64-cpython-39/drudge/wickcore.cpython-39-x86_64-linux-gnu.so drudge/
cp build/lib.linux-x86_64-cpython-39/drudge/canonpy.cpython-39-x86_64-linux-gnu.so drudge/
```
These are _**EXAMPLE**_ lines. Yours might look different. What you're looking for is:
  1) In the Build Folder inside the root folder
  2) In the folder that starts with `lib.`
  3) In its `drudge` folder
  4) The two files that end with `.so`

Copy both these files into the `drudge/drudge` folder that contains the `canonpy.cpp` and `wickcore.cpp` files.

This step is the reason that the script is impossible to generalize across operating systems. I can see little rhyme or reason for the way these files/folders get named so predicting them in code appears impossible.

### Get Dummy Spark
Ensure you're in the base drudge directory and
```
git clone https://github.com/DrudgeCAS/DummyRDD ../dummyRDD/
cp -r ../dummyRDD/dummy_spark .
rm -rf ../dummyRDD/
```

These lines:
  1) Clone the repository that contains dummy_spark just outside of the drudge directory
  2) Copies the relevant `dummy_spark/` folder into the drudge base directory
  3) Deletes the now unnecessary `dummyRDD` repository

### That's it!
   It should be completely installed now. If you now run `code .` from the drudge base directory you'll open a vscode window with the conda environment activated, the environment variables set, and the correct interpreter selected.

   If you should close this vscode window and want to open it again you'll need to do a couple steps

## Utilizing VSCode
There are some steps required for drudge to function in its current state in vscode. You should treat this as a checklist every time you open the project.

### 1) Correct Interpreter
In the bottom right of vscode, just to the left of the bell you should see something like `3.9.20 ('drudge': conda)`. This denotes the currently enabled python interpreter (interpreter=python executable file). If it does not show up, ensure you have a python file open. You want to look through this interpreter list and choose the one that corresponds to the conda environment you made during installation.

### 2) Conda Environment Activated
In the terminal in the bottom portion of the window (you can open with `ctrl/cmd + ~` if it's closed) with the `TERMINAL` tab selected you should see your command prompt. At the very left there might be some things in parenthesis like `(drudge) (base)`. You want to ensure that your drudge environment name is here. If it's not, simply run 
```
conda activate drudge
```
with drudge replaced with whatever your environment name is. 

NOTE: If you're having import or version issues and have multiple environments listed in parenthesis it can be helpful to deactivate all environments by running
```
conda deactivate
```
repeatedly until all environment names are cleared, and then activating your drudge environment again.

### 3) Set Environment Variables
```
export PYTHONPATH=$(pwd)
export DUMMY_SPARK=1
```
Every time you open a new terminal:
  - You just opened vscode
  - You clicked debug for the first time this session
  - You hit the plus sign to the right of the TERMINAL tab

you'll need to ensure that both the drudge conda environment is activated, and that the environment variables are set. To set the `PYTHONPATH` variable correctly you need to ensure you are in the `drudge/` base directory (the one that github clones).

### You're set.
This should be everything you need to do to get drudge running. If there's problems or you encounter other errors, I recommend you take notes on what the problem was and what you did to fix it.

<!-- 
## Dependencies

In order to fully take advantage of the latest technology, the drudge/gristmill
stack requires Python at least 3.6, and Apache Spark at least 2.2 is need.  To
compile the binary components, a C++ compiler with good C++14 support is
required.  Clang++ later than 3.9 and g++ later than 6.3 is known to work.

 -->
## Downloads

All components of the drudge/gristmill stack are hosted on Github.  The
symbolic drudge code is hosted at
[tschijnmo/drudge](https://github.com/tschijnmo/drudge), which has the
[libcanon core](https://github.com/tschijnmo/libcanon) as a submodule for the
core algorithms for the canonicalization of combinatorial objects.

The code optimizer and generator gristmill is similarly hosted at
[tschijnmo/gristmill](https://github.com/tschijnmo/gristmill), which has the
submodules of

* `fbitset` at [tschijnmo/fbitset](https://github.com/tschijnmo/fbitset), for a
  highly-optimized bitmap container for the combinatorial algorithms in
  gristmill,
* `libparenth` at
  [tschijnmo/libparenth](https://github.com/tschijnmo/libparenth), for the core
  algorithm to find an optimal execution plan for tensor contractions by
  parenthesization, and
* `cpypp` at [tschijnmo/cpypp](https://github.com/tschijnmo/cpypp), for
  wrapping core C++ native modules for Python with ease.

As a result, to clone the repositories, `--recurse-submodules` is recommended.
<!--
## Compilation and installation

By `setuptools`, inside the root directory of the source tree of drudge or
gristmill, the compilation and installation can simply be

```
python3 setup.py build
python3 setup.py install
```
 -->
