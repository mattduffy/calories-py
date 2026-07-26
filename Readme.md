## Contents
- [Simple Calories](#simple-calories)
- [Pandolf-Santee Model](#the-pandolf-santee-model)
- [LCDA Model](#the-lcda-model)
- [Minimum Mechanics Model](#the-minimum-mechanics-model)
- [Calorie Ensemble](#the-calorie-ensemble)

## Estimating Energy Expenditure and Calories Burned
This package is a dependency-free ES module that estimates calories burned during physical activities (walking, hiking, rucking, etc) with functions for both simple calorie estimates, and more advanced methods utilizing GPS data.

Creating accurate estimates of the number of calories burned during a physical activity period is notoriously difficult, especially when attempting to incorporate positional data.  Most instances of estimating calories burned are simply calculated as an exertion effort based on body weight, time duration and a known **MET** ([Metabolic Equivalent Task](https://en.wikipedia.org/wiki/Metabolic_equivalent_of_task)) value for a given activity.  This method doesn't include positional data such as distance, velocity or elevation changes.  This can be considered a simple calorie estimate.

There are several, more advanced methods for estimating calories burned that do attempt to incorporate GPS data for a richer, more nuanced estimate.  This package provides more advanced functions to calculate calories burned using either the Pandolf-Santee, Minimum Mechanics or LCDA predictive models.

## Using 

```bash
python -m pip install calories-py
```

```python
from calories-py import lcdaCalories, simpleCalories, pandolfCalories, calorieEnsemble, minimumMechanicCalories
```

## Simple Calories
### Using Metabolic Equivalent Tasks
The simple calories calculation takes 3 parameters: ``minutes``, ``weights``, and ``MET``, and returns a positive floating point value.  The function throws an ``Error`` if the required parameters are missing, or of the wrong type.  You need to know the ``MET`` value for any specific activity you are measuring.  A good list of ``MET`` values can be found at the [Compendium of Physical Activities](https://pacompendium.com).  The required body weight parameter is measured in kilograms.

```python
# The number of minutes MET activity is performed.
# Required and must be greater than zero.
minutes = 35
# Weights, measured in Kilograms.  Body weight is
# required.  If a ruck weight was carried, include
# that too.  Optionally include weight of water
# carried as well.
# useful conversions:
#   1Kg == 2.2lbs or 1lbs == 0.45359Kg
#   1 fl oz of water == 1.042oz or 15.355 fl oz == 1lbs or 33.781 fl oz == 1kg
weights = {
  "body": 70, # required Kg
  "ruck": 5,  # optional Kg
  "water": 0, # optional Kg
}
# The MET number for a particular task.  For example:
#     Walking slowly:         2.0
#     Walking, 3.0 mph:       3.0
#     Weight lifting:         5.0
#     Backpacking:            7.5 <-- Default value
#     Swimming:               8.0
#     Rope jumping (84/min): 10.5
#     Jogging, 6.8 mph:      11.2
MET = 7.5
simple_calories = simpleCalories(minutes, weights, MET)
print(simple_calories)
# 143.381765625
```

## Advanced Calorie Predictive Models
### The Pandolf-Santee Model
This method of estimating energy expenditure is based on the [Pandolf-Santee](https://en.wikipedia.org/wiki/Pandolf_equation) equation.  The required parameters include an array of GPS coordinate data, and a body weight, measured in kilograms.  Additional values can be provided in the options parameter; including the weight of a ruck load, the weight of additional water carried, and the type of terrain covered.  There is also an option to _smooth_ out the GPS elevation data.  If the elevation data comes from a GPS sensor (rather than a barometric pressure sensor), it can be useful to smooth out the values with a rolling average because some GPS sensors can provide pretty jittery values for this field.

The ``pandolfCalories()`` function expects the coordinates parameter to be an List of List with the following format: ``[longitude, latitude, heading, altitude (m), accuracy (m), timestamp (ms)]``.  In this particular implementation, the heading and accuracy fields are not currently being used.  Those fields can be empty or ``None``.  The fields for longitude, latitude, altitude and timestamp must be valid, non-null values.  Altitude is measured in meters and the timestamp is Javascript default milliseconds.

The Santee correction factor for including downhill travel (negative grade values) is being applied when calculating the advanced estimates.  This correction factor results in energy expenditure estimates that are typically about 16% - 25% higher when the GPS data contains significant amounts of downhill travel vs the original pandolf equation that couldn't account for negative grade values.

To calculate the results, the pandolf-santee model is executed over each consecutive pair-wise GPS points in the the coordinates array.  Each of these pair-wise calculations is referred to as a segment.  To get the final results, the segments are aggregated together.  The boolean options property ``options["returnSegments"]`` controls whether an list of segment results is included in the function return value.  The default value is ``False``.  Setting this to ``True`` includes this segments list.

```python
cooords = [
# [gps longitude,       gps latitude,      heading (in deg), altitude (meters),  gps accuracy (m),  timestamp (ms)], 
  [-122.18413372578239, 37.82762389320808, 289.500900176593, 410.60703301243484, 6.935079779936697, 1781733047033],
  [-122.18414765202105, 37.827625731095864, 291.71648070840496, 411.11239344626665, 6.935079779936697, 1781733048037],
  [-122.1841647535281, 37.82762780033335, 286.09169894511865, 410.85964420530945, 7.091013324104003, 1781733049031],
  [-122.18417633225566, 37.827625146283225, 284.4996500921467, 411.22145825996995, 7.091013324104003, 1781733050034],
  ...,
]
# Optional terrain characterization values include:
# Paved road / treadmill:              1.0
# Dirt path / packed trail:            1.1
# Light off-trail, grass:              1.2
# Soft sand, deep grass, loose gravel: 1.5
# Snow, heavy brush, swamp:            1.8

# To remove GPS elevation jitter, set smooth to true.
# The window size sets amount of smoothing, 5 is usually
# sufficient.  If elevation data comes from a barometric
# sensor, set smooth to false.
options = {
  "bodyWeightKg": 70,     # Required, measured in kilograms
  "loadKg": 13.6,         # optional, measured in kilograms
  "waterKg": 0,           # optional, measured in kilograms
  "terrain": 1.1,         # optional, default value = 1.1
  "smooth": True,         # optional, smooth GSP elvation values
  "smoothWindow": 5,      # optional, default value == 5
  "returnSegments": False # optional, return calculated GPS segments
}
pandolf_calories = pandofCalories(coords, options)
print(pandolf_calories)
# {
#   'totalKcal': 581.492205191523,
#   'totalDistanceM': 5544.758689134893,
#   'totalDurationSec': 3829.9640000000027,
#   'avgSpeedMs': 1.4477312813214143,
#   'segments': [{...},{...},...], # Only included if options["returnSegments"] == True
# }
```

### The LCDA Model
A much more recently developed predictive model for calculating energy expenditure over distance, while carrying a load is the **L**oad **C**arrying **D**ecision **A**id model. [LCDA](https://pmc.ncbi.nlm.nih.gov/articles/PMC8919998/) is considered to be slightly more accurate than the Pandolf model at the extra expense of requiring parameters to calculate basal metabolic rate.

The ``coords`` and ``options`` parameters for ``lcdaCalories()`` are the same as for the above ``pandolfCalories()`` function.  The values in the ``BMR`` parameter object are used to create a value for basal metabolic rate using the [Mifflin-St Jeor equation](https://www.jandonline.org/article/S0002-8223(05)00149-5/abstract).

```python
BMR = {
  "height": 162.5 # Required, measured in centimeters
  "weight": 70    # Required, measured in kilograms
  "age": 45       # Required, measured in years
  "sex": 'm'      # Required, either 'm' or 'f'
}
options = {
  "bodyWeightKg": 70,     # Required, measured in kilograms
  "loadKg": 13.6,         # optional, measured in kilograms
  "waterKg": 0,           # optional, measured in kilograms
  "terrain": 1.1,         # optional, default value == 1.1
  "smooth": True,         # optional, smooth GSP elvation values
  "smoothWindow": 5,      # optional, default value == 5
  "returnSegments": False # optional, return calculated GPS segments
}
lcda_calories = lcdaCalories(coords, BMR, options)
print(lcda_calories)
# {
#   'totalKcal': 590.292205191523,
#   'totalDistanceM': 5544.758689134893,
#   'totalDurationSec': 3829.9640000000027,
#   'avgSpeedMs': 1.4477312813214143
# }
```

### The Minimum Mechanics Model
The Minimum Mechanics predictive model was developed by [Ludlow & Weyland](https://pubmed.ncbi.nlm.nih.gov/28729390/) as a less complex model altrnative to the negative grade-corrective Pandolf-Santee model.  This model incorporates the basal metabolic rate, like the **LCDA** model above, but forgoes terrain characterization.  The function signature is the same as that for **LCDA**.

```python
BMR = {
  "height": 162.5 # Required, measured in centimeters
  "weight": 70    # Required, measured in kilograms
  "age": 45       # Required, measured in years
  "sex": 'm'      # Required, either 'm' or 'f'
}
options = {
  "bodyWeightKg": 70,     # Required, measured in kilograms
  "loadKg": 13.6,         # optional, measured in kilograms
  "waterKg": 0,           # optional, measured in kilograms
  "smooth": True,         # optional, smooth GSP elvation values
  "smoothWindow": 5,      # optional, default value == 5
  "returnSegments": False # optional, return calculated GPS segments
}
minMech_calories = minimumMechanicCalories(coords, BMR, options)
print(lcda_calories)
# {
#   'totalKcal': 476.211434723359,
#   'totalDistanceM': 5544.758689134893,
#   'totalDurationSec': 3829.9640000000027,
#   'avgSpeedMs': 1.4477312813214143
# }
```

### The Calorie Ensemble
If you would like to compare the results of each of the predictive models for a given hike's dataset, you can use the `calorieEnsemble()` function.  This function maps each of the predictive models over each segment of the coordinates array in a single pass, to give comparative results.  For this function, the `BMR` parameter is combined into the `options` parameter.  You will notice that each of the predictive models gives a slightly different result for `totalKcal`.  This is expected and indicative of the differences in the respective models.

```python
options = {
  "bodyWeightKg": 70,     # Required, measured in kilograms
  "loadKg": 13.6,         # optional, measured in kilograms
  "waterKg": 0,           # optional, measured in kilograms
  "smooth": True,         # optional, smooth GSP elvation values
  "smoothWindow": 5,      # optional, default value == 5
  "returnSegments": False # optional, return calculated GPS segments
  "BMR": {
    "height": 162.5       # Required, measured in centimeters
    "weight": 70          # Required, measured in kilograms
    "age": 45             # Required, measured in years
    "sex": 'm'            # Required, either 'm' or 'f'
  },
}
resultSet = calorieEnsemble(coords, options)
print(resultSet)
# {
#   'lcda': {
#     'totalKcal': 590.292205191523,
#     'totalDistanceM': 5544.758689134893,
#     'totalDurationSec': 3829.9640000000027,
#     'avgSpeedMs': 1.4477312813214143
#   },
#   'pandolf': {
#     'totalKcal': 581.492205191523,
#     'totalDistanceM': 5544.758689134893,
#     'totalDurationSec': 3829.9640000000027,
#     'avgSpeedMs': 1.4477312813214143
#   },
#   'minMech': {
#     'totalKcal': 476.211434723359,
#     'totalDistanceM': 5544.758689134893,
#     'totalDurationSec': 3829.9640000000027,
#     'avgSpeedMs': 1.4477312813214143
#   }
# }
```
