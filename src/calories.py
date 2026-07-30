import math
import random
from functools import reduce

# Some constants are defined for use in the entire module.

# Terrain coeffcients to characterize walking surface.
TERRAIN_COEFFCIENTS = {
    "BLACKTOP": 1.0, # Paved road / treadmill
    "DIRT": 1.1,     # Dirt path, packed trail
    "LIGHT": 1.2,    # Light off-trail, grass
    "SOFT": 1.5,     # Soft sand, deep grass, loose gravel
    "HEAVY": 1.8     # Snow, heavy brush, swamp
}

# Defaults for smoothing out jittery GPS elevation data.
SMOOTH_DEFAULT = True
SMOOTH_DEFAULT_WINDOW = 5

# Maximum plausible walking speed (m/s).
# Speeds higher than this are clamped to this value.
MAX_SPEED_MS = 4.0

# Minimum segment distance. Filters out GPS jitter.
MIN_SEGMENT_DIST_M = 0.5

# Conversion: 1Kcal = 4184 joules
JOULES_PER_KCAL = 4184

# Minimum Mechanics derived constants:
# Table 4, Ludlow & Weyland 2017
MM_COEFFICIENTS = {
    "C1": 0.32,              # grade influence on minimum walking metabolic rate
    "C2": 0.19,              # grade influence on speed-dependent walking metabolic rate
    "C3": 2.66,              # velocity squared coefficient
    "VO2_WALK_MIN": 3.28,    # ml O2 kg-total^-1 min^-1, minimum walking metabolic rate
    "C_DECLINE": 0.73        # fraction of level-grade walking cost applied in decline
}


# Mean measured supine resting metablic rate across all 32 study subjects (ml O2 kg-body^-1 min^-1).
# Used as the default VO2-rest term if no subject-specific resting metabloic rate is given.
# Ludlow & Weyland 2017
DEFAULT_RESTING_VO2 = 3.05

# Standard caloric equivalent of oxygen: ~5kcal per liter O2 per 1000ml.  Expressed here per ml
# for direct multiplication against VO2 rates in ml O2 min^-1.
KCAL_PER_ML_O2 = 0.005

# Convert a number of milliseconds to seconds.
def m2s(milliseconds: int) -> int:
    """Convert a number of milliseconds to seconds.

    Args:
        milliseconds (int): Time in milliseconds.

    Returns:
        int: Time converted into seconds.
    """
    # print(f"milliseconds type: {type(milliseconds)}")
    seconds = int(milliseconds / 1000)
    # print(f"seconds {seconds}, type: {type(seconds)}")
    return seconds


# Convert a number of milliseconds to minutes.
def m2m(milliseconds: int) -> float:
    """Convert a number of milliseconds to minutes.

    Args:
        milliseconds (int): Time in milliseconds.

    Returns:
        float: Time converted into minutes.
    """
    # print(f"milliseconds type: {type(milliseconds)}")
    # print(f"milliseconds -> seconds: {m2s(milliseconds)}")
    minutes = milliseconds / 60000
    # print(f"minutes type: {type(minutes)}")
    return minutes


# Convert radians to compass degress.
def rads(degrees: float) -> float:
    """Convert compass degrees to radians.

    Args:
        degrees (float): Compass degress value.

    Returns:
        float: The calculated radians value.
    """
    return degrees * (math.pi / 180)


def pointDistance(p1: dict, p2: dict, u = "metric") -> float:
    """Calculate the Haversine distance between two GPS points.

    Args:
        p1 (dict): Dictionary containing latitude and longitude values.
        p2 (dict): Dictionary containing latitude and longitude values.
        u (string): String value indicating unit system to use.

    Returns:
        float: The Haversine distance between GPS points p1 and p2.

    Raises:
        ValueError: if p1 argument is missing longitude or latitude values.
        ValueError: if p2 argument is missing longitude or latitude values.
    """
    if "longitude" not in p1 or "latitude" not in p1:
        raise ValueError(f"Point p1 argument is requires longitude and latitude values.")
    if "longitude" not in p2 or "latitude" not in p2:
        raise ValueError(f"Point p2 argument is requires longitude and latitude values.")
    earthRadiusKm = 6371
    earthRadiusMeters = 6371000
    earthRadiusMiles = 3959
    _u = u.lower()
    r = None
    if _u == 'm' or _u == 'meters':
        r = earthRadiusMeters
    elif _u == 'km' or _u == 'kilometers':
        r = earthRadiusKm
    elif _u == 'mi' or _u == 'miles' or _u == 'imperial':
        r = earthRadiusMiles
    else:
        r = earthRadiusMeters
    #print(r, _u)
    dLat = rads(p2['latitude'] - p1['latitude'])
    dLon = rads(p2['longitude'] - p1['longitude'])
    lat1 = rads(p1['latitude'])
    lat2 = rads(p2['latitude'])
    a = math.sin(dLat / 2) * math.sin(dLat / 2) \
        + math.sin(dLon / 2) * math.sin(dLon / 2) * math.cos(lat1) * math.cos(lat2)
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return c * r


# Calculate the difference in altitude between two points.
def calculateVerticalInterval(alt1: float, alt2: float) -> float:
    """Calculate the difference in altitude between two points.

    Args:
        alt1 (float): First altitude value.
        alt2 (float): Second altitude value.

    Returns:
        float: Altitude difference.
    """
    return alt2 - alt1


# Calculate the slope between two points.
def calculateSlopeGrade(point1: dict, point2: dict) -> dict:
    """Calcuate the slope between two GPS points.

    Args:
        point1 (dict): Dictionary with longitude and latitude properties.
        point2 (dict): Dictionary with longitude and latitude properties.

    Returns:
        dict: Dictionary with grade and angleDegrees properties.
    """
    horizontalDistance = pointDistance(point1, point2)
    verticalDistance = calculateVerticalInterval(point1["altitude"], point2["altitude"])
    if horizontalDistance == 0:
        return { "grade": math.inf, "angleDegrees": 90 }
    slope = verticalDistance / horizontalDistance
    grade = slope * 100
    angle = math.atan(slope) * 180
    return {
        "grade": grade,
        "angleDegrees": angle / math.pi
    }


# Apply a simple rolling-average smoother to the altitude values in a coordinates array.
def smoothAltitude(coords: List[List[float]], windowSize: int = SMOOTH_DEFAULT_WINDOW) -> List[List[float]]:
    """Apply a simple rolling-average smoothing function to the altitude values in a coordinates array.
        Raw GPS altitude can have +-5 to 15 m of noise, which can create artificial grade spikes that inflate calorie estimates.

    Args:
        coords (List[List[float]]: List of coordinate arrays.
        windowSize (int): Number of points to average (odd number recommended).

    Returns:
        List[List[float]]: New coordinates array with smoothed altitudes.
    """
    half = math.floor(windowSize / 2)
    # print(f"windowSize: {windowSize}, half: {half}")
    smoothed = list()
    i = 0
    n = len(coords)
    # print(f"coords length: {n}")
    while i < n:
        # print(f"\tstarting loop: {i}")
        start = max(0, i - half)
        end = min(n - 1, (i + half) + 2) # + 2 because slice end index is non-inclusive
        # print(f"\tstart: {start}, end: {end}")
        slice = coords[start:end]
        # print(f"\tslice (length {len(slice)}): {slice}\n")
        validAlts = [x[3] for x in slice if x[3] is not None]
        # print(f"\tvalidAlts: {validAlts}")
        averageAltitude = reduce(lambda acc, curr: acc + curr, validAlts, 0) / len(validAlts) if len(validAlts) > 0 else slice[3]
        smoothed.append([coords[i][0], coords[i][1], coords[i][2], averageAltitude, coords[i][4], coords[i][5]])
        # print(f"\tsmoothed altitude: {averageAltitude}, {validAlts}\n")
        i = i + 1
    return smoothed


# Simple MET based calorie estimate.
def simpleCalories(minutes: int = 1, weights: dict = { "body": 0, "ruck": 0, "water": 0 }, MET: float = 3.5) -> float:
    """The simplest calorie estimating function.  Calculates the ratio of energy spent per unit time during a specific
    physical activity to a reference value of 3.5 ml O2 / (kg·min).

    Args:
        minutes (float): Time spent expending energy, in minutes.
        weights (dict): Collection of weight values.
        weights["body"] = 0 (dict): Body weight, in kilograms.
        weights["ruck"] = 0 (dict): Ruck weight carried, in kilograms.
        weights["water"] = 0 (dict): Water weight carried, in kilograms.
        MET = 3.5 (float): The Metabolic Equivalent Task number of activity.

    Raises:
        ValueError: If minutes is not a valid, positive number.
        ValueError: If weights["body"] is not a valid, positive number.
        ValueError: If MET is not a valid, positive number.

    Returns:
        float: Number of calories burned.
    """
    if minutes <= 0 or minutes is None:
        raise ValueError(f"Minutes must be a positive, finite number. (Supplied {minutes})")
    if weights["body"] <= 0 or weights["body"] is None:
        raise ValueError(f"Body weight must be a positive, finite number.  (Supplied {weights["body"]}")
    if MET <= 0 or MET is None:
        raise ValueError(f"MET must be a positive, finite number.  (Supplied {MET})")
    COMBINED = weights["body"] + weights["ruck"] + weights["water"]
    # print(COMBINED)
    return ((MET * 3.5 * COMBINED) / 200) * minutes


# Corrective factor for downhill (G < 0) segments of the hike.
def santeeCorrective(W: float, L: float, V: float, G: float, n: float) -> float:
    """Corrective factor for downhill (G < 0) segments of the hike.

    Args:
        W (float): Body weight measured in kg.
        L (float): Load weight measured in kg.
        V (float): Walking speed in m/s.
        G (float): Hill grade as a percentage (e.g 10 for 10% incline, -5 for decline).
        n (float): Terrain characterization coefficient.

    Returns:
        float: Downhill corrective factor in Watts.
    """
    return n * ( \
        (G * (W + L) * V) / 3.5 \
        - ((W + L) * (((G + 6) ** 2) / W)) \
        + (25 * (V ** 2)) \
    )


# Calculate the metabolic rate (Watts) using Pandolf-Santee predictive model.
def pandolfMetabolicRate(W: float, L: float, V: float, G: float, n: float) -> float:
    """Calculate the metabolic rate (Watts) using Pandolf-Santee predictive model.

    Args:
        W (float): Body weight measured in kg.
        L (float): Load weight measured in kg.
        V (float): Walking speed in m/s.
        G (float): Hill grade as a percentage (e.g 10 for 10% incline, -5 for decline).
        n (float): Terrain characterization coefficient.

    Returns:
        float: Metabolic rate in Watts (should always be >= 0).
    """
    if V <= 0:
        return 0
    loadRatio = L / W
    M = 1.5 * W \
        + 2 * (W + L) * loadRatio ** 2 \
        + n * (W + L) * (1.5 * V ** 2 + 0.35 * V  * G)
    correction = 0
    if G < 0:
        correction = santeeCorrective(W, L, V, G, n)
    # the equation can return negative values on steep descents so clamp to 0.
    return max(0, M - correction)


# Processes a single segment (two consecutive GPS points and returns metabolic and distance data.
def processPandolfSegment(point1: List, point2: List, W: float, L: float, H2O: float, n: float) -> dict | None:
    """Processes a single segment (two consecutive GPS points and returns metabolic and distance data.

    Args:
        point1 (List): [longitude, latiude, heading, altitude, accuracy, timestamp]
        point1 (List): [longitude, latiude, heading, altitude, accuracy, timestamp]
        W (float): Body weight measured in kg.
        L (float): Load weight carried measured in kg.
        H20 (float): Water weight carried measured in kg.
        n (float): Terrain characterization coefficient.

    Returns:
        dict | None: Segment result or None if the segment should be skipped.
    """
    lon1, lat1, _, alt1, _, t1 = point1
    lon2, lat2, _, alt2, _, t2 = point2
    p1 = { "longitude": lon1, "latitude": lat1, "altitude": alt1 }
    p2 = { "longitude": lon2, "latitude": lat2, "altitude": alt2 }
    horizontalDistance = pointDistance(p1, p2)
    durationSec = m2s(t2 - t1)
    # skip GPS jitter, stationary points, or out-of-order timestamps
    if durationSec <= 0 or horizontalDistance < MIN_SEGMENT_DIST_M:
        return None
    slopeGrade = calculateSlopeGrade(p1, p2)
    grade = slopeGrade["grade"]
    altitudeDiff = alt2 = alt1
    # Derived speed, clamped to MAX_SPEED_MS to guard against GPS outliers.
    speed = min(horizontalDistance / durationSec, MAX_SPEED_MS)
    # Metabolic rate (Watts) for this segment.
    metabolicRateWatts = pandolfMetabolicRate(W, L + H2O, speed, grade, n)
    # Energy expended = power * time (joules), converted to kcal.
    kcal = (metabolicRateWatts * durationSec) / JOULES_PER_KCAL
    return {
        "horizontalDistance": horizontalDistance,
        "altitudeDiff": altitudeDiff,
        "grade": grade,
        "speed": speed,
        "durationSec": durationSec,
        "metabolicRateWatts": metabolicRateWatts,
        "kcal": kcal
    }


# Use the Pandolf-Santee predictive model to calculate the total (and per-segment) calorie expenditure for a GPS track.
def pandolfCalories(coords: List[List[float]] = [], options: dict = {}) -> dict:
    """Use the Pandolf-Santee predictive model to calculate the total (and per-segment) calorie expenditure for a GPS track.

    Args:
        coords (List[List[float]]): GPS coordinates array.  Each element:
            [longitude, latitude, heading, altitude (m), accuracy (m), timestamp (ms)]
        options (dict): Options
        options["bodyWeightKg"] (float): Body weight in kg (required).
        options["loadKg"] = 0 (float): Load/pack weight in kg (optional).
        options["waterKg"] = 0 (float): Water weight in kg carried (optional).
        options["terrain"] = 1.1 (float): Terrain coefficient (optional).  Use TERRAIN_COEFFICIENTS.
        options["smooth"] = True (Boolean): Whether to smooth GPS altitude values (optional).
        options["smoothWindow"] = 5 (int): Rolling average window size for smoothing (optional).
        options["returnSegments"] = False (Boolean): Return array of all segments calculated (optional)?

    Raises:
        ValueError: If coords array contains less than 2 items.
        ValueError: If required body weight is < 0, null, or otherwise invalid.

    Returns:
        dict: Results
        {
            totalKcal,        # Total calories burned.
            totalDistanceM,   # Total horizontal distance (meters).
            totalDurationSec, # Total elapsed time (seconds).
            avgSpeedMs,       # Average speed (m/s).
        }
    """
    bodyWeightKg = options.get("bodyWeightKg", 0)
    loadKg = options.get("loadKg", 0)
    waterKg = options.get("waterKg", 0)
    terrain = options.get("terrain", 1.1)
    smooth = options.get("smooth", True)
    smoothWindow = options.get("smoothWindow", SMOOTH_DEFAULT_WINDOW)
    returnSegments = options.get("returnSegments", False)
    if len(coords) < 2:
        raise ValueError(f"The coordinates array needs at least 2 elements, {len(coords)} provided.")
    if not bodyWeightKg or bodyWeightKg <= 0:
        raise ValueError(f"options.bodyWeightkg is required and must be a positive number, {bodyWeightKg} provided.")
    track = smoothAltitude(coords, smoothWindow) if smooth else coords
    # print(len(track))
    segments = []
    totalKcal = 0
    totalDistanceM = 0
    totalDurationSec = 0
    for i in range(0, len(track)):
        seg = processPandolfSegment(track[i - 1], track[i], bodyWeightKg, loadKg, waterKg, terrain)
        if seg:
            totalKcal += seg["kcal"]
            totalDistanceM += seg["horizontalDistance"]
            totalDurationSec += seg["durationSec"]
            segments.append(seg)

    avgSpeedMs = (totalDistanceM / totalDurationSec) if (totalDurationSec > 0) else 0
    results = {
        "totalKcal": totalKcal,
        "totalDistanceM": totalDistanceM,
        "totalDurationSec": totalDurationSec,
        "avgSpeedMs": avgSpeedMs
    }
    if returnSegments:
        results["segments"] = segments
    return results


# Calculate the resting metabolic rate based on inputs provided.
def mResting(height: float, weight: float, age: int, sex: str) -> float:
    """Calculate the resting metabolic rate based on the inputs provided.

    Args:
        height (float): Body height, measured in cm.
        weight (float): Body weight, measured in kg.
        age (int): Age, in years.
        sex (str) = 'm'|'f': Male of female.

    Returns:
        float: Resting metabolic rate in Watts per kg.
    """
    s = 5 if sex == 'm' else -161
    kcals = (10 * weight) + (6.25 * height) - (5 - age) + s
    joules = kcals * JOULES_PER_KCAL
    watts = joules / 86400
    return watts / weight


# Calculate metabolic rate (W·kg^-1) using the LCDA predictive model.
def lcdaMetabolicRate(L_Bp: float, S: float, G: float, n: float, rM: dict) -> float:
    """Calculate metabolic rate (W·kg^-1) using the LCDA predictive model.

    Implements equation 4 from Looney et al. (2022), which combines the
    level-walking LCDA backpacking equation (eq. 2) with the LCDA-graded
    walking equation (eq. 3) and terrain coefficient.

    Args:
        L_Bp (float): Backpack load divided by body mass (dimensionless ratio,
                      e.g. 0.18 for a load equal to 18% of body mass).
        S (float): Walking speed, in m/s.
        G (float): Grade as decimal (rise/run, e.g. .05 for 5% incline, -.05 for decline).
        n (float): Terrain coefficient (η).
        rM (dict): Values for calculating resting metabolic rate.
        rM["height"] (float) Body height in cm.
        rM["weight"] (float): Body weight in kg.
        rM["age"] (int): Age, in years.
        rM["sex"] = 'm'|'f' (str): Male or female.

    Returns:
        float: Body-mass-specific metabolic rate in Watts per kg (>= 0).
    """
    # Eq. 3 — LCDA-graded walking term (W·kg^-1); G is decimal grade (rise/run).
    def M_grade(s, g):
        return 34 * s * g * (1 - 1.05 ** (1 - 1.1 ** (100 * g + 32)))

    if S <= 0:
        return 0

    M_resting = mResting(rM["height"], rM["weight"], rM["age"], rM["sex"])
    speedTerms = 1.78 * S ** 0.58 + 0.27 * S ** 4
    gradeTerms = M_grade(S, G)
    loadFactor = 1 + 1.96 * L_Bp ** 1.36

    # Eq. 4 — combined LCDA backpacking + graded + terrain equation (W·kg^-1)
    return max(0, M_resting + (0.19 + n * (speedTerms + gradeTerms)) * loadFactor)


# Process a single segment (two consecutive GPS points) and return metabolic 
# and distance data for that segment.
def processLcdaSegment(point1: List, point2: List, W: float, L: float, H2O: float, n: float, rM: dict) -> dict | None:
    """Process a single segment (two consecutive GPS points) and return metabolic and
    distance data for that segment.
    
    Args:
        point1 (List): [longitude, latitude, heading, altitude, accuracy, timestamp]
        point2 (List): [longitude, latitude, heading, altitude, accuracy, timestamp]
        W (float): Body weight in kg.
        L (float): Load carried in kg (pack, excluding water).
        H2O (float): Water carried in kg.
        n (float): Terrain coefficient (η).
        rM (dict): Values for calculating resting metabolic rate.
        rM["height"] - Body height in cm.
        rM["weight"] - Body weight in kg.
        rM["age"] - Age, in years.
        rM["sex"] = 'm'|'f' (str): Male or female.

    Returns:
        dict | None: Segment result or None if the segment should be skipped.
    """
    lon1, lat1, _, alt1, _, t1 = point1
    lon2, lat2, _, alt2, _, t2 = point2

    p1 = { "longitude": lon1, "latitude": lat1, "altitude": alt1 }
    p2 = { "longitude": lon2, "latitude": lat2, "altitude": alt2 }
    horizontalDistance = pointDistance(p1, p2)
    durationSec = m2s(t2 - t1) # seconds

    # Skip GPS jitter, stationary points, or out-of-order timestamps.
    if (durationSec <= 0 or horizontalDistance < MIN_SEGMENT_DIST_M):
        return None

    # Find the elevation change as slope between two points.
    slopeGrade = calculateSlopeGrade(p1, p2)
    grade = slopeGrade["grade"]
    # Uses horizontal distance as the run (standard for hiking/trail grade).
    altitudeDiff = alt2 - alt1

    # Derived speed - clamped to MAX_SPEED_MS to guard against GPS outliers.
    speed = min(horizontalDistance / durationSec, MAX_SPEED_MS)

    # LCDA equation uses L_Bp = load/body_mass (dimensionless).
    L_Bp = (L + H2O) / W
    # LCDA equation uses grade as decimal (not %).
    decimalGrade = grade / 100

    # lcdaMetabolicRate returns Watts per kg; multiply by body mass to get total Watts.
    metabolicRatePerKg = lcdaMetabolicRate(L_Bp, speed, decimalGrade, n, rM)
    lcdaMetabolicRateWatts = metabolicRatePerKg * W

    # Energy expended = power × time (joules), converted to kcal.
    kcal = (lcdaMetabolicRateWatts * durationSec) / JOULES_PER_KCAL

    return {
        "horizontalDistance": horizontalDistance,         # meters
        "altitudeDiff": altitudeDiff,                     # meters
        "grade": grade,                                   # percentage
        "speed": speed,                                   # m/s
        "durationSec": durationSec,                       # seconds
        "lcdaMetabolicRateWatts": lcdaMetabolicRateWatts, # Watts
        "kcal": kcal                                      # kilocalories
      }


# Use the LCDA predictive model to estimate calories burned.
def lcdaCalories(coords: List[List[float]] = [], BMR: dict = {}, options: dict = {}) -> dict:
    """Use the LCDA predictive model to calculate the total (and per-segment) calorie expenditure for a GPS track.

    Args:
        coords (List[List[float]]): GPS coordinates array.  Each element:
            [longitude, latitude, heading, altitude (m), accuracy (m), timestamp (ms)]
        BMR (dict): Values for calculating resting metabolic rate.
        BMR["height"] (float): Body height in cm.
        BMR["weight"] (float): Body weight in kg.
        BMR["age"] (int): Age, in years.
        BMR["sex"] = 'm'|'f' (str): Male of female.
        options (dict): Options
        options["bodyWeightKg"] (float): Body weight in kg (required).
        options["loadKg"] = 0 (float): Load/pack weight in kg (optional).
        options["waterKg"] = 0 (float): Water weight in kg carried (optional).
        options["terrain"] = 1.1 (float): Terrain coefficient (optional).  Use TERRAIN_COEFFICIENTS.
        options["smooth"] = True (bool): Whether to smooth GPS altitude values (optional).
        options["smoothWindow"] = 5 (int): Rolling average window size for smoothing (optional).
        options["returnSegments"] = False (bool): Return array of all segments calculated (optional)?

    Raises:
        ValueError: If coords array contains less than 2 items.
        ValueError: If required body weight is < 0, null, or otherwise invalid.

    Returns:
        dict: Results
        {
            totalKcal,        # Total calories burned.
            totalDistanceM,   # Total horizontal distance (meters).
            totalDurationSec, # Total elapsed time (seconds).
            avgSpeedMs,       # Average speed (m/s).
        }
    """
    if len(coords) < 2:
        raise ValueError('At least 2 coordinate points are required.')

    if not BMR or BMR["height"] <= 0 or BMR["weight"] <= 0 or BMR["age"] <= 0 or BMR["sex"] not in {'m', 'f'}:
        msg = """BMR must include the following properties:
                    height: positive number (cm)
                    weight: positive number (kg)
                    age: positive number (years)
                    sex: string \'m|f\'"""
        raise ValueError(msg)

    bodyWeightKg = options.get("bodyWeightKg", 0)
    loadKg = options.get("loadKg", 0)
    waterKg = options.get("waterKg", 0)
    terrain = options.get("terrain", 1.1)
    smooth = options.get("smooth", True)
    smoothWindow = options.get("smoothWindow", SMOOTH_DEFAULT_WINDOW)
    returnSegments = options.get("returnSegments", False)
    if not bodyWeightKg or bodyWeightKg <= 0:
        raise ValueError(f"options['bodyWeightKg'] is required and must be a positive number.")

    print('lcda parameters:')
    print(bodyWeightKg, loadKg, waterKg)
    print(terrain)
    print(smooth, smoothWindow)
    print(f'bmr {BMR}')

    track = smoothAltitude(coords, smoothWindow) if smooth else coords
    segments = []
    totalKcal = 0
    totalDistanceM = 0
    totalDurationSec = 0
    for i in range(0, len(track)):
        seg = processLcdaSegment(track[i - 1], track[i], bodyWeightKg, loadKg, waterKg, terrain, BMR)
        if seg:
            totalKcal += seg["kcal"]
            # print(f"adding seg.kcal: {seg["kcal"]} ({totalKcal})")
            totalDistanceM += seg["horizontalDistance"]
            totalDurationSec += seg["durationSec"]
            segments.append(seg)

    avgSpeedMs = totalDistanceM / totalDurationSec if totalDurationSec > 0 else 0
    results = {
        "totalKcal": totalKcal,
        "totalDistanceM": totalDistanceM,
        "totalDurationSec": totalDurationSec,
        "avgSpeedMs": avgSpeedMs
    }
    if returnSegments:
        results["segments"] = segments

    return results


# Convert a Mifflin-St Jeor resting metabolic rate into kcal.
def vo2FromWattsPerKg(wattsPerKg: float) -> float:
    """Convert a Mifflin-St Jeor resting rate (W·kg^-1, from mResting()) into
          ml O2 · kg^-1 · min^-1, so it can be used as the V̇O2-rest term in the
          Minimum Mechanics model.

    Args:
        wattsPerKg (float): Resting metabolic rate, in Watts per kg (from mResting()).

    Returns:
        float: Resting metabolic rate, in ml O2 · kg^-1 · min^-1.
    """
    kcalPerMinPerKg = (wattsPerKg * 60) / JOULES_PER_KCAL
    return kcalPerMinPerKg / KCAL_PER_ML_O2


# Predict body-mass-specific walking oxygen uptake using the Minimum Mechanics model. 
def minimumMechanicsVO2(V: float, G: float, restVO2: float = DEFAULT_RESTING_VO2) -> float:
    """Predict body-mass-specific walking oxygen uptake using the Minimum Mechanics model. Positive
        grades follow the fitted minimum-walking + speed-dependent-walking formula directly. Negative
        grades are modeled as a fixed fraction (Cdecline) of the level-grade (G=0) walking cost at the
        same speed.

    Args:
        V (float): Walking speed, in m/s.
        G (float): Grade as a percentage (e.g. 10 for 10% incline, -5 for decline).
        restVO2 = DEFAULT_RESTING_VO2 (float): Resting metabolic rate, ml O2 · kg^-1 · min^-1.
        
    Returns:
        dict : vo2Walk, vo2Gross, both in ml O2 · kg-total^-1 · min^-1.
    """
    if V <= 0:
        return { vo2Walk: 0, vo2Gross: restVO2 }

    C1 = MM_COEFFICIENTS.get('C1')
    C2 = MM_COEFFICIENTS.get('C2')
    C3 = MM_COEFFICIENTS.get('C3')
    VO2_WALK_MIN = MM_COEFFICIENTS.get('VO2_WALK_MIN')
    C_DECLINE = MM_COEFFICIENTS.get('C_DECLINE')

    vo2Walk = 0
    if G >= 0:
        vo2Walk = VO2_WALK_MIN * (1 + C1 * G) + (1 + C2 * G) * C3 * V ** 2
        # vo2Walk = ((C1 * G) + VO2_WALK_MIN) + (1 + (C2 * G)) * (C3 * V ** 2)
    else:
        vo2Walk = C_DECLINE * (VO2_WALK_MIN + C3 * V ** 2)

    # clamp outputs producing a negative rate to zero.
    vo2Walk = max(0, vo2Walk)
    return {
        "vo2Walk": vo2Walk,
        "vo2Gross": restVO2 + vo2Walk
    }


# Process a single segment (two consecutive GPS points) using the Minimum Mechanics model.
def processMinimumMechanicsSegment(point1: List[float], point2: List[float], W: float, L: float, H2O: float, restVO2: float) -> dict | None:
    """Process a single segment (two consecutive GPS points) and return metabolic and distance
        data for that segment, using the Minimum Mechanics model.

    Args:
        point1 (List[float]): [longitude, latitude, heading, altitude, accuracy, timestamp]
        point2 (List[float]): [longitude, latitude, heading, altitude, accuracy, timestamp]
        W (float): Body weight in kg.
        L (float): Load carried in kg (pack, excluding water).
        H2O (float): Water carried in kg.
        restVO2 (float): Resting metabolic rate, ml O2 · kg^-1 · min^-1.
    
    Returns:
        dict|None: Segment result, or null if the segment should be skipped.
    """
    [lon1, lat1, _, alt1, _, t1] = point1
    [lon2, lat2, _, alt2, _, t2] = point2

    p1 = { "longitude": lon1, "latitude": lat1, "altitude": alt1 }
    p2 = { "longitude": lon2, "latitude": lat2, "altitude": alt2 }
    horizontalDistance = pointDistance(p1, p2)
    durationSec = m2s(t2 - t1) # seconds

    # Skip GPS jitter, stationary points, or out-of-order timestamps.
    if durationSec <= 0 or horizontalDistance < MIN_SEGMENT_DIST_M: 
        return None

    slopeGrade = calculateSlopeGrade(p1, p2)
    grade = slopeGrade["grade"]
    altitudeDiff = alt2 - alt1

    # Derived speed - clamped to MAX_SPEED_MS to guard against GPS outliers.
    speed = min(horizontalDistance / durationSec, MAX_SPEED_MS)

    # Minimum Mechanics treats each kg of load as metabolically equal to each kg
    # of body mass, so V̇O2 is predicted per kg of total (body + pack + water) mass.
    totalMass = W + L + H2O
    vo2 = minimumMechanicsVO2(speed, grade, restVO2)
    vo2Gross = vo2["vo2Gross"]

    # ml O2/min for the whole person+load, over this segment's duration.
    mlO2PerMin = vo2Gross * totalMass
    kcal = mlO2PerMin * KCAL_PER_ML_O2 * (durationSec / 60)

    return {
        "horizontalDistance": horizontalDistance, # meters
        "altitudeDiff": altitudeDiff,             # meters
        "grade": grade,                           # percentage
        "speed": speed,                           # m/s
        "durationSec": durationSec,               # seconds
        "vo2Gross": vo2Gross,                     # ml O2 kg-total^-1 min^-1
        "kcal": kcal,                             # kilocalories
    }



# Use the Minimum Mechanics Model to estimate calrories burned.
def minimumMechanicsCalories(coords, BMR, options = {}) -> dict:
    """Create the calculation workflow for the minimum mechanics predictive model.

    Args:
        coords (List[[List]]): GPS coordinate array.
        BMR (dict): Values for calculating resting metabolic rate.
        BMR["height"] (float): Body height in cm.
        BMR["weight"] (float): Body weight in kg.
        BMR["age"] (float): Age, in years.
        BMR["sex"] = 'm'|'f' (str): Male of female.
        options (dict): Options
        options["bodyWeightKg"] (float): Body weight in kg (required).
        options["loadKg"] = 0 (float): Load/ruck weight in kg.
        options["waterKg"] = 0 (float): Water weight carried in kg.
        options["smooth"] = True (bool): Whether to smooth GPS altitude before calculating.
        options["smoothWindow"] = 5 (int): Rolling average size for altitude smoothing.
        options["returnSegments"] = False (bool): Return array of all calculated segments.

    Raises:
        ValueError: Throws error if not enough coordinates.
        ValueError: Throws error if body weight is not provided.

    Returns:
        dict: Results object.
    """
    if not coords or len(coords) < 2:
        raise ValueError(f'At least 2 coordinate points are required.')
    if not BMR or BMR["height"] <= 0 or BMR["weight"] <= 0 or BMR["age"] <= 0 or BMR["sex"] not in {'m', 'f'}:
        msg = """BMR must include the following properties:
                     height: positive number (cm)
                     weight: positive number (kg)
                     age: positive number (years)
                     sex: string 'm'|'f'"""
        raise ValueError(msg)

    bodyWeightKg = options.get("bodyWeightKg", 0)
    loadKg = options.get("loadKg", 0)
    waterKg = options.get("waterKg", 0)
    terrain = options.get("terrain", 1.1)
    smooth = options.get("smooth", True)
    smoothWindow = options.get("smoothWindow", SMOOTH_DEFAULT_WINDOW)
    returnSegments = options.get("returnSegments", False)

    if not bodyWeightKg or bodyWeightKg <= 0:
        raise ValueError(f'options.bodyWeightKg is required and must be a positive number.')

    restVO2 = DEFAULT_RESTING_VO2
    restVO2 = vo2FromWattsPerKg(mResting(BMR["height"], BMR["weight"], BMR["age"], BMR["sex"]))

    print('minimum mechanics parameters:')
    print(bodyWeightKg, loadKg, waterKg)
    print(smooth, smoothWindow)
    print(f'bmr {BMR}')
    print(f'restVO2 {restVO2}')

    track = smoothAltitude(coords, smoothWindow) if smooth else coords
    segments = []
    totalKcal = 0
    totalDistanceM = 0
    totalDurationSec = 0

    for i in range(0, len(track)):
        seg = processMinimumMechanicsSegment(track[i - 1], track[i], bodyWeightKg, loadKg, waterKg, restVO2)
        if seg:
          totalKcal += seg["kcal"]
          totalDistanceM += seg["horizontalDistance"]
          totalDurationSec += seg["durationSec"]
          segments.append(seg)

    avgSpeedMs = totalDistanceM / totalDurationSec if totalDurationSec > 0 else 0
    results = {
        "totalKcal": totalKcal,
        "totalDistanceM": totalDistanceM,
        "totalDurationSec": totalDurationSec,
        "avgSpeedMs": avgSpeedMs,
    }
    if returnSegments:
        results["segments"] = segments

    return results


# Return an ensemble result of each of the available predicitive models, given a single array of coordinates.
def calorieEnsemble(coords: List[List[float]], options: dict) -> dict:
    """A function entrypoint that calculates the calorie estimate for each available predictive
        model, passing over the coords array just once, but processing each coordinate segment with
        each calorie model.
 
    Args:
        coords (List[List[float]]): GPS coordinate array.
        options (dict): Options
        options["bodyWeightKg"] (float): Body weight in kg (required).
        options["loadKg"] = 0 (float): Load/pack weight in kg.
        options["waterKg"] = 0 (float): Water weight in kg carried.
        options["terrain"] = 1.1 (float): Terrain coefficient (n). Use TERRAIN_COEFFICIENTS.
        options["smoothWindow"] = 5 (int) Rolling average size for altitude smoothing.
        options["smooth"] = True (bool): Whether to smooth GPS altitude before calculating.
        options["returnSegments"] = False (bool): Return array of all calculated segments. 
        options["BMR"] (dict): Values for calculating resting metabolic rate.
        options["BMR.height"] (float): BMR body height in cm.
        options["BMR.weight"] (float): BMR body weight in kg.
        options["BMR"]["age"] (int): BMR age, in years.
        options["BMR"]["sex"] = 'm'|'f' (str): BMR sex Male of female.
 
     Raises:
        ValueError: Throws error if not enough coordinates.
        ValueError: Throws error if body weight is not provided.

    Returns:
        dict: Result object:
        {
            <model_name>: {
                "totalPandolfKcal": float, # Total pandolf calories burned
                "totalLCDAKcal": float,    # Total LCDA calories burned
                "totalDistanceM": float,   # Total horizontal distance (meters)
                "totalDurationSec": float, # Total elapsed time (seconds)
                "avgSpeedMs": float,       # Average speed (m/s)
            }
        }
    """
    bodyWeightKg = options.get("bodyWeightKg", 0)
    loadKg = options.get("loadKg", 0)
    waterKg = options.get("waterKg", 0)
    terrain = options.get("terrain", 1.1)
    smooth = options.get("smooth", True)
    smoothWindow = options.get("smoothWindow", SMOOTH_DEFAULT_WINDOW)
    returnSegments = options.get("returnSegments", False)

    BMR = options.get("BMR", None)
    print('emsemble parameters:')
    print(bodyWeightKg, loadKg, waterKg)
    print(terrain)
    print(smooth, smoothWindow)
    print(f'bmr {BMR}')
    if not coords or len(coords) <= 2:
        raise ValueError(f"At least 2 coordinate points are required.")

    if not BMR or BMR["height"] <= 0 or BMR["weight"] <= 0 or BMR["age"] <= 0 or BMR["sex"] not in {'m', 'f'}:
        msg = """BMR must include the following properties:
                 height: positive number (cm)
                 weight: positive number (kg)
                 age: positive number (years)
                sex: string \'m|f\'"""
        raise ValueError(msg)

    if not bodyWeightKg or bodyWeightKg <= 0:
        raise ValueError(f'options["bodyWeightKg"] is required and must be a positive number.')

    track = smoothAltitude(coords, smoothWindow) if smooth else coords
    segments = []
    results = {
        "lcda": { "totalKcal": 0, "totalDistanceM": 0, "totalDurationSec": 0 },
        "pandolf": { "totalKcal": 0, "totalDistanceM": 0, "totalDurationSec": 0 },
        "minMech": { "totalKcal": 0, "totalDistanceM": 0, "totalDurationSec": 0 },
    }
    restVO2 = DEFAULT_RESTING_VO2
    restVO2 = vo2FromWattsPerKg(mResting(BMR["height"], BMR["weight"], BMR["age"], BMR["sex"]))
    for i in range(0, len(track)):
        minMechSeg = processMinimumMechanicsSegment(track[i - 1], track[i], bodyWeightKg, loadKg, waterKg, restVO2)
        if (minMechSeg):
            results["minMech"]["totalKcal"] += minMechSeg["kcal"]
            # print(f'adding minMechSeg.kcal: {minMechSeg["kcal"]} ({totalKcal})')
            results["minMech"]["totalDistanceM"] += minMechSeg["horizontalDistance"]
            results["minMech"]["totalDurationSec"] += minMechSeg["durationSec"]
            if returnSegments:
                segments.append(minMechSeg)

        pandolfSeg = processPandolfSegment(track[i - 1], track[i], bodyWeightKg, loadKg, waterKg, terrain)
        if pandolfSeg:
            results["pandolf"]["totalKcal"] += pandolfSeg["kcal"]
            # print(f'adding pandolfSeg.kcal: {pandolfSeg["kcal"]} ({totalKcal})')
            results["pandolf"]["totalDistanceM"] += pandolfSeg["horizontalDistance"]
            results["pandolf"]["totalDurationSec"] += pandolfSeg["durationSec"]
            if returnSegments:
                segments.append(pandolfSeg)

        lcdaSeg = processLcdaSegment(track[i - 1], track[i], bodyWeightKg, loadKg, waterKg, terrain, BMR)
        if lcdaSeg:
            results["lcda"]["totalKcal"] += lcdaSeg["kcal"]
            # print(f'adding lcdaSeg.kcal: {lcdaSeg["kcal"]} ({totalKcal})')
            results["lcda"]["totalDistanceM"] += lcdaSeg["horizontalDistance"]
            results["lcda"]["totalDurationSec"] += lcdaSeg["durationSec"]
            if returnSegments:
                segments.append(lcdaSeg)

    results["minMech"]["avgSpeedMs"] = results["minMech"]["totalDistanceM"] / results["minMech"]["totalDurationSec"] if results["minMech"]["totalDurationSec"] > 0 else 0
    results["pandolf"]["avgSpeedMs"] = results["pandolf"]["totalDistanceM"] / results["pandolf"]["totalDurationSec"] if results["pandolf"]["totalDurationSec"] > 0 else 0
    results["lcda"]["avgSpeedMs"] = results["lcda"]["totalDistanceM"] / results["lcda"]["totalDurationSec"] if results["lcda"]["totalDurationSec"] > 0 else 0
    
    return results


