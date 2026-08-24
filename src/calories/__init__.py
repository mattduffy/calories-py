"""Create a package for the calories.py module."""
# load the public functions
from .calories import simpleCalories, pandolfCalories, lcdaCalories, minimumMechanicsCalories, calorieEnsemble, load_sample_data, models

try:
    from ._version import __version__
except ImportError:
    # Fallback for local, unbuilt source trees
    __version__ = "0.0.0.dev0"
    
# optional, but good practice
__all__ = ["simpleCalories", "pandolfCalories", "lcdaCalories", "minimumMechanicsCalories", "calorieEnsemble", "load_sample_data", "models", "__version__"]
