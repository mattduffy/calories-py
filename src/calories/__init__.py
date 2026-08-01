"""Create a package for the calories.py module."""
# load the public functions
from .calories import simpleCalories, pandolfCalories, lcdaCalories, minimumMechanicsCalories, calorieEnsemble, load_sample_data

# optional, but good practice
__all__ = ["simpleCalories", "pandolfCalories", "lcdaCalories", "minimumMechanicsCalories", "calorieEnsemble", "load_sample_data"]