# calories-py 
Python implementation of my npm @mattduffy/calories package.

To launch the Jupyter notebook server, run:

```bash
cd <calories-py_dir>
# Create the virtual environment if it does not already exist.
python3 -m venv ./
# Activate the venv.
source ./courses/bin/activate
# Create the jupyter kernel for this venv before launching notebook for the first time.
python3 -m pip install ipykernel
python3 -m ipykernel install --user --name=calories --display-name="Python3 (calories)"
# Launch jupyter as notebook server. 
/opt/homebrew/bin/jupyter notebook
```

Make sure to use the "Python3 (calories)" notebook kernel.  This will ensure that any packages installed inside the notebook for this package will be installed in this virtual environment, rather than the system python3 root.

[Jupyter package / kernel help](https://jakevdp.github.io/blog/2017/12/05/installing-python-packages-from-jupyter/) for help troubleshooting how jupyter interacts with virtual environments regarding package installation.
