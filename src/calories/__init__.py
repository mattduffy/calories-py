"""Create a package for the calories.py module."""
# load the public functions
from .calories import pandolfCalories, lcdaCalories, minimumMechanicsCalories, calorieEnsemble, load_sample_data

# optional, but good practice
__all__ = ["pandolfCalories", "lcdaCalories", "minimumMechanicsCalories", "calorieEnsemble", "load_sample_data"]